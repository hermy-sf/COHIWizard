import psutil
import os
import numpy as np
import libm2k
import threading
import queue
import platform
import subprocess
import time

output_chunks = []
chunk_queue = queue.Queue(maxsize=20)  # Buffer size = 20 blocks

def pipe_reader_thread(stdout_pipe, buffer_size):
    try:
        while True:
            chunk = stdout_pipe.read(buffer_size)
            if not chunk:
                break
            chunk_queue.put(chunk)  # non-blocking push into queue
    except Exception as e:
        print(f"Reader thread error: {e}")
    finally:
        chunk_queue.put(None)  # Signal: EOF

def pusher_thread(ao):
    try:
        while True:
            chunk = chunk_queue.get()
            if chunk is None:
                break  # EOF
            samples = np.frombuffer(chunk, dtype=np.float32).tolist()
            if ao == None:
                print(f"pusher thread chunk begin: {chunk[:10]}... end: {chunk[-10:]}")
            else:
                ao.push(0, samples)
    except Exception as e:
        print(f"Pusher thread error: {e}")

def gen_ffmpeg_cmd(ffmpeg_path, SRAdalm = 2500000, sampling_rate = 1250000 , lo_shift = 1125000, preset_volume = 1):
    """generates ffmpeg command for reading from stdin, complex modulation to target RF band
    and writing to stdout.

    :param ffmpeg_path: path to the ffmpeg executable
    :type ffmpeg_path: str
    :param SRAdalm: effective Sampling rate of transfer to the ADALM2000
    :type SRDdalm: int
    :param sampling_rate: sampling rate of the IQ file to be processed
    :type sampling_rate: int
    :param lo_shift: local oscillator shift
    :type lo_shift: int
    :param preset_volume: preset volume level
    :type preset_volume: int        
    :return: ffmpeg command as a list of strings
    :rtype: list[str]
    """
    formatstring = "s16le"
    #SRAdalm = 7500000 #maximum DAC SR of Adalm

    a = (np.tan(np.pi * lo_shift / SRAdalm) - 1) / (np.tan(np.pi * lo_shift / SRAdalm) + 1)

    ffmpeg_cmd = [
        os.path.join(str(ffmpeg_path),"ffmpeg"), "-y", "-loglevel", "error", "-hide_banner",
        "-f", formatstring, "-ar", str(sampling_rate), "-ac", "2", "-i", "-",  # Lese von stdin
        "-filter_complex",
        "[0:a]aresample=osr=" + str(SRAdalm) + ",channelsplit=channel_layout=stereo [re][im];"
        "sine=frequency=" + str(lo_shift) + ":sample_rate="  + str(SRAdalm) + "[sine_base];"
        "[sine_base] asplit=2[sine_sin1][sine_sin2];"
        "[sine_sin2]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[sine_cos];"
        "[re][sine_cos]amultiply[mod_re];"
        "[im][sine_sin1]amultiply[mod_im];"
        "[mod_im]volume=volume="  + str(preset_volume) + "[part_im];"
        "[mod_re]volume=volume="  + str(preset_volume) + "[part_re];"
        "[part_re][part_im]amix=inputs=2:duration=shortest[out]",
        #"-map", "[out]", "-c:a", "pcm_s8", "-f", "caf", "-"
        #"-map", "[out]", "-c:a", "pcm_f32le", "-f", "caf", str(outfile)
        "-map", "[out]", "-c:a", "pcm_f32le", "-f", "f32le", "pipe:1"  # Schreibe in die Standardausgabe (stdout)
        ]

    return ffmpeg_cmd

def maximize_OSR(SRDAC, lo_shift, sampling_rate):
    """Calculate oversampling OSR from SRDAC and required Nyquist frequency
    f_nyquist = (lo_shift+sampling_rate/2))
    OSR is tha value which divides SRDAC such that 
    (1) SRDAC/OSR >= 2 * f_nyquist
    (2) r = SRDAC/OSR is integer, ideally r is an integer multiple of sampling_rate 

    :param SRDAC: sampling rate of the ADALM DAC (clock)
    :type SRDAC: int
    :param lo_shift: central frequency f the band plus offset (LO frequency)
    :type lo_shift: int
    :param sampling_rate: bandwidth of the complex IQ signal == sampling rate of IQ file
    :type sampling_rate: int
    
    :return: oversampling rate OSR

    """
    f_nyquist = lo_shift+sampling_rate/2
    r_max = SRDAC / (2 *f_nyquist) # maximum allowable OSR
    for OSR in np.arange(int(np.floor(r_max)),1,-1):
        r = SRDAC / OSR
        if SRDAC % r == 0:
            break
    return OSR

######################################################################################################

def stream_to_adalm_file(input_file, ffmpeg_path, SRDAC, sampling_rate, lo_shift, buffer_size=4096):
    """
    Streamt einen Bytestream aus einer Datei und übergibt ihn per stdin an fl2k_file.

    :param input_file: Pfad zur Eingabedatei.
    :param sampling_rate: Abtastrate für fl2k_file (z. B. 10000000 für 10 MS/s).
    :param fl2k_file_path: Pfad zur fl2k_file-Binärdatei.
    :param buffer_size: Puffergröße für das Streaming (Standard: 4096 Bytes).
    """
    ctxopen = False
    ix = 0
    TEST = False
    OSR = maximize_OSR(SRDAC, lo_shift, sampling_rate)
    preset_volume = 100.0  # Volume preset for the output

    #outfile =  os.path.join(os.getcwd(),"testout.raw")
    #ADALM cmd:
    RF_channel = 0  # DAC-Kanal für Ausgabe des IQ Files
    sine_channel = 1 #Kanal für Upmixing LO-Signal
    LO_upmix_freq = 2000000
    sine = 0.9 * np.sin(np.arange(0,2*np.pi,0.1*np.pi * LO_upmix_freq * OSR /SRDAC))
    try:
        ctx = libm2k.m2kOpen()
        ctx.calibrateDAC()
        ctxopen = True
        ao = ctx.getAnalogOut()
        ao.setSampleRate(RF_channel, SRDAC)
        print(f"ADALM2000: OSR: {OSR}")
        ao.setOversamplingRatio(RF_channel, int(OSR)) ### TODO: set oversampling ratio according band requirements; 
        #For MW we could live with a value between 15 and 20 
        ao.enableChannel(RF_channel, True)
        ao.setKernelBuffersCount(0, 32)
        ao.setCyclic(RF_channel, False)
        ao.enableChannel(sine_channel, True) 
        ao.setCyclic(sine_channel, True)  # Kanal 1 im Wiederholmodus
        ao.push(sine_channel, sine.tolist())
    except:
        ao = None
        print("ADALM not initialized")

    #Starte ffmpeg Prozess:
    try:
        ffmpeg_cmd = gen_ffmpeg_cmd(ffmpeg_path, SRDAC/OSR, sampling_rate , lo_shift , preset_volume )

        # Prozess starten
        ffmpeg_process = subprocess.Popen(ffmpeg_cmd, 
            stdin=subprocess.PIPE, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )

    except FileNotFoundError:
        print(f"Input file not found")
        return()
    except subprocess.SubprocessError as e:
        print(f"Error when executing fl2k_file: {e}")
        return()    
    except Exception as e:
        print(f"Unexpected error: {e}")
        return()    
    psutil.Process(ffmpeg_process.pid).nice(psutil.IDLE_PRIORITY_CLASS)

    reader = threading.Thread(target=pipe_reader_thread, args=(ffmpeg_process.stdout, buffer_size))
    reader.start()
    pusher = threading.Thread(target=pusher_thread, args=(ao,))
    pusher.start()

    while True:
        if ix > 1: break
        print (f"iteration {ix}")
        ix += 1
        try:
            # Öffnen der Eingabedatei im Binärmodus
            with open(input_file, "rb") as f:

                # Lesen und Streamen der Datei in Blöcken
                while chunk := f.read(buffer_size):
                    if not chunk:
                        break  # EOF
                    print("readchunk")
                    ffmpeg_process.stdin.write(chunk)
                    ffmpeg_process.stdin.flush()
                    #processed_chunk = ffmpeg_process.stdout.read(4*buffer_size)

                print(f"ffmpeg_poll: {ffmpeg_process.poll()}")
                
        except FileNotFoundError:
            print(f"Die Datei {input_file} wurde nicht gefunden.")
        except subprocess.SubprocessError as e:
            print(f"Fehler beim Ausführen von fl2k_file: {e}")
        except Exception as e:
            print(f"Ein unerwarteter Fehler ist aufgetreten: {e}")

    ffmpeg_process.stdin.close()  # Wichtig: stdin schließen
    ffmpeg_process.stdout.close()  # Falls stdout genutzt wird
    ffmpeg_process.terminate()  # Beendet den Prozess sanft
    ffmpeg_process.wait()  # Wartet auf das Ende
    #TODO TODO TODO: activate pusher
    reader.join()
    pusher.join()
    print("Streaming abgeschlossen.")

    print("DONE")
    
    if ao is not None:
        try:
            print("close ADALM ao object")
            ao.push(0, [0.0] * 5000)  # send a final block of zero data
            time.sleep(0.01)
            ao.enableChannel(RF_channel, False)
            ao.setSampleRate(RF_channel, 0)  # set sample rate to 0 to disable RF_channel
            ao.enableChannel(sine_channel, False)
            ao.setSampleRate(sine_channel, 0)  # set sample rate to 0 to disable RF_channel            
        except:
            print("Error closing ADALM2000 context or disabling channel.")
            pass
        libm2k.contextClose(ctx)
    

system = platform.system().lower()
if system == "linux":
    ffmpeg_path = ""
else:    
    rootpath = "C:/Users/scharfetter_admin/Documents/COHIRADIA/Softwareentwicklung/COHIWizard_2023/sources"
    ffmpeg_path = os.path.join(rootpath,"ffmpeg-master-latest-win64-gpl-shared/bin")

#ffmpeg_executable = os.path.join(str(ffmpeg_path),"ffmpeg")

buffer_size =  4096*256*32 #4096*16 #
SRDAC = 75000000 #7500000 #maximum DAC SR of Adalm
sampling_rate = 1250000
lo_shift = 1125000
#SRDAC = int(lo_shift*2)
wav_path = "C:/Users/scharfetter_admin/Documents/COHIRADIA/Data/SDR_Testaufzeichnungen"
input_file = os.path.join(wav_path, "A_gaincorrSDRuno_20220910_095058Z_1125kHz.wav")
stream_to_adalm_file(input_file, ffmpeg_path, SRDAC, sampling_rate, lo_shift, buffer_size)