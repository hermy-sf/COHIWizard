# Makefile for libdspflmod.so  (fl2k_modulator)
#
# Requirements:
#   apt install libliquid-dev libosmo-fl2k-dev   (or build from source)
#
# Usage:
#   make          – build libdspflmod.so
#   make asan     – AddressSanitizer build
#   make clean    – remove build artefacts

CXX      = g++
CXXFLAGS = -std=c++17 -O3 -march=native -ffast-math -fPIC \
           -I/usr/local/include -Wall -Wextra -Wpedantic
LDFLAGS  = -shared -L/usr/local/lib
LIBS     = -lliquid -losmo-fl2k -lpthread -lm

TARGET   = libdspflmod.so
SRC      = DspWorkerFLMod.cpp

.PHONY: all asan clean

all: $(TARGET)

$(TARGET): $(SRC) DspWorkerFLMod.h
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o $@ $< $(LIBS)
	@echo "Built $(TARGET) successfully."

asan: $(SRC) DspWorkerFLMod.h
	$(CXX) -std=c++17 -O1 -fPIC -fsanitize=address -fno-omit-frame-pointer \
	       -I/usr/local/include -Wall \
	       $(LDFLAGS) -fsanitize=address \
	       -o $(TARGET) $< $(LIBS)
	@echo "Built $(TARGET) with AddressSanitizer."

clean:
	rm -f $(TARGET)
