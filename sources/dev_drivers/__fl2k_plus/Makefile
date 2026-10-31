# Makefile for libdspfl2k.so
# Builds the COHIWizard fl2k DSP+hardware shared library
#
# Requirements:
#   apt install libliquid-dev libosmo-fl2k-dev   (or build from source)
#   Libraries must be under /usr/local/{include,lib}
#
# Usage:
#   make          – build libdspfl2k.so
#   make clean    – remove build artefacts

CXX      = g++
CXXFLAGS = -std=c++17 -O3 -march=native -ffast-math -fPIC \
           -I/usr/local/include -Wall -Wextra -Wpedantic
LDFLAGS  = -shared -L/usr/local/lib
LIBS     = -lliquid -losmo-fl2k -lpthread -lm

TARGET   = libdspfl2k.so
SRC      = DspWorkerFL2K.cpp

.PHONY: all asan clean

all: $(TARGET)

$(TARGET): $(SRC) DspWorkerFL2K.h
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o $@ $< $(LIBS)
	@echo "Built $(TARGET) successfully."
	@echo "Run 'sudo ldconfig /usr/local/lib .' if needed to resolve at runtime."

# AddressSanitizer build – exact heap-overflow / use-after-free detection with line numbers.
# Usage after 'make asan':
#   LD_PRELOAD=$(gcc -print-file-name=libasan.so) \
#   ASAN_OPTIONS=detect_leaks=0,halt_on_error=1 \
#   python3 /path/to/COHIWizard.py 2>&1 | tee /tmp/cohiwizard_asan.log
asan: $(SRC) DspWorkerFL2K.h
	$(CXX) -std=c++17 -O1 -fPIC -fsanitize=address -fno-omit-frame-pointer \
	       -I/usr/local/include -Wall \
	       $(LDFLAGS) -fsanitize=address \
	       -o $(TARGET) $< $(LIBS)
	@echo "Built $(TARGET) with AddressSanitizer."

clean:
	rm -f $(TARGET)
