CXX      := g++
CXXFLAGS := -std=c++17 -O3 -march=native -ffast-math -fPIC
TARGET   := libdspflmod.so

all: $(TARGET)

$(TARGET): DspWorkerFLMod.cpp DspWorkerFLMod.h
	$(CXX) $(CXXFLAGS) -shared -o $@ $< -losmo-fl2k -lpthread -lm

clean:
	rm -f $(TARGET)

.PHONY: all clean
