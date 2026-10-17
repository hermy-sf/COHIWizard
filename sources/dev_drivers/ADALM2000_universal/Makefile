CXX      = g++
CXXFLAGS = -std=c++17 -O3 -march=native -ffast-math -fPIC
LDFLAGS  = -shared -lpthread -lm

all: libdspadlm.so

libdspadlm.so: DspWorkerADALM.cpp DspWorkerADALM.h
	$(CXX) $(CXXFLAGS) $(LDFLAGS) $< -o $@

clean:
	rm -f libdspadlm.so
