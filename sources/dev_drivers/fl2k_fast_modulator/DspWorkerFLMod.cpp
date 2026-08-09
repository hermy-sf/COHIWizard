/*
 * DspWorkerFLMod.cpp  –  fl2k_fast_modulator variant
 *
 * liquidDSP-free pure AM synthesizer.  Drop-in replacement for
 * fl2k_modulator with identical C API.
 *
 * Algorithm changes vs. fl2k_modulator:
 *
 *  1. Audio resampling (audio_rate → baseband_rate):
 *       Zero-order hold (ZOH): each audio sample is repeated
 *       round(baseband_rate / audio_rate) times.  Replaces msresamp_rrrf.
 *
 *  2. Baseband upsampling (baseband_rate → target_rate):
 *       Cosine-interpolation between adjacent baseband samples +
 *       7-tap symmetric integer FIR {4,16,26,36,26,16,4} (sum=128, >>7).
 *       mu2_lut[k] precomputed once per run — no cosf() in hot path.
 *       Replaces msresamp_crcf.
 *
 *  3. All oscillators:
 *       32-bit phase accumulator + 12-bit sin/cos LUT (4096 int16_t entries).
 *       Replaces nco_crcf.
 *
 *  Gain scaling:
 *       current_gain_fast = gainValue × GAIN_SCALE / 32767
 *       GAIN_SCALE = 256 × 127 = 32512  (same reference as fl2k_modulator)
 *       → identical gainValue semantics as fl2k_modulator.
 *
 *  Build:
 *    g++ -std=c++17 -O3 -march=native -ffast-math -fPIC -shared \
 *        DspWorkerFLMod.cpp -o libdspflmod.so -losmo-fl2k -lpthread -lm
 */

#include "DspWorkerFLMod.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
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
static constexpr int LUT_SIZE = 1 << LUT_BITS;
static int16_t g_lut_sin[LUT_SIZE];
static int16_t g_lut_cos[LUT_SIZE];
static bool    g_lut_ready = false;

static void init_lut()
{
    if (g_lut_ready) return;
    for (int i = 0; i < LUT_SIZE; ++i) {
        double a     = 2.0 * M_PI * i / LUT_SIZE;
        g_lut_sin[i] = (int16_t)std::round(std::sin(a) * 32767.0);
        g_lut_cos[i] = (int16_t)std::round(std::cos(a) * 32767.0);
    }
    g_lut_ready = true;
}

static inline int16_t lut_sin(uint32_t phase) { return g_lut_sin[phase >> (32 - LUT_BITS)]; }
static inline int16_t lut_cos(uint32_t phase) { return g_lut_cos[phase >> (32 - LUT_BITS)]; }

static inline uint32_t freq_to_pinc(double freq_hz, double sample_rate)
{
    return (uint32_t)(freq_hz / sample_rate * 4294967296.0);
}

/* ================================================================== */
/* IQf – float complex pair                                            */
/* ================================================================== */
struct IQf { float re, im; };

/* ================================================================== */
/* Constants                                                           */
/* ================================================================== */
static constexpr size_t RING_BUFS  = 16;
static constexpr size_t RING_SIZE  = (size_t)FL2K_BUF_LEN * RING_BUFS;
static constexpr size_t DSP_BLOCK  = 8192;
static constexpr size_t MON_SIZE   = 8192;
static constexpr float  SCALE_MON  = 1048576.0f;

/* ================================================================== */
/* AudioFifo                                                           */
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
        if (first < got)
            std::copy(buf.data(), buf.data() + (got - first), dst + first);
        head = (head + got) % cap;
        cnt -= got;
        if (got < n) std::fill(dst + got, dst + n, 0.f);
        return got;
    }

    size_t available() const { return cnt; }
    void   clear()           { head = cnt = 0; }
};

/* ================================================================== */
/* Internal worker struct                                              */
/* ================================================================== */
struct DspWorkerFLMod {

    /* synthesis config */
    float              targetRate   = 10'000'000.f;
    float              centerFreq   = 0.f;
    float              basebandRate = 1'250'000.f;
    std::atomic<float> gainValue    {0.65f};
    bool               useAGC       = true;

    /* callbacks */
    flmod_monitor_cb_t  mon_cb  = nullptr; void* mon_ud  = nullptr;
    flmod_finished_cb_t fin_cb  = nullptr; void* fin_ud  = nullptr;
    flmod_error_cb_t    err_cb  = nullptr; void* err_ud  = nullptr;

    /* ring buffer */
    std::vector<int8_t>     ring       = std::vector<int8_t>(RING_SIZE, 0);
    size_t                  ring_head  = 0, ring_tail = 0, ring_count = 0;
    std::mutex              ring_mtx;
    std::condition_variable ring_not_empty, ring_not_full;
    std::vector<int8_t>     fl2k_buf   = std::vector<int8_t>(FL2K_BUF_LEN, 0);

    /* control */
    std::atomic<bool>   running {false};
    std::atomic<bool>   paused  {false};

    /* device */
    fl2k_dev_t*         dev     = nullptr;
    std::mutex          dev_mtx;
    std::atomic<bool>   dev_open{false};

    /* threads */
    std::thread dsp_thr, fl2k_thr;

    /* =================================================================
     * Audio channels
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

        /* ZOH audio tracking */
        float    current_aud   = 0.f;   /* held sample                        */
        double   aud_phase     = 0.0;   /* fractional position [0,1)           */
        double   aud_phase_inc = 0.0;   /* audio_rate / basebandRate           */

        /* LUT NCO for AM carrier at basebandRate */
        uint32_t nco_phase     = 0;
        uint32_t nco_phase_inc = 0;

        std::vector<uint8_t> udp_recv_buf;
        AudioFifo raw_fifo{1'048'576};  /* ~42 s @ 25 kHz */
    };

    std::vector<AudioChanCfg> audio_cfgs;
    std::vector<AudioChanRT>  audio_rt;
    float                     audio_rate    = 25000.f;
    float                     audio_mix_lvl = 1.0f;

    /* helpers */
    void write_ring(const int8_t* data, size_t n);
    void drain_ring(int8_t* buf, size_t n);
    void run_dsp();
    void run_fl2k();
    void run_modulator();
    void close_audio_sockets();
    void setup_channels();
    void teardown_channels();
    void mix_audio_block_fast(IQf* x, size_t n_bb);

    static void fl2k_callback(fl2k_data_info_t* info);
};

/* ================================================================== */
/* Ring buffer                                                         */
/* ================================================================== */

void DspWorkerFLMod::write_ring(const int8_t* data, size_t n)
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
        if (first < chunk)
            memcpy(ring.data(), data + written + first, chunk - first);
        ring_head   = (ring_head + chunk) % RING_SIZE;
        ring_count += chunk;
        written    += chunk;
        ring_not_empty.notify_one();
    }
}

void DspWorkerFLMod::drain_ring(int8_t* buf, size_t n)
{
    static uint64_t cb_cnt       = 0;
    static uint64_t underrun_cnt = 0;
    ++cb_cnt;

    std::lock_guard<std::mutex> lk(ring_mtx);
    if (ring_count < n) {
        ++underrun_cnt;
        size_t have = ring_count;
        fprintf(stderr,
                "[fl2k_fast_mod] RING UNDERRUN #%llu (cb=%llu): ring=%zu < need=%zu\n",
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

void DspWorkerFLMod::fl2k_callback(fl2k_data_info_t* info)
{
    auto* self = static_cast<DspWorkerFLMod*>(info->ctx);
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

void DspWorkerFLMod::run_fl2k()
{
    {
        std::lock_guard<std::mutex> lk(dev_mtx);
        int r = fl2k_open(&dev, 0);
        if (r != FL2K_SUCCESS) {
            char msg[128];
            snprintf(msg, sizeof(msg),
                     "fl2k_open failed (code %d). Check USB connection.", r);
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

    {
        std::unique_lock<std::mutex> lk(ring_mtx);
        ring_not_empty.wait_for(lk, std::chrono::seconds(5), [this] {
            return ring_count >= 4 * FL2K_BUF_LEN || !running.load();
        });
        fprintf(stderr, "[fl2k_fast_mod] ring pre-fill: %zu bytes ready\n", ring_count);
    }

    fl2k_start_tx(dev, fl2k_callback, this, 0);

    while (running.load(std::memory_order_acquire))
        std::this_thread::sleep_for(std::chrono::milliseconds(10));

    fl2k_stop_tx(dev);
    fl2k_close(dev);
    { std::lock_guard<std::mutex> lk(dev_mtx); dev = nullptr; dev_open.store(false); }
}

/* ================================================================== */
/* Audio channel helpers                                               */
/* ================================================================== */

void DspWorkerFLMod::close_audio_sockets()
{
    for (auto& rt : audio_rt) {
        if (rt.udp_fd >= 0) { _sock_close(rt.udp_fd); rt.udp_fd = -1; }
    }
    audio_rt.clear();
}

/*
 * setup_channels – compute ZOH phase increments and LUT NCO phase increments.
 * Called once before run_modulator().
 */
void DspWorkerFLMod::setup_channels()
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

        /* ZOH: audio_rate → basebandRate */
        rt.aud_phase     = 0.0;
        rt.aud_phase_inc = (double)audio_rate / basebandRate;
        rt.current_aud   = 0.f;

        /* LUT NCO: carrier at delta_f within basebandRate */
        double delta_f   = (double)cfg.freq_hz - centerFreq;
        rt.nco_phase     = 0;
        rt.nco_phase_inc = freq_to_pinc(delta_f, basebandRate);

        rt.udp_recv_buf.assign(16384, 0);
        rt.raw_fifo.clear();

        float nyq = basebandRate * 0.5f;
        if (std::fabs(delta_f) > nyq)
            fprintf(stderr,
                    "[fl2k_fast_mod] WARNING ch[%zu] '%s': delta_f=%.0f Hz "
                    "outside baseband Nyquist ±%.0f Hz – will alias.\n",
                    i, cfg.name, delta_f, nyq);

        fprintf(stderr,
                "[fl2k_fast_mod] ch[%zu] '%s': carrier=%.1f Hz  delta_f=%.1f Hz  "
                "port=%d  gain=%.4f  aud_phase_inc=%.6f\n",
                i, cfg.name, cfg.freq_hz, delta_f, cfg.udp_port, ba, rt.aud_phase_inc);
    }
}

void DspWorkerFLMod::teardown_channels()
{
    for (auto& rt : audio_rt) rt.active = false;
}

/*
 * mix_audio_block_fast – ZOH + LUT NCO AM synthesis at basebandRate.
 *
 * x[] must be zeroed by the caller before each call.
 * For each active channel:
 *   1. Drain UDP socket into raw_fifo (non-blocking recv).
 *   2. Advance ZOH position by aud_phase_inc per baseband sample;
 *      pop one new audio sample from raw_fifo when phase ≥ 1.
 *   3. DSB-LC AM with integer LUT NCO:
 *        x[k] += gain * (1 + mod_idx * audio) * exp(j * nco_phase)
 */
void DspWorkerFLMod::mix_audio_block_fast(IQf* x, size_t n_bb)
{
    static uint64_t call_cnt = 0;
    ++call_cnt;

    for (size_t chi = 0; chi < audio_rt.size(); ++chi) {
        AudioChanRT& rt = audio_rt[chi];
        if (!rt.active) continue;

        /* 1. Drain UDP into raw_fifo */
        if (rt.raw_fifo.available() < rt.raw_fifo.cap) {
            ssize_t nr;
            while ((nr = recv(rt.udp_fd, rt.udp_recv_buf.data(),
                              rt.udp_recv_buf.size(), MSG_DONTWAIT)) > 0)
            {
                for (ssize_t k = 0; k < nr; ++k) {
                    float s = (static_cast<float>(rt.udp_recv_buf[k]) - 128.f) / 128.f;
                    rt.raw_fifo.push(&s, 1);
                }
                if (rt.raw_fifo.available() >= rt.raw_fifo.cap) break;
            }
        }

        /* 2+3. ZOH + LUT NCO + AM accumulate */
        const float inv32767 = 1.f / 32767.f;
        for (size_t k = 0; k < n_bb; ++k) {

            /* ZOH: pop next audio sample when phase crosses 1 */
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
        fprintf(stderr, "[fl2k_fast_mod] diag call=%llu  channels:",
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
/* 7-tap integer FIR (identical to fl2k_fast_plus)                    */
/* ================================================================== */

static constexpr int32_t FIR_COEFFS[7] = { 4, 16, 26, 36, 26, 16, 4 };

static inline int32_t fir_step(int32_t* hist, int32_t new_val)
{
    hist[0]=hist[1]; hist[1]=hist[2]; hist[2]=hist[3];
    hist[3]=hist[4]; hist[4]=hist[5]; hist[5]=hist[6];
    hist[6] = new_val;
    return (hist[0]*FIR_COEFFS[0] + hist[1]*FIR_COEFFS[1] +
            hist[2]*FIR_COEFFS[2] + hist[3]*FIR_COEFFS[3] +
            hist[4]*FIR_COEFFS[4] + hist[5]*FIR_COEFFS[5] +
            hist[6]*FIR_COEFFS[6]) >> 7;
}

/* ================================================================== */
/* Modulator DSP loop                                                  */
/* ================================================================== */

/*
 * run_modulator – core synthesis loop.
 *
 * Per block:
 *   1. Zero x[] (the complex baseband).
 *   2. mix_audio_block_fast: fill x[] by summing N AM-modulated channels.
 *   3. AGC peak tracking on x[].
 *   4. Upsample x[] from basebandRate → targetRate via cosine-interp + FIR.
 *   5. LUT NCO upconversion (complex → real), clip → int8 → ring buffer.
 *
 * The gain chain is identical to fl2k_modulator:
 *   current_gain_fast = gainValue × GAIN_SCALE / 32767
 * where GAIN_SCALE = 256×127 = 32512.  Since mixed ≈ x.re × 32767,
 * the output hf = mixed × current_gain_fast ≈ x.re × gainValue × 32512,
 * which equals fl2k_modulator's  hf = x.re × gainValue × GAIN_SCALE.
 */
void DspWorkerFLMod::run_modulator()
{
    /* Precompute cosine-interpolation LUT for upsampling
     * mu2_lut[k] = (1 - cos(k/N * π)) / 2  for k=0..N-1
     * N = round(targetRate / basebandRate)                           */
    double upRatio  = (double)targetRate / basebandRate;
    int    n_interp = (int)std::round(upRatio);
    if (n_interp < 1) n_interp = 1;

    std::vector<float> mu2_lut(n_interp);
    for (int k = 0; k < n_interp; ++k) {
        double mu   = (double)k / upRatio;
        mu2_lut[k]  = (float)((1.0 - std::cos(mu * M_PI)) / 2.0);
    }

    /* Main LUT NCO: upconvert baseband to centerFreq at targetRate */
    uint32_t vco_phase     = 0;
    uint32_t vco_phase_inc = freq_to_pinc(centerFreq, targetRate);

    /* Per-channel setup */
    setup_channels();

    /* Gain / AGC state
     * GAIN_SCALE is −8 dB vs. fl2k_modulator to suppress cross-modulation. */
    const float bitScale    = 127.0f;
    const float GAIN_SCALE  = 256.0f * bitScale / 2.5f;   /* ≈12800, −8 dB */
    float current_gain_fast = gainValue.load() * GAIN_SCALE / 32767.f;
    float peak_hold         = 0.1f;

    /* IQ interpolation state */
    int32_t lastI = 0, lastQ = 0, nextI = 0, nextQ = 0;
    int32_t i_hist[7] = {}, q_hist[7] = {};

    /* Buffers */
    std::vector<IQf>   x(DSP_BLOCK);
    std::vector<int8_t>  out8(DSP_BLOCK * (n_interp + 1));
    std::vector<float>   mon(MON_SIZE);

    size_t monIdx       = 0;
    size_t blockCnt     = 0;
    size_t blocksPerSec = (size_t)((double)basebandRate / DSP_BLOCK) + 1;

    fprintf(stderr,
            "[fl2k_fast_mod] started: bb=%.0f Hz  target=%.0f Hz  "
            "n_interp=%d  channels=%zu\n",
            (double)basebandRate, (double)targetRate, n_interp, audio_rt.size());

    while (running.load(std::memory_order_acquire)) {

        /* Pause: feed silence */
        while (paused.load(std::memory_order_acquire)
               && running.load(std::memory_order_acquire))
        {
            static const int8_t zeros[4096] = {};
            write_ring(zeros, sizeof(zeros));
        }
        if (!running.load(std::memory_order_acquire)) break;

        /* Zero baseband block */
        std::fill(x.begin(), x.end(), IQf{0.f, 0.f});

        /* Synthesise: mix all AM channels into x[] */
        if (!audio_rt.empty())
            mix_audio_block_fast(x.data(), DSP_BLOCK);

        /* AGC: slow peak-hold on baseband magnitude */
        float bpeak = 0.0001f;
        for (size_t i = 0; i < DSP_BLOCK; ++i) {
            float m = sqrtf(x[i].re*x[i].re + x[i].im*x[i].im);
            if (m > bpeak) bpeak = m;
        }
        peak_hold = 0.95f * peak_hold + 0.05f * bpeak;

        if (useAGC) {
            /* tg: target gain so that peak output ≈ bitScale × 0.65
             * peak_hold × 32767 × tg = bitScale × 0.65               */
            float tg = (bitScale * 0.65f) / ((peak_hold + 0.0001f) * 32767.f);
            current_gain_fast = 0.98f * current_gain_fast + 0.02f * tg;
        } else {
            current_gain_fast = gainValue.load() * GAIN_SCALE / 32767.f;
        }

        /* Upsample basebandRate → targetRate + LUT NCO + int8 output
         *
         * For each baseband sample x[bi]:
         *   a) convert float → int32 ±32767
         *   b) cosine-interpolate n_interp output samples to next sample
         *   c) 7-tap integer FIR
         *   d) LUT NCO mix (upconvert to centerFreq) → real
         *   e) gain + clip → int8                                      */
        size_t out_pos = 0;
        const float inv32767 = 1.f / 32767.f;

        for (size_t bi = 0; bi < DSP_BLOCK; ++bi) {
            lastI = nextI;
            lastQ = nextQ;
            nextI = (int32_t)(x[bi].re * 32767.f);
            nextQ = (int32_t)(x[bi].im * 32767.f);

            for (int k = 0; k < n_interp; ++k) {
                float mu2  = mu2_lut[k];

                int32_t currI = (int32_t)((float)lastI + mu2 * (float)(nextI - lastI));
                int32_t currQ = (int32_t)((float)lastQ + mu2 * (float)(nextQ - lastQ));

                int32_t fI = fir_step(i_hist, currI);
                int32_t fQ = fir_step(q_hist, currQ);

                int16_t c = lut_cos(vco_phase);
                int16_t s = lut_sin(vco_phase);
                vco_phase += vco_phase_inc;

                /* Real part of (fI+j*fQ) × exp(j*phi): fI*cos - fQ*sin
                 * Product fits in int32: |fI*c| ≤ 32767² < 2^31       */
                int32_t mixed = ((int32_t)fI * c - (int32_t)fQ * s) >> 15;

                float hf = (float)mixed * current_gain_fast;
                if      (hf >  127.f) hf =  127.f;
                else if (hf < -128.f) hf = -128.f;
                out8[out_pos++] = (int8_t)hf;
            }
        }

        write_ring(out8.data(), out_pos);

        /* Monitoring: baseband I, pre-upsampling */
        size_t n_mon = std::min(MON_SIZE - monIdx, DSP_BLOCK);
        for (size_t k = 0; k < n_mon; ++k)
            mon[monIdx++] = x[k].re * SCALE_MON;

        ++blockCnt;
        if (blockCnt >= blocksPerSec) {
            blockCnt = 0;
            if (mon_cb && monIdx > 0)
                mon_cb(mon.data(), static_cast<int>(monIdx), mon_ud);
            monIdx = 0;
        }
    }

    teardown_channels();
}

/* ================================================================== */
/* DSP thread entry                                                    */
/* ================================================================== */

void DspWorkerFLMod::run_dsp()
{
    run_modulator();

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

DspFLModHandle dsp_flmod_create()
{
#ifdef _WIN32
    WSADATA wsa; WSAStartup(MAKEWORD(2,2), &wsa);
#endif
    init_lut();
    fprintf(stderr, "[fl2k_fast_mod] *** libdspflmod BUILD %s %s (fast-no-liquid) ***\n",
            __DATE__, __TIME__);
    return new DspWorkerFLMod();
}

void dsp_flmod_destroy(DspFLModHandle h)
{
    if (!h) return;
    dsp_flmod_stop(h);
    static_cast<DspWorkerFLMod*>(h)->close_audio_sockets();
    delete static_cast<DspWorkerFLMod*>(h);
#ifdef _WIN32
    WSACleanup();
#endif
}

int dsp_flmod_configure(DspFLModHandle h,
                        float target_rate, float center_freq,
                        float baseband_rate, float gain, int use_agc)
{
    if (!h) return -1;
    auto* w = static_cast<DspWorkerFLMod*>(h);
    w->targetRate   = target_rate;
    w->centerFreq   = center_freq;
    w->basebandRate = (baseband_rate > 0.f) ? baseband_rate : 1'250'000.f;
    w->gainValue.store(gain);
    w->useAGC       = (use_agc != 0);
    return 0;
}

int dsp_flmod_configure_channels(DspFLModHandle        h,
                                  const DspFLModChannel* channels,
                                  int                    n_channels,
                                  float                  audio_rate,
                                  float                  mix_level)
{
    if (!h) return -1;
    auto* w = static_cast<DspWorkerFLMod*>(h);

    w->close_audio_sockets();
    w->audio_cfgs.clear();
    w->audio_rate    = (audio_rate > 0.f) ? audio_rate : 25000.f;
    w->audio_mix_lvl = (mix_level  > 0.f) ? mix_level  : 1.0f;

    if (!channels || n_channels <= 0) return 0;

    w->audio_cfgs.resize(n_channels);
    w->audio_rt.resize(n_channels);

    for (int i = 0; i < n_channels; ++i) {
        DspWorkerFLMod::AudioChanCfg& cfg = w->audio_cfgs[i];
        DspWorkerFLMod::AudioChanRT&  rt  = w->audio_rt[i];

        cfg.freq_hz  = channels[i].freq_hz;
        cfg.bw_hz    = (channels[i].bandwidth_hz > 0.f)
                       ? channels[i].bandwidth_hz : 4500.f;
        cfg.mod_idx  = (channels[i].mod_index > 0.f && channels[i].mod_index <= 1.f)
                       ? channels[i].mod_index : 0.9f;
        strncpy(cfg.name, channels[i].name, 63);
        cfg.name[63] = '\0';
        cfg.udp_port = channels[i].udp_port;

        rt.active = false; rt.mod_idx = 0.9f; rt.gain = 0.f;
        rt.current_aud = 0.f; rt.aud_phase = 0.0; rt.aud_phase_inc = 0.0;
        rt.nco_phase = 0; rt.nco_phase_inc = 0;
        rt.udp_recv_buf.clear();
        rt.raw_fifo.clear();
        rt.udp_fd = -1;

        int fd = ::socket(AF_INET, SOCK_DGRAM, 0);
        if (fd < 0) {
            fprintf(stderr, "[fl2k_fast_mod] socket() failed ch[%d] '%s': %s\n",
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
            fprintf(stderr, "[fl2k_fast_mod] bind() failed ch[%d] '%s' port %d: %s\n",
                    i, cfg.name, cfg.udp_port, strerror(errno));
            _sock_close(fd);
            continue;
        }
        _sock_set_nonblocking(fd);
        rt.udp_fd = fd;
        fprintf(stderr, "[fl2k_fast_mod] ch[%d] '%s': UDP port %d bound, carrier %.1f Hz\n",
                i, cfg.name, cfg.udp_port, cfg.freq_hz);
    }
    return 0;
}

void dsp_flmod_prefill(DspFLModHandle h, int duration_ms)
{
    if (!h || duration_ms <= 0) return;
    auto* w = static_cast<DspWorkerFLMod*>(h);

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

    float ar = (w->audio_rate > 0.f) ? w->audio_rate : 25000.f;
    for (size_t i = 0; i < w->audio_rt.size(); ++i) {
        auto& rt = w->audio_rt[i];
        if (rt.udp_fd < 0) continue;
        fprintf(stderr, "[fl2k_fast_mod] prefill ch[%zu]: raw_fifo=%zu (%.1f s)\n",
                i, rt.raw_fifo.available(), (float)rt.raw_fifo.available() / ar);
    }
}

void dsp_flmod_set_monitor_cb(DspFLModHandle h, flmod_monitor_cb_t cb, void* ud)
{ if (h) { auto* w=static_cast<DspWorkerFLMod*>(h); w->mon_cb=cb; w->mon_ud=ud; } }

void dsp_flmod_set_finished_cb(DspFLModHandle h, flmod_finished_cb_t cb, void* ud)
{ if (h) { auto* w=static_cast<DspWorkerFLMod*>(h); w->fin_cb=cb; w->fin_ud=ud; } }

void dsp_flmod_set_error_cb(DspFLModHandle h, flmod_error_cb_t cb, void* ud)
{ if (h) { auto* w=static_cast<DspWorkerFLMod*>(h); w->err_cb=cb; w->err_ud=ud; } }

int dsp_flmod_start(DspFLModHandle h)
{
    if (!h) return -1;
    auto* w = static_cast<DspWorkerFLMod*>(h);
    if (w->running.load()) return -1;
    {
        std::lock_guard<std::mutex> lk(w->ring_mtx);
        w->ring_head = w->ring_tail = w->ring_count = 0;
    }
    w->dev_open.store(false);
    w->running.store(true, std::memory_order_release);
    w->fl2k_thr = std::thread(&DspWorkerFLMod::run_fl2k, w);

    for (int ms = 0; ms < 1000; ms += 20) {
        if (w->dev_open.load() || !w->running.load()) break;
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }
    if (!w->running.load()) {
        if (w->fl2k_thr.joinable()) w->fl2k_thr.join();
        return -3;
    }
    w->dsp_thr = std::thread(&DspWorkerFLMod::run_dsp, w);
    return 0;
}

void dsp_flmod_stop(DspFLModHandle h)
{
    if (!h) return;
    auto* w = static_cast<DspWorkerFLMod*>(h);
    w->running.store(false, std::memory_order_release);
    w->ring_not_full.notify_all();
    w->ring_not_empty.notify_all();
    if (w->dsp_thr.joinable())  w->dsp_thr.join();
    if (w->fl2k_thr.joinable()) w->fl2k_thr.join();
}

void dsp_flmod_set_gain(DspFLModHandle h, float gain)
{ if (h) static_cast<DspWorkerFLMod*>(h)->gainValue.store(gain); }

void dsp_flmod_set_pause(DspFLModHandle h, int paused)
{ if (h) static_cast<DspWorkerFLMod*>(h)->paused.store(paused != 0); }

int dsp_flmod_is_running(DspFLModHandle h)
{ return h ? (static_cast<DspWorkerFLMod*>(h)->running.load() ? 1 : 0) : 0; }

int dsp_flmod_check_device()
{
    if (fl2k_get_device_count() == 0) return -1;
    fl2k_dev_t* dev = nullptr;
    int r = fl2k_open(&dev, 0);
    if (r != FL2K_SUCCESS) return -1;
    fl2k_close(dev);
    return 0;
}
