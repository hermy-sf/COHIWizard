/*
 * DspWorkerFL2K.h
 * C API for the COHIWizard DSP+FL2K engine.
 *
 * Replaces the ffmpeg + fl2k_file pipeline with a single C++ shared library
 * that does IQ resampling / NCO mixing (via liquiddsp) and drives the fl2k
 * USB-VGA DAC directly (via libosmo-fl2k).
 *
 * Usage from Python (ctypes):
 *   lib = ctypes.CDLL("libdspfl2k.so")
 *   h   = lib.dsp_fl2k_create()
 *   lib.dsp_fl2k_configure(h, target_rate, shift_freq, gain, use_agc, fnames, n)
 *   lib.dsp_fl2k_start(h)          # non-blocking
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

/* Callback types  (all called from DSP thread, Python GIL acquired by ctypes) */
typedef void (*dsp_monitor_cb_t) (const float* samples, int n,    void* ud);
typedef void (*dsp_progress_cb_t)(float pct,                       void* ud);
typedef void (*dsp_finished_cb_t)(void* ud);
typedef void (*dsp_error_cb_t)   (const char* msg,                 void* ud);
typedef void (*dsp_nextfile_cb_t)(const char* path,                void* ud);

/* Lifecycle */
DspFL2KHandle dsp_fl2k_create  (void);
void          dsp_fl2k_destroy (DspFL2KHandle h);

/*
 * Configure the engine.  Must be called before dsp_fl2k_start.
 *   target_rate  – fl2k DAC sample rate in Hz (e.g. 10 000 000)
 *   shift_freq   – LO shift frequency in Hz (carrier / centre frequency)
 *   gain         – manual gain factor [0 … 1], only used when use_agc == 0
 *   use_agc      – 1 = automatic gain, 0 = manual
 *   filenames    – array of WAV file paths (NULL-terminated strings)
 *   num_files    – length of filenames array
 * Returns 0 on success.
 */
int  dsp_fl2k_configure(DspFL2KHandle h,
                        float         target_rate,
                        float         shift_freq,
                        float         gain,
                        int           use_agc,
                        const char**  filenames,
                        int           num_files);

/* Register optional callbacks (may be NULL).  Safe to set before start. */
void dsp_fl2k_set_monitor_cb (DspFL2KHandle h, dsp_monitor_cb_t  cb, void* ud);
void dsp_fl2k_set_progress_cb(DspFL2KHandle h, dsp_progress_cb_t cb, void* ud);
void dsp_fl2k_set_finished_cb(DspFL2KHandle h, dsp_finished_cb_t cb, void* ud);
void dsp_fl2k_set_error_cb   (DspFL2KHandle h, dsp_error_cb_t    cb, void* ud);
void dsp_fl2k_set_nextfile_cb(DspFL2KHandle h, dsp_nextfile_cb_t cb, void* ud);

/* Start processing (non-blocking: launches DSP + FL2K threads). Returns 0 OK. */
int  dsp_fl2k_start    (DspFL2KHandle h);

/* Request stop.  Blocks until both threads have exited. */
void dsp_fl2k_stop     (DspFL2KHandle h);

/* Pause / resume without stopping.  Thread-safe. */
void dsp_fl2k_set_pause(DspFL2KHandle h, int paused);

/* Update gain on the fly (e.g. from GUI slider).  Thread-safe. */
void dsp_fl2k_set_gain (DspFL2KHandle h, float gain);

/* Poll: 1 if both threads are still running, 0 otherwise. */
int  dsp_fl2k_is_running(DspFL2KHandle h);

/*
 * Check whether an fl2k device is present.
 * Opens device 0, immediately closes it.
 * Returns 0 if a device was found, -1 otherwise.
 */
int  dsp_fl2k_check_device(void);

/*
 * Seek the WAV file read pointer to the requested position.
 * Thread-safe; the DSP thread performs the seek at the next block boundary
 * and also flushes the ring buffer so output reflects the new position quickly.
 *
 *   byte_pos – byte offset (same coordinate as Python's file.seek())
 *   whence   – 0 = from start of file, 1 = from current position, 2 = from end
 */
void dsp_fl2k_seek(DspFL2KHandle h, int64_t byte_pos, int whence);

#ifdef __cplusplus
}
#endif
