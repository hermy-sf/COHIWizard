/*
 * DspWorkerFL2K.h  –  fl2k_plus variant
 * C API for the COHIWizard DSP+FL2K engine.
 *
 * Extends fl2k_C with N AM-modulated web-radio overlay channels.
 * Each channel receives real PCM audio (u8, configurable rate) via a local
 * UDP socket fed by an ffmpeg subprocess, AM-modulates it onto a specified
 * carrier frequency, and mixes it into the complex IQ baseband before the
 * main upsampler — so the full output benefits from a single resampling pass.
 *
 * Usage from Python (ctypes):
 *   lib = ctypes.CDLL("libdspfl2k.so")
 *   h   = lib.dsp_fl2k_create()
 *   lib.dsp_fl2k_configure(h, target_rate, shift_freq, gain, use_agc, fnames, n)
 *   lib.dsp_fl2k_configure_audio(h, channels, n_channels, audio_rate, mix_level)
 *   lib.dsp_fl2k_start(h)
 *   while lib.dsp_fl2k_is_running(h): ...
 *   lib.dsp_fl2k_stop(h)
 *   lib.dsp_fl2k_destroy(h)
 */

#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Opaque worker handle */
typedef void* DspFL2KHandle;

/* Callback types  (all called from DSP thread) */
typedef void (*dsp_monitor_cb_t) (const float* samples, int n,    void* ud);
typedef void (*dsp_progress_cb_t)(float pct,                       void* ud);
typedef void (*dsp_finished_cb_t)(void* ud);
typedef void (*dsp_error_cb_t)   (const char* msg,                 void* ud);
typedef void (*dsp_nextfile_cb_t)(const char* path,                void* ud);

/* ------------------------------------------------------------------ */
/* Audio overlay channel descriptor                                    */
/* ------------------------------------------------------------------ */

/*
 * One AM overlay channel.  The matching ffmpeg subprocess must send
 * mono u8 PCM to  udp://127.0.0.1:<udp_port>  at <audio_rate> Hz.
 */
typedef struct {
    float freq_hz;        /* carrier frequency in Hz                    */
    float bandwidth_hz;   /* audio low-pass bandwidth in Hz (e.g. 4500) */
    char  name[64];       /* station name (display / log only)          */
    int   udp_port;       /* local UDP port to receive audio from       */
    float mod_index;      /* AM modulation index [0..1], typical 0.9    */
} DspAudioChannel;

/* ------------------------------------------------------------------ */
/* Lifecycle                                                           */
/* ------------------------------------------------------------------ */

DspFL2KHandle dsp_fl2k_create  (void);
void          dsp_fl2k_destroy (DspFL2KHandle h);

/* ------------------------------------------------------------------ */
/* Main IQ configuration  (must be called before dsp_fl2k_start)      */
/* ------------------------------------------------------------------ */

int  dsp_fl2k_configure(DspFL2KHandle h,
                        float         target_rate,
                        float         shift_freq,
                        float         gain,
                        int           use_agc,
                        const char**  filenames,
                        int           num_files);

/* ------------------------------------------------------------------ */
/* Audio overlay configuration  (optional, call before dsp_fl2k_start)*/
/* ------------------------------------------------------------------ */

/*
 * Configure N AM audio overlay channels.
 *
 *   channels    – array of N DspAudioChannel descriptors
 *   n_channels  – number of entries; 0 disables the feature
 *   audio_rate  – PCM sample rate of the UDP audio streams in Hz
 *   mix_level   – amplitude weight of the combined audio overlay
 *                 relative to the IQ signal:
 *                   1.0  →  equal RMS power (50 % each, recommended)
 *                   0.5  →  audio at ~25 % power vs. IQ
 *                 Per-channel gain = mix_level / sqrt(N).
 *
 * Opens one non-blocking UDP receive socket per channel.
 * Safe to call again to reconfigure; closes previously opened sockets.
 * Returns 0 on success.
 */
int  dsp_fl2k_configure_audio(DspFL2KHandle          h,
                               const DspAudioChannel* channels,
                               int                    n_channels,
                               float                  audio_rate,
                               float                  mix_level);

/*
 * Pre-fill the raw_fifo of every audio channel by repeatedly draining
 * their UDP sockets for duration_ms milliseconds (poll interval 100 ms).
 * Call AFTER configure_audio and BEFORE start.  Compensates for the
 * ~0.3 % systematic under-delivery of ffmpeg resampled streams so that
 * the 1 M-sample raw_fifo starts nearly full, giving ≥ 2 h drift margin.
 */
void dsp_fl2k_prefill_audio(DspFL2KHandle h, int duration_ms);

/* ------------------------------------------------------------------ */
/* Callbacks (may be NULL)                                             */
/* ------------------------------------------------------------------ */

void dsp_fl2k_set_monitor_cb (DspFL2KHandle h, dsp_monitor_cb_t  cb, void* ud);
void dsp_fl2k_set_progress_cb(DspFL2KHandle h, dsp_progress_cb_t cb, void* ud);
void dsp_fl2k_set_finished_cb(DspFL2KHandle h, dsp_finished_cb_t cb, void* ud);
void dsp_fl2k_set_error_cb   (DspFL2KHandle h, dsp_error_cb_t    cb, void* ud);
void dsp_fl2k_set_nextfile_cb(DspFL2KHandle h, dsp_nextfile_cb_t cb, void* ud);

/* ------------------------------------------------------------------ */
/* Runtime control                                                     */
/* ------------------------------------------------------------------ */

int  dsp_fl2k_start    (DspFL2KHandle h);   /* non-blocking, returns 0 OK */
void dsp_fl2k_stop     (DspFL2KHandle h);   /* blocks until threads exit  */
void dsp_fl2k_set_pause(DspFL2KHandle h, int paused);
void dsp_fl2k_set_gain (DspFL2KHandle h, float gain);
int  dsp_fl2k_is_running(DspFL2KHandle h);
int  dsp_fl2k_check_device(void);
void dsp_fl2k_seek(DspFL2KHandle h, int64_t byte_pos, int whence);

#ifdef __cplusplus
}
#endif
