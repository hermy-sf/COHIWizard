/*
 * DspWorkerADALM.cpp  –  ADALM2000_universal
 *
 * DSP engine for ADALM2000, derived from fl2k_fast_plus/DspWorkerFL2K.cpp.
 *
 * Differences from the fl2k variant:
 *   - No osmo-fl2k dependency (no fl2k device, no fl2k ring callback).
 *   - Output is int16_t PCM (bitScale = 32767), not int8_t.
 *   - Consumer is Python via dsp_adlm_pull() → libm2k pushRaw.
 *   - Mode B: run_dsp_audioonly() synthesises AM carriers without a WAV file.
 *
 * Build:
 *   g++ -std=c++17 -O3 -march=native -ffast-math -fPIC -shared \
 *       DspWorkerADALM.cpp -o libdspadlm.so -lpthread -lm
 */

#ifndef _USE_MATH_DEFINES
#  define _USE_MATH_DEFINES
#endif

#include "DspWorkerADALM.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cctype>
#include <cmath>
#include <fstream>
#include <vector>
#include <string>
#include <atomic>
#include <mutex>
#include <condition_variable>
#include <thread>
#include <chrono>
#include <algorithm>

/* Platform-specific socket support */
#ifdef _WIN32
#  include <winsock2.h>
#  include <ws2tcpip.h>
#  pragma comment(lib, "ws2_32.lib")
#  ifndef _SSIZE_T_DEFINED
     typedef SSIZE_T ssize_t;
#    define _SSIZE_T_DEFINED
#  endif
#  define MSG_DONTWAIT 0
#  define SOCKOPT_VAL(p) ((const char*)(p))
static inline int  _sock_close(int fd)           { return closesocket((SOCKET)fd); }
static inline void _sock_set_nonblocking(int fd) { u_long m=1; ioctlsocket((SOCKET)fd,FIONBIO,&m); }
#else
#  include <sys/socket.h>
#  include <netinet/in.h>
#  include <arpa/inet.h>
#  include <unistd.h>
#  include <fcntl.h>
#  include <errno.h>
#  define SOCKOPT_VAL(p) (p)
static inline int  _sock_close(int fd)           { return ::close(fd); }
static inline void _sock_set_nonblocking(int fd) { int f=fcntl(fd,F_GETFL,0); fcntl(fd,F_SETFL,f|O_NONBLOCK); }
#endif

/* ================================================================== */
/* LUT NCO  –  12-bit, 4096 entries, float ±1.0                       */
/* ================================================================== */

static constexpr int LUT_BITS      = 12;
static constexpr int LUT_SIZE      = 1 << LUT_BITS;   /* 4096 */
static constexpr int LUT_FRAC_BITS = 8;
static float   g_lut_sin[LUT_SIZE];
static float   g_lut_cos[LUT_SIZE];
static bool    g_lut_ready = false;

static void init_lut()
{
    if (g_lut_ready) return;
    for (int i = 0; i < LUT_SIZE; ++i) {
        double a     = 2.0 * M_PI * i / LUT_SIZE;
        g_lut_sin[i] = (float)std::sin(a);
        g_lut_cos[i] = (float)std::cos(a);
    }
    g_lut_ready = true;
}

static inline float lut_sin(uint32_t phase) { return g_lut_sin[phase >> (32 - LUT_BITS)]; }
static inline float lut_cos(uint32_t phase) { return g_lut_cos[phase >> (32 - LUT_BITS)]; }

/* Interpolated LUT for main VCO — reduces systematic frequency error to < 0.01 Hz */
static inline void lut_sincos_lerp(uint32_t phase,
                                   float* __restrict__ s_out,
                                   float* __restrict__ c_out)
{
    uint32_t idx  = phase >> (32 - LUT_BITS);
    float    frac = (float)((phase >> (32 - LUT_BITS - LUT_FRAC_BITS))
                            & ((1u << LUT_FRAC_BITS) - 1))
                   * (1.f / (float)(1u << LUT_FRAC_BITS));
    uint32_t idx1 = (idx + 1) & (LUT_SIZE - 1);
    *s_out = g_lut_sin[idx] + (g_lut_sin[idx1] - g_lut_sin[idx]) * frac;
    *c_out = g_lut_cos[idx] + (g_lut_cos[idx1] - g_lut_cos[idx]) * frac;
}

static inline uint32_t freq_to_pinc(double freq_hz, double sample_rate)
{
    return (uint32_t)(freq_hz / sample_rate * 4294967296.0);
}

/* ================================================================== */
/* IQf                                                                 */
/* ================================================================== */
struct IQf { float re, im; };

/* ================================================================== */
/* WAV / RIFF binary structures                                        */
/* ================================================================== */
#pragma pack(push, 1)
struct ChunkHeader  { char id[4]; uint32_t size; };
struct RiffHeader   { char chunkId[4]; uint32_t chunkSize; char format[4]; };
struct FmtStruct    {
    uint16_t audioFormat; uint16_t numChannels;
    uint32_t sampleRate;  uint32_t byteRate;
    uint16_t blockAlign;  uint16_t bitsPerSample;
};
struct AuxiContent  { uint8_t padding[68]; char filename[96]; };
#pragma pack(pop)


/* ================================================================== */
/* Exact chunk walking – same rules as sources/wavchunks.py            */
/* The samples must start exactly at the first byte of the data chunk: */
/* a shifted start swaps I/Q (16 bit) or mixes samples (24 bit).       */
/* ================================================================== */
static bool wav_valid_tag(const char* t)
{
    for (int i = 0; i < 4; ++i)
        if ((unsigned char)t[i] < 0x20 || (unsigned char)t[i] > 0x7E) return false;
    return true;
}

static bool wav_tag_at(std::ifstream& f, std::streamoff pos, std::streamoff fileSize)
{
    if (pos < 0 || pos + 8 > fileSize) return false;
    char t[4];
    const std::streamoff keep = f.tellg();
    f.seekg(pos);
    f.read(t, 4);
    const bool ok = static_cast<bool>(f) && wav_valid_tag(t);
    f.clear();
    f.seekg(keep);
    return ok;
}

/* Position of the chunk following the chunk at 'start'. A size field which does
 * not lead to a valid chunk is replaced by the known content length of the chunk
 * (e.g. 'auxi' written with sdr_nChunkSize 172 but containing 164 bytes).
 * Returns -1 if the layout cannot be resolved. */
static std::streamoff wav_next_chunk(std::ifstream& f, std::streamoff start,
                                     const ChunkHeader& ch, std::streamoff fileSize)
{
    const std::streamoff nxt = start + 8 + (std::streamoff)ch.size + (ch.size & 1);
    if (wav_tag_at(f, nxt, fileSize)) return nxt;
    static const struct { char tag[5]; int sizes[3]; } KNOWN[] = {
        {"fmt ", {16, 18, 40}}, {"auxi", {164, 0, 0}}, {"rcvr", {34, 0, 0}} };
    for (const auto& k : KNOWN) {
        if (std::memcmp(ch.id, k.tag, 4) != 0) continue;
        for (int s : k.sizes) {
            if (s <= 0) break;
            const std::streamoff cand = start + 8 + s;
            if (wav_tag_at(f, cand, fileSize)) {
                printf("[wav] chunk '%.4s' at %lld: size field %u, actual content %d bytes\n",
                       ch.id, (long long)start, ch.size, s);
                return cand;
            }
        }
    }
    return -1;
}

/* Raw IQ files of the old COHIRADIA RFCorder (.dat/.raw): no RIFF header, the
 * first 216 bytes are reserved for one (same rule as sources/wavchunks.py,
 * STANDARD_DATA_OFFSET). Their format is set by dsp_adlm_set_raw_format. */
static constexpr std::streamoff RAW_DATA_OFFSET = 216;

static bool is_raw_name(const std::string& path)
{
    const size_t dot = path.find_last_of('.');
    if (dot == std::string::npos) return false;
    std::string ext = path.substr(dot);
    for (auto& c : ext) c = (char)std::tolower((unsigned char)c);
    return ext == ".dat" || ext == ".raw";
}

/* ================================================================== */
/* Constants                                                           */
/* ================================================================== */
static constexpr size_t ADLM_BUF_LEN = 65536;    /* legacy size; pull block set in Python */
static constexpr size_t RING_BUFS    = 64;        /* 64 × 64 KiB × 2 B = 8 MB ring */
/* Ring stores int16_t output → 2 bytes/sample */
static constexpr size_t RING_SIZE    = ADLM_BUF_LEN * sizeof(int16_t) * RING_BUFS;
static constexpr size_t DSP_BLOCK    = 8192;
static constexpr size_t MON_SIZE     = 8192;
static constexpr float  SCALE_MON   = 1048576.0f;

/* ================================================================== */
/* AudioFifo – lock-free single-producer/single-consumer ring          */
/* ================================================================== */
struct AudioFifo {
    size_t             cap;
    std::vector<float> buf;
    size_t             head = 0, cnt = 0;

    explicit AudioFifo(size_t n = 65536) : cap(n), buf(n, 0.f) {}

    void push(const float* src, size_t n) {
        if (n == 0) return;
        size_t space = cap - cnt;
        if (n > space) n = space;
        if (n == 0) return;
        size_t tail  = (head + cnt) % cap;
        size_t first = std::min(n, cap - tail);
        std::copy(src, src + first, buf.data() + tail);
        if (first < n) std::copy(src + first, src + n, buf.data());
        cnt += n;
    }

    size_t pop(float* dst, size_t n) {
        size_t got   = std::min(n, cnt);
        size_t first = std::min(got, cap - head);
        std::copy(buf.data() + head, buf.data() + head + first, dst);
        if (first < got) std::copy(buf.data(), buf.data() + (got - first), dst + first);
        head = (head + got) % cap;
        cnt -= got;
        if (got < n) std::fill(dst + got, dst + n, 0.f);
        return got;
    }

    size_t available() const { return cnt; }
    void   clear()           { head = cnt = 0; }
};

/* ================================================================== */
/* DspWorkerADALM – internal state                                     */
/* ================================================================== */
struct DspWorkerADALM {

    /* --- main IQ config ------------------------------------------- */
    float              targetRate  = 2'343'750.f;
    float              shiftFreq   = 0.f;
    std::atomic<float> gainValue   {0.65f};
    bool               useAGC      = true;
    bool               audio_only  = false;
    std::vector<std::string> filenames;
    /* format of raw .dat/.raw files without RIFF header, see dsp_adlm_set_raw_format */
    uint32_t rawSampleRate = 0;
    uint16_t rawAudioFormat = 1;
    uint16_t rawBitsPerSample = 16;

    /* --- callbacks ------------------------------------------------- */
    dsp_monitor_cb_t  mon_cb  = nullptr; void* mon_ud  = nullptr;
    dsp_progress_cb_t prog_cb = nullptr; void* prog_ud = nullptr;
    dsp_finished_cb_t fin_cb  = nullptr; void* fin_ud  = nullptr;
    dsp_error_cb_t    err_cb  = nullptr; void* err_ud  = nullptr;
    dsp_nextfile_cb_t nxt_cb  = nullptr; void* nxt_ud  = nullptr;

    /* --- ring buffer (DSP writes, pull reads) ---------------------- */
    std::vector<int8_t>      ring       = std::vector<int8_t>(RING_SIZE, 0);
    size_t                   ring_head  = 0, ring_tail = 0, ring_count = 0;
    std::mutex               ring_mtx;
    std::condition_variable  ring_not_empty, ring_not_full;

    /* --- seek request --------------------------------------------- */
    struct SeekReq { bool pending = false; int64_t pos = 0; int whence = 0; };
    std::mutex seek_mtx; SeekReq seek_req;

    /* --- control -------------------------------------------------- */
    std::atomic<bool> running {false};
    std::atomic<bool> paused  {false};

    /* --- threads -------------------------------------------------- */
    std::thread dsp_thr;

    /* =================================================================
     * Audio overlay channels
     * ================================================================*/
    struct AudioChanCfg {
        float freq_hz        = 0.f;
        float bw_hz          = 4500.f;
        float mod_idx        = 0.9f;
        char  name[64]       = {};
        int   udp_port       = -1;
        float schroeder_phase = 0.f;
    };

    struct AudioChanRT {
        bool     active        = false;
        int      udp_fd        = -1;
        float    mod_idx       = 0.9f;

        float    current_aud   = 0.f;
        double   aud_phase     = 0.0;
        double   aud_phase_inc = 0.0;

        uint32_t nco_phase     = 0;
        uint32_t nco_phase_inc = 0;

        std::vector<uint8_t> udp_recv_buf;
        AudioFifo raw_fifo{1'048'576};
    };

    std::vector<AudioChanCfg> audio_cfgs;
    std::vector<AudioChanRT>  audio_rt;
    float                     audio_rate    = 25000.f;
    std::atomic<float>        audio_mix_lvl {1.0f};
    float                     audio_gain_cur = 0.f;   /* carrier gain at end of last block */

    /* --- helpers -------------------------------------------------- */
    void write_ring(const int8_t* data, size_t n);
    void run_dsp();
    void run_dsp_audioonly();
    std::string process_file(const std::string& path);
    void close_audio_sockets();
    void setup_audio_for_file(uint32_t sr);
    void teardown_audio_for_file();
    void mix_audio_block_fast(IQf* x, size_t n_iq);
};

/* ================================================================== */
/* Ring buffer – write side (DSP thread)                               */
/* ================================================================== */

void DspWorkerADALM::write_ring(const int8_t* data, size_t n)
{
    size_t written = 0;
    while (written < n && running.load(std::memory_order_acquire)) {
        std::unique_lock<std::mutex> lk(ring_mtx);
        /* Wait for ANY free space (not for the entire block at once).
         * This allows partial writes for large IQ-mode blocks and prevents
         * the pull thread from starving while the writer stalls. */
        ring_not_full.wait(lk, [&] {
            return ring_count < RING_SIZE
                   || !running.load(std::memory_order_relaxed);
        });
        if (!running.load(std::memory_order_relaxed)) break;
        size_t chunk = std::min(n - written, RING_SIZE - ring_count);
        size_t first = std::min(chunk, RING_SIZE - ring_head);
        memcpy(ring.data() + ring_head, data + written, first);
        if (first < chunk) memcpy(ring.data(), data + written + first, chunk - first);
        ring_head   = (ring_head + chunk) % RING_SIZE;
        ring_count += chunk;
        written    += chunk;
        ring_not_empty.notify_one();
    }
}

/* ================================================================== */
/* Audio overlay helpers                                               */
/* ================================================================== */

void DspWorkerADALM::close_audio_sockets()
{
    for (auto& rt : audio_rt) {
        if (rt.udp_fd >= 0) { _sock_close(rt.udp_fd); rt.udp_fd = -1; }
    }
    audio_rt.clear();
}

void DspWorkerADALM::setup_audio_for_file(uint32_t sr)
{
    if (audio_rt.empty()) return;
    float ba = audio_mix_lvl.load() / sqrtf((float)audio_rt.size());
    audio_gain_cur = ba;

    for (size_t i = 0; i < audio_rt.size(); ++i) {
        AudioChanRT&  rt  = audio_rt[i];
        AudioChanCfg& cfg = audio_cfgs[i];

        rt.mod_idx  = cfg.mod_idx;
        rt.active   = (rt.udp_fd >= 0);
        if (!rt.active) continue;

        rt.aud_phase     = 0.0;
        rt.aud_phase_inc = (double)audio_rate / sr;
        rt.current_aud   = 0.f;

        double delta_f = (double)cfg.freq_hz - shiftFreq;
        {
            double sp = fmod((double)cfg.schroeder_phase, 2.0 * M_PI);
            if (sp < 0.0) sp += 2.0 * M_PI;
            rt.nco_phase = (uint32_t)(sp / (2.0 * M_PI) * 4294967296.0);
        }
        rt.nco_phase_inc = freq_to_pinc(delta_f, sr);

        rt.udp_recv_buf.assign(16384, 0);
        rt.raw_fifo.clear();

        float nyq = sr * 0.5f;
        if (std::fabs(delta_f) > nyq)
            printf("[ADALM2000_univ] WARNING ch[%zu] '%s': "
                   "delta_f=%.0f Hz exceeds Nyquist ±%.0f Hz – will alias.\n",
                   i, cfg.name, delta_f, nyq);

        printf("[ADALM2000_univ] ch[%zu] '%s': carrier=%.1f Hz  delta_f=%.1f Hz  "
               "udp_port=%d  gain=%.4f  aud_phase_inc=%.6f\n",
               i, cfg.name, cfg.freq_hz, delta_f, cfg.udp_port, ba, rt.aud_phase_inc);
    }
}

void DspWorkerADALM::teardown_audio_for_file()
{
    for (auto& rt : audio_rt) rt.active = false;
}

void DspWorkerADALM::mix_audio_block_fast(IQf* x, size_t n_iq)
{
    static uint64_t call_cnt = 0;
    ++call_cnt;

    /* The mix level may change at runtime: ramp the carrier gain over the block */
    const float gain_target = audio_mix_lvl.load(std::memory_order_relaxed)
                              / sqrtf((float)audio_rt.size());
    const float gain_step   = (gain_target - audio_gain_cur) / (float)n_iq;

    for (size_t chi = 0; chi < audio_rt.size(); ++chi) {
        AudioChanRT& rt = audio_rt[chi];
        if (!rt.active) continue;

        /* Drain UDP socket into raw_fifo (u8 PCM, silence=128) */
        if (rt.raw_fifo.available() < rt.raw_fifo.cap) {
            ssize_t nr;
            while ((nr = recv(rt.udp_fd, reinterpret_cast<char*>(rt.udp_recv_buf.data()),
                              rt.udp_recv_buf.size(), MSG_DONTWAIT)) > 0)
            {
                for (ssize_t k = 0; k < nr; ++k) {
                    float s = (static_cast<float>(rt.udp_recv_buf[k]) - 128.f) / 128.f;
                    rt.raw_fifo.push(&s, 1);
                }
                if (rt.raw_fifo.available() >= rt.raw_fifo.cap) break;
            }
        }

        float g = audio_gain_cur;
        for (size_t k = 0; k < n_iq; ++k) {
            rt.aud_phase += rt.aud_phase_inc;
            if (rt.aud_phase >= 1.0) {
                rt.aud_phase -= 1.0;
                rt.raw_fifo.pop(&rt.current_aud, 1);
            }

            float cf = lut_cos(rt.nco_phase);
            float sf = lut_sin(rt.nco_phase);
            rt.nco_phase += rt.nco_phase_inc;

            float am = g * (1.f + rt.mod_idx * rt.current_aud);
            x[k].re += am * cf;
            x[k].im += am * sf;
            g += gain_step;
        }
    }
    audio_gain_cur = gain_target;

    if (call_cnt % 500 == 0) {
        fprintf(stderr, "[ADALM2000_univ] diag call=%llu  channels:",
                (unsigned long long)call_cnt);
        for (size_t i = 0; i < audio_rt.size(); ++i) {
            auto& r = audio_rt[i];
            if (!r.active) { fprintf(stderr, " ch[%zu]=off", i); continue; }
            fprintf(stderr, " ch[%zu] raw=%zu", i, r.raw_fifo.available());
        }
        fprintf(stderr, "\n");
    }
}

/* ================================================================== */
/* Polyphase sinc FIR for IQ upsampling  (identical to fl2k variant)  */
/*                                                                    */
/* The ring buffer is doubled (2*POLY_TAPS_MAX) so that the newest    */
/* taps samples are always contiguous → vectorisable dot product.     */
/* Cutoff at fs_in/2.  Image rejection for a band filling ±0.45 fs_in: */
/* GOOD: taps=32, beta=7  →  -76 dB beyond 0.6 fs_in, 0.2 dB droop    */
/* ================================================================== */
static constexpr int POLY_TAPS_MAX  = 32;   /* MUST be power of 2 */
static constexpr int POLY_TAPS_GOOD = 32;
static constexpr int POLY_TAPS_FAST = 16;

static double bessel_i0(double x)
{
    double sum = 1.0, term = 1.0;
    for (int k = 1; k <= 30; ++k) {
        term *= (0.25 * x * x) / ((double)k * k);
        sum  += term;
        if (term < 1e-12 * sum) break;
    }
    return sum;
}

static std::vector<std::vector<float>>
build_poly_coeffs(int L, int taps, double beta)
{
    const int    total  = L * taps;
    const int    center = total / 2;
    const double i0b    = bessel_i0(beta);
    /* Cutoff at the input Nyquist frequency (normalised to the output
     * rate).  Was 0.9/L = 0.9·fs_in, which passed the first image band
     * unattenuated: the interpolated output then peaked ~5 dB above the
     * baseband peak the clip guard measures → hard clipping. */
    const double cut    = 0.5 / L;

    std::vector<float> h(total, 0.f);
    for (int i = 0; i < total; ++i) {
        double n    = i - center;
        double sinc = (n == 0.0) ? (2.0 * cut)
                                 : (std::sin(2.0 * M_PI * cut * n) / (M_PI * n));
        double t    = 2.0 * i / (total - 1) - 1.0;
        double w    = bessel_i0(beta * std::sqrt(std::max(0.0, 1.0 - t * t))) / i0b;
        h[i] = (float)(sinc * w);
    }
    double norm = 0.0;
    for (auto v : h) norm += (double)v;
    float scale = (norm > 0.0) ? (float)(L / norm) : 1.f;
    for (auto& v : h) v *= scale;

    /* poly[p][j] = h[p + (taps-1-j)*L]: taps in time order oldest→newest
     * to match the contiguous ring-buffer window. */
    std::vector<std::vector<float>> poly(L, std::vector<float>(taps, 0.f));
    for (int p = 0; p < L; ++p)
        for (int t = 0; t < taps; ++t)
            if (p + t * L < total)
                poly[p][taps - 1 - t] = h[p + t * L];
    return poly;
}

/* ================================================================== */
/* DSP: process a single WAV file  (Mode A)                            */
/* ================================================================== */

std::string DspWorkerADALM::process_file(const std::string& path)
{
    std::ifstream f(path, std::ios::binary);
    if (!f) {
        if (err_cb) err_cb(("Cannot open: " + path).c_str(), err_ud);
        return "";
    }
    if (nxt_cb) nxt_cb(path.c_str(), nxt_ud);

    f.seekg(0, std::ios::end);
    const std::streamoff fileSize = f.tellg();
    f.seekg(0, std::ios::beg);
    RiffHeader riff;
    f.read(reinterpret_cast<char*>(&riff), sizeof(riff));
    const bool isRiff = static_cast<bool>(f)
                        && std::memcmp(riff.chunkId, "RIFF", 4) == 0
                        && std::memcmp(riff.format, "WAVE", 4) == 0;
    const bool isRaw  = !isRiff && is_raw_name(path) && fileSize > RAW_DATA_OFFSET;
    if (!isRiff && !isRaw) {
        if (err_cb) err_cb(("No RIFF/WAVE file: " + path).c_str(), err_ud);
        return "";
    }
    if (isRaw && rawSampleRate == 0) {
        if (err_cb) err_cb(("Raw IQ file without format information: " + path).c_str(), err_ud);
        return "";
    }
    f.clear();
    f.seekg(isRaw ? RAW_DATA_OFFSET : (std::streamoff)sizeof(riff), std::ios::beg);
    bool dataFound = false;

    uint32_t sampleRate    = 0;
    uint16_t audioFormat   = 1;
    uint16_t bitsPerSample = 16;
    uint16_t numChannels   = 2;
    std::string nextFile;
    ChunkHeader chunk;

    /* raw file: the samples start at RAW_DATA_OFFSET, the stream is already there;
     * the loop below starts with a synthetic 'data' chunk instead of reading one */
    bool rawPending = isRaw;
    if (isRaw) {
        sampleRate    = rawSampleRate;
        audioFormat   = rawAudioFormat;
        bitsPerSample = rawBitsPerSample;
        numChannels   = 2;
        std::memcpy(chunk.id, "data", 4);
        chunk.size = (uint32_t)std::min<std::streamoff>(fileSize - RAW_DATA_OFFSET, 0xFFFFFFFFLL);
    }

    printf("[ADALM2000_univ] Processing: %s\n", path.c_str());
    printf("[ADALM2000_univ] shiftFreq: %.0f Hz\n", shiftFreq);

    while ((rawPending || f.read(reinterpret_cast<char*>(&chunk), sizeof(chunk)))
           && running.load(std::memory_order_acquire))
    {
        rawPending = false;
        const std::streamoff chunkStart = (std::streamoff)f.tellg() - (std::streamoff)sizeof(chunk);
        if (!wav_valid_tag(chunk.id)) break;
        std::string tag(chunk.id, 4);

        if (tag == "fmt ") {
            FmtStruct fmt;
            f.read(reinterpret_cast<char*>(&fmt), sizeof(fmt));
            sampleRate    = fmt.sampleRate;
            audioFormat   = fmt.audioFormat;
            bitsPerSample = fmt.bitsPerSample;
            numChannels   = fmt.numChannels;
        }
        else if (tag == "auxi") {
            AuxiContent aux;
            f.read(reinterpret_cast<char*>(&aux), sizeof(aux));
            std::string raw(aux.filename, 96);
            static const std::string JUNK(" \t\n\r\0\x01", 6);
            size_t last = raw.find_last_not_of(JUNK);
            if (last != std::string::npos) nextFile = raw.substr(0, last + 1);
        }
        else if (tag == "data") {
            dataFound = true;      /* the stream is now exactly at the first sample byte */

            if (sampleRate == 0 || numChannels < 2) {
                if (err_cb) err_cb("Invalid WAV header", err_ud);
                break;
            }

            double upRatio  = (double)targetRate / sampleRate;
            int    n_interp = (int)std::round(upRatio);
            if (n_interp < 1) n_interp = 1;

            auto poly_good = build_poly_coeffs(n_interp, POLY_TAPS_GOOD, 7.0);
            auto poly_fast = build_poly_coeffs(n_interp, POLY_TAPS_FAST, 6.0);
            printf("[ADALM2000_univ] polyphase FIR: L=%d  GOOD=%dt/β7  FAST=%dt/β6\n",
                   n_interp, POLY_TAPS_GOOD, POLY_TAPS_FAST);

            const decltype(poly_good)* active_poly      = &poly_good;
            int                        active_poly_taps  = POLY_TAPS_GOOD;
            float                      dsp_load_smooth   = 0.0f;
            const double               block_real_time   = (double)DSP_BLOCK / (double)sampleRate;

            uint32_t vco_phase     = 0;
            uint32_t vco_phase_inc = freq_to_pinc(shiftFreq, targetRate);

            setup_audio_for_file(sampleRate);

            /* int16_t output: bitScale = 32767
             * Manual gain is absolute: current_gain_fast = gainValue * GAIN_SCALE
             * maps a full-scale IQ file (peak 1.0) to the former level.  It used
             * to be gainValue * block_safe, i.e. every block normalised to its
             * own peak: the output then ignored the file level, while the AVC
             * (monitor × slider gain) sees the true level → for low-level files
             * the AVC raised gainValue far above 1 → massive clipping. */
            const float bitScale    = 32767.0f;
            const float GAIN_SCALE  = (bitScale - 1.f) / 1.05f;
            float current_gain_fast = bitScale * 0.65f;
            float peak_hold         = 0.1f;
            float prev_block_gain   = current_gain_fast;
            /* Emergency limiter ceiling: instant attack on overload, slow
             * release (~6 dB/s), as in DspWorkerFL2K. */
            const float lim_release = powf(10.f, 6.f / 20.f * (float)DSP_BLOCK / sampleRate);
            float       lim_ceiling = 1e9f;

            float i_buf[2 * POLY_TAPS_MAX] = {};
            float q_buf[2 * POLY_TAPS_MAX] = {};
            int   buf_ptr                 = 0;

            std::vector<IQf>     x(DSP_BLOCK);
            std::vector<int16_t> rb16(DSP_BLOCK * 2);
            std::vector<float>   rb32(DSP_BLOCK * 2);
            std::vector<int32_t> rb32i(DSP_BLOCK * 2);
            std::vector<uint8_t> rb24(DSP_BLOCK * 6);
            /* out16: int16_t output samples */
            std::vector<int16_t> out16(DSP_BLOCK * (n_interp + 1));
            std::vector<float>   mon(MON_SIZE);

            uint32_t dataBytesTotal = (uint32_t)std::min<std::streamoff>(
                chunk.size, std::max<std::streamoff>(0, fileSize - (std::streamoff)f.tellg()));
            uint32_t dataBytesRead  = 0;
            size_t   blocksPerSec   = (size_t)((double)sampleRate / DSP_BLOCK) + 1;
            size_t   blockCnt       = 0;
            size_t   monIdx         = 0;

            printf("[ADALM2000_univ] SR=%u  upRatio=%.3f  n_interp=%d  targetRate=%.0f\n",
                   sampleRate, upRatio, n_interp, (double)targetRate);

            while (running.load(std::memory_order_acquire)) {

                /* -- seek request -- */
                {
                    std::lock_guard<std::mutex> slk(seek_mtx);
                    if (seek_req.pending) {
                        auto dir = (seek_req.whence == 0) ? std::ios::beg
                                 : (seek_req.whence == 1) ? std::ios::cur
                                                          : std::ios::end;
                        f.clear();
                        f.seekg(seek_req.pos, dir);
                        seek_req.pending = false;
                        {
                            std::lock_guard<std::mutex> rlk(ring_mtx);
                            ring_head = ring_tail = ring_count = 0;
                            ring_not_full.notify_all();
                        }
                        std::fill(i_buf, i_buf + 2 * POLY_TAPS_MAX, 0.f);
                        std::fill(q_buf, q_buf + 2 * POLY_TAPS_MAX, 0.f);
                        buf_ptr = 0;
                    }
                }

                /* -- pause: feed silence into ring -- */
                while (paused.load(std::memory_order_acquire)
                       && running.load(std::memory_order_acquire))
                {
                    static const int8_t zeros[DSP_BLOCK * 2] = {};
                    write_ring(zeros, sizeof(zeros));
                }
                if (!running.load(std::memory_order_acquire)) break;

                /* -- read one block of IQ samples -- */
                bool ok = false;
                if (audioFormat == 1 && bitsPerSample == 16) {
                    ok = (bool)f.read(reinterpret_cast<char*>(rb16.data()), DSP_BLOCK * 4);
                    if (ok)
                        for (size_t i = 0; i < DSP_BLOCK; ++i)
                            x[i] = { rb16[2*i] / 32768.f, rb16[2*i+1] / 32768.f };
                }
                else if (audioFormat == 3 && bitsPerSample == 32) {
                    ok = (bool)f.read(reinterpret_cast<char*>(rb32.data()), DSP_BLOCK * 8);
                    if (ok)
                        for (size_t i = 0; i < DSP_BLOCK; ++i)
                            x[i] = { rb32[2*i], rb32[2*i+1] };
                }
                else if (audioFormat == 1 && bitsPerSample == 32) {
                    ok = (bool)f.read(reinterpret_cast<char*>(rb32i.data()), DSP_BLOCK * 8);
                    if (ok)
                        for (size_t i = 0; i < DSP_BLOCK; ++i)
                            x[i] = { rb32i[2*i] / 2147483648.f, rb32i[2*i+1] / 2147483648.f };
                }
                else if (audioFormat == 1 && bitsPerSample == 24) {
                    ok = (bool)f.read(reinterpret_cast<char*>(rb24.data()), DSP_BLOCK * 6);
                    if (ok)
                        for (size_t i = 0; i < DSP_BLOCK; ++i) {
                            auto cvt = [](const uint8_t* b) {
                                int32_t v = b[0] | (b[1]<<8) | (b[2]<<16);
                                if (v >= (1<<23)) v -= (1<<24);
                                return v / 8388608.f;
                            };
                            x[i] = { cvt(&rb24[6*i]), cvt(&rb24[6*i+3]) };
                        }
                }
                else {
                    char msg[128];
                    snprintf(msg, sizeof(msg), "Unsupported WAV: fmt=%u bits=%u",
                             audioFormat, bitsPerSample);
                    if (err_cb) err_cb(msg, err_ud);
                    break;
                }
                if (!ok) break;

                dataBytesRead += (uint32_t)(DSP_BLOCK * numChannels * (bitsPerSample / 8));

                if (!audio_rt.empty())
                    mix_audio_block_fast(x.data(), DSP_BLOCK);

                /* AGC */
                float bpeak = 0.0001f;
                for (size_t i = 0; i < DSP_BLOCK; ++i) {
                    float m = sqrtf(x[i].re*x[i].re + x[i].im*x[i].im);
                    if (m > bpeak) bpeak = m;
                }
                peak_hold = 0.95f * peak_hold + 0.05f * bpeak;

                const float block_safe = (bitScale - 1.f) / (bpeak * 1.05f + 1e-4f);
                lim_ceiling = fminf(block_safe, fminf(lim_ceiling * lim_release, 1e9f));
                if (useAGC) {
                    float tg = (bitScale * 0.65f) / (peak_hold + 0.0001f);
                    current_gain_fast = fminf(lim_ceiling,
                                             0.95f * current_gain_fast + 0.05f * tg);
                } else {
                    current_gain_fast = fminf(gainValue.load() * GAIN_SCALE, lim_ceiling);
                }

                const float ramp_start = fminf(prev_block_gain, block_safe);
                const float gain_ramp_step = (current_gain_fast - ramp_start)
                                             / (float)(DSP_BLOCK * n_interp);
                float gain_ramp = ramp_start;

                auto t0_blk = std::chrono::steady_clock::now();
                size_t out_pos = 0;

                uint32_t lcg = vco_phase ^ 0xdeadbeefU;

                for (size_t bi = 0; bi < DSP_BLOCK; ++bi) {
                    buf_ptr = (buf_ptr + 1) & (POLY_TAPS_MAX - 1);
                    i_buf[buf_ptr] = i_buf[buf_ptr + POLY_TAPS_MAX] = x[bi].re;
                    q_buf[buf_ptr] = q_buf[buf_ptr + POLY_TAPS_MAX] = x[bi].im;
                    /* newest active_poly_taps samples, oldest first */
                    const int    w0 = buf_ptr + POLY_TAPS_MAX - active_poly_taps + 1;
                    const float* wi = i_buf + w0;
                    const float* wq = q_buf + w0;

                    for (int k = 0; k < n_interp; ++k) {
                        const float* pc = (*active_poly)[k].data();
                        float fI = 0.f, fQ = 0.f;
                        for (int t = 0; t < active_poly_taps; ++t) {
                            fI += pc[t] * wi[t];
                            fQ += pc[t] * wq[t];
                        }

                        float c, s;
                        lut_sincos_lerp(vco_phase, &s, &c);
                        vco_phase += vco_phase_inc;

                        float mixed = fI * c - fQ * s;
                        float hf    = mixed * gain_ramp;
                        gain_ramp  += gain_ramp_step;

                        /* TPDF dither for int16 — two uniform ±0.5 LSB → triangular ±1 LSB */
                        lcg = lcg * 1664525u + 1013904223u;
                        hf += (float)(lcg >> 16) * (1.f/65536.f) - 0.5f;
                        lcg = lcg * 1664525u + 1013904223u;
                        hf += (float)(lcg >> 16) * (1.f/65536.f) - 0.5f;

                        if      (hf >  32767.f) hf =  32767.f;
                        else if (hf < -32768.f) hf = -32768.f;
                        out16[out_pos++] = (int16_t)hf;
                    }
                }

                write_ring(reinterpret_cast<const int8_t*>(out16.data()),
                           out_pos * sizeof(int16_t));
                prev_block_gain = current_gain_fast;

                /* Track load for diagnostics only — no quality switching.
                 * write_ring dominates block time (≈100% load in steady state),
                 * so switching polyphase quality has no effect on ring fill level. */
                {
                    auto t1_blk  = std::chrono::steady_clock::now();
                    float load   = (float)(std::chrono::duration<double>(t1_blk - t0_blk).count()
                                          / block_real_time);
                    dsp_load_smooth = 0.95f * dsp_load_smooth + 0.05f * load;
                }

                /* Monitoring */
                size_t n_mon = std::min(MON_SIZE - monIdx, DSP_BLOCK);
                for (size_t k = 0; k < n_mon; ++k)
                    mon[monIdx++] = x[k].re * SCALE_MON;

                ++blockCnt;
                if (blockCnt >= blocksPerSec) {
                    {
                        std::unique_lock<std::mutex> lk(ring_mtx);
                        fprintf(stderr,
                            "[ADALM2000_univ] IQ: load=%.0f%%  ring=%zu/%zu  n_interp=%d\n",
                            dsp_load_smooth * 100.f, ring_count, RING_SIZE, n_interp);
                    }
                    blockCnt = 0;
                    if (mon_cb && monIdx > 0)
                        mon_cb(mon.data(), static_cast<int>(monIdx), mon_ud);
                    monIdx = 0;
                    if (prog_cb && dataBytesTotal > 0)
                        prog_cb((float)dataBytesRead / dataBytesTotal * 100.f, prog_ud);
                }
            }

            teardown_audio_for_file();
            break;
        }
        /* all other chunks: continue with the next one */
        const std::streamoff nxt = wav_next_chunk(f, chunkStart, chunk, fileSize);
        if (nxt < 0) break;
        f.clear();
        f.seekg(nxt);
    }
    if (!dataFound && running.load(std::memory_order_acquire) && err_cb)
        err_cb(("Inconsistent WAV header, data chunk not found: " + path).c_str(), err_ud);

    return nextFile;
}

/* ================================================================== */
/* Mode B: pure AM synthesis (no IQ file)                              */
/* ================================================================== */

void DspWorkerADALM::run_dsp_audioonly()
{
    if (audio_rt.empty()) {
        if (err_cb) err_cb("audio_only mode: no audio channels configured", err_ud);
        running.store(false, std::memory_order_release);
        ring_not_empty.notify_all();
        if (fin_cb) fin_cb(fin_ud);
        return;
    }

    setup_audio_for_file((uint32_t)targetRate);

    const float bitScale    = 32767.0f;
    float current_gain_fast = bitScale * 0.65f;
    float peak_hold         = 0.1f;
    float prev_block_gain   = current_gain_fast;

    std::vector<IQf>     x(DSP_BLOCK);
    std::vector<int16_t> out16(DSP_BLOCK);
    std::vector<float>   mon(MON_SIZE);

    const size_t blocksPerSec = (size_t)((double)targetRate / DSP_BLOCK) + 1;
    size_t blockCnt = 0;
    size_t monIdx   = 0;

    uint32_t lcg = 0x12345678u;

    while (running.load(std::memory_order_acquire)) {

        /* Pause: write silence to keep the ring (and DAC) alive */
        while (paused.load(std::memory_order_acquire)
               && running.load(std::memory_order_acquire))
        {
            static const int8_t zeros[DSP_BLOCK * 2] = {};
            write_ring(zeros, sizeof(zeros));
        }
        if (!running.load(std::memory_order_acquire)) break;

        /* Synthesise block: start from zero, add each AM channel */
        std::fill(x.begin(), x.end(), IQf{0.f, 0.f});
        mix_audio_block_fast(x.data(), DSP_BLOCK);

        /* AGC on real part of composite */
        float bpeak = 0.0001f;
        for (size_t i = 0; i < DSP_BLOCK; ++i) {
            float m = std::fabs(x[i].re);
            if (m > bpeak) bpeak = m;
        }
        peak_hold = 0.95f * peak_hold + 0.05f * bpeak;

        const float block_safe = (bitScale - 1.f) / (bpeak * 1.05f + 1e-4f);
        if (useAGC) {
            float tg = (bitScale * 0.65f) / (peak_hold + 0.0001f);
            current_gain_fast = fminf(block_safe, 0.95f * current_gain_fast + 0.05f * tg);
        } else {
            current_gain_fast = gainValue.load() * block_safe;
        }

        const float ramp_start     = fminf(prev_block_gain, block_safe);
        const float gain_ramp_step = (current_gain_fast - ramp_start) / (float)DSP_BLOCK;
        float       gain_ramp      = ramp_start;

        for (size_t k = 0; k < DSP_BLOCK; ++k) {
            float hf    = x[k].re * gain_ramp;
            gain_ramp  += gain_ramp_step;

            lcg = lcg * 1664525u + 1013904223u;
            hf += (float)(lcg >> 16) * (1.f/65536.f) - 0.5f;
            lcg = lcg * 1664525u + 1013904223u;
            hf += (float)(lcg >> 16) * (1.f/65536.f) - 0.5f;

            if      (hf >  32767.f) hf =  32767.f;
            else if (hf < -32768.f) hf = -32768.f;
            out16[k] = (int16_t)hf;
        }

        write_ring(reinterpret_cast<const int8_t*>(out16.data()),
                   DSP_BLOCK * sizeof(int16_t));
        prev_block_gain = current_gain_fast;

        /* Monitor: accumulate pre-AGC real part, fire callback once per second */
        size_t n_mon = std::min(MON_SIZE - monIdx, DSP_BLOCK);
        for (size_t k = 0; k < n_mon; ++k)
            mon[monIdx++] = x[k].re * SCALE_MON;
        if (++blockCnt >= blocksPerSec) {
            blockCnt = 0;
            if (mon_cb && monIdx > 0)
                mon_cb(mon.data(), static_cast<int>(monIdx), mon_ud);
            monIdx = 0;
        }
    }

    teardown_audio_for_file();

    running.store(false, std::memory_order_release);
    ring_not_full.notify_all();
    ring_not_empty.notify_all();
    if (fin_cb) fin_cb(fin_ud);
}

/* ================================================================== */
/* DSP thread entry                                                    */
/* ================================================================== */

void DspWorkerADALM::run_dsp()
{
    if (audio_only) {
        run_dsp_audioonly();
        return;
    }

    /* Mode A: file loop */
    for (size_t i = 0; i < filenames.size() && running.load(); ) {
        std::string next = process_file(filenames[i]);
        if (!next.empty()) {
            bool found = false;
            for (size_t j = 0; j < filenames.size(); ++j) {
                if (filenames[j].find(next) != std::string::npos) {
                    i = j; found = true; break;
                }
            }
            if (!found) break;
        } else {
            ++i;
        }
    }

    /* Wait for ring to drain before signalling done */
    {
        std::unique_lock<std::mutex> lk(ring_mtx);
        ring_not_empty.wait_for(lk, std::chrono::seconds(5),
            [this] { return ring_count == 0 || !running.load(); });
    }

    running.store(false, std::memory_order_release);
    ring_not_full.notify_all();
    ring_not_empty.notify_all();
    if (fin_cb) fin_cb(fin_ud);
}

/* ================================================================== */
/* C API implementation                                                */
/* ================================================================== */

DspADLMHandle dsp_adlm_create()
{
#ifdef _WIN32
    WSADATA wsa; WSAStartup(MAKEWORD(2,2), &wsa);
#endif
    init_lut();
    fprintf(stderr, "[ADALM2000_univ] *** libdspadlm BUILD %s %s ***\n",
            __DATE__, __TIME__);
    return new DspWorkerADALM();
}

void dsp_adlm_destroy(DspADLMHandle h)
{
    if (!h) return;
    dsp_adlm_stop(h);
    auto* w = static_cast<DspWorkerADALM*>(h);
    w->mon_cb = nullptr;
    w->err_cb = nullptr;
    w->fin_cb = nullptr;
    w->close_audio_sockets();
    delete w;
#ifdef _WIN32
    WSACleanup();
#endif
}

int dsp_adlm_configure(DspADLMHandle h,
                       float         sample_rate,
                       float         lo_shift,
                       float         gain,
                       int           use_agc,
                       int           ao_mode,
                       const char**  filenames,
                       int           num_files)
{
    if (!h) return -1;
    auto* w = static_cast<DspWorkerADALM*>(h);
    w->targetRate  = sample_rate;
    w->shiftFreq   = lo_shift;
    w->gainValue.store(gain);
    w->useAGC      = (use_agc != 0);
    w->audio_only  = (ao_mode != 0);
    w->filenames.clear();
    for (int i = 0; i < num_files; ++i)
        if (filenames && filenames[i]) w->filenames.emplace_back(filenames[i]);
    return 0;
}

int dsp_adlm_configure_audio(DspADLMHandle          h,
                              const DspAudioChannel* channels,
                              int                    n_channels,
                              float                  audio_rate,
                              float                  mix_level)
{
    if (!h) return -1;
    auto* w = static_cast<DspWorkerADALM*>(h);

    w->close_audio_sockets();
    w->audio_cfgs.clear();
    w->audio_rate    = (audio_rate > 0.f) ? audio_rate : 25000.f;
    w->audio_mix_lvl = (mix_level  > 0.f) ? mix_level  : 1.0f;

    if (!channels || n_channels <= 0) return 0;

    w->audio_cfgs.resize(n_channels);
    w->audio_rt.resize(n_channels);

    for (int i = 0; i < n_channels; ++i) {
        DspWorkerADALM::AudioChanCfg& cfg = w->audio_cfgs[i];
        DspWorkerADALM::AudioChanRT&  rt  = w->audio_rt[i];

        cfg.freq_hz  = channels[i].freq_hz;
        cfg.bw_hz    = (channels[i].bandwidth_hz > 0.f) ? channels[i].bandwidth_hz : 4500.f;
        cfg.mod_idx  = (channels[i].mod_index > 0.f && channels[i].mod_index <= 1.f)
                       ? channels[i].mod_index : 0.9f;
        strncpy(cfg.name, channels[i].name, 63);
        cfg.name[63] = '\0';
        cfg.udp_port        = channels[i].udp_port;
        cfg.schroeder_phase = channels[i].schroeder_phase;

        rt.active = false; rt.mod_idx = 0.9f;
        rt.current_aud = 0.f; rt.aud_phase = 0.0; rt.aud_phase_inc = 0.0;
        rt.nco_phase = 0; rt.nco_phase_inc = 0;
        rt.udp_recv_buf.clear();
        rt.raw_fifo.clear();
        rt.udp_fd = -1;

        int fd = ::socket(AF_INET, SOCK_DGRAM, 0);
        if (fd < 0) {
            printf("[ADALM2000_univ] socket() failed ch[%d] '%s': %s\n",
                   i, cfg.name, strerror(errno));
            continue;
        }
        int one = 1;
        setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, SOCKOPT_VAL(&one), sizeof(one));
        int rcvbuf = 524288;
        setsockopt(fd, SOL_SOCKET, SO_RCVBUF, SOCKOPT_VAL(&rcvbuf), sizeof(rcvbuf));

        struct sockaddr_in addr{};
        addr.sin_family      = AF_INET;
        addr.sin_port        = htons((uint16_t)cfg.udp_port);
        addr.sin_addr.s_addr = INADDR_ANY;

        if (::bind(fd, reinterpret_cast<struct sockaddr*>(&addr), sizeof(addr)) != 0) {
            printf("[ADALM2000_univ] bind() failed ch[%d] '%s' port %d: %s\n",
                   i, cfg.name, cfg.udp_port, strerror(errno));
            _sock_close(fd);
            continue;
        }
        _sock_set_nonblocking(fd);
        rt.udp_fd = fd;
        printf("[ADALM2000_univ] ch[%d] '%s': bound UDP port %d, carrier %.1f Hz\n",
               i, cfg.name, cfg.udp_port, cfg.freq_hz);
    }
    return 0;
}

void dsp_adlm_prefill_audio(DspADLMHandle h, int duration_ms)
{
    if (!h || duration_ms <= 0) return;
    auto* w = static_cast<DspWorkerADALM*>(h);

    constexpr int    POLL_MS = 100;
    constexpr size_t RBUF_SZ = 16384;
    std::vector<uint8_t> recv_buf(RBUF_SZ);

    for (int elapsed = 0; elapsed < duration_ms; elapsed += POLL_MS) {
        for (auto& rt : w->audio_rt) {
            if (rt.udp_fd < 0) continue;
            ssize_t nr;
            while ((nr = ::recv(rt.udp_fd, reinterpret_cast<char*>(recv_buf.data()),
                                recv_buf.size(), MSG_DONTWAIT)) > 0) {
                for (ssize_t k = 0; k < nr; ++k) {
                    float s = (static_cast<float>(recv_buf[k]) - 128.f) / 128.f;
                    rt.raw_fifo.push(&s, 1);
                }
            }
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(POLL_MS));
    }

    float ar = w->audio_rate > 0 ? w->audio_rate : 25000.f;
    for (size_t i = 0; i < w->audio_rt.size(); ++i) {
        auto& rt = w->audio_rt[i];
        if (rt.udp_fd < 0) continue;
        float secs = (float)rt.raw_fifo.available() / ar;
        fprintf(stderr, "[ADALM2000_univ] prefill ch[%zu]: raw_fifo=%zu (%.1f s)\n",
                i, rt.raw_fifo.available(), secs);
    }
}

void dsp_adlm_set_monitor_cb (DspADLMHandle h, dsp_monitor_cb_t  cb, void* ud)
{ if (h) { auto* w=static_cast<DspWorkerADALM*>(h); w->mon_cb =cb; w->mon_ud =ud; } }
void dsp_adlm_set_progress_cb(DspADLMHandle h, dsp_progress_cb_t cb, void* ud)
{ if (h) { auto* w=static_cast<DspWorkerADALM*>(h); w->prog_cb=cb; w->prog_ud=ud; } }
void dsp_adlm_set_finished_cb(DspADLMHandle h, dsp_finished_cb_t cb, void* ud)
{ if (h) { auto* w=static_cast<DspWorkerADALM*>(h); w->fin_cb =cb; w->fin_ud =ud; } }
void dsp_adlm_set_error_cb   (DspADLMHandle h, dsp_error_cb_t    cb, void* ud)
{ if (h) { auto* w=static_cast<DspWorkerADALM*>(h); w->err_cb =cb; w->err_ud =ud; } }
void dsp_adlm_set_nextfile_cb(DspADLMHandle h, dsp_nextfile_cb_t cb, void* ud)
{ if (h) { auto* w=static_cast<DspWorkerADALM*>(h); w->nxt_cb =cb; w->nxt_ud =ud; } }

int dsp_adlm_start(DspADLMHandle h)
{
    if (!h) return -1;
    auto* w = static_cast<DspWorkerADALM*>(h);
    if (w->running.load()) return -1;
    if (w->filenames.empty() && !w->audio_only) return -2;
    if (w->audio_rt.empty() && w->audio_only)   return -3;

    {
        std::lock_guard<std::mutex> lk(w->ring_mtx);
        w->ring_head = w->ring_tail = w->ring_count = 0;
    }
    w->running.store(true, std::memory_order_release);
    w->dsp_thr = std::thread(&DspWorkerADALM::run_dsp, w);
    return 0;
}

void dsp_adlm_stop(DspADLMHandle h)
{
    if (!h) return;
    auto* w = static_cast<DspWorkerADALM*>(h);
    w->running.store(false, std::memory_order_release);
    w->ring_not_full.notify_all();
    w->ring_not_empty.notify_all();
    if (w->dsp_thr.joinable()) w->dsp_thr.join();
}

void dsp_adlm_set_pause(DspADLMHandle h, int p)
{ if (h) static_cast<DspWorkerADALM*>(h)->paused.store(p != 0); }

void dsp_adlm_set_audio_mix(DspADLMHandle h, float mix_level)
{ if (h && mix_level > 0.f) static_cast<DspWorkerADALM*>(h)->audio_mix_lvl.store(mix_level); }

void dsp_adlm_set_gain(DspADLMHandle h, float gain)
{ if (h) static_cast<DspWorkerADALM*>(h)->gainValue.store(gain); }

int dsp_adlm_is_running(DspADLMHandle h)
{ return h ? (static_cast<DspWorkerADALM*>(h)->running.load() ? 1 : 0) : 0; }

void dsp_adlm_seek(DspADLMHandle h, int64_t byte_pos, int whence)
{
    if (!h) return;
    auto* w = static_cast<DspWorkerADALM*>(h);
    std::lock_guard<std::mutex> lk(w->seek_mtx);
    w->seek_req.pending = true;
    w->seek_req.pos     = byte_pos;
    w->seek_req.whence  = whence;
}

void dsp_adlm_set_raw_format(DspADLMHandle h, uint32_t sample_rate, int audio_format, int bits_per_sample)
{
    if (!h) return;
    auto* w = static_cast<DspWorkerADALM*>(h);
    w->rawSampleRate    = sample_rate;
    w->rawAudioFormat   = (uint16_t)audio_format;
    w->rawBitsPerSample = (uint16_t)bits_per_sample;
}

/* ================================================================== */
/* Pull API  (replaces the fl2k drain_ring / fl2k_callback pattern)   */
/* ================================================================== */

int dsp_adlm_pull(DspADLMHandle h, int16_t* buf, int n_samples)
{
    if (!h || !buf || n_samples <= 0) return -1;
    auto* w = static_cast<DspWorkerADALM*>(h);

    if (!w->running.load(std::memory_order_acquire)) return -1;

    const size_t nbytes = (size_t)n_samples * sizeof(int16_t);

    std::unique_lock<std::mutex> lk(w->ring_mtx);
    bool ok = w->ring_not_empty.wait_for(lk, std::chrono::milliseconds(200),
        [&] { return w->ring_count >= nbytes || !w->running.load(); });

    if (!ok || w->ring_count < nbytes) {
        if (!w->running.load()) return -1;
        fprintf(stderr, "[ADALM2000_univ] pull TIMEOUT: ring=%zu  need=%zu\n",
                w->ring_count, nbytes);
        return 0;   /* timeout — caller should retry */
    }

    size_t first = std::min(nbytes, RING_SIZE - w->ring_tail);
    memcpy(buf, w->ring.data() + w->ring_tail, first);
    if (first < nbytes)
        memcpy(reinterpret_cast<int8_t*>(buf) + first, w->ring.data(), nbytes - first);
    w->ring_tail    = (w->ring_tail + nbytes) % RING_SIZE;
    w->ring_count  -= nbytes;
    w->ring_not_full.notify_one();

    return n_samples;
}
