/*
 * DspWorkerFL2K.cpp  –  fl2k_fast_plus variant
 *
 * liquidDSP-free replacement for fl2k_plus.  Designed for high channel
 * counts where the polyphase resamplers in liquidDSP become the bottleneck.
 *
 * Key algorithm changes vs. fl2k_plus:
 *
 *  1. IQ upsampling (WAV → targetRate):
 *       Cosine-interpolation between adjacent WAV samples + 7-tap symmetric
 *       integer FIR smoother (coefficients {4,16,26,36,26,16,4}, sum=128).
 *       Replaces liquidDSP msresamp_crcf.
 *       Idea from COHIRADIAStreamer / DspWorker::run_dsp_engine_32INT.
 *
 *  2. Audio resampling (audio_rate → sampleRate):
 *       Zero-order hold (ZOH / sample-repetition):  each audio sample from
 *       the raw_fifo is held for round(sampleRate/audio_rate) IQ samples.
 *       Introduces images at multiples of audio_rate, but these are far
 *       outside the AM demodulator's passband (typically < 5 kHz).
 *       Replaces liquidDSP msresamp_rrrf.
 *       Idea from AMWaveSynth / am_modulator_multiple_channels.c.
 *
 *  3. All NCOs: 32-bit phase accumulator + 12-bit sin/cos LUT (4096 entries,
 *       int16_t ±32767 values).  Replaces liquidDSP nco_crcf.
 *
 *  No liquidDSP dependency.  Build with:
 *    g++ -std=c++17 -O3 -march=native -ffast-math -fPIC -shared \
 *        DspWorkerFL2K.cpp -o libdspfl2k.so -losmo-fl2k -lpthread -lm
 */

#include "DspWorkerFL2K.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <fstream>
#include <vector>
#include <string>
#include <atomic>
#include <mutex>
#include <condition_variable>
#include <thread>
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

#include <osmo-fl2k.h>

/* ================================================================== */
/* LUT NCO  –  12-bit, 4096 entries, int16_t ±32767                   */
/* ================================================================== */

static constexpr int LUT_BITS = 12;
static constexpr int LUT_SIZE = 1 << LUT_BITS;   /* 4096 */
static int16_t g_lut_sin[LUT_SIZE];
static int16_t g_lut_cos[LUT_SIZE];
static bool    g_lut_ready = false;

static void init_lut()
{
    if (g_lut_ready) return;
    for (int i = 0; i < LUT_SIZE; ++i) {
        double a    = 2.0 * M_PI * i / LUT_SIZE;
        g_lut_sin[i] = (int16_t)std::round(std::sin(a) * 32767.0);
        g_lut_cos[i] = (int16_t)std::round(std::cos(a) * 32767.0);
    }
    g_lut_ready = true;
}

/* Phase accumulator access: upper LUT_BITS select table entry */
static inline int16_t lut_sin(uint32_t phase) { return g_lut_sin[phase >> (32 - LUT_BITS)]; }
static inline int16_t lut_cos(uint32_t phase) { return g_lut_cos[phase >> (32 - LUT_BITS)]; }

/* Frequency (Hz) → uint32_t phase increment at sample_rate */
static inline uint32_t freq_to_pinc(double freq_hz, double sample_rate)
{
    return (uint32_t)(freq_hz / sample_rate * 4294967296.0);
}

/* ================================================================== */
/* IQf  –  lightweight float complex (no liquidDSP dependency)         */
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
/* Constants                                                           */
/* ================================================================== */
static constexpr size_t RING_BUFS = 16;
static constexpr size_t RING_SIZE = (size_t)FL2K_BUF_LEN * RING_BUFS;
static constexpr size_t DSP_BLOCK = 8192;
static constexpr size_t MON_SIZE  = 8192;
static constexpr float  SCALE_MON = 1048576.0f;

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
/* DspWorkerFL2K – internal state                                      */
/* ================================================================== */
struct DspWorkerFL2K {

    /* --- main IQ config ------------------------------------------- */
    float              targetRate  = 10'000'000.f;
    float              shiftFreq   = 0.f;
    std::atomic<float> gainValue   {0.65f};
    bool               useAGC      = true;
    std::vector<std::string> filenames;

    /* --- callbacks ------------------------------------------------- */
    dsp_monitor_cb_t  mon_cb  = nullptr; void* mon_ud  = nullptr;
    dsp_progress_cb_t prog_cb = nullptr; void* prog_ud = nullptr;
    dsp_finished_cb_t fin_cb  = nullptr; void* fin_ud  = nullptr;
    dsp_error_cb_t    err_cb  = nullptr; void* err_ud  = nullptr;
    dsp_nextfile_cb_t nxt_cb  = nullptr; void* nxt_ud  = nullptr;

    /* --- ring buffer (DSP writes, FL2K callback reads) ------------ */
    std::vector<int8_t>     ring       = std::vector<int8_t>(RING_SIZE, 0);
    size_t                  ring_head  = 0, ring_tail = 0, ring_count = 0;
    std::mutex              ring_mtx;
    std::condition_variable ring_not_empty, ring_not_full;
    std::vector<int8_t>     fl2k_buf   = std::vector<int8_t>(FL2K_BUF_LEN, 0);

    /* --- seek request --------------------------------------------- */
    struct SeekReq { bool pending = false; int64_t pos = 0; int whence = 0; };
    std::mutex seek_mtx; SeekReq seek_req;

    /* --- control -------------------------------------------------- */
    std::atomic<bool> running {false};
    std::atomic<bool> paused  {false};

    /* --- device --------------------------------------------------- */
    fl2k_dev_t*       dev      = nullptr;
    std::mutex        dev_mtx;
    std::atomic<bool> dev_open {false};

    /* --- threads -------------------------------------------------- */
    std::thread dsp_thr, fl2k_thr;

    /* =================================================================
     * Audio overlay channels
     * ================================================================*/
    struct AudioChanCfg {
        float freq_hz  = 0.f;
        float bw_hz    = 4500.f;
        float mod_idx  = 0.9f;
        char  name[64] = {};
        int   udp_port = -1;
    };

    struct AudioChanRT {
        bool     active        = false;
        int      udp_fd        = -1;
        float    mod_idx       = 0.9f;
        float    gain          = 0.f;

        /* ZOH audio position tracking */
        float    current_aud   = 0.f;  /* currently held sample (ZOH)       */
        double   aud_phase     = 0.0;  /* fractional position [0,1)          */
        double   aud_phase_inc = 0.0;  /* audio_rate / sampleRate            */

        /* Integer LUT NCO for the AM carrier */
        uint32_t nco_phase     = 0;    /* 32-bit phase accumulator           */
        uint32_t nco_phase_inc = 0;    /* phase step per IQ sample at SR     */

        /* Scratch buffers */
        std::vector<uint8_t> udp_recv_buf;

        /* 1 M-sample raw_fifo: same deep buffer as fl2k_plus for UDP data  */
        AudioFifo raw_fifo{1'048'576};
    };

    std::vector<AudioChanCfg> audio_cfgs;
    std::vector<AudioChanRT>  audio_rt;
    float                     audio_rate    = 25000.f;
    float                     audio_mix_lvl = 1.0f;

    /* --- helpers -------------------------------------------------- */
    void write_ring(const int8_t* data, size_t n);
    void drain_ring(int8_t* buf, size_t n);
    void run_dsp();
    void run_fl2k();
    std::string process_file(const std::string& path);
    void close_audio_sockets();
    void setup_audio_for_file(uint32_t sr);
    void teardown_audio_for_file();
    void mix_audio_block_fast(IQf* x, size_t n_iq);

    static void fl2k_callback(fl2k_data_info_t* info);
};

/* ================================================================== */
/* Ring buffer                                                         */
/* ================================================================== */

void DspWorkerFL2K::write_ring(const int8_t* data, size_t n)
{
    size_t written = 0;
    while (written < n && running.load(std::memory_order_acquire)) {
        std::unique_lock<std::mutex> lk(ring_mtx);
        ring_not_full.wait(lk, [&] {
            return (RING_SIZE - ring_count) >= (n - written)
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

void DspWorkerFL2K::drain_ring(int8_t* buf, size_t n)
{
    static uint64_t cb_cnt       = 0;
    static uint64_t underrun_cnt = 0;
    ++cb_cnt;

    std::lock_guard<std::mutex> lk(ring_mtx);
    if (ring_count < n) {
        ++underrun_cnt;
        size_t have = ring_count;
        fprintf(stderr,
                "[fl2k_fast_plus] RING UNDERRUN #%llu (cb=%llu): ring=%zu < need=%zu\n",
                (unsigned long long)underrun_cnt, (unsigned long long)cb_cnt, have, n);
        if (have > 0) {
            size_t first = std::min(have, RING_SIZE - ring_tail);
            memcpy(buf, ring.data() + ring_tail, first);
            if (first < have) memcpy(buf + first, ring.data(), have - first);
            memset(buf + have, 0, n - have);
            ring_tail  = (ring_tail + have) % RING_SIZE;
            ring_count = 0;
            ring_not_full.notify_one();
        } else {
            memset(buf, 0, n);
        }
        return;
    }
    size_t first = std::min(n, RING_SIZE - ring_tail);
    memcpy(buf, ring.data() + ring_tail, first);
    if (first < n) memcpy(buf + first, ring.data(), n - first);
    ring_tail   = (ring_tail + n) % RING_SIZE;
    ring_count -= n;
    ring_not_full.notify_one();
}

/* ================================================================== */
/* FL2K callback                                                       */
/* ================================================================== */

void DspWorkerFL2K::fl2k_callback(fl2k_data_info_t* info)
{
    auto* self = static_cast<DspWorkerFL2K*>(info->ctx);
    if (!self) return;
    if (info->device_error) {
        self->running.store(false, std::memory_order_release);
        if (self->err_cb) self->err_cb("fl2k device error", self->err_ud);
        return;
    }
    info->sampletype_signed = 1;
    uint32_t n = info->len;
    self->drain_ring(self->fl2k_buf.data(), n);
    if (info->using_zerocopy) {
        if (info->r_buf) memcpy(info->r_buf, self->fl2k_buf.data(), n);
    } else {
        info->r_buf = reinterpret_cast<char*>(self->fl2k_buf.data());
    }
}

/* ================================================================== */
/* FL2K thread                                                         */
/* ================================================================== */

void DspWorkerFL2K::run_fl2k()
{
    {
        std::lock_guard<std::mutex> lk(dev_mtx);
        int r = fl2k_open(&dev, 0);
        if (r != FL2K_SUCCESS) {
            char msg[128];
            snprintf(msg, sizeof(msg), "fl2k_open failed (code %d). Check USB connection.", r);
            if (err_cb) err_cb(msg, err_ud);
            running.store(false, std::memory_order_release);
            ring_not_full.notify_all();
            if (fin_cb) fin_cb(fin_ud);
            return;
        }
        fl2k_set_sample_rate(dev, static_cast<uint32_t>(targetRate));
        dev_open.store(true, std::memory_order_release);
    }

    if (!running.load(std::memory_order_acquire)) {
        fl2k_close(dev);
        { std::lock_guard<std::mutex> lk(dev_mtx); dev = nullptr; }
        return;
    }

    /* Wait for DSP pre-fill (~524 ms) before handing off to hardware */
    {
        std::unique_lock<std::mutex> lk(ring_mtx);
        ring_not_empty.wait_for(lk, std::chrono::seconds(5), [this] {
            return ring_count >= 4 * FL2K_BUF_LEN || !running.load();
        });
        fprintf(stderr, "[fl2k_fast_plus] ring pre-fill: %zu bytes ready\n", ring_count);
    }

    fl2k_start_tx(dev, fl2k_callback, this, 0);

    while (running.load(std::memory_order_acquire))
        std::this_thread::sleep_for(std::chrono::milliseconds(10));

    fl2k_stop_tx(dev);
    fl2k_close(dev);
    { std::lock_guard<std::mutex> lk(dev_mtx); dev = nullptr; dev_open.store(false); }
}

/* ================================================================== */
/* Audio overlay helpers                                               */
/* ================================================================== */

void DspWorkerFL2K::close_audio_sockets()
{
    for (auto& rt : audio_rt) {
        if (rt.udp_fd >= 0) { _sock_close(rt.udp_fd); rt.udp_fd = -1; }
    }
    audio_rt.clear();
}

void DspWorkerFL2K::setup_audio_for_file(uint32_t sr)
{
    if (audio_rt.empty()) return;
    float ba = audio_mix_lvl / sqrtf((float)audio_rt.size());

    for (size_t i = 0; i < audio_rt.size(); ++i) {
        AudioChanRT&  rt  = audio_rt[i];
        AudioChanCfg& cfg = audio_cfgs[i];

        rt.mod_idx  = cfg.mod_idx;
        rt.gain     = ba;
        rt.active   = (rt.udp_fd >= 0);
        if (!rt.active) continue;

        /* ZOH: audio_rate → sampleRate */
        rt.aud_phase     = 0.0;
        rt.aud_phase_inc = (double)audio_rate / sr;
        rt.current_aud   = 0.f;

        /* LUT NCO at delta_f = carrier - centerFreq, running at sampleRate */
        double delta_f = (double)cfg.freq_hz - shiftFreq;
        rt.nco_phase     = 0;
        rt.nco_phase_inc = freq_to_pinc(delta_f, sr);

        /* Allocate UDP receive scratch */
        rt.udp_recv_buf.assign(16384, 0);
        rt.raw_fifo.clear();

        float nyq = sr * 0.5f;
        if (std::fabs(delta_f) > nyq)
            printf("[fl2k_fast_plus] WARNING ch[%zu] '%s': "
                   "delta_f=%.0f Hz exceeds Nyquist ±%.0f Hz – will alias.\n",
                   i, cfg.name, delta_f, nyq);

        printf("[fl2k_fast_plus] ch[%zu] '%s': carrier=%.1f Hz  delta_f=%.1f Hz  "
               "udp_port=%d  gain=%.4f  aud_phase_inc=%.6f\n",
               i, cfg.name, cfg.freq_hz, delta_f, cfg.udp_port, ba, rt.aud_phase_inc);
    }
}

void DspWorkerFL2K::teardown_audio_for_file()
{
    for (auto& rt : audio_rt) rt.active = false;
}

/*
 * mix_audio_block_fast – ZOH + LUT NCO audio mixing at sampleRate.
 *
 * For each active channel:
 *   1. Drain available UDP datagrams into raw_fifo (u8 PCM → float).
 *   2. Advance ZOH audio position by aud_phase_inc per IQ sample;
 *      pop one new audio sample from raw_fifo whenever phase ≥ 1.
 *   3. DSB-LC AM with integer LUT NCO:
 *        x[k] += gain * (1 + mod_idx * audio) * exp(j * nco_phase)
 *
 * Signal-theoretically, ZOH introduces a sinc roll-off and images at
 * multiples of audio_rate.  For typical audio_rate=25 kHz these images
 * are at ±25 kHz from the AM carrier – well outside any demodulator's
 * passband and acceptable for the AM-broadcast use case.
 */
void DspWorkerFL2K::mix_audio_block_fast(IQf* x, size_t n_iq)
{
    static uint64_t call_cnt = 0;
    ++call_cnt;

    for (size_t chi = 0; chi < audio_rt.size(); ++chi) {
        AudioChanRT& rt = audio_rt[chi];
        if (!rt.active) continue;

        /* 1. Drain UDP socket into raw_fifo */
        if (rt.raw_fifo.available() < rt.raw_fifo.cap) {
            ssize_t nr;
            while ((nr = recv(rt.udp_fd, rt.udp_recv_buf.data(),
                              rt.udp_recv_buf.size(), MSG_DONTWAIT)) > 0)
            {
                /* u8 PCM (silence=128) → float [-1..1] */
                for (ssize_t k = 0; k < nr; ++k) {
                    float s = (static_cast<float>(rt.udp_recv_buf[k]) - 128.f) / 128.f;
                    rt.raw_fifo.push(&s, 1);
                }
                if (rt.raw_fifo.available() >= rt.raw_fifo.cap) break;
            }
        }

        /* 2+3. ZOH advance + LUT NCO + AM mix */
        const float inv32767 = 1.f / 32767.f;
        for (size_t k = 0; k < n_iq; ++k) {

            /* ZOH: advance audio position, pop when phase crosses 1 */
            rt.aud_phase += rt.aud_phase_inc;
            if (rt.aud_phase >= 1.0) {
                rt.aud_phase -= 1.0;
                rt.raw_fifo.pop(&rt.current_aud, 1);
            }

            /* LUT NCO */
            float cf = lut_cos(rt.nco_phase) * inv32767;
            float sf = lut_sin(rt.nco_phase) * inv32767;
            rt.nco_phase += rt.nco_phase_inc;

            /* DSB-LC AM: (1 + m * audio) * carrier */
            float am = rt.gain * (1.f + rt.mod_idx * rt.current_aud);
            x[k].re += am * cf;
            x[k].im += am * sf;
        }
    }

    /* Periodic diagnostics */
    if (call_cnt % 500 == 0) {
        fprintf(stderr, "[fl2k_fast_plus] diag call=%llu  channels:",
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
/* DSP: process a single WAV file                                      */
/* ================================================================== */

/*
 * 7-tap symmetric FIR smoother  {4,16,26,36,26,16,4}  (sum=128 → >>7).
 * Applied after cosine-interpolation upsampling to suppress spectral
 * images from the zero-order-hold staircase.
 * Coefficients from COHIRADIAStreamer / DspWorker::run_dsp_engine_32INT.
 */
static constexpr int32_t FIR_COEFFS[7] = { 4, 16, 26, 36, 26, 16, 4 };

static inline int32_t fir_step(int32_t* hist, int32_t new_val)
{
    /* Shift history and insert new sample at position 6 */
    hist[0] = hist[1]; hist[1] = hist[2]; hist[2] = hist[3];
    hist[3] = hist[4]; hist[4] = hist[5]; hist[5] = hist[6];
    hist[6] = new_val;
    return (hist[0]*FIR_COEFFS[0] + hist[1]*FIR_COEFFS[1] +
            hist[2]*FIR_COEFFS[2] + hist[3]*FIR_COEFFS[3] +
            hist[4]*FIR_COEFFS[4] + hist[5]*FIR_COEFFS[5] +
            hist[6]*FIR_COEFFS[6]) >> 7;
}

std::string DspWorkerFL2K::process_file(const std::string& path)
{
    std::ifstream f(path, std::ios::binary);
    if (!f) {
        if (err_cb) err_cb(("Cannot open: " + path).c_str(), err_ud);
        return "";
    }
    if (nxt_cb) nxt_cb(path.c_str(), nxt_ud);

    RiffHeader riff;
    f.read(reinterpret_cast<char*>(&riff), sizeof(riff));

    uint32_t sampleRate    = 0;
    uint16_t audioFormat   = 1;
    uint16_t bitsPerSample = 16;
    uint16_t numChannels   = 2;
    std::string nextFile;
    ChunkHeader chunk;

    printf("[fl2k_fast_plus] Processing: %s\n", path.c_str());
    printf("[fl2k_fast_plus] shiftFreq: %.0f Hz\n", shiftFreq);

    while (f.read(reinterpret_cast<char*>(&chunk), sizeof(chunk))
           && running.load(std::memory_order_acquire))
    {
        std::string tag(chunk.id, 4);

        if (tag == "fmt ") {
            FmtStruct fmt;
            f.read(reinterpret_cast<char*>(&fmt), sizeof(fmt));
            sampleRate    = fmt.sampleRate;
            audioFormat   = fmt.audioFormat;
            bitsPerSample = fmt.bitsPerSample;
            numChannels   = fmt.numChannels;
            long skip = (long)chunk.size - (long)sizeof(fmt);
            if (skip > 0) f.seekg(skip, std::ios::cur);
        }
        else if (tag == "auxi") {
            AuxiContent aux;
            f.read(reinterpret_cast<char*>(&aux), sizeof(aux));
            std::string raw(aux.filename, 96);
            static const std::string JUNK(" \t\n\r\0\x01", 6);
            size_t last = raw.find_last_not_of(JUNK);
            if (last != std::string::npos) nextFile = raw.substr(0, last + 1);
            long skip = (long)chunk.size - (long)sizeof(aux);
            if (skip > 0) f.seekg(skip, std::ios::cur);
        }
        else if (tag == "data") {

            if (sampleRate == 0 || numChannels < 2) {
                if (err_cb) err_cb("Invalid WAV header", err_ud);
                break;
            }

            /* ----------------------------------------------------------
             * Precompute cosine-interpolation LUT for IQ upsampling.
             *
             * mu2_lut[k] = (1 - cos(k/N * π)) / 2  for k = 0..N-1
             * where N = round(targetRate / sampleRate).
             *
             * The inner loop interpolates from lastI to nextI using
             * mu2 as the mixing coefficient (cosine-shaped for smooth
             * spectral roll-off vs. linear interpolation).
             *
             * Precomputing removes the cosf() call from the hot path.
             * --------------------------------------------------------*/
            double upRatio = (double)targetRate / sampleRate;
            int    n_interp = (int)std::round(upRatio);
            if (n_interp < 1) n_interp = 1;

            std::vector<float> mu2_lut(n_interp);
            for (int k = 0; k < n_interp; ++k) {
                double mu    = (double)k / upRatio;
                mu2_lut[k]   = (float)((1.0 - std::cos(mu * M_PI)) / 2.0);
            }

            /* Main LUT NCO: shift IQ baseband to shiftFreq at targetRate */
            uint32_t vco_phase     = 0;
            uint32_t vco_phase_inc = freq_to_pinc(shiftFreq, targetRate);

            /* Audio overlay setup */
            setup_audio_for_file(sampleRate);

            /* AGC / gain state
             * GAIN_SCALE = 256 * bitScale matches fl2k_plus semantics:
             *   gainValue × GAIN_SCALE / 32767 maps the same gainValue range to the
             *   same output amplitude as fl2k_plus (which uses gainValue × GAIN_SCALE
             *   on a ±1 float signal; here mixed is ±32767, hence the ÷32767). */
            const float bitScale    = 127.0f;
            const float GAIN_SCALE  = 256.0f * bitScale;   /* = 32512, same as fl2k_plus */
            float current_gain_fast = gainValue.load() * GAIN_SCALE / 32767.f;
            float peak_hold         = 0.1f;

            /* IQ cosine-interp state: integer ±32767 */
            int32_t lastI = 0, lastQ = 0, nextI = 0, nextQ = 0;
            int32_t i_hist[7] = {}, q_hist[7] = {};

            /* Buffers */
            std::vector<IQf>   x(DSP_BLOCK);
            std::vector<int16_t> rb16(DSP_BLOCK * 2);
            std::vector<float>   rb32(DSP_BLOCK * 2);
            std::vector<int32_t> rb32i(DSP_BLOCK * 2);
            std::vector<uint8_t> rb24(DSP_BLOCK * 6);
            /* out8: worst case n_interp output samples per WAV sample */
            std::vector<int8_t>  out8(DSP_BLOCK * (n_interp + 1));
            std::vector<float>   mon(MON_SIZE);

            uint32_t dataBytesTotal = chunk.size;
            uint32_t dataBytesRead  = 0;
            size_t   blocksPerSec   = (size_t)((double)sampleRate / DSP_BLOCK) + 1;
            size_t   blockCnt       = 0;
            size_t   monIdx         = 0;

            printf("[fl2k_fast_plus] SR=%u  upRatio=%.3f  n_interp=%d\n",
                   sampleRate, upRatio, n_interp);

            /* ---- inner read-and-process loop ---- */
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
                        /* Reset interpolation state to avoid a glitch */
                        lastI = lastQ = nextI = nextQ = 0;
                        std::fill(std::begin(i_hist), std::end(i_hist), 0);
                        std::fill(std::begin(q_hist), std::end(q_hist), 0);
                    }
                }

                /* -- pause: feed silence -- */
                while (paused.load(std::memory_order_acquire)
                       && running.load(std::memory_order_acquire))
                {
                    static const int8_t zeros[4096] = {};
                    write_ring(zeros, sizeof(zeros));
                }
                if (!running.load(std::memory_order_acquire)) break;

                /* -- read one block of IQ samples from WAV -- */
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

                /* -- mix audio overlay channels into baseband at sampleRate -- */
                if (!audio_rt.empty())
                    mix_audio_block_fast(x.data(), DSP_BLOCK);

                /* -- AGC: track peak amplitude of combined IQ block -- */
                float bpeak = 0.0001f;
                for (size_t i = 0; i < DSP_BLOCK; ++i) {
                    float m = sqrtf(x[i].re*x[i].re + x[i].im*x[i].im);
                    if (m > bpeak) bpeak = m;
                }
                peak_hold = 0.95f * peak_hold + 0.05f * bpeak;

                if (useAGC) {
                    /* Target: peak_hold maps to bitScale * 0.65 in output */
                    float tg = (bitScale * 0.65f)
                               / ((peak_hold + 0.0001f) * 32767.f);
                    current_gain_fast = 0.98f * current_gain_fast + 0.02f * tg;
                } else {
                    current_gain_fast = gainValue.load() * GAIN_SCALE / 32767.f;
                }

                /* -- Upsample + LUT NCO + int8 output --
                 *
                 * For each WAV sample pair in x[]:
                 *   a) convert float IQ → int32 ±32767
                 *   b) cosine-interpolate n_interp output samples between
                 *      lastI/Q and nextI/Q using the precomputed mu2_lut
                 *   c) push each interpolated sample through the 7-tap FIR
                 *   d) mix with main LUT NCO (frequency shift to shiftFreq)
                 *   e) apply gain + clip → int8_t
                 */
                size_t out_pos = 0;
                const float inv32767 = 1.f / 32767.f;

                for (size_t bi = 0; bi < DSP_BLOCK; ++bi) {
                    lastI = nextI;
                    lastQ = nextQ;
                    nextI = (int32_t)(x[bi].re * 32767.f);
                    nextQ = (int32_t)(x[bi].im * 32767.f);

                    for (int k = 0; k < n_interp; ++k) {
                        float mu2 = mu2_lut[k];

                        /* Cosine-interpolated IQ */
                        int32_t currI = (int32_t)((float)lastI + mu2 * (float)(nextI - lastI));
                        int32_t currQ = (int32_t)((float)lastQ + mu2 * (float)(nextQ - lastQ));

                        /* 7-tap FIR */
                        int32_t fI = fir_step(i_hist, currI);
                        int32_t fQ = fir_step(q_hist, currQ);

                        /* LUT NCO: extract real part of IQ * exp(j*phi)
                         * = I*cos(phi) - Q*sin(phi)                    */
                        int16_t c = lut_cos(vco_phase);
                        int16_t s = lut_sin(vco_phase);
                        vco_phase += vco_phase_inc;

                        /* Product fits in int32: |fI*c| ≤ 32767² < 2^31 */
                        int32_t mixed = ((int32_t)fI * c - (int32_t)fQ * s) >> 15;

                        /* Apply gain and clip to signed 8-bit */
                        float hf = (float)mixed * current_gain_fast;
                        if      (hf >  127.f) hf =  127.f;
                        else if (hf < -128.f) hf = -128.f;
                        out8[out_pos++] = (int8_t)hf;
                    }
                }

                write_ring(out8.data(), out_pos);

                /* -- monitoring (pre-upsample IQ real part) -- */
                size_t n_mon = std::min(MON_SIZE - monIdx, DSP_BLOCK);
                for (size_t k = 0; k < n_mon; ++k)
                    mon[monIdx++] = x[k].re * SCALE_MON;

                ++blockCnt;
                if (blockCnt >= blocksPerSec) {
                    blockCnt = 0;
                    if (mon_cb && monIdx > 0)
                        mon_cb(mon.data(), static_cast<int>(monIdx), mon_ud);
                    monIdx = 0;
                    if (prog_cb && dataBytesTotal > 0)
                        prog_cb((float)dataBytesRead / dataBytesTotal * 100.f, prog_ud);
                }
            } /* inner while */

            teardown_audio_for_file();
            break;
        }
        else {
            f.seekg(chunk.size, std::ios::cur);
            if (chunk.size & 1) f.seekg(1, std::ios::cur);
        }
    }

    return nextFile;
}

/* ================================================================== */
/* DSP thread entry                                                    */
/* ================================================================== */

void DspWorkerFL2K::run_dsp()
{
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
/* C API                                                               */
/* ================================================================== */

DspFL2KHandle dsp_fl2k_create()
{
#ifdef _WIN32
    WSADATA wsa; WSAStartup(MAKEWORD(2,2), &wsa);
#endif
    init_lut();
    fprintf(stderr, "[fl2k_fast_plus] *** libdspfl2k BUILD %s %s (fast-no-liquid) ***\n",
            __DATE__, __TIME__);
    return new DspWorkerFL2K();
}

void dsp_fl2k_destroy(DspFL2KHandle h)
{
    if (!h) return;
    dsp_fl2k_stop(h);
    static_cast<DspWorkerFL2K*>(h)->close_audio_sockets();
    delete static_cast<DspWorkerFL2K*>(h);
#ifdef _WIN32
    WSACleanup();
#endif
}

int dsp_fl2k_configure(DspFL2KHandle h,
                       float target_rate, float shift_freq,
                       float gain, int use_agc,
                       const char** filenames, int num_files)
{
    if (!h) return -1;
    auto* w = static_cast<DspWorkerFL2K*>(h);
    w->targetRate = target_rate;
    w->shiftFreq  = shift_freq;
    w->gainValue.store(gain);
    w->useAGC     = (use_agc != 0);
    w->filenames.clear();
    for (int i = 0; i < num_files; ++i)
        if (filenames && filenames[i]) w->filenames.emplace_back(filenames[i]);
    return 0;
}

int dsp_fl2k_configure_audio(DspFL2KHandle          h,
                              const DspAudioChannel* channels,
                              int                    n_channels,
                              float                  audio_rate,
                              float                  mix_level)
{
    if (!h) return -1;
    auto* w = static_cast<DspWorkerFL2K*>(h);

    w->close_audio_sockets();
    w->audio_cfgs.clear();
    w->audio_rate    = (audio_rate > 0.f) ? audio_rate : 25000.f;
    w->audio_mix_lvl = (mix_level  > 0.f) ? mix_level  : 1.0f;

    if (!channels || n_channels <= 0) return 0;

    w->audio_cfgs.resize(n_channels);
    w->audio_rt.resize(n_channels);

    for (int i = 0; i < n_channels; ++i) {
        DspWorkerFL2K::AudioChanCfg& cfg = w->audio_cfgs[i];
        DspWorkerFL2K::AudioChanRT&  rt  = w->audio_rt[i];

        cfg.freq_hz  = channels[i].freq_hz;
        cfg.bw_hz    = (channels[i].bandwidth_hz > 0.f) ? channels[i].bandwidth_hz : 4500.f;
        cfg.mod_idx  = (channels[i].mod_index > 0.f && channels[i].mod_index <= 1.f)
                       ? channels[i].mod_index : 0.9f;
        strncpy(cfg.name, channels[i].name, 63);
        cfg.name[63] = '\0';
        cfg.udp_port = channels[i].udp_port;

        /* Reset runtime state */
        rt.active = false; rt.mod_idx = 0.9f; rt.gain = 0.f;
        rt.current_aud = 0.f; rt.aud_phase = 0.0; rt.aud_phase_inc = 0.0;
        rt.nco_phase = 0; rt.nco_phase_inc = 0;
        rt.udp_recv_buf.clear();
        rt.raw_fifo.clear();
        rt.udp_fd = -1;

        /* Open non-blocking UDP receive socket */
        int fd = ::socket(AF_INET, SOCK_DGRAM, 0);
        if (fd < 0) {
            printf("[fl2k_fast_plus] socket() failed ch[%d] '%s': %s\n",
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
            printf("[fl2k_fast_plus] bind() failed ch[%d] '%s' port %d: %s\n",
                   i, cfg.name, cfg.udp_port, strerror(errno));
            _sock_close(fd);
            continue;
        }
        _sock_set_nonblocking(fd);
        rt.udp_fd = fd;
        printf("[fl2k_fast_plus] ch[%d] '%s': bound UDP port %d, carrier %.1f Hz\n",
               i, cfg.name, cfg.udp_port, cfg.freq_hz);
    }
    return 0;
}

void dsp_fl2k_prefill_audio(DspFL2KHandle h, int duration_ms)
{
    if (!h || duration_ms <= 0) return;
    auto* w = static_cast<DspWorkerFL2K*>(h);

    constexpr int    POLL_MS = 100;
    constexpr size_t RBUF_SZ = 16384;
    std::vector<uint8_t> recv_buf(RBUF_SZ);

    for (int elapsed = 0; elapsed < duration_ms; elapsed += POLL_MS) {
        for (auto& rt : w->audio_rt) {
            if (rt.udp_fd < 0) continue;
            ssize_t nr;
            while ((nr = ::recv(rt.udp_fd, recv_buf.data(),
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
        fprintf(stderr, "[fl2k_fast_plus] prefill ch[%zu]: raw_fifo=%zu (%.1f s)\n",
                i, rt.raw_fifo.available(), secs);
    }
}

void dsp_fl2k_set_monitor_cb (DspFL2KHandle h, dsp_monitor_cb_t  cb, void* ud)
{ if (h) { auto* w=static_cast<DspWorkerFL2K*>(h); w->mon_cb =cb; w->mon_ud =ud; } }
void dsp_fl2k_set_progress_cb(DspFL2KHandle h, dsp_progress_cb_t cb, void* ud)
{ if (h) { auto* w=static_cast<DspWorkerFL2K*>(h); w->prog_cb=cb; w->prog_ud=ud; } }
void dsp_fl2k_set_finished_cb(DspFL2KHandle h, dsp_finished_cb_t cb, void* ud)
{ if (h) { auto* w=static_cast<DspWorkerFL2K*>(h); w->fin_cb =cb; w->fin_ud =ud; } }
void dsp_fl2k_set_error_cb   (DspFL2KHandle h, dsp_error_cb_t    cb, void* ud)
{ if (h) { auto* w=static_cast<DspWorkerFL2K*>(h); w->err_cb =cb; w->err_ud =ud; } }
void dsp_fl2k_set_nextfile_cb(DspFL2KHandle h, dsp_nextfile_cb_t cb, void* ud)
{ if (h) { auto* w=static_cast<DspWorkerFL2K*>(h); w->nxt_cb =cb; w->nxt_ud =ud; } }

int dsp_fl2k_start(DspFL2KHandle h)
{
    if (!h) return -1;
    auto* w = static_cast<DspWorkerFL2K*>(h);
    if (w->running.load()) return -1;
    if (w->filenames.empty()) return -2;

    {
        std::lock_guard<std::mutex> lk(w->ring_mtx);
        w->ring_head = w->ring_tail = w->ring_count = 0;
    }
    w->dev_open.store(false);
    w->running.store(true, std::memory_order_release);

    w->fl2k_thr = std::thread(&DspWorkerFL2K::run_fl2k, w);

    for (int ms = 0; ms < 1000; ms += 20) {
        if (w->dev_open.load() || !w->running.load()) break;
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }
    if (!w->running.load()) {
        if (w->fl2k_thr.joinable()) w->fl2k_thr.join();
        return -3;
    }

    w->dsp_thr = std::thread(&DspWorkerFL2K::run_dsp, w);
    return 0;
}

void dsp_fl2k_stop(DspFL2KHandle h)
{
    if (!h) return;
    auto* w = static_cast<DspWorkerFL2K*>(h);
    w->running.store(false, std::memory_order_release);
    w->ring_not_full.notify_all();
    w->ring_not_empty.notify_all();
    if (w->dsp_thr.joinable())  w->dsp_thr.join();
    if (w->fl2k_thr.joinable()) w->fl2k_thr.join();
}

void dsp_fl2k_set_pause(DspFL2KHandle h, int p)
{ if (h) static_cast<DspWorkerFL2K*>(h)->paused.store(p != 0); }

void dsp_fl2k_set_gain(DspFL2KHandle h, float gain)
{ if (h) static_cast<DspWorkerFL2K*>(h)->gainValue.store(gain); }

int dsp_fl2k_is_running(DspFL2KHandle h)
{ return h ? (static_cast<DspWorkerFL2K*>(h)->running.load() ? 1 : 0) : 0; }

int dsp_fl2k_check_device()
{
    if (fl2k_get_device_count() == 0) return -1;
    fl2k_dev_t* dev = nullptr;
    int r = fl2k_open(&dev, 0);
    if (r != FL2K_SUCCESS) return -1;
    fl2k_close(dev);
    return 0;
}

void dsp_fl2k_seek(DspFL2KHandle h, int64_t byte_pos, int whence)
{
    if (!h) return;
    auto* w = static_cast<DspWorkerFL2K*>(h);
    std::lock_guard<std::mutex> lk(w->seek_mtx);
    w->seek_req.pending = true;
    w->seek_req.pos     = byte_pos;
    w->seek_req.whence  = whence;
}
