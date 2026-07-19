/*
 * test_mix_asan.cpp  –  Standalone ASAN test for mix_audio_block
 *
 * Replicates the exact code path that causes the segfault:
 *   3 audio channels, sr=1250000, audio_rate=25000, rs_ratio=50
 *   ch[0]: raw_fifo empty (no UDP data)
 *   ch[1]: raw_fifo partially filled (~7800 samples)
 *   ch[2]: raw_fifo full (65536 samples = CAP, overflow path taken)
 *
 * Compile (with ASAN):
 *   g++ -std=c++17 -O1 -fsanitize=address -fno-omit-frame-pointer \
 *       -I/usr/local/include test_mix_asan.cpp -o test_mix_asan \
 *       -L/usr/local/lib -lliquid -lpthread -lm
 *
 * Run:
 *   ./test_mix_asan
 *
 * ASAN will print exact file+line of any heap overflow.
 */

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <vector>
#include <algorithm>
#include <cassert>
#include <thread>
#include <chrono>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <liquid/liquid.h>

/* ------------------------------------------------------------------ */
/* Exact copy of AudioFifo from DspWorkerFL2K.cpp                     */
/* ------------------------------------------------------------------ */
struct AudioFifo {
    static constexpr size_t CAP = 65536;
    std::vector<float> buf = std::vector<float>(CAP, 0.f);
    size_t head = 0, cnt = 0;

    void push(const float* src, size_t n) {
        if (n == 0) return;
        size_t space = CAP - cnt;
        if (n > space) n = space;
        if (n == 0) return;
        size_t tail  = (head + cnt) % CAP;
        size_t first = std::min(n, CAP - tail);
        std::copy(src, src + first, buf.data() + tail);
        if (first < n)
            std::copy(src + first, src + n, buf.data());
        cnt += n;
    }

    size_t pop(float* dst, size_t n) {
        size_t got   = std::min(n, cnt);
        size_t first = std::min(got, CAP - head);
        std::copy(buf.data() + head, buf.data() + head + first, dst);
        if (first < got)
            std::copy(buf.data(), buf.data() + (got - first), dst + first);
        head = (head + got) % CAP;
        cnt -= got;
        if (got < n) std::fill(dst + got, dst + n, 0.f);
        return got;
    }
    size_t available() const { return cnt; }
    void   clear()           { head = cnt = 0; }
};

/* ------------------------------------------------------------------ */
/* Exact copy of AudioChanRT from DspWorkerFL2K.cpp                   */
/* ------------------------------------------------------------------ */
struct AudioChanRT {
    float           carrier_hz  = 0.f;
    float           mod_idx     = 0.9f;
    float           gain        = 0.f;
    int             udp_fd      = -1;
    bool            active      = false;
    msresamp_rrrf   resamp      = nullptr;
    nco_crcf        nco         = nullptr;
    AudioFifo       raw_fifo;
    AudioFifo       rs_fifo;
    std::vector<float>   a_in_buf;
    std::vector<float>   a_rs_buf;
    std::vector<float>   rs_scratch;
    std::vector<uint8_t> udp_recv_buf;
};

/* ------------------------------------------------------------------ */
/* Parameters matching the real crash scenario                         */
/* ------------------------------------------------------------------ */
static constexpr size_t DSP_BLOCK   = 4096;
static constexpr size_t N_FEED      = 64;
static constexpr size_t UDP_BUF_SZ  = 16384;
static constexpr int    N_CHANNELS  = 3;
static constexpr float  AUDIO_RATE  = 25000.f;
static constexpr uint32_t SR        = 1250000;  /* WAV sample rate */
static constexpr int    BASE_PORT   = 19234;    /* use obscure ports for test */

/* carrier frequencies (Hz offset from centre) */
static const float CARRIERS[N_CHANNELS] = { 80000.f, 180000.f, 231000.f };

/* ------------------------------------------------------------------ */
/* Exact copy of setup_audio_for_file logic                           */
/* ------------------------------------------------------------------ */
static void setup_channels(std::vector<AudioChanRT>& audio_rt,
                            float shiftFreq, float audio_mix_lvl,
                            uint32_t sr)
{
    float ba = audio_mix_lvl / sqrtf((float)audio_rt.size());
    float rs_ratio = (float)sr / AUDIO_RATE;

    for (size_t i = 0; i < audio_rt.size(); ++i) {
        AudioChanRT& rt = audio_rt[i];
        rt.carrier_hz = CARRIERS[i];
        rt.mod_idx    = 0.8f;
        rt.gain       = ba;
        rt.active     = (rt.udp_fd >= 0);
        if (!rt.active) continue;

        float delta_f = CARRIERS[i] - shiftFreq;

        rt.resamp = msresamp_rrrf_create(rs_ratio, 60.f);
        rt.nco    = nco_crcf_create(LIQUID_VCO);
        nco_crcf_set_frequency(rt.nco,
                               2.f * (float)M_PI * delta_f / (float)sr);

        size_t rs_out_max = (size_t)(N_FEED * rs_ratio) + 64;
        size_t a_rs_sz    = std::max(rs_out_max, UDP_BUF_SZ);

        rt.a_in_buf.assign(N_FEED,      0.f);
        rt.a_rs_buf.assign(a_rs_sz,     0.f);
        rt.rs_scratch.assign(DSP_BLOCK + 64, 0.f);
        rt.udp_recv_buf.assign(UDP_BUF_SZ,   0);
        rt.raw_fifo.clear();
        rt.rs_fifo.clear();

        fprintf(stderr, "[test] ch[%zu]: rs_ratio=%.2f a_rs_sz=%zu"
                " rs_out_max=%zu udp_fd=%d\n",
                i, rs_ratio, a_rs_sz, rs_out_max, rt.udp_fd);
    }
}

/* ------------------------------------------------------------------ */
/* Exact copy of mix_audio_block logic (with full logging)            */
/* ------------------------------------------------------------------ */
static void mix_audio_block(std::vector<AudioChanRT>& audio_rt,
                             liquid_float_complex* x, size_t n_iq)
{
    for (size_t _chi = 0; _chi < audio_rt.size(); ++_chi) {
        AudioChanRT& rt = audio_rt[_chi];
        if (!rt.active) continue;
        if (!rt.resamp || !rt.nco) {
            fprintf(stderr, "[test] ERROR ch[%zu]: null resamp/nco\n", _chi);
            rt.active = false;
            continue;
        }

        fprintf(stderr, "[test] ch[%zu]: raw=%zu rs=%zu a_rs_sz=%zu\n",
                _chi, rt.raw_fifo.available(), rt.rs_fifo.available(),
                rt.a_rs_buf.size());

        /* Step 1 */
        fprintf(stderr, "[test] ch[%zu] STEP1 start\n", _chi);
        {
            ssize_t nr;
            while ((nr = recv(rt.udp_fd, rt.udp_recv_buf.data(),
                              rt.udp_recv_buf.size(), MSG_DONTWAIT)) > 0)
            {
                for (ssize_t k = 0; k < nr; ++k)
                    rt.a_rs_buf[k] = (static_cast<float>(rt.udp_recv_buf[k]) - 128.f)
                                     / 128.f;
                rt.raw_fifo.push(rt.a_rs_buf.data(), static_cast<size_t>(nr));
            }
        }
        fprintf(stderr, "[test] ch[%zu] STEP1 done, raw=%zu\n",
                _chi, rt.raw_fifo.available());

        /* Step 2 */
        fprintf(stderr, "[test] ch[%zu] STEP2 start\n", _chi);
        {
            unsigned int iters = 0;
            while (rt.rs_fifo.available() < 2 * n_iq
                   && rt.raw_fifo.available() >= N_FEED)
            {
                size_t n_feed = std::min(rt.raw_fifo.available(), N_FEED);
                rt.raw_fifo.pop(rt.a_in_buf.data(), n_feed);
                unsigned int n_out = 0;
                msresamp_rrrf_execute(rt.resamp,
                                      rt.a_in_buf.data(),
                                      (unsigned int)n_feed,
                                      rt.a_rs_buf.data(), &n_out);
                if (iters == 0)
                    fprintf(stderr, "[test] ch[%zu] STEP2 iter0: n_feed=%zu"
                            " n_out=%u a_rs_sz=%zu\n",
                            _chi, n_feed, n_out, rt.a_rs_buf.size());
                if (n_out > rt.a_rs_buf.size()) {
                    fprintf(stderr, "[test] ch[%zu] OVERFLOW: n_out=%u > a_rs_sz=%zu!\n",
                            _chi, n_out, rt.a_rs_buf.size());
                    abort();
                }
                rt.rs_fifo.push(rt.a_rs_buf.data(), n_out);
                ++iters;
            }
        }
        fprintf(stderr, "[test] ch[%zu] STEP2 done, rs=%zu\n",
                _chi, rt.rs_fifo.available());

        /* Step 3 */
        fprintf(stderr, "[test] ch[%zu] STEP3 start, n_iq=%zu rs_scratch=%zu\n",
                _chi, n_iq, rt.rs_scratch.size());
        rt.rs_fifo.pop(rt.rs_scratch.data(), n_iq);
        fprintf(stderr, "[test] ch[%zu] STEP3 done\n", _chi);

        /* Step 4 */
        fprintf(stderr, "[test] ch[%zu] STEP4 start\n", _chi);
        const float* a = rt.rs_scratch.data();
        for (size_t k = 0; k < n_iq; ++k) {
            float c = nco_crcf_cos(rt.nco);
            float s = nco_crcf_sin(rt.nco);
            nco_crcf_step(rt.nco);
            float am = rt.gain * (1.f + rt.mod_idx * a[k]);
            x[k].real += am * c;
            x[k].imag += am * s;
        }
        fprintf(stderr, "[test] ch[%zu] DONE\n", _chi);
    }
    fprintf(stderr, "[test] mix_audio_block END\n");
}

/* ------------------------------------------------------------------ */
/* Open a UDP receive socket on the given port                         */
/* ------------------------------------------------------------------ */
static int open_udp_rx(int port)
{
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) { perror("socket"); return -1; }

    int rcvbuf = 524288;
    setsockopt(fd, SOL_SOCKET, SO_RCVBUF, &rcvbuf, sizeof(rcvbuf));

    sockaddr_in addr{};
    addr.sin_family      = AF_INET;
    addr.sin_port        = htons((uint16_t)port);
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);

    if (bind(fd, (sockaddr*)&addr, sizeof(addr)) < 0) {
        perror("bind"); close(fd); return -1;
    }

    /* Non-blocking */
    int fl = fcntl(fd, F_GETFL, 0);
    fcntl(fd, F_SETFL, fl | O_NONBLOCK);
    return fd;
}

/* ------------------------------------------------------------------ */
/* Send N_PKTS UDP packets of PKT_BYTES silence to localhost:port      */
/* ------------------------------------------------------------------ */
static void send_udp_mock(int port, size_t n_pkts, size_t pkt_bytes)
{
    int s = socket(AF_INET, SOCK_DGRAM, 0);
    if (s < 0) { perror("send socket"); return; }

    sockaddr_in dst{};
    dst.sin_family      = AF_INET;
    dst.sin_port        = htons((uint16_t)port);
    dst.sin_addr.s_addr = htonl(INADDR_LOOPBACK);

    std::vector<uint8_t> pkt(pkt_bytes, 128);  /* silence = 128 */
    for (size_t i = 0; i < n_pkts; ++i)
        sendto(s, pkt.data(), pkt_bytes, 0, (sockaddr*)&dst, sizeof(dst));
    close(s);
}

/* ------------------------------------------------------------------ */
/* main                                                                */
/* ------------------------------------------------------------------ */
int main()
{
    fprintf(stderr, "[test] ASAN test for mix_audio_block\n");
    fprintf(stderr, "[test] SR=%u audio_rate=%.0f rs_ratio=%.1f DSP_BLOCK=%zu\n",
            SR, AUDIO_RATE, (float)SR/AUDIO_RATE, DSP_BLOCK);

    /* Open receive sockets */
    std::vector<AudioChanRT> audio_rt(N_CHANNELS);
    for (int i = 0; i < N_CHANNELS; ++i) {
        audio_rt[i].udp_fd = open_udp_rx(BASE_PORT + i);
        if (audio_rt[i].udp_fd < 0) {
            fprintf(stderr, "[test] Failed to open socket for ch%d\n", i);
            return 1;
        }
    }

    /* Pre-fill UDP buffers to replicate the real crash scenario:
     *   ch[0]: 0 packets    → raw_fifo stays 0
     *   ch[1]: 31 packets   → raw_fifo ≈ 7936 (31 × 256)
     *   ch[2]: 300 packets  → raw_fifo = 65536 (overflows, stays at CAP)
     */
    fprintf(stderr, "[test] Sending mock UDP data...\n");
    send_udp_mock(BASE_PORT + 0,   0, 256);   /* ch[0]: no data */
    send_udp_mock(BASE_PORT + 1,  31, 256);   /* ch[1]: ~7936 bytes */
    send_udp_mock(BASE_PORT + 2, 300, 256);   /* ch[2]: 76800 bytes → fifo overflows */

    /* Give the OS time to deliver datagrams */
    std::this_thread::sleep_for(std::chrono::milliseconds(50));

    /* Setup channels (equivalent to setup_audio_for_file) */
    setup_channels(audio_rt, 0.f, 1.0f, SR);

    /* Allocate IQ buffer (same as in process_file) */
    std::vector<liquid_float_complex> x(DSP_BLOCK, {0.f, 0.f});

    /* Call mix_audio_block several times */
    for (int call = 1; call <= 5; ++call) {
        fprintf(stderr, "[test] ====== mix_audio_block call #%d ======\n", call);
        std::fill(x.begin(), x.end(), liquid_float_complex{0.f, 0.f});
        mix_audio_block(audio_rt, x.data(), DSP_BLOCK);
        fprintf(stderr, "[test] call #%d returned OK\n\n", call);
    }

    /* Cleanup */
    for (auto& rt : audio_rt) {
        if (rt.resamp) msresamp_rrrf_destroy(rt.resamp);
        if (rt.nco)    nco_crcf_destroy(rt.nco);
        if (rt.udp_fd >= 0) close(rt.udp_fd);
    }

    fprintf(stderr, "[test] ALL CALLS COMPLETED — no ASAN error detected\n");
    return 0;
}
