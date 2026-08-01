/*
 * DspWorkerFL2K.h  –  fl2k_fast_plus variant
 * C API for the COHIWizard DSP+FL2K engine.
 *
 * Drop-in replacement for fl2k_plus, but WITHOUT liquidDSP:
 *   - IQ upsampling  : cosine-interpolation + 7-tap integer FIR
 *   - Audio resampling: zero-order hold (sample-repetition / padding)
 *   - All NCOs       : 32-bit phase accumulator + 12-bit sin/cos LUT
 *
 * Identical C API to fl2k_plus – the Python SDR_control.py / ctypes
 * layer does NOT need to be changed.
 *
 * Build:
 *   g++ -std=c++17 -O3 -march=native -ffast-math -fPIC -shared \
 *       DspWorkerFL2K.cpp -o libdspfl2k.so \
 *       -losmo-fl2k -lpthread -lm
 */

#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef void* DspFL2KHandle;

typedef void (*dsp_monitor_cb_t) (const float* samples, int n,    void* ud);
typedef void (*dsp_progress_cb_t)(float pct,                       void* ud);
typedef void (*dsp_finished_cb_t)(void* ud);
typedef void (*dsp_error_cb_t)   (const char* msg,                 void* ud);
typedef void (*dsp_nextfile_cb_t)(const char* path,                void* ud);

/* ------------------------------------------------------------------ */
/* Audio overlay channel descriptor (same as fl2k_plus)               */
/* ------------------------------------------------------------------ */
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
/* Configuration                                                       */
/* ------------------------------------------------------------------ */
int  dsp_fl2k_configure(DspFL2KHandle h,
                        float         target_rate,
                        float         shift_freq,
                        float         gain,
                        int           use_agc,
                        const char**  filenames,
                        int           num_files);

int  dsp_fl2k_configure_audio(DspFL2KHandle          h,
                               const DspAudioChannel* channels,
                               int                    n_channels,
                               float                  audio_rate,
                               float                  mix_level);

void dsp_fl2k_prefill_audio(DspFL2KHandle h, int duration_ms);

/* ------------------------------------------------------------------ */
/* Callbacks                                                           */
/* ------------------------------------------------------------------ */
void dsp_fl2k_set_monitor_cb (DspFL2KHandle h, dsp_monitor_cb_t  cb, void* ud);
void dsp_fl2k_set_progress_cb(DspFL2KHandle h, dsp_progress_cb_t cb, void* ud);
void dsp_fl2k_set_finished_cb(DspFL2KHandle h, dsp_finished_cb_t cb, void* ud);
void dsp_fl2k_set_error_cb   (DspFL2KHandle h, dsp_error_cb_t    cb, void* ud);
void dsp_fl2k_set_nextfile_cb(DspFL2KHandle h, dsp_nextfile_cb_t cb, void* ud);

/* ------------------------------------------------------------------ */
/* Runtime control                                                     */
/* ------------------------------------------------------------------ */
int  dsp_fl2k_start    (DspFL2KHandle h);
void dsp_fl2k_stop     (DspFL2KHandle h);
void dsp_fl2k_set_pause(DspFL2KHandle h, int paused);
void dsp_fl2k_set_gain (DspFL2KHandle h, float gain);
int  dsp_fl2k_is_running(DspFL2KHandle h);
int  dsp_fl2k_check_device(void);
void dsp_fl2k_seek(DspFL2KHandle h, int64_t byte_pos, int whence);

#ifdef __cplusplus
}
#endif
