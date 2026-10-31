# Makefile – Linux build of the shared DSP libraries used by several dev_drivers
#
#   libdspfl2k.so   (DspWorkerFL2K)  – fl2k_universal Mode A (IQ file ± audio overlay)
#   libdspflmod.so  (DspWorkerFLMod) – fl2k_universal Mode B, stemlab_eff_universal (pull API)
#
# Usage:
#   make           – build both libraries
#   make clean     – remove build artefacts

CXX      := g++
CXXFLAGS := -std=c++17 -O3 -march=native -ffast-math -fPIC
TARGETS  := libdspfl2k.so libdspflmod.so

all: $(TARGETS)

libdspfl2k.so: DspWorkerFL2K.cpp DspWorkerFL2K.h
	$(CXX) $(CXXFLAGS) -shared -o $@ $< -losmo-fl2k -lpthread -lm

libdspflmod.so: DspWorkerFLMod.cpp DspWorkerFLMod.h
	$(CXX) $(CXXFLAGS) -shared -o $@ $< -losmo-fl2k -lpthread -lm

clean:
	rm -f $(TARGETS)

.PHONY: all clean
