# smisdr_raw: build of the up-conversion tool cohi_native_upconverter
# (source from COHI-Player-Universal, GPL-3.0, Claus Peter Gallenmiller / radiolab81)
#
#   make                 Linux / macOS:  ./cohi_native_upconverter
#   make MARCH=          without -march=native (binary that is moved to another machine)
#   make -f Makefile     Windows (MSYS2/MinGW):  make EXE=.exe
#
# -march=native makes the binary run ONLY on the CPU model it was built on; build on the
# target machine, or pass MARCH= (empty) / MARCH=-march=x86-64-v2 for a portable binary.

CXX      ?= g++
MARCH    ?= -march=native
CXXFLAGS ?= -O3 $(MARCH) -ffast-math
LDLIBS   ?= -lm -lpthread
EXE      ?=

TARGET := cohi_native_upconverter$(EXE)

.PHONY: all clean

all: $(TARGET)

$(TARGET): cohi_native_upconverter.cpp
	$(CXX) $(CXXFLAGS) -o $@ $< $(LDLIBS)

clean:
	rm -f cohi_native_upconverter cohi_native_upconverter.exe
