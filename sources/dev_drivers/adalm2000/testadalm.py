import subprocess
import numpy as np
import libm2k
import threading
import queue
import time
import io
from PyQt5.QtCore import *
import psutil


# def ffmpeg_log_reader():
#     for line in ffmpeg_stderr_text:
#         print("FFmpeg >>>>>>>>>>>>>>>>>>>>>>>>>", line.strip())


sourcefile_path = 'C:/Users/scharfetter_admin/Documents/COHIRADIA/Data/SDR_Testaufzeichnungen/A_gaincorrSDRuno_20220910_095058Z_1125kHz.wav'
targetfile_path = 'C:/Users/scharfetter_admin/Documents/COHIRADIA/Data/SDR_Testaufzeichnungen/A_gaincorrSDRuno_20220910_095058Z_1125kHz_ADALM.raw'
formatstring = "s16le"

sampling_rate = 1250000
lo_shift = 1125000
SRDAC = 7500000 #maximum DAC SR of Adalm
OSR = np.floor(SRDAC/(np.floor((lo_shift+sampling_rate/2)*3))) #TODO: factor 3 is 2*1.5, 1.5 has 50% margin above Nyquist; investigate more thoroughly and optimize !
tSR = SRDAC
mutex = QMutex()
preset_volume = 1.0  # Volume preset for the output
a = (np.tan(np.pi * lo_shift / tSR) - 1) / (np.tan(np.pi * lo_shift / tSR) + 1)
try:
    ffmpeg_cmd = [
    "ffmpeg", "-y", "-report", "-loglevel", "debug", "-hide_banner",  
    "-f", formatstring, "-ar", str(sampling_rate), "-ac", "2", "-i", "-",  # read from stdin
    "-filter_complex",
    "[0:a]aresample=osr=" + str(tSR) + ",channelsplit=channel_layout=stereo [re][im];"
    "sine=frequency=" + str(lo_shift) + ":sample_rate="  + str(tSR) + "[sine_base];"
    "[sine_base] asplit=2[sine_sin1][sine_sin2];"
    "[sine_sin2]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[sine_cos];"
    "[re][sine_cos]amultiply[mod_re];"
    "[im][sine_sin1]amultiply[mod_im];"
    "[mod_im]volume=volume=" + str(preset_volume) + "[part_im];"
    "[mod_re]volume=volume=" + str(preset_volume) + "[part_re];"
    "[part_re][part_im]amix=inputs=2:duration=shortest[out]",
    #ORIGINAL: 
    "-map", "[out]", "-c:a", "pcm_f32le", "-f", "caf", "-" # write to stdout --> ADALM
    #"-map", "[out]", "-c:a", "pcm_f32le", "-f", "caf", str(targetfile_path)
    #"-map", "[out]", "-acodec", "pcm_f32le", "-ac", "1", "-ar", str(tSR), "-" # write to stdout --> ADALM
    ]
    print(f"<<<<<<<<<<<<<<< ADALM 2000: ffmpeg_command: {ffmpeg_cmd}")
    channel = 0  # DAC-Kanal für Ausgabe

            
    ctx = libm2k.m2kOpen()
    ctx.calibrateDAC()
    ao = ctx.getAnalogOut()
    ao.setSampleRate(channel, SRDAC)
    print(f"ADALM2000: type of OSR: {type(OSR)}")
    ao.setOversamplingRatio(channel, int(OSR)) ### TODO: set oversampling ratio according band requirements; 
    #For MW we could live with a value between 15 and 20 
    ao.enableChannel(channel, True)

    DATABLOCKSIZE = 4096*256*16*8
    ADALM_blocksize = DATABLOCKSIZE
    ffmpeg_process = subprocess.Popen(ffmpeg_cmd, 
        stdin=subprocess.PIPE, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,  # or subprocess.STDOUT if you want to see logs
        #text=False,
        # encoding='utf-8',
        #bufsize=0
        bufsize=DATABLOCKSIZE)  # 
except FileNotFoundError:
    print(f"Input file not found, probably ffmpeg path is wrong")
except subprocess.SubprocessError as e:
    print(f"Error when executing fl2k_file: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
psutil.Process(ffmpeg_process.pid).nice(psutil.IDLE_PRIORITY_CLASS)
#ffmpeg_stderr_text = io.TextIOWrapper(ffmpeg_process.stderr, encoding='utf-8', errors='replace')
#threading.Thread(target=ffmpeg_log_reader, daemon=True).start()


# Queue for outgoing data blocks
# input_queue = queue.Queue()
# output_queue = queue.Queue()

# === Writer Thread ===
# def writer_thread():
#     while True:
#         block = input_queue.get()
#         if block is None:
#             break  # signal to end
#         ffmpeg_process.stdin.write(block.astype(np.int16).tobytes())

# # === Reader Thread ===
# def reader_thread():
#     DATABLOCKSIZE = 1024
#     while True:
#         print("Reader thread waiting for data...")
#         if ffmpeg_process.poll() is not None:
#             print("FFmpeg process terminated, exiting reader thread.")
#             break
#         print("trying to read raw data from ffmpeg_process stdout")
#         # Read raw data from ffmpeg process stdout
#         raw = ffmpeg_process.stdout.read(DATABLOCKSIZE * 4)  # 4 bytes per float32
#         print(f"Reader thread read raw data of size: {len(raw)}")
#         if not raw:
#             print("waiting for data in reader thread")
#             time.sleep(1)  # EOF
            
#         output_block = np.frombuffer(raw, dtype=np.float32)
#         output_queue.put(output_block)
#     print("Reader thread exiting...")
# # Start threads
# threading.Thread(target=writer_thread, daemon=True).start()
# threading.Thread(target=reader_thread, daemon=True).start()

fileHandle = open(sourcefile_path, 'rb')
fileHandle.seek(216, 1)
count = 0
data = np.empty(DATABLOCKSIZE, dtype=np.int16)
size = fileHandle.readinto(data)
# for _ in range(30):
#     size = fileHandle.readinto(data)
#     if size <= 0:
#         break
#     aux1 = data[:size]
#     # input_queue.put(aux1)
#     # print("Pre-filling input queue")

while size > 0:
    print(f"iteration loop entered play_loop_filelist: size: {size} count: {count}")
    mutex.lock()
    if ffmpeg_process.poll() != None:
        print("Error: ffmpeg process terminated")
        mutex.unlock()
        break
    else:
        print("ffmpeg process still running")
        mutex.unlock()
    aux1 = data[0:size]
    try: 
        aux1 = data[0:size]
            
        #input_queue.put(aux1)
        # Wait for processed output
        #raw = output_queue.get()
        print("ffmpeg write to stdin")
        ffmpeg_process.stdin.write(aux1)
        #ffmpeg_process.stdin.write(aux1.astype(np.int16))
        ffmpeg_process.stdin.flush()
        print(f"ffmpeg_poll: {ffmpeg_process.poll()}")
        #ffmpeg_process.stdin.flush()
        #ffmpeg_process.stdin.write(aux1.astype(np.int16))
        print(f"ffmpeg_process.stdout.read(ADALM_blocksize* 4) {ADALM_blocksize* 4}")
        raw = ffmpeg_process.stdout.read(ADALM_blocksize)
        samples = np.frombuffer(raw, dtype=np.float32)
        print(f"ffmpeg_process.stdout.read(ADALM_blocksize* 4) samples: {samples}, len(samples): {len(samples)}")
        if samples.size == 0:
            print("No samples read from ffmpeg process, exiting.")
            break           

        print("ADALM push command reached")
        ao.push([samples])  # Mono-Ausgabe auf ADALM2000
    except BlockingIOError:
        print("Blocking data socket error in playloop worker")
        break
    except ConnectionResetError:
        print("Diagnostic Message: Connection data socket error in playloop worker")
        break
    except Exception as e:
        print("Class e type error data transfer error in playloop worker")
        print(e)
        break
    except BrokenPipeError:
        print(" FFMPEG-Prozess terminated or pipe closed. Please restart procedure.")
        break
    size = fileHandle.readinto(data)

    count += 1

print("close file ")
fileHandle.close()

ffmpeg_process.stdin.close()  # close stdin
ffmpeg_process.stdout.close()  # close stdout
ffmpeg_process.terminate()  # stop process gently
ffmpeg_process.wait()  # wait for process termination
try:
    ao.enableChannel(channel, False)
    ao.setSampleRate(channel, 0)  # set sample rate to 0 to disable channel
    libm2k.context.m2kClose(ctx)
except:
    print("Error closing ADALM2000 context or disabling channel.")
    pass


