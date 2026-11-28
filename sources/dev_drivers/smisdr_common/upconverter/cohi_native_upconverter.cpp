////////////////////////////////////////////////////
// COHI-Player-Universal
// V1.2.4, 23.11.2026
// Author: Claus Peter Gallenmiller, cpg-radio@gmx.de
// Modified by radiolab81:
//   V1.1.0, 10.11.2026: smiSDR / parlioSDR output with 8 to 14 bit DAC formats
//   V1.1.1, 11.11.2026: UDP field strength control, sferics / lightning simulation (AMWaveSynth protocol)
//   V1.2.1, 16.11.2026: real-time pacing of the live output thread (fixes stuttering COHI-Stream audio
//                       and decoder restarts with smiSDR / parlioSDR, see README 5.5)
//   V1.2.4, 23.11.2026: real-time pacing also in the pure WAV mode (no live channels), same
//                       mechanism as the live output thread; lead 100 ms / reset threshold
//                       250 ms in both modes
////////////////////////////////////////////////////

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <thread>
#include <cmath>
#include <vector>
#include <string>
#include <chrono>

#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <pthread.h>
#include <atomic>
#endif

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#define LUT_BITS 12
#define LUT_SIZE (1 << LUT_BITS)

constexpr int FILTER_SHIFT = 7;

namespace {

struct LiveChannelArg {
    int udp_port = 0;
    double freq_hz = 0.0;
    double audio_rate_hz = 0.0;
};

struct Args {
    double sample_rate = 0.0;
    double center_freq = 0.0;
    double target_rate = 0.0;
    int output_shift = 6;
    int output_bits = 8;
    int fir_taps = 15;
    std::vector<LiveChannelArg> live_channels;
    int live_gain_shift = 2;
    double live_gain_trim = 1.0;
    int live_control_port = 0;
    int live_sferics_port = 0;
    int debug_udp_port = 0;
};

std::vector<int32_t> design_lowpass_filter(int num_taps, double cutoff_normalized) {
    if (num_taps < 1) num_taps = 1;
    if (num_taps % 2 == 0) num_taps += 1;

    std::vector<double> h(num_taps);
    int center = (num_taps - 1) / 2;
    double sum = 0.0;
    for (int n = 0; n < num_taps; ++n) {
        int k = n - center;
        double sinc_val = (k == 0)
            ? cutoff_normalized
            : std::sin(M_PI * cutoff_normalized * k) / (M_PI * k);
        double window = 0.54 - 0.46 * std::cos(2.0 * M_PI * n / (num_taps - 1));
        h[n] = sinc_val * window;
        sum += h[n];
    }

    double scale = std::ldexp(1.0, FILTER_SHIFT) / sum;
    std::vector<int32_t> coeffs(num_taps);
    for (int n = 0; n < num_taps; ++n) {
        coeffs[n] = static_cast<int32_t>(std::lround(h[n] * scale));
    }
    return coeffs;
}

class DebugUdpSender {
public:
    void init(int port) {
        if (port <= 0) return;
        sock_ = socket(AF_INET, SOCK_DGRAM, 0);
        if (sock_ < 0) return;
        std::memset(&addr_, 0, sizeof(addr_));
        addr_.sin_family = AF_INET;
        addr_.sin_port = htons(static_cast<uint16_t>(port));
        addr_.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        enabled_ = true;
        last_sent_at_ = std::chrono::steady_clock::now() - std::chrono::seconds(1);
    }

    bool enabled() const { return enabled_; }

    void maybe_send(const int8_t* data, size_t count) {
        if (!enabled_ || count == 0) return;
        auto now = std::chrono::steady_clock::now();
        double elapsed = std::chrono::duration<double>(now - last_sent_at_).count();
        if (elapsed < MIN_INTERVAL_S) return;
        last_sent_at_ = now;

        size_t n = count < MAX_SAMPLES ? count : MAX_SAMPLES;
        std::vector<uint8_t> packet(8 + n);
        packet[0] = 'C'; packet[1] = 'D'; packet[2] = 'B'; packet[3] = 'G';
        uint32_t n32 = static_cast<uint32_t>(n);
        std::memcpy(&packet[4], &n32, sizeof(n32));
        std::memcpy(&packet[8], data + (count - n), n);
        (void)sendto(sock_, packet.data(), packet.size(), 0,
                      reinterpret_cast<sockaddr*>(&addr_), sizeof(addr_));
    }

private:
    static constexpr double MIN_INTERVAL_S = 0.1;
    static constexpr size_t MAX_SAMPLES = 8192;
    int sock_ = -1;
    struct sockaddr_in addr_ {};
    bool enabled_ = false;
    std::chrono::steady_clock::time_point last_sent_at_{};
};

struct OutputStage {
    int shift_right = 0;
    int shift_left = 0;
    int32_t limit = 127;
    int bits = 8;

    void init(const Args& args) {
        bits = args.output_bits;
        limit = (1 << (bits - 1)) - 1;
        int net_shift = args.output_shift - (bits - 8);
        shift_right = net_shift > 0 ? net_shift : 0;
        shift_left = net_shift < 0 ? -net_shift : 0;
    }

    bool wide() const { return bits > 8; }

    inline int16_t quantize(int32_t mixed) const {
        int32_t v = (mixed << shift_left) >> shift_right;
        if (v > limit) v = limit;
        else if (v < -limit) v = -limit;
        return static_cast<int16_t>(v);
    }

    void emit(const int16_t* data, size_t n, DebugUdpSender& debug, std::vector<int8_t>& tmp) const {
        if (n == 0) return;
        if (!wide()) {
            if (tmp.size() < n) tmp.resize(n);
            for (size_t k = 0; k < n; ++k) tmp[k] = static_cast<int8_t>(data[k]);
            debug.maybe_send(tmp.data(), n);
            std::fwrite(tmp.data(), sizeof(int8_t), n, stdout);
        } else {
            if (debug.enabled()) {
                if (tmp.size() < n) tmp.resize(n);
                const int d = bits - 8;
                for (size_t k = 0; k < n; ++k) tmp[k] = static_cast<int8_t>(data[k] >> d);
                debug.maybe_send(tmp.data(), n);
            }
            std::fwrite(data, sizeof(int16_t), n, stdout);
        }
    }
};

bool parse_args(int argc, char** argv, Args& out) {
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        auto next_double = [&](double& target) {
            if (i + 1 >= argc) return false;
            target = std::atof(argv[++i]);
            return true;
        };
        if (arg == "--sample-rate") {
            if (!next_double(out.sample_rate)) return false;
        } else if (arg == "--center-freq") {
            if (!next_double(out.center_freq)) return false;
        } else if (arg == "--target-rate") {
            if (!next_double(out.target_rate)) return false;
        } else if (arg == "--output-shift") {
            if (i + 1 >= argc) return false;
            out.output_shift = std::atoi(argv[++i]);
        } else if (arg == "--output-bits") {
            if (i + 1 >= argc) return false;
            out.output_bits = std::atoi(argv[++i]);
            if (out.output_bits != 8 && out.output_bits != 10 &&
                out.output_bits != 12 && out.output_bits != 14) {
                std::fprintf(stderr, "cohi_native_upconverter: --output-bits muss 8, 10, 12 oder 14 sein\n");
                return false;
            }
        } else if (arg == "--fir-taps") {
            if (i + 1 >= argc) return false;
            out.fir_taps = std::atoi(argv[++i]);
        } else if (arg == "--live-channel") {
            if (i + 1 >= argc) return false;
            std::string spec = argv[++i];
            size_t p1 = spec.find(':');
            size_t p2 = (p1 == std::string::npos) ? std::string::npos : spec.find(':', p1 + 1);
            if (p1 == std::string::npos || p2 == std::string::npos) {
                std::fprintf(stderr, "cohi_native_upconverter: ungueltiges --live-channel-Format "
                             "(erwartet udp_port:freq_hz:audio_rate_hz): %s\n", spec.c_str());
                return false;
            }
            LiveChannelArg ch;
            ch.udp_port = std::atoi(spec.substr(0, p1).c_str());
            ch.freq_hz = std::atof(spec.substr(p1 + 1, p2 - p1 - 1).c_str());
            ch.audio_rate_hz = std::atof(spec.substr(p2 + 1).c_str());
            out.live_channels.push_back(ch);
        } else if (arg == "--live-gain-shift") {
            if (i + 1 >= argc) return false;
            out.live_gain_shift = std::atoi(argv[++i]);
        } else if (arg == "--live-gain-trim") {
            if (i + 1 >= argc) return false;
            out.live_gain_trim = std::atof(argv[++i]);
            if (!(out.live_gain_trim > 0.0 && out.live_gain_trim <= 1.0)) {
                std::fprintf(stderr, "cohi_native_upconverter: --live-gain-trim muss im Bereich "
                             "0 < F <= 1 liegen\n");
                return false;
            }
        } else if (arg == "--live-control-port") {
            if (i + 1 >= argc) return false;
            out.live_control_port = std::atoi(argv[++i]);
        } else if (arg == "--live-sferics-port") {
            if (i + 1 >= argc) return false;
            out.live_sferics_port = std::atoi(argv[++i]);
        } else if (arg == "--debug-udp-port") {
            if (i + 1 >= argc) return false;
            out.debug_udp_port = std::atoi(argv[++i]);
        } else {
            std::fprintf(stderr, "cohi_native_upconverter: unbekanntes Argument: %s\n", arg.c_str());
            return false;
        }
    }
    return out.sample_rate > 0.0 && out.target_rate > 0.0;
}

int16_t g_sine_lut[LUT_SIZE];
int16_t g_cos_lut[LUT_SIZE];

void init_luts() {
    for (int i = 0; i < LUT_SIZE; ++i) {
        double angle = 2.0 * M_PI * i / LUT_SIZE;
        g_sine_lut[i] = static_cast<int16_t>(std::lround(std::sin(angle) * 32767.0));
        g_cos_lut[i] = static_cast<int16_t>(std::lround(std::cos(angle) * 32767.0));
    }
}

#ifndef _WIN32

static constexpr float PEAK_HOLD_DECAY_PER_SAMPLE = 0.9999886622f;

struct LiveChannel {
    int udp_port = 0;
    int sock = -1;

    static constexpr uint32_t RING_SIZE = 1048576;
    std::vector<uint8_t> ring;
    std::atomic<uint32_t> head{0};
    std::atomic<uint32_t> tail{0};

    double samples_per_audio_sample = 1.0;
    double audio_phase = 0.0;

    uint64_t starved_count = 0;

    std::atomic<uint64_t> overflow_count{0};

    float gain = 1.0f;
    float peak_hold = 0.1f;

    double freq_hz = 0.0;
    std::atomic<float> external_gain{1.0f};
};

struct LiveCarrierState {
    std::vector<float> cos_val;
    std::vector<float> sin_val;
    std::vector<float> cos_delta;
    std::vector<float> sin_delta;
    std::vector<float> mod_register;

    void resize(size_t n) {
        cos_val.assign(n, 1.0f);
        sin_val.assign(n, 0.0f);
        cos_delta.assign(n, 1.0f);
        sin_delta.assign(n, 0.0f);
        mod_register.assign(n, 0);
    }

    void set_frequency(size_t i, double freq_hz, double target_rate) {
        double angle = 2.0 * M_PI * freq_hz / target_rate;
        cos_delta[i] = static_cast<float>(std::cos(angle));
        sin_delta[i] = static_cast<float>(std::sin(angle));
    }

    void renormalize() {
        for (size_t i = 0; i < cos_val.size(); ++i) {
            float mag_sq = cos_val[i] * cos_val[i] + sin_val[i] * sin_val[i];
            float correction = 1.5f - 0.5f * mag_sq;
            cos_val[i] *= correction;
            sin_val[i] *= correction;
        }
    }
};

// Steuerport im Protokoll des AMWaveSynth / AMWaveSynthPropagationSimulator:
// UDP-Datagramm als ASCII-Text "FREQ_HZ:GAIN" (z.B. "603000:0.35"). Der Kanal
// wird ueber die Traegerfrequenz gefunden (Toleranz < 1 Hz), GAIN skaliert
// Traeger und Modulation des Senders gemeinsam (1.0 = unveraendert, 0 = aus).
struct LiveControlArgs {
    std::vector<LiveChannel>* channels;
    int port;
    const char* tool_name;
};

void* live_control_receiver(void* arg) {
    LiveControlArgs* ca = static_cast<LiveControlArgs*>(arg);
    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0) {
        std::fprintf(stderr, "%s: Steuerport %d: Socket konnte nicht angelegt werden\n",
                     ca->tool_name, ca->port);
        return nullptr;
    }
    int reuse = 1;
    setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));
    struct sockaddr_in addr;
    std::memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(static_cast<uint16_t>(ca->port));
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    if (bind(sock, reinterpret_cast<struct sockaddr*>(&addr), sizeof(addr)) != 0) {
        std::fprintf(stderr, "%s: Steuerport UDP %d: bind() fehlgeschlagen - "
                     "Sendersteuerung (Feldstaerke) nicht verfuegbar\n", ca->tool_name, ca->port);
        close(sock);
        return nullptr;
    }
    std::fprintf(stderr, "%s: Steuerport UDP %d bereit (Format FREQ_HZ:GAIN)\n",
                 ca->tool_name, ca->port);

    char buf[256];
    bool first_message_logged = false;
    while (true) {
        ssize_t n = recv(sock, buf, sizeof(buf) - 1, 0);
        if (n <= 0) {
            usleep(1000);
            continue;
        }
        buf[n] = '\0';
        double freq = 0.0, gain = 0.0;
        if (std::sscanf(buf, "%lf:%lf", &freq, &gain) != 2) continue;
        if (!std::isfinite(gain)) continue;
        if (gain < 0.0) gain = 0.0;
        for (LiveChannel& ch : *ca->channels) {
            if (std::fabs(ch.freq_hz - freq) < 1.0) {
                ch.external_gain.store(static_cast<float>(gain), std::memory_order_relaxed);
                if (!first_message_logged) {
                    std::fprintf(stderr, "%s: erster Steuerbefehl: %.0f Hz -> Gain %.3f\n",
                                 ca->tool_name, ch.freq_hz, gain);
                    first_message_logged = true;
                }
                break;
            }
        }
    }
    return nullptr;
}

// Sferics / Blitzsimulation im Protokoll des AMWaveSynth: UDP-Datagramm
// "AMPLITUDE:DAUER_MS" (z.B. "800:12.5"). Ein Blitz ist ein Rauschburst mit
// exponentiell abklingender Huellkurve (Abfall auf 1 % nach DAUER_MS). Die
// Amplitude ist wie im Original relativ zum Traeger (AMPLITUDE/128 = Spitzenwert
// des Rauschens im Verhaeltnis zu einem Traeger mit Gain 1.0).
std::atomic<float> g_sferics_decay{0.0f};
std::atomic<float> g_sferics_amp{0.0f};   // wird zuletzt geschrieben = "Go"-Signal

struct SfericsArgs {
    int port;
    double rate;
    const char* tool_name;
};

void* sferics_receiver(void* arg) {
    SfericsArgs* sa = static_cast<SfericsArgs*>(arg);
    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0) {
        std::fprintf(stderr, "%s: Sferics-Port %d: Socket konnte nicht angelegt werden\n",
                     sa->tool_name, sa->port);
        return nullptr;
    }
    int reuse = 1;
    setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));
    struct sockaddr_in addr;
    std::memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(static_cast<uint16_t>(sa->port));
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    if (bind(sock, reinterpret_cast<struct sockaddr*>(&addr), sizeof(addr)) != 0) {
        std::fprintf(stderr, "%s: Sferics-Port UDP %d: bind() fehlgeschlagen - "
                     "Blitzsimulation nicht verfuegbar\n", sa->tool_name, sa->port);
        close(sock);
        return nullptr;
    }
    std::fprintf(stderr, "%s: Sferics-Port UDP %d bereit (Format AMPLITUDE:DAUER_MS)\n",
                 sa->tool_name, sa->port);

    char buf[256];
    while (true) {
        ssize_t n = recv(sock, buf, sizeof(buf) - 1, 0);
        if (n <= 0) {
            usleep(1000);
            continue;
        }
        buf[n] = '\0';
        double amp = 0.0, decay_ms = 0.0;
        if (std::sscanf(buf, "%lf:%lf", &amp, &decay_ms) != 2) continue;
        if (!std::isfinite(amp) || !std::isfinite(decay_ms) || amp <= 0.0 || decay_ms < 0.0) continue;
        double total_samples = (decay_ms / 1000.0) * sa->rate;
        float decay = static_cast<float>(std::exp(-4.60517 / (total_samples + 1.0)));
        g_sferics_decay.store(decay, std::memory_order_relaxed);
        g_sferics_amp.store(static_cast<float>(amp), std::memory_order_release);
    }
    return nullptr;
}

struct SfericsState {
    float env = 0.0f;
    float amp = 0.0f;
    float decay = 0.0f;
    uint32_t prng = 2463534242u;

    // einmal pro Batch aufrufen: neuen Blitz uebernehmen
    void poll() {
        float trig = g_sferics_amp.load(std::memory_order_acquire);
        if (trig > 0.0f) {
            decay = g_sferics_decay.load(std::memory_order_relaxed);
            amp = trig;
            env = 1.0f;
            g_sferics_amp.store(0.0f, std::memory_order_relaxed);
        }
    }
    // Rauschwert -1..1 (Xorshift32)
    float noise() {
        prng ^= prng << 13;
        prng ^= prng >> 17;
        prng ^= prng << 5;
        return (static_cast<float>(prng & 0xFFFF) - 32768.0f) * (1.0f / 32768.0f);
    }
    void step_env() {
        env *= decay;
        if (env < 3e-4f) env = 0.0f;
    }
};

void* live_channel_receiver(void* arg) {
    LiveChannel* ch = static_cast<LiveChannel*>(arg);
    uint8_t buf[4096];
    while (true) {
        ssize_t n = recv(ch->sock, buf, sizeof(buf), 0);
        if (n > 0) {
            uint32_t head = ch->head.load(std::memory_order_relaxed);
            uint32_t tail = ch->tail.load(std::memory_order_acquire);
            uint32_t used = head - tail;
            uint32_t free_space = LiveChannel::RING_SIZE - used;
            size_t to_write = std::min(static_cast<size_t>(n), static_cast<size_t>(free_space));

            if (to_write < static_cast<size_t>(n)) {
                ch->overflow_count.fetch_add(static_cast<uint64_t>(n) - to_write,
                                              std::memory_order_relaxed);
            }

            if (to_write > 0) {
                uint32_t start_idx = head & (LiveChannel::RING_SIZE - 1);
                size_t first_part = std::min(to_write,
                                              static_cast<size_t>(LiveChannel::RING_SIZE - start_idx));
                std::memcpy(&ch->ring[start_idx], buf, first_part);
                if (first_part < to_write) {
                    std::memcpy(&ch->ring[0], buf + first_part, to_write - first_part);
                }
                ch->head.store(head + static_cast<uint32_t>(to_write), std::memory_order_release);
            }
        } else {
            usleep(1000);
        }
    }
    return nullptr;
}

struct LiveSetupResult {
    std::vector<LiveChannel> channels;
    LiveCarrierState carrier;
};

LiveSetupResult setup_live_channels(const std::vector<LiveChannelArg>& specs,
                                     double target_rate) {
    struct Prepared {
        LiveChannelArg spec;
        int sock;
    };
    std::vector<Prepared> prepared;
    for (const auto& spec : specs) {
        int sock = socket(AF_INET, SOCK_DGRAM, 0);
        if (sock < 0) {
            std::fprintf(stderr, "cohi_native_upconverter: Live-Kanal Port %d: "
                         "Socket konnte nicht angelegt werden\n", spec.udp_port);
            continue;
        }
        struct sockaddr_in addr;
        std::memset(&addr, 0, sizeof(addr));
        addr.sin_family = AF_INET;
        addr.sin_port = htons(static_cast<uint16_t>(spec.udp_port));
        addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        if (bind(sock, reinterpret_cast<struct sockaddr*>(&addr), sizeof(addr)) != 0) {
            std::fprintf(stderr, "cohi_native_upconverter: Live-Kanal Port %d: "
                         "bind() fehlgeschlagen, Kanal bleibt stumm\n", spec.udp_port);
            close(sock);
            continue;
        }
        prepared.push_back({spec, sock});
    }

    LiveSetupResult result;
    result.channels = std::vector<LiveChannel>(prepared.size());
    result.carrier.resize(prepared.size());
    for (size_t i = 0; i < prepared.size(); ++i) {
        LiveChannel& ch = result.channels[i];
        ch.ring.resize(LiveChannel::RING_SIZE);
        ch.udp_port = prepared[i].spec.udp_port;
        ch.sock = prepared[i].sock;
        ch.freq_hz = prepared[i].spec.freq_hz;
        ch.samples_per_audio_sample = target_rate / prepared[i].spec.audio_rate_hz;

        result.carrier.set_frequency(i, prepared[i].spec.freq_hz, target_rate);

        pthread_t tid;
        pthread_create(&tid, nullptr, live_channel_receiver, &ch);
        pthread_detach(tid);

        std::fprintf(stderr, "cohi_native_upconverter: Live-Kanal auf UDP-Port %d bei %.0f Hz "
                     "(Audiorate %.0f Hz)\n", prepared[i].spec.udp_port,
                     prepared[i].spec.freq_hz, prepared[i].spec.audio_rate_hz);
    }
    return result;
}

struct WavRingBuffer {
    static constexpr uint32_t SIZE = 1 << 17;
    std::vector<int32_t> data;
    std::atomic<uint32_t> head{0};
    std::atomic<uint32_t> tail{0};
    std::atomic<bool> active{true};

    WavRingBuffer() : data(SIZE, 0) {}
};

struct WavThreadArgs {
    Args args;
    WavRingBuffer* ring;
};

void* wav_reader_thread_func(void* raw_arg) {
    WavThreadArgs* targs = static_cast<WavThreadArgs*>(raw_arg);
    const Args& args = targs->args;
    WavRingBuffer* ring = targs->ring;

    const std::vector<int32_t> fir_coeffs =
        design_lowpass_filter(args.fir_taps, args.sample_rate / args.target_rate);
    const int fir_len = static_cast<int>(fir_coeffs.size());
    std::vector<int32_t> i_history(2 * fir_len, 0);
    std::vector<int32_t> q_history(2 * fir_len, 0);
    int hist_pos = 0;
    std::fprintf(stderr, "cohi_native_upconverter: (WAV-Thread) Filter mit %d Taps entworfen "
                 "(Grenzfrequenz %.0f Hz)\n", fir_len, args.sample_rate / 2.0);

    const double samples_per_input_sample = args.target_rate / args.sample_rate;
    double input_phase = 0.0;
    const uint32_t phase_inc_nco = static_cast<uint32_t>(
        (args.center_freq / args.target_rate) * 4294967296.0);
    uint32_t phase_nco = 0;
    int32_t last_i = 0, last_q = 0;

    const size_t block_size = 1024;
    std::vector<int16_t> read_buf(block_size * 2);

    while (true) {
        size_t got = std::fread(read_buf.data(), sizeof(int16_t), block_size * 2, stdin);
        if (got == 0) {
            break;
        }
        size_t n_pairs = got / 2;

        for (size_t n = 0; n < n_pairs; ++n) {
            int32_t next_i = read_buf[2 * n];
            int32_t next_q = read_buf[2 * n + 1];

            while (input_phase < samples_per_input_sample) {
                float mu = static_cast<float>(input_phase / samples_per_input_sample);
                float mu2 = (1.0f - std::cos(mu * static_cast<float>(M_PI))) / 2.0f;
                int32_t curr_i = static_cast<int32_t>(last_i * (1.0f - mu2) + next_i * mu2);
                int32_t curr_q = static_cast<int32_t>(last_q * (1.0f - mu2) + next_q * mu2);

                i_history[hist_pos] = curr_i;
                i_history[hist_pos + fir_len] = curr_i;
                q_history[hist_pos] = curr_q;
                q_history[hist_pos + fir_len] = curr_q;
                const int32_t* i_window = &i_history[hist_pos + 1];
                const int32_t* q_window = &q_history[hist_pos + 1];
                int64_t acc_i = 0, acc_q = 0;
                for (int k = 0; k < fir_len; ++k) {
                    acc_i += static_cast<int64_t>(i_window[k]) * fir_coeffs[k];
                    acc_q += static_cast<int64_t>(q_window[k]) * fir_coeffs[k];
                }
                int32_t filt_i = static_cast<int32_t>(acc_i >> FILTER_SHIFT);
                int32_t filt_q = static_cast<int32_t>(acc_q >> FILTER_SHIFT);
                hist_pos = (hist_pos + 1) % fir_len;

                phase_nco += phase_inc_nco;
                uint32_t lut_idx = phase_nco >> (32 - LUT_BITS);
                int32_t c = g_cos_lut[lut_idx];
                int32_t s = g_sine_lut[lut_idx];
                int32_t mixed = ((filt_i * c) - (filt_q * s)) >> 15;

                uint32_t head = ring->head.load(std::memory_order_relaxed);
                while (head - ring->tail.load(std::memory_order_acquire) >= WavRingBuffer::SIZE) {
                    usleep(100);
                }
                ring->data[head & (WavRingBuffer::SIZE - 1)] = mixed;
                ring->head.store(head + 1, std::memory_order_release);

                input_phase += 1.0;
            }
            input_phase -= samples_per_input_sample;
            last_i = next_i;
            last_q = next_q;
        }
    }

    ring->active.store(false, std::memory_order_release);
    return nullptr;
}
#endif

}

int main(int argc, char** argv) {
    Args args;
    if (!parse_args(argc, argv, args)) {
        std::fprintf(stderr,
            "Verwendung: %s --sample-rate HZ --center-freq HZ --target-rate HZ "
            "[--output-shift N] [--output-bits 8|10|12|14] [--fir-taps N] "
            "[--live-channel PORT:FREQ:AUDIORATE ...] [--live-gain-shift N] "
            "[--live-gain-trim F] [--live-control-port UDPPORT] [--live-sferics-port UDPPORT]\n", argv[0]);
        return 1;
    }

#ifdef _WIN32
    if (!args.live_channels.empty()) {
        std::fprintf(stderr, "cohi_native_upconverter: --live-channel wird unter Windows "
                     "noch nicht unterstuetzt (nur Linux/POSIX) - COHI-Player (WAV-Hochmischung) "
                     "ist davon unabhaengig und funktioniert weiterhin, aber ohne COHI-Stream.\n");
        return 1;
    }
    _setmode(_fileno(stdin), _O_BINARY);
    _setmode(_fileno(stdout), _O_BINARY);
#endif

    std::setvbuf(stdin, nullptr, _IONBF, 0);

    init_luts();

    DebugUdpSender debug_sender;
    debug_sender.init(args.debug_udp_port);

    OutputStage out_stage;
    out_stage.init(args);
    std::vector<int8_t> out_tmp;

    size_t num_live_channels = args.live_channels.size();

    if (num_live_channels == 0) {
        const std::vector<int32_t> fir_coeffs =
            design_lowpass_filter(args.fir_taps, args.sample_rate / args.target_rate);
        const int fir_len = static_cast<int>(fir_coeffs.size());
        std::vector<int32_t> i_history(2 * fir_len, 0);
        std::vector<int32_t> q_history(2 * fir_len, 0);
        int hist_pos = 0;
        std::fprintf(stderr, "cohi_native_upconverter: Filter mit %d Taps entworfen "
                     "(Grenzfrequenz %.0f Hz)\n", fir_len, args.sample_rate / 2.0);

        const double samples_per_input_sample = args.target_rate / args.sample_rate;
        double input_phase = 0.0;
        const uint32_t phase_inc_nco = static_cast<uint32_t>(
            (args.center_freq / args.target_rate) * 4294967296.0);
        uint32_t phase_nco = 0;
        int32_t last_i = 0, last_q = 0;

        const size_t block_size = 1024;
        std::vector<int16_t> read_buf(block_size * 2);
        const size_t out_capacity = static_cast<size_t>(block_size * samples_per_input_sample) + 256;
        std::vector<int16_t> out_buf(out_capacity);

        auto load_window_started_at = std::chrono::steady_clock::now();
        double busy_seconds_in_window = 0.0;
        double audio_seconds_in_window = 0.0;
        constexpr double LOAD_LOG_INTERVAL_S = 10.0;

        // --- ECHTZEIT-PACING (reiner WAV-Betrieb, ohne Live-Kanaele) -------------
        // Wie im Live-Zweig weiter unten: Ohne Uhr laeuft der Upconverter nur so
        // schnell, wie die Senke Daten annimmt. smiSDR/parlioSDR nehmen ueber
        // Socket-/Pi-Puffer schneller als Echtzeit an (fl2k_tcp bremst dagegen per
        // USB selbst). Die Deadline wird um die Dauer jedes ausgegebenen Blocks
        // weitergeschoben; der Block darf hoechstens PACE_LEAD_S vor der Echtzeit
        // liegen. Faellt er mehr als PACE_MAX_BEHIND_S zurueck (Titelwechsel,
        // Pause, Lesestau), wird die Uhr neu aufgesetzt statt im Burst aufzuholen.
        // Da der Upconverter dann langsamer von stdin liest, bremst die Pipe den
        // Player (Backpressure) und Pause / Titelwechsel greifen ohne grossen Nachlauf.
        constexpr double PACE_LEAD_S = 0.100;
        constexpr double PACE_MAX_BEHIND_S = 0.250;
        const auto pace_lead = std::chrono::duration_cast<std::chrono::steady_clock::duration>(
            std::chrono::duration<double>(PACE_LEAD_S));
        const auto pace_max_behind = std::chrono::duration_cast<std::chrono::steady_clock::duration>(
            std::chrono::duration<double>(PACE_MAX_BEHIND_S));
        auto pace_deadline = std::chrono::steady_clock::now();
        // --------------------------------------------------------------------------

        while (true) {
            size_t got = std::fread(read_buf.data(), sizeof(int16_t), block_size * 2, stdin);
            if (got == 0) {
                break;
            }
            auto batch_started_at = std::chrono::steady_clock::now();
            size_t n_pairs = got / 2;
            size_t out_idx = 0;

            for (size_t n = 0; n < n_pairs; ++n) {
                int32_t next_i = read_buf[2 * n];
                int32_t next_q = read_buf[2 * n + 1];

                while (input_phase < samples_per_input_sample) {
                    float mu = static_cast<float>(input_phase / samples_per_input_sample);
                    float mu2 = (1.0f - std::cos(mu * static_cast<float>(M_PI))) / 2.0f;
                    int32_t curr_i = static_cast<int32_t>(last_i * (1.0f - mu2) + next_i * mu2);
                    int32_t curr_q = static_cast<int32_t>(last_q * (1.0f - mu2) + next_q * mu2);

                    i_history[hist_pos] = curr_i;
                    i_history[hist_pos + fir_len] = curr_i;
                    q_history[hist_pos] = curr_q;
                    q_history[hist_pos + fir_len] = curr_q;
                    const int32_t* i_window = &i_history[hist_pos + 1];
                    const int32_t* q_window = &q_history[hist_pos + 1];
                    int64_t acc_i = 0, acc_q = 0;
                    for (int k = 0; k < fir_len; ++k) {
                        acc_i += static_cast<int64_t>(i_window[k]) * fir_coeffs[k];
                        acc_q += static_cast<int64_t>(q_window[k]) * fir_coeffs[k];
                    }
                    int32_t filt_i = static_cast<int32_t>(acc_i >> FILTER_SHIFT);
                    int32_t filt_q = static_cast<int32_t>(acc_q >> FILTER_SHIFT);
                    hist_pos = (hist_pos + 1) % fir_len;

                    phase_nco += phase_inc_nco;
                    uint32_t lut_idx = phase_nco >> (32 - LUT_BITS);
                    int32_t c = g_cos_lut[lut_idx];
                    int32_t s = g_sine_lut[lut_idx];
                    int32_t mixed = ((filt_i * c) - (filt_q * s)) >> 15;

                    if (out_idx < out_capacity) {
                        out_buf[out_idx++] = out_stage.quantize(mixed);
                    }
                    input_phase += 1.0;
                }
                input_phase -= samples_per_input_sample;
                last_i = next_i;
                last_q = next_q;
            }

            auto compute_ended_at = std::chrono::steady_clock::now();
            if (out_idx > 0) {
                out_stage.emit(out_buf.data(), out_idx, debug_sender, out_tmp);
                std::fflush(stdout);

                // Pacing: Echtzeit-Deadline um die Dauer dieses Blocks weiterschieben
                pace_deadline += std::chrono::duration_cast<std::chrono::steady_clock::duration>(
                    std::chrono::duration<double>(static_cast<double>(out_idx) / args.target_rate));
                auto now = std::chrono::steady_clock::now();
                if (now - pace_deadline > pace_max_behind) {
                    pace_deadline = now;                   // nicht im Burst aufholen
                } else if (pace_deadline - pace_lead > now) {
                    std::this_thread::sleep_until(pace_deadline - pace_lead);
                }
            }

            auto batch_ended_at = std::chrono::steady_clock::now();
            busy_seconds_in_window += std::chrono::duration<double>(compute_ended_at - batch_started_at).count();
            audio_seconds_in_window += static_cast<double>(out_idx) / args.target_rate;
            double elapsed_in_window =
                std::chrono::duration<double>(batch_ended_at - load_window_started_at).count();
            if (elapsed_in_window >= LOAD_LOG_INTERVAL_S) {
                double load_percent = (audio_seconds_in_window > 0.0)
                    ? (busy_seconds_in_window / audio_seconds_in_window) * 100.0 : 0.0;
                std::fprintf(stderr,
                    "cohi_native_upconverter: Auslastung %.1f%% (%.3fs Rechenzeit fuer %.3fs Audio "
                    "in den letzten %.0fs)\n",
                    load_percent, busy_seconds_in_window, audio_seconds_in_window, elapsed_in_window);
                load_window_started_at = batch_ended_at;
                busy_seconds_in_window = 0.0;
                audio_seconds_in_window = 0.0;
            }
        }
        return 0;
    }

#ifdef _WIN32
    return 1;
#else
    WavRingBuffer ring;
    WavThreadArgs wav_thread_args{args, &ring};
    pthread_t wav_tid;
    pthread_create(&wav_tid, nullptr, wav_reader_thread_func, &wav_thread_args);
    pthread_detach(wav_tid);

    LiveSetupResult live_setup = setup_live_channels(args.live_channels, args.target_rate);
    std::vector<LiveChannel>& live_channels = live_setup.channels;
    LiveCarrierState& carrier = live_setup.carrier;
    const size_t n_live_channels = live_channels.size();

    LiveControlArgs live_control_args{&live_channels, args.live_control_port, "cohi_native_upconverter"};
    if (args.live_control_port > 0 && n_live_channels > 0) {
        pthread_t control_tid;
        pthread_create(&control_tid, nullptr, live_control_receiver, &live_control_args);
        pthread_detach(control_tid);
    }

    SfericsArgs sferics_args{args.live_sferics_port, args.target_rate, "cohi_native_upconverter"};
    if (args.live_sferics_port > 0 && n_live_channels > 0) {
        pthread_t sferics_tid;
        pthread_create(&sferics_tid, nullptr, sferics_receiver, &sferics_args);
        pthread_detach(sferics_tid);
    }
    SfericsState sferics;

    const size_t OUTPUT_BATCH_SIZE = 4096;
    std::vector<int16_t> out_buf(OUTPUT_BATCH_SIZE);

    const float live_scale = (n_live_channels > 0)
        ? static_cast<float>(args.live_gain_trim) / static_cast<float>(n_live_channels)
        : 0.0f;

    auto load_window_started_at = std::chrono::steady_clock::now();
    double busy_seconds_in_window = 0.0;
    double audio_seconds_in_window = 0.0;
    double max_batch_seconds_in_window = 0.0;
    uint64_t wav_ring_empty_count = 0;
    constexpr double LOAD_LOG_INTERVAL_S = 10.0;

    // --- ECHTZEIT-PACING des Ausgabe-Threads ---------------------------------
    // Die Live-Kanaele (UDP-Audio der Decoder) liefern ihre Samples in Echtzeit,
    // der Ausgabe-Thread zieht sie aber im Takt seines eigenen Ausgangs. Ohne
    // Uhr laeuft er nur so schnell, wie die Senke (stdout -> Pipe -> TCP) Daten
    // annimmt: bei fl2k_tcp ist das exakt Echtzeit, da der Fl2k DAC per USB auch 
    // bei fl2k_tcp genau den Speed vorgibt (Senke bremst);
    // bei smiSDR/parlioSDR nimmt die Kette (Socket-/Pi-Puffer) Daten schneller als
    // Echtzeit an -> Ringe laufen leer ("hungrig"), Audio stockt.
    // Der Ausgabe-Thread ist hier selbst die Zeitbasis: ein Batch darf hoechstens
    // PACE_LEAD_S vor der Echtzeit liegen. Faellt er laenger als PACE_MAX_BEHIND_S
    // zurueck (Senke blockierte), wird die Uhr neu aufgesetzt statt im Burst
    // aufzuholen (ein Burst wuerde die Live-Ringe sofort wieder leersaugen).
    constexpr double PACE_LEAD_S = 0.100;
    constexpr double PACE_MAX_BEHIND_S = 0.250;
    const auto pace_batch_duration = std::chrono::duration_cast<std::chrono::steady_clock::duration>(
        std::chrono::duration<double>(static_cast<double>(OUTPUT_BATCH_SIZE) / args.target_rate));
    const auto pace_lead = std::chrono::duration_cast<std::chrono::steady_clock::duration>(
        std::chrono::duration<double>(PACE_LEAD_S));
    const auto pace_max_behind = std::chrono::duration_cast<std::chrono::steady_clock::duration>(
        std::chrono::duration<double>(PACE_MAX_BEHIND_S));
    auto pace_deadline = std::chrono::steady_clock::now();
    // --------------------------------------------------------------------------

    while (true) {
        auto batch_started_at = std::chrono::steady_clock::now();
        sferics.poll();

        for (size_t out_idx = 0; out_idx < OUTPUT_BATCH_SIZE; ++out_idx) {
            int32_t mixed = 0;
            uint32_t head = ring.head.load(std::memory_order_acquire);
            uint32_t tail = ring.tail.load(std::memory_order_relaxed);
            if (head != tail) {
                mixed = ring.data[tail & (WavRingBuffer::SIZE - 1)];
                ring.tail.store(tail + 1, std::memory_order_release);
            } else {
                ++wav_ring_empty_count;
            }

            for (size_t i = 0; i < n_live_channels; ++i) {
                LiveChannel& ch = live_channels[i];
                ch.audio_phase += 1.0;
                if (ch.audio_phase < ch.samples_per_audio_sample) {
                    continue;
                }
                ch.audio_phase -= ch.samples_per_audio_sample;

                uint32_t lhead = ch.head.load(std::memory_order_acquire);
                uint32_t ltail = ch.tail.load(std::memory_order_relaxed);
                if (lhead == ltail) {
                    ++ch.starved_count;
                    continue;
                }
                int32_t raw = static_cast<int32_t>(
                    ch.ring[ltail & (LiveChannel::RING_SIZE - 1)]) - 128;
                ch.tail.store(ltail + 1, std::memory_order_release);

                float raw_f = static_cast<float>(raw) / 128.0f;
                float peak = std::fabs(raw_f);
                ch.peak_hold *= PEAK_HOLD_DECAY_PER_SAMPLE;
                if (peak > ch.peak_hold) {
                    ch.peak_hold = 0.995f * ch.peak_hold + 0.005f * peak;
                }
                float target_gain = 0.8f / (ch.peak_hold + 0.001f);
                ch.gain = 0.998f * ch.gain + 0.002f * target_gain;
                if (ch.gain > 8.0f) ch.gain = 8.0f;
                if (ch.gain < 0.1f) ch.gain = 0.1f;

                float ext_gain = ch.external_gain.load(std::memory_order_relaxed);
                int32_t total_gain_int = static_cast<int32_t>(ch.gain * ext_gain * 64.0f);
                int32_t carrier_base_int = static_cast<int32_t>(16384.0f * ext_gain);
                carrier.mod_register[i] = static_cast<float>(carrier_base_int + raw * total_gain_int);
            }

            float live_mix_f = 0.0f;
            for (size_t i = 0; i < n_live_channels; ++i) {
                float new_cos = carrier.cos_val[i] * carrier.cos_delta[i]
                               - carrier.sin_val[i] * carrier.sin_delta[i];
                float new_sin = carrier.sin_val[i] * carrier.cos_delta[i]
                               + carrier.cos_val[i] * carrier.sin_delta[i];
                carrier.cos_val[i] = new_cos;
                carrier.sin_val[i] = new_sin;
                live_mix_f += carrier.mod_register[i] * new_cos;
            }
            if (n_live_channels > 0) {
                int32_t live_mix = static_cast<int32_t>(live_mix_f * live_scale);
                mixed += live_mix >> args.live_gain_shift;

                if (sferics.env > 0.0f) {
                    // live_scale = live_gain_trim / n_live_channels: Blitzpegel folgt dem
                    // Pegel der Sender (fl2k_live_gain_shift), bei trim = 1 wie bisher
                    float burst = sferics.noise() * sferics.env * sferics.amp * 128.0f
                                  * live_scale;
                    mixed += static_cast<int32_t>(burst) >> args.live_gain_shift;
                    sferics.step_env();
                }
            }

            out_buf[out_idx] = out_stage.quantize(mixed);
        }

        carrier.renormalize();

        auto compute_ended_at = std::chrono::steady_clock::now();

        out_stage.emit(out_buf.data(), OUTPUT_BATCH_SIZE, debug_sender, out_tmp);
        std::fflush(stdout);

        // Pacing: Echtzeit-Deadline um einen Batch weiterschieben und ggf. warten
        pace_deadline += pace_batch_duration;
        {
            auto now = std::chrono::steady_clock::now();
            if (now - pace_deadline > pace_max_behind) {
                pace_deadline = now;                       // nicht im Burst aufholen
            } else if (pace_deadline - pace_lead > now) {
                std::this_thread::sleep_until(pace_deadline - pace_lead);
            }
        }

        auto batch_ended_at = std::chrono::steady_clock::now();
        double batch_compute_seconds =
            std::chrono::duration<double>(compute_ended_at - batch_started_at).count();
        busy_seconds_in_window += batch_compute_seconds;
        if (batch_compute_seconds > max_batch_seconds_in_window) {
            max_batch_seconds_in_window = batch_compute_seconds;
        }
        audio_seconds_in_window += static_cast<double>(OUTPUT_BATCH_SIZE) / args.target_rate;
        double elapsed_in_window =
            std::chrono::duration<double>(batch_ended_at - load_window_started_at).count();
        if (elapsed_in_window >= LOAD_LOG_INTERVAL_S) {
            double load_percent = (audio_seconds_in_window > 0.0)
                ? (busy_seconds_in_window / audio_seconds_in_window) * 100.0 : 0.0;

            uint64_t total_starved = 0;
            std::string starved_detail;
            uint64_t total_overflow = 0;
            std::string overflow_detail;
            for (LiveChannel& ch : live_channels) {
                total_starved += ch.starved_count;
                if (ch.starved_count > 0) {
                    if (!starved_detail.empty()) starved_detail += ", ";
                    starved_detail += std::to_string(ch.udp_port) + ":"
                                     + std::to_string(ch.starved_count);
                }
                ch.starved_count = 0;

                uint64_t overflow = ch.overflow_count.exchange(0, std::memory_order_relaxed);
                total_overflow += overflow;
                if (overflow > 0) {
                    if (!overflow_detail.empty()) overflow_detail += ", ";
                    overflow_detail += std::to_string(ch.udp_port) + ":" + std::to_string(overflow);
                }
            }
            if (starved_detail.empty()) starved_detail = "keine";
            if (overflow_detail.empty()) overflow_detail = "keine";

            std::fprintf(stderr,
                "cohi_native_upconverter: Auslastung %.1f%% (%.3fs Rechenzeit fuer %.3fs Audio "
                "in den letzten %.0fs, %zu Live-Kanaele, Ausgabe-Thread, groesster Batch %.1fms, "
                "WAV-Ringpuffer %llu mal leer, Live-Kanaele hungrig gesamt: %llu, betroffene "
                "Ports (Port:Anzahl): %s, Live-Kanaele Ueberlauf gesamt: %llu, betroffene Ports "
                "(Port:Anzahl): %s)\n",
                load_percent, busy_seconds_in_window, audio_seconds_in_window,
                elapsed_in_window, num_live_channels, max_batch_seconds_in_window * 1000.0,
                static_cast<unsigned long long>(wav_ring_empty_count),
                static_cast<unsigned long long>(total_starved), starved_detail.c_str(),
                static_cast<unsigned long long>(total_overflow), overflow_detail.c_str());
            load_window_started_at = batch_ended_at;
            busy_seconds_in_window = 0.0;
            audio_seconds_in_window = 0.0;
            max_batch_seconds_in_window = 0.0;
            wav_ring_empty_count = 0;
        }
    }

    return 0;
#endif
}
