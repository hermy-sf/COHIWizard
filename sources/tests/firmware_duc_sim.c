/* firmware_duc_sim.c - runs a recorded I/Q stream (as sent to port 1234) through the parser, the
 * rate planner and the DSP of the parlioSDR firmware (duc_proto.c, sdr_plan.c, sdr_dsp.c) on the
 * host, in the same order as main/duc.c does it, and writes the RF samples (int16, signed, 16 bit
 * DAC) plus a summary.  Build:
 *   gcc -O2 -I <parlioSDR>/main -o sim firmware_duc_sim.c <parlioSDR>/main/{duc_proto,sdr_plan,sdr_dsp}.c -lm
 * Use:  ./sim stream.bin rf.bin [fixed_gain]      (no gain: AGC like the firmware default)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "duc_proto.h"
#include "sdr_dsp.h"
#include "sdr_plan.h"

#define OUT_CAP 1024
static sdr_dsp_t dsp;

int main(int argc, char **argv)
{
    if (argc < 3) { fprintf(stderr, "usage: sim stream.bin rf.bin [fixed_gain]\n"); return 2; }
    FILE *in = fopen(argv[1], "rb");
    FILE *out = fopen(argv[2], "wb");
    if (!in || !out) { perror("open"); return 2; }
    int use_agc = argc < 4;
    float gain = use_agc ? 0.f : (float)atof(argv[3]);

    fseek(in, 0, SEEK_END); long n = ftell(in); fseek(in, 0, SEEK_SET);
    uint8_t *buf = malloc(n);
    if (fread(buf, 1, n, in) != (size_t)n) return 2;

    sdr_dsp_global_init();
    duc_proto_t p; duc_proto_init(&p);
    uint32_t pend_fs = 0; double pend_shift = 0; int dirty = 0, cfg_ok = 0;
    uint32_t fs = 0, fs_out = 0; int hold = 0, planned_n = 0; double shift_used = 0;
    int16_t iq[2 * OUT_CAP];
    int16_t *rf = malloc(sizeof(int16_t) * 4 * 4 * 2 * SDR_BLOCK_MAX * 4);
    size_t total_out = 0, n_events = 0, n_bad_cfg = 0;
    unsigned seed = 12345;

    size_t pos = 0;
    while (pos < (size_t)n) {
        /* TCP delivers arbitrary pieces */
        seed = seed * 1103515245u + 12345u;
        size_t chunk = 1 + (seed >> 16) % 1460;
        if (chunk > n - pos) chunk = n - pos;
        size_t off = 0;
        while (off < chunk) {
            size_t used = 0, got = 0; duc_event_t ev;
            duc_feed_t r = duc_proto_feed(&p, buf + pos + off, chunk - off, &used, iq, OUT_CAP, &got, &ev);
            off += used;
            if (got) {
                if (dirty) {
                    sdr_plan_t pl;
                    if (fs_out == 0 || 1) {
                        if (pend_fs && sdr_plan_rate(pend_fs, pend_shift, 10000000u, &pl) == 0) {
                            const int fast = pend_fs >= SDR_FAST_FS_HZ;
                            sdr_dsp_cfg_t dc = { .bits = 16, .offset_binary = 0,
                                                 .hold = fast ? pl.n / 2 : pl.n / 4,
                                                 .phase_inc = sdr_phase_inc(pend_shift, pl.fs_out), .fast = fast };
                            dsp.agc = use_agc; dsp.manual_gain = gain;
                            sdr_dsp_init(&dsp, &dc);
                            fs = pend_fs; fs_out = pl.fs_out; hold = dc.hold; planned_n = pl.n; shift_used = pend_shift;
                            cfg_ok = 1;
                        } else { cfg_ok = 0; n_bad_cfg++; }
                    }
                    dirty = 0;
                }
                if (cfg_ok) {
                    size_t done = 0;
                    while (done < got) {
                        size_t k = got - done < SDR_BLOCK_MAX ? got - done : SDR_BLOCK_MAX;
                        size_t outn = sdr_dsp_process(&dsp, iq + 2 * done, k, rf);
                        fwrite(rf, sizeof(int16_t), outn, out);
                        total_out += outn; done += k;
                    }
                }
            }
            if (r == DUC_FEED_EVENT) {
                n_events++;
                if (ev.type == DUC_EV_SHIFT) { pend_shift = duc_ftw_to_hz_signed(ev.value); dirty = 1; }
                else if (ev.type == DUC_EV_RATE) { pend_fs = duc_ftw_to_rate_hz(ev.value); dirty = 1; }
            }
        }
        pos += chunk;
    }
    printf("fs=%u shift=%.3f fs_out=%u N=%d hold=%d pairs=%llu cmds=%u bad=%u drop_i=%u drop_q=%u events=%zu out=%zu "
           "agc_gain=%.4f last_peak=%.4f bad_cfg=%zu\n",
           fs, shift_used, fs_out, planned_n, hold, (unsigned long long)p.n_pairs, p.n_cmds, p.n_bad,
           p.drop_i, p.drop_q, n_events, total_out, dsp.gain, dsp.last_peak, n_bad_cfg);
    fclose(out);
    return 0;
}
