CXX      := g++
CXXFLAGS := -std=c++17 -O3 -march=native -ffast-math -fPIC
TARGET   := libdspfl2k.so

all: $(TARGET)

$(TARGET): DspWorkerFL2K.cpp DspWorkerFL2K.h
	$(CXX) $(CXXFLAGS) -shared -o $@ $< -losmo-fl2k -lpthread -lm

clean:
	rm -f $(TARGET)

.PHONY: all clean
