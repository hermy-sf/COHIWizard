/*
 * DspWorkerADALM.h  –  ADALM2000_universal
 *
 * C API for the COHIWizard DSP engine for ADALM2000.
 * Mirrors the architecture of fl2k_fast_plus/DspWorkerFL2K.h, but:
 *   - No fl2k device dependency
 *   - Output via pull API (dsp_adlm_pull) → int16_t PCM → Python → libm2k
 *   - Mode A: IQ WAV files (internal read) + optional AM audio overlay
 *   - Mode B: pure AM synthesis from UDP audio streams (audio_only)
 *
 * Build:
 *   g++ -std=c++17 -O3 -march=native -ffast-math -fPIC -shared \
 *       DspWorkerADALM.cpp -o libdspadlm.so -lpthread -lm
 */

#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef void* DspADLMHandle;

typedef void (*dsp_monitor_cb_t) (const float* samples, int n,    void* ud);
typedef void (*dsp_progress_cb_t)(float pct,                       void* ud);
typedef void (*dsp_finished_cb_t)(void* ud);
typedef void (*dsp_error_cb_t)   (const char* msg,                 void* ud);
typedef void (*dsp_nextfile_cb_t)(const char* path,                void* ud);

/* ------------------------------------------------------------------ */
/* Audio overlay channel descriptor (same layout as DspWorkerFL2K.h)  */
/* ------------------------------------------------------------------ */
typedef struct {
    float freq_hz;          /* carrier frequency in Hz                    */
    float bandwidth_hz;     /* audio low-pass bandwidth in Hz             */
    char  name[64];         /* station name (display / log only)          */
    int   udp_port;         /* local UDP port to receive audio from       */
    float mod_index;        /* AM modulation index [0..1], typical 0.9   */
    float schroeder_phase;  /* Schröder initial phase (rad)               */
} DspAudioChannel;

/* ------------------------------------------------------------------ */
/* Lifecycle                                                           */
/* ------------------------------------------------------------------ */
DspADLMHandle dsp_adlm_create  (void);
void          dsp_adlm_destroy (DspADLMHandle h);

/* ------------------------------------------------------------------ */
/* Configuration                                                       */
/* ------------------------------------------------------------------ */
int  dsp_adlm_configure(DspADLMHandle h,
                        float         sample_rate,   /* DAC rate = 75e6/OSR  */
                        float         lo_shift,      /* LO Hz (0 = audio_only) */
                        float         gain,
                        int           use_agc,
                        int           audio_only,    /* 0=IQ+audio, 1=audio_only */
                        const char**  filenames,
                        int           num_files);

int  dsp_adlm_configure_audio(DspADLMHandle          h,
                               const DspAudioChannel* channels,
                               int                    n_channels,
                               float                  audio_rate,
                               float                  mix_level);

void dsp_adlm_prefill_audio(DspADLMHandle h, int duration_ms);

/* ------------------------------------------------------------------ */
/* Callbacks                                                           */
/* ------------------------------------------------------------------ */
void dsp_adlm_set_monitor_cb (DspADLMHandle h, dsp_monitor_cb_t  cb, void* ud);
void dsp_adlm_set_progress_cb(DspADLMHandle h, dsp_progress_cb_t cb, void* ud);
void dsp_adlm_set_finished_cb(DspADLMHandle h, dsp_finished_cb_t cb, void* ud);
void dsp_adlm_set_error_cb   (DspADLMHandle h, dsp_error_cb_t    cb, void* ud);
void dsp_adlm_set_nextfile_cb(DspADLMHandle h, dsp_nextfile_cb_t cb, void* ud);

/* ------------------------------------------------------------------ */
/* Runtime control                                                     */
/* ------------------------------------------------------------------ */
int  dsp_adlm_start    (DspADLMHandle h);
void dsp_adlm_stop     (DspADLMHandle h);
void dsp_adlm_set_pause(DspADLMHandle h, int paused);
void dsp_adlm_set_gain (DspADLMHandle h, float gain);
int  dsp_adlm_is_running(DspADLMHandle h);
void dsp_adlm_seek(DspADLMHandle h, int64_t byte_pos, int whence);

/* ------------------------------------------------------------------ */
/* Output pull                                                         */
/* ------------------------------------------------------------------ */
/* Returns n_samples on success, 0 on timeout (retry), -1 when done. */
int  dsp_adlm_pull(DspADLMHandle h, int16_t* buf, int n_samples);

#ifdef __cplusplus
}
#endif
