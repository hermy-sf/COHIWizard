/*
 * DspWorkerFL2K.cpp
 * This code is a modified version of the original DspWorker.cpp in the project https://github.com/radiolab81/COHIRADIAStreamer by radiolab81. 
 *
 * COHIWizard fl2k driver – replaces ffmpeg + fl2k_file with
 *   liquiddsp (resampling + NCO mixing) + libosmo-fl2k (device I/O).
 *
 * Threading model:
 *   DSP thread  – reads WAV file → resample → NCO mix → ring buffer
 *   FL2K thread – opens fl2k device, calls fl2k_start_tx() (blocks);
 *                 the fl2k callback drains the ring buffer each ~131 ms
 *
 * Build:
 *   g++ -std=c++17 -O3 -march=native -ffast-math -fPIC -shared \
 *       DspWorkerFL2K.cpp -o libdspfl2k.so \
 *       -lliquid -losmo-fl2k -lpthread -lm
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

#include <liquid/liquid.h>
#include <osmo-fl2k.h>

/* ------------------------------------------------------------------ */
/* WAV / RIFF binary structures                                        */
/* ------------------------------------------------------------------ */
#pragma pack(push, 1)
struct ChunkHeader  { char id[4]; uint32_t size; };
struct RiffHeader   { char chunkId[4]; uint32_t chunkSize; char format[4]; };
struct FmtStruct    {
    uint16_t audioFormat;   /* 1 = PCM, 3 = IEEE float               */
    uint16_t numChannels;
    uint32_t sampleRate;
    uint32_t byteRate;
    uint16_t blockAlign;
    uint16_t bitsPerSample;
};
struct AuxiContent  { uint8_t padding[68]; char filename[96]; };
#pragma pack(pop)

/* ------------------------------------------------------------------ */
/* Constants                                                           */
/* ------------------------------------------------------------------ */
static constexpr size_t RING_BUFS  = 16;
static constexpr size_t RING_SIZE  = (size_t)FL2K_BUF_LEN * RING_BUFS; /* ~10 MB */
static constexpr size_t DSP_BLOCK  = 2*8192;   /* WAV input samples per DSP block  */
static constexpr size_t MON_SIZE   = 8192;   /* monitoring window (float samples) */
/* SCALE_MON must match fl2k_stream: there data = preset_volume * scalefactor_fl2k * int16
 *   = 512 * (1/16) * int16 = 32 * int16.
 * Here x[k].real = int16 / 32768, so we need SCALE_MON = 32 * 32768 = 1048576. */
static constexpr float  SCALE_MON  = 1048576.0f;

/* ------------------------------------------------------------------ */
/* Internal worker struct                                              */
/* ------------------------------------------------------------------ */
struct DspWorkerFL2K {

    /* --- configuration -------------------------------------------- */
    float              targetRate   = 10'000'000.f;
    float              shiftFreq    = 0.f;
    std::atomic<float> gainValue    {0.65f};
    bool               useAGC       = true;
    std::vector<std::string> filenames;

    /* --- user callbacks ------------------------------------------- */
    dsp_monitor_cb_t   mon_cb   = nullptr; void* mon_ud   = nullptr;
    dsp_progress_cb_t  prog_cb  = nullptr; void* prog_ud  = nullptr;
    dsp_finished_cb_t  fin_cb   = nullptr; void* fin_ud   = nullptr;
    dsp_error_cb_t     err_cb   = nullptr; void* err_ud   = nullptr;
    dsp_nextfile_cb_t  nxt_cb   = nullptr; void* nxt_ud   = nullptr;

    /* --- ring buffer (DSP writes, FL2K callback reads) ------------ */
    std::vector<int8_t>         ring       = std::vector<int8_t>(RING_SIZE, 0);
    size_t                      ring_head  = 0;   /* write position */
    size_t                      ring_tail  = 0;   /* read position  */
    size_t                      ring_count = 0;   /* bytes available */
    std::mutex                  ring_mtx;
    std::condition_variable     ring_not_empty;
    std::condition_variable     ring_not_full;

    /* Persistent buffer handed to the FL2K callback */
    std::vector<int8_t>         fl2k_buf   = std::vector<int8_t>(FL2K_BUF_LEN, 0);

    /* --- seek request (set from Python, consumed by DSP thread) -- */
    struct SeekReq { bool pending = false; int64_t pos = 0; int whence = 0; };
    std::mutex  seek_mtx;
    SeekReq     seek_req;

    /* --- control -------------------------------------------------- */
    std::atomic<bool>   running  {false};
    std::atomic<bool>   paused   {false};

    /* --- device --------------------------------------------------- */
    fl2k_dev_t*         dev      = nullptr;
    std::mutex          dev_mtx;
    std::atomic<bool>   dev_open {false};

    /* --- threads -------------------------------------------------- */
    std::thread         dsp_thr;
    std::thread         fl2k_thr;

    /* --- helpers -------------------------------------------------- */
    void write_ring(const int8_t* data, size_t n);
    void drain_ring(int8_t* buf, size_t n);

    void run_dsp();
    void run_fl2k();
    std::string process_file(const std::string& path);

    static void fl2k_callback(fl2k_data_info_t* info);
};

/* ------------------------------------------------------------------ */
/* Ring buffer                                                         */
/* ------------------------------------------------------------------ */

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
        if (first < chunk)
            memcpy(ring.data(), data + written + first, chunk - first);
        ring_head   = (ring_head + chunk) % RING_SIZE;
        ring_count += chunk;
        written    += chunk;
        ring_not_empty.notify_one();
    }
}

void DspWorkerFL2K::drain_ring(int8_t* buf, size_t n)
{
    std::lock_guard<std::mutex> lk(ring_mtx);
    if (ring_count < n) {
        /* underflow → silence; do NOT update read pointer */
        memset(buf, 0, n);
        return;
    }
    size_t first = std::min(n, RING_SIZE - ring_tail);
    memcpy(buf, ring.data() + ring_tail, first);
    if (first < n)
        memcpy(buf + first, ring.data(), n - first);
    ring_tail   = (ring_tail + n) % RING_SIZE;
    ring_count -= n;
    ring_not_full.notify_one();
}

/* ------------------------------------------------------------------ */
/* FL2K callback (called by libosmo-fl2k transfer thread)             */
/* ------------------------------------------------------------------ */

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
        /* kernel buffer pre-allocated by driver – copy into it */
        if (info->r_buf) memcpy(info->r_buf, self->fl2k_buf.data(), n);
    } else {
        /* provide our own user-space buffer */
        info->r_buf = reinterpret_cast<char*>(self->fl2k_buf.data());
    }
    /* g_buf / b_buf intentionally left unchanged – unused for audio */
}

/* ------------------------------------------------------------------ */
/* FL2K thread                                                         */
/* ------------------------------------------------------------------ */

void DspWorkerFL2K::run_fl2k()
{
    {
        std::lock_guard<std::mutex> lk(dev_mtx);
        int r = fl2k_open(&dev, 0);
        if (r != FL2K_SUCCESS) {
            char msg[128];
            snprintf(msg, sizeof(msg), "fl2k_open failed (code %d). "
                     "Check USB connection.", r);
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
        {
            std::lock_guard<std::mutex> lk(dev_mtx);
            dev = nullptr;
        }
        return;
    }

    /* fl2k_start_tx is NON-BLOCKING: it spawns libosmo-fl2k's internal USB
     * and sample-worker threads and returns immediately.
     * We must NOT call fl2k_close() before fl2k_stop_tx() — doing so while
     * holding dev_mtx would deadlock with dsp_fl2k_stop() / run_dsp()
     * which also need dev_mtx to call fl2k_stop_tx().
     * Correct sequence: wait for running==false (set by dsp_fl2k_stop or
     * run_dsp), then call fl2k_stop_tx + fl2k_close without holding dev_mtx. */
    fl2k_start_tx(dev, fl2k_callback, this, 0);

    /* Spin-wait for stop signal — no mutex held, so dsp_fl2k_stop() can
     * proceed normally while we wait here. */
    while (running.load(std::memory_order_acquire))
        std::this_thread::sleep_for(std::chrono::milliseconds(10));

    /* Signal libosmo-fl2k's internal threads to stop */
    fl2k_stop_tx(dev);

    /* Block until libosmo-fl2k's USB and sample threads have exited */
    fl2k_close(dev);

    {
        std::lock_guard<std::mutex> lk(dev_mtx);
        dev = nullptr;
        dev_open.store(false, std::memory_order_release);
    }
}

/* ------------------------------------------------------------------ */
/* DSP: process a single WAV file, return auxi "next file" name       */
/* ------------------------------------------------------------------ */

std::string DspWorkerFL2K::process_file(const std::string& path)
{
    std::ifstream f(path, std::ios::binary);
    if (!f) {
        if (err_cb) err_cb(("Cannot open: " + path).c_str(), err_ud);
        return "";
    }
    if (nxt_cb) nxt_cb(path.c_str(), nxt_ud);

    /* Read RIFF header */
    RiffHeader riff;
    f.read(reinterpret_cast<char*>(&riff), sizeof(riff));

    uint32_t sampleRate    = 0;
    uint16_t audioFormat   = 1;
    uint16_t bitsPerSample = 16;
    uint16_t numChannels   = 2;
    std::string nextFile;
    ChunkHeader chunk;
    printf("##################### Processing WAV file: %s\n", path.c_str());
    printf("##################### shiftFreq: %f\n", shiftFreq);
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
            /* trim trailing garbage */
            static const std::string JUNK(" \t\n\r\0\x01", 6);
            size_t last = raw.find_last_not_of(JUNK);
            if (last != std::string::npos)
                nextFile = raw.substr(0, last + 1);
            long skip = (long)chunk.size - (long)sizeof(aux);
            if (skip > 0) f.seekg(skip, std::ios::cur);
        }
        else if (tag == "data") {

            if (sampleRate == 0 || numChannels < 2) {
                if (err_cb) err_cb("Invalid WAV header", err_ud);
                break;
            }

            /* ---- set up liquiddsp resampler + NCO ---- */
            float upRate  = targetRate / (float)sampleRate;
            msresamp_crcf resamp = msresamp_crcf_create(upRate, 60.0f);
            nco_crcf      vco    = nco_crcf_create(LIQUID_VCO);
            nco_crcf_set_frequency(vco, 2.f * M_PIf * shiftFreq / targetRate);

            /* ---- gain / AGC state ---- */
            const float bitScale  = 127.0f;
            /* fl2k_stream-equivalent: Python gain G is applied to raw int16 before ffmpeg;
             * ffmpeg applies volume=512, amix normalises by /2 → effective factor = 256*127.
             * Non-AGC path uses this same factor so the Python AGC gain value produces
             * the same clipping behaviour as fl2k_stream. */
            const float GAIN_SCALE = 256.0f * bitScale;  /* = 32512 */
            float current_gain    = gainValue.load() * GAIN_SCALE;
            float peak_hold       = 0.1f;

            /* ---- buffers ---- */
            size_t outMax = (size_t)(DSP_BLOCK * upRate) + 512;
            std::vector<liquid_float_complex> x(DSP_BLOCK), y(outMax);
            std::vector<int16_t> rb16(DSP_BLOCK * 2);
            std::vector<float>   rb32(DSP_BLOCK * 2);
            std::vector<int32_t> rb32i(DSP_BLOCK * 2);
            std::vector<uint8_t> rb24(DSP_BLOCK * 6);
            std::vector<int8_t>  out8(outMax);
            std::vector<float>   mon(MON_SIZE);

            uint32_t dataBytesTotal = chunk.size;
            uint32_t dataBytesRead  = 0;
            size_t   blocksPerSec   = (size_t)(sampleRate / (float)DSP_BLOCK) + 1;
            size_t   blockCnt       = 0;
            size_t   monIdx         = 0;

            /* ---- inner read-and-process loop ---- */
            while (running.load(std::memory_order_acquire)) {

                /* -- handle seek request from Python -- */
                {
                    std::lock_guard<std::mutex> slk(seek_mtx);
                    if (seek_req.pending) {
                        auto dir = (seek_req.whence == 0) ? std::ios::beg
                                 : (seek_req.whence == 1) ? std::ios::cur
                                                          : std::ios::end;
                        f.clear();          /* reset EOF / error bits first  */
                        f.seekg(seek_req.pos, dir);
                        seek_req.pending = false;
                        /* flush ring so stale samples do not play */
                        {
                            std::lock_guard<std::mutex> rlk(ring_mtx);
                            ring_head  = 0;
                            ring_tail  = 0;
                            ring_count = 0;
                            ring_not_full.notify_all();
                        }
                    }
                }

                /* -- handle pause: feed silence without advancing file -- */
                while (paused.load(std::memory_order_acquire)
                       && running.load(std::memory_order_acquire))
                {
                    static const int8_t zeros[4096] = {};
                    write_ring(zeros, sizeof(zeros));
                }
                if (!running.load(std::memory_order_acquire)) break;

                /* -- read one block of IQ samples -- */
                bool ok = false;
                if (audioFormat == 1 && bitsPerSample == 16) {
                    ok = (bool)f.read(reinterpret_cast<char*>(rb16.data()),
                                      DSP_BLOCK * 4);
                    if (ok)
                        for (size_t i = 0; i < DSP_BLOCK; ++i)
                            x[i] = { rb16[2*i] / 32768.f, rb16[2*i+1] / 32768.f };
                }
                else if (audioFormat == 3 && bitsPerSample == 32) {
                    ok = (bool)f.read(reinterpret_cast<char*>(rb32.data()),
                                      DSP_BLOCK * 8);
                    if (ok)
                        for (size_t i = 0; i < DSP_BLOCK; ++i)
                            x[i] = { rb32[2*i], rb32[2*i+1] };
                }
                else if (audioFormat == 1 && bitsPerSample == 32) {
                    ok = (bool)f.read(reinterpret_cast<char*>(rb32i.data()),
                                      DSP_BLOCK * 8);
                    if (ok)
                        for (size_t i = 0; i < DSP_BLOCK; ++i)
                            x[i] = { rb32i[2*i] / 2147483648.f,
                                     rb32i[2*i+1] / 2147483648.f };
                }
                else if (audioFormat == 1 && bitsPerSample == 24) {
                    ok = (bool)f.read(reinterpret_cast<char*>(rb24.data()),
                                      DSP_BLOCK * 6);
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
                    snprintf(msg, sizeof(msg),
                             "Unsupported WAV format: tag=%u bits=%u",
                             audioFormat, bitsPerSample);
                    if (err_cb) err_cb(msg, err_ud);
                    break;
                }

                if (!ok) break; /* EOF or read error */

                dataBytesRead += (uint32_t)(DSP_BLOCK * numChannels
                                            * (bitsPerSample / 8));

                /* -- AGC peak tracking -- */
                float bpeak = 0.0001f;
                for (size_t i = 0; i < DSP_BLOCK; ++i) {
                    float m = sqrtf(x[i].real*x[i].real + x[i].imag*x[i].imag);
                    if (m > bpeak) bpeak = m;
                }
                peak_hold = 0.95f * peak_hold + 0.05f * bpeak;

                if (useAGC) {
                    /* Target ~65 % of full scale (bitScale*0.65 ≈ 82) */
                    float tg = (bitScale * 0.65f) / (peak_hold + 0.0001f);
                    current_gain = 0.98f * current_gain + 0.02f * tg;
                } else {
                    /* Use Python-supplied gain with fl2k_stream-equivalent boost */
                    current_gain = gainValue.load() * GAIN_SCALE;
                }

                /* -- resample -- */
                unsigned int nw;
                msresamp_crcf_execute(resamp, x.data(), DSP_BLOCK, y.data(), &nw);

                /* -- NCO mix + clip + int8 conversion -- this process is phase coherent, i.e. there are no phase jumps in the vco generated sine/cosine signalsbetween consecutive blocks */
                for (unsigned int j = 0; j < nw; ++j) {
                    float c = nco_crcf_cos(vco), s = nco_crcf_sin(vco);
                    nco_crcf_step(vco);
                    float hf = (y[j].real * c - y[j].imag * s) * current_gain;
                    if      (hf >  bitScale) hf =  bitScale;
                    else if (hf < -bitScale) hf = -bitScale;
                    out8[j] = static_cast<int8_t>(hf);
                }

                /* -- push to ring (blocks if full – natural back-pressure) -- */
                write_ring(out8.data(), nw);

                /* -- monitoring: collect pre-resample input -- */
                size_t n_mon = std::min(MON_SIZE - monIdx, DSP_BLOCK);
                for (size_t k = 0; k < n_mon; ++k)
                    mon[monIdx++] = x[k].real * SCALE_MON;

                ++blockCnt;
                if (blockCnt >= blocksPerSec) {
                    blockCnt = 0;
                    if (mon_cb && monIdx > 0)
                        mon_cb(mon.data(), static_cast<int>(monIdx), mon_ud);
                    monIdx = 0;
                    if (prog_cb && dataBytesTotal > 0)
                        prog_cb((float)dataBytesRead / dataBytesTotal * 100.f,
                                prog_ud);
                }
            } /* inner while */

            msresamp_crcf_destroy(resamp);
            nco_crcf_destroy(vco);
            break; /* only one "data" chunk */
        }
        else {
            /* skip unknown chunk, keep RIFF word alignment */
            f.seekg(chunk.size, std::ios::cur);
            if (chunk.size & 1) f.seekg(1, std::ios::cur);
        }
    } /* chunk loop */

    return nextFile;
}

/* ------------------------------------------------------------------ */
/* DSP thread entry                                                    */
/* ------------------------------------------------------------------ */

void DspWorkerFL2K::run_dsp()
{
    for (size_t i = 0; i < filenames.size() && running.load(); ) {
        std::string next = process_file(filenames[i]);
        if (!next.empty()) {
            /* auxi chain: find next file in list */
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

    /* Allow the ring to drain before pulling the plug on fl2k (max 5 s) */
    {
        std::unique_lock<std::mutex> lk(ring_mtx);
        ring_not_empty.wait_for(lk, std::chrono::seconds(5),
            [this] { return ring_count == 0 || !running.load(); });
    }

    running.store(false, std::memory_order_release);
    ring_not_full.notify_all();
    ring_not_empty.notify_all();
    /* run_fl2k() detects running==false and handles fl2k_stop_tx + fl2k_close */

    if (fin_cb) fin_cb(fin_ud);
}

/* ================================================================== */
/* C API implementation                                                */
/* ================================================================== */

DspFL2KHandle dsp_fl2k_create()
{
    return new DspWorkerFL2K();
}

void dsp_fl2k_destroy(DspFL2KHandle h)
{
    if (!h) return;
    dsp_fl2k_stop(h);
    delete static_cast<DspWorkerFL2K*>(h);
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

void dsp_fl2k_set_monitor_cb(DspFL2KHandle h, dsp_monitor_cb_t cb, void* ud)
{
    if (h) { auto* w = static_cast<DspWorkerFL2K*>(h); w->mon_cb  = cb; w->mon_ud  = ud; }
}
void dsp_fl2k_set_progress_cb(DspFL2KHandle h, dsp_progress_cb_t cb, void* ud)
{
    if (h) { auto* w = static_cast<DspWorkerFL2K*>(h); w->prog_cb = cb; w->prog_ud = ud; }
}
void dsp_fl2k_set_finished_cb(DspFL2KHandle h, dsp_finished_cb_t cb, void* ud)
{
    if (h) { auto* w = static_cast<DspWorkerFL2K*>(h); w->fin_cb  = cb; w->fin_ud  = ud; }
}
void dsp_fl2k_set_error_cb(DspFL2KHandle h, dsp_error_cb_t cb, void* ud)
{
    if (h) { auto* w = static_cast<DspWorkerFL2K*>(h); w->err_cb  = cb; w->err_ud  = ud; }
}
void dsp_fl2k_set_nextfile_cb(DspFL2KHandle h, dsp_nextfile_cb_t cb, void* ud)
{
    if (h) { auto* w = static_cast<DspWorkerFL2K*>(h); w->nxt_cb  = cb; w->nxt_ud  = ud; }
}

int dsp_fl2k_start(DspFL2KHandle h)
{
    if (!h) return -1;
    auto* w = static_cast<DspWorkerFL2K*>(h);
    if (w->running.load()) return -1; /* already running */
    if (w->filenames.empty()) return -2;

    /* reset ring buffer */
    {
        std::lock_guard<std::mutex> lk(w->ring_mtx);
        w->ring_head  = 0;
        w->ring_tail  = 0;
        w->ring_count = 0;
    }
    w->dev_open.store(false);
    w->running.store(true, std::memory_order_release);

    /* Start FL2K thread first so the device is ready for data */
    w->fl2k_thr = std::thread(&DspWorkerFL2K::run_fl2k, w);

    /* Wait up to 1 s for device open (handles USB enumeration delay) */
    for (int ms = 0; ms < 1000; ms += 20) {
        if (w->dev_open.load() || !w->running.load()) break;
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }

    if (!w->running.load()) {
        /* device failed to open */
        if (w->fl2k_thr.joinable()) w->fl2k_thr.join();
        return -3;
    }

    /* Start DSP thread */
    w->dsp_thr = std::thread(&DspWorkerFL2K::run_dsp, w);
    return 0;
}

void dsp_fl2k_stop(DspFL2KHandle h)
{
    if (!h) return;
    auto* w = static_cast<DspWorkerFL2K*>(h);

    /* Signal both threads to stop.  run_fl2k() monitors running and will
     * call fl2k_stop_tx() + fl2k_close() itself once it sees running==false,
     * so we must NOT call fl2k_stop_tx() here (that would race with
     * run_fl2k() and could also deadlock if run_fl2k() holds dev_mtx). */
    w->running.store(false, std::memory_order_release);
    w->ring_not_full.notify_all();
    w->ring_not_empty.notify_all();

    if (w->dsp_thr.joinable())  w->dsp_thr.join();
    if (w->fl2k_thr.joinable()) w->fl2k_thr.join();
}

void dsp_fl2k_set_pause(DspFL2KHandle h, int paused)
{
    if (h) static_cast<DspWorkerFL2K*>(h)->paused.store(paused != 0,
                                                         std::memory_order_release);
}

void dsp_fl2k_set_gain(DspFL2KHandle h, float gain)
{
    if (h) static_cast<DspWorkerFL2K*>(h)->gainValue.store(gain,
                                                            std::memory_order_release);
}

int dsp_fl2k_is_running(DspFL2KHandle h)
{
    if (!h) return 0;
    return static_cast<DspWorkerFL2K*>(h)->running.load() ? 1 : 0;
}

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
