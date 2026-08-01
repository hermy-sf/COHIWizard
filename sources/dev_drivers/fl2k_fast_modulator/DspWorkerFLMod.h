/*
 * DspWorkerFLMod.h  –  fl2k_fast_modulator variant
 *
 * Pure AM synthesizer for the FL2K USB-VGA DAC.
 * No IQ-WAV file required: N audio streams (UDP, fed by ffmpeg) are
 * AM-modulated onto individual carriers, summed in a complex baseband,
 * then upsampled once to the FL2K output rate.
 *
 * Signal chain:
 *   UDP → [ZOH audio_rate → baseband_rate] per channel
 *       → AM-mod with per-channel integer LUT NCO (at baseband_rate)
 *       → complex baseband sum
 *       → [cosine-interp + 7-tap integer FIR  baseband_rate → target_rate]
 *       → main LUT NCO upconversion (complex → real)
 *       → int8 ring buffer → FL2K callback
 *
 * liquidDSP-free drop-in for fl2k_modulator.  Same C API.
 *
 * Build:
 *   g++ -std=c++17 -O3 -march=native -ffast-math -fPIC -shared \
 *       DspWorkerFLMod.cpp -o libdspflmod.so \
 *       -losmo-fl2k -lpthread -lm
 */

#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef void* DspFLModHandle;

typedef void (*flmod_monitor_cb_t) (const float* samples, int n, void* ud);
typedef void (*flmod_finished_cb_t)(void* ud);
typedef void (*flmod_error_cb_t)   (const char* msg,      void* ud);

/* One AM overlay channel. ffmpeg must send mono u8 PCM to
 * udp://127.0.0.1:<udp_port> at <audio_rate> Hz. */
typedef struct {
    float freq_hz;       /* absolute carrier frequency (Hz)              */
    float bandwidth_hz;  /* audio LP bandwidth (informational, Hz)       */
    char  name[64];      /* station name (display / log only)            */
    int   udp_port;      /* local UDP port to receive audio from         */
    float mod_index;     /* AM modulation index [0..1], typical 0.9      */
} DspFLModChannel;

/* Lifecycle */
DspFLModHandle dsp_flmod_create (void);
void           dsp_flmod_destroy(DspFLModHandle h);

/* Main synthesis parameters – call before dsp_flmod_start.
 *   target_rate   – FL2K output sample rate (e.g. 10e6)
 *   center_freq   – upconversion LO frequency (Hz)
 *   baseband_rate – complex baseband rate; ideally target_rate / 2^N
 *   gain          – initial amplitude [0..1] (ignored when use_agc != 0)
 *   use_agc       – 1 = automatic gain control
 */
int dsp_flmod_configure(DspFLModHandle h,
                        float target_rate,
                        float center_freq,
                        float baseband_rate,
                        float gain,
                        int   use_agc);

/* Configure N AM channels – call before dsp_flmod_start.
 *   audio_rate – PCM rate of the UDP streams (Hz)
 *   mix_level  – amplitude weight of combined audio; 1.0 = equal RMS power
 */
int  dsp_flmod_configure_channels(DspFLModHandle        h,
                                   const DspFLModChannel* channels,
                                   int                    n_channels,
                                   float                  audio_rate,
                                   float                  mix_level);

/* Pre-fill raw_fifo by draining UDP sockets for duration_ms ms.
 * Call AFTER configure_channels, BEFORE start. */
void dsp_flmod_prefill(DspFLModHandle h, int duration_ms);

/* Callbacks (may be NULL; called from DSP thread) */
void dsp_flmod_set_monitor_cb (DspFLModHandle h, flmod_monitor_cb_t  cb, void* ud);
void dsp_flmod_set_finished_cb(DspFLModHandle h, flmod_finished_cb_t cb, void* ud);
void dsp_flmod_set_error_cb   (DspFLModHandle h, flmod_error_cb_t    cb, void* ud);

/* Runtime control */
int  dsp_flmod_start    (DspFLModHandle h);
void dsp_flmod_stop     (DspFLModHandle h);
void dsp_flmod_set_gain (DspFLModHandle h, float gain);
void dsp_flmod_set_pause(DspFLModHandle h, int paused);
int  dsp_flmod_is_running(DspFLModHandle h);
int  dsp_flmod_check_device(void);

#ifdef __cplusplus
}
#endif
