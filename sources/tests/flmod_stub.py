"""Builds libdspflmod from the REAL source (dev_drivers/libs/DspWorkerFLMod.cpp) for the tests.

The shipped libdspflmod.so is linked against libosmo-fl2k, which is only present on machines
with the FL2K software; the pull API the live drivers use does not touch the dongle.  The
build therefore gets a tiny stand-in for <osmo-fl2k.h> (types and no-op functions)."""
import os
import shutil
import subprocess

HEADER = r'''
#pragma once
#include <stdint.h>
#define FL2K_BUF_LEN (1280 * 1024)
#define FL2K_SUCCESS 0
#define FL2K_INACTIVE (-1)
typedef struct fl2k_dev fl2k_dev_t;
typedef struct {
    int sampletype_signed, using_zerocopy, device_error;
    uint32_t len, underflow_cnt;
    char *r_buf, *g_buf, *b_buf;
    void *ctx;
} fl2k_data_info_t;
typedef void (*fl2k_tx_cb_t)(fl2k_data_info_t *);
extern "C" {
int fl2k_open(fl2k_dev_t **, uint32_t);
int fl2k_close(fl2k_dev_t *);
int fl2k_set_sample_rate(fl2k_dev_t *, uint32_t);
int fl2k_start_tx(fl2k_dev_t *, fl2k_tx_cb_t, void *, uint32_t);
int fl2k_stop_tx(fl2k_dev_t *);
uint32_t fl2k_get_device_count(void);
}
'''
IMPL = r'''
#include "osmo-fl2k.h"
extern "C" {
int fl2k_open(fl2k_dev_t **, uint32_t) { return -1; }
int fl2k_close(fl2k_dev_t *) { return 0; }
int fl2k_set_sample_rate(fl2k_dev_t *, uint32_t) { return -1; }
int fl2k_start_tx(fl2k_dev_t *, fl2k_tx_cb_t, void *, uint32_t) { return -1; }
int fl2k_stop_tx(fl2k_dev_t *) { return 0; }
uint32_t fl2k_get_device_count(void) { return 0; }
}
'''


def build(directory, sources_dir):
    """-> path of the built libdspflmod.so or None (no compiler / build error)"""
    compiler = shutil.which("g++") or shutil.which("c++")
    if compiler is None:
        return None
    with open(os.path.join(directory, "osmo-fl2k.h"), "w") as fh:
        fh.write(HEADER)
    with open(os.path.join(directory, "fl2k_stub.cpp"), "w") as fh:
        fh.write(IMPL)
    out = os.path.join(directory, "libdspflmod.so")
    libs = os.path.join(sources_dir, "dev_drivers", "libs")
    result = subprocess.run(
        [compiler, "-std=c++17", "-O2", "-fPIC", "-shared", "-I", directory, "-I", libs,
         "-o", out, os.path.join(libs, "DspWorkerFLMod.cpp"),
         os.path.join(directory, "fl2k_stub.cpp"), "-lpthread", "-lm"],
        capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr[-2000:])
        return None
    return out
