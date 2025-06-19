import subprocess
import psutil
import os
import numpy as np

def stream_to_fl2k_file(input_file, target_sampling_rate, buffer_size=4096, fl2k_file_path="fl2k_file"):
    """
    Streamt einen Bytestream aus einer Datei und übergibt ihn per stdin an fl2k_file.

    :param input_file: Pfad zur Eingabedatei.
    :param sampling_rate: Abtastrate für fl2k_file (z. B. 10000000 für 10 MS/s).
    :param fl2k_file_path: Pfad zur fl2k_file-Binärdatei.
    :param buffer_size: Puffergröße für das Streaming (Standard: 4096 Bytes).
    """
    ix = 0
    lo_shift = 1125000 +2000000
    # delay = 1/lo_shift/4*1000
    sampling_rate = 1250000
    tSR = 10000000*(1 + np.floor((lo_shift+sampling_rate/2)*4/10000000))
    tSR = min(100000000,tSR)
    a = (np.tan(np.pi * lo_shift / tSR) - 1) / (np.tan(np.pi * lo_shift / tSR) + 1)
    ###################
    #Starte ffmpeg Prozess:

    # try:
    #     ffmpeg_cmd = [
    #     "ffmpeg", "-y", "-loglevel", "error", "-hide_banner",  
    #     "-f", "s16le", "-ar", str(sampling_rate), "-ac", "2", "-i", "-",  # Lese von stdin
    #     "-filter_complex",
    #     "[0:a]aresample=osr=" + str(tSR) + ",channelsplit=channel_layout=stereo [re][im];"
    #     "sine=frequency=" + str(lo_shift) + ":sample_rate="  + str(tSR) + "[sine_base];"
    #     "[sine_base] asplit=2[sine_sin1][sine_sin2];"
    #     "[sine_sin2]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[sine_cos];"
    #     #"[sine_sin2]biquad=b0=-0.461006:b1=1:b2=0:a0=1:a1=-0.461006:a2=0[sine_cos];"
    #     "[re][sine_cos]amultiply[mod_re];"
    #     "[im][sine_sin1]amultiply[mod_im];"
    #     "[mod_im]volume=volume=200[part_im];"
    #     "[mod_re]volume=volume=200[part_re];"
    #     "[part_re][part_im]amix=inputs=2:duration=shortest[out]",
    #     "-map", "[out]", "-c:a", "pcm_s8", "-f", "caf", "-"
    #     ]
    #     ## "-map", "[out]", "-c:a", "pcm_s8", "-f", "caf", "-"

    #     # Prozess starten
    #     ffmpeg_process = subprocess.Popen(ffmpeg_cmd, 
    #         stdin=subprocess.PIPE, 
    #         stdout=subprocess.PIPE, 
    #         stderr=subprocess.PIPE
    #     )

    # except FileNotFoundError:
    #     print(f"Input file not found")
    #     return()
    # except subprocess.SubprocessError as e:
    #     print(f"Error when executing fl2k_file: {e}")
    #     return()    
    # except Exception as e:
    #     print(f"Unexpected error: {e}")
    #     return()    
    # psutil.Process(ffmpeg_process.pid).nice(psutil.IDLE_PRIORITY_CLASS)

    # Starten von fl2k_file mit den entsprechenden Parametern
    try:

        # FIFO-Dateien erstellen
        fifo_r = "fifo_r"
        fifo_g = "fifo_g"

        if not os.path.exists(fifo_r):
            os.mkfifo(fifo_r)
        if not os.path.exists(fifo_g):
            os.mkfifo(fifo_g)

        # Starte fl2k_rgb mit den FIFO-Dateien als Eingabe für R und G
        fl2k_proc = subprocess.Popen(
            ["fl2k_file2", "-d", "0", "-s", str(tSR),
            "-R8", "-R", fifo_r, "-G8", "-G", fifo_g, "-B8", "-B", "/dev/null"],
            stdin=subprocess.DEVNULL,
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

    while True:
        if ix > 10: break
        print (f"iteration {ix}")
        ix += 1
        try:
            with open(fifo_r, "wb") as fr, open(fifo_g, "wb") as fg, open(input_file, "rb") as f:
                # while True:
                #     # Erzeuge zufällige 16-Bit-Daten als Beispiel
                #     data = np.random.randint(0, 65536, buffer_size, dtype=np.uint16)

                #     # Zerlege die 16-Bit-Werte in High-Byte (R) und Low-Byte (G)
                #     r_data = (data >> 8).astype(np.uint8).tobytes()
                #     g_data = (data & 0xFF).astype(np.uint8).tobytes()

                #     # Schreibe die Daten in die FIFOs
                #     fr.write(r_data)
                #     fg.write(g_data)
                #     fr.flush()
                #     fg.flush()

            # Öffnen der Eingabedatei im Binärmodus
            #with open(input_file, "rb") as f:

                # Lesen und Streamen der Datei in Blöcken
                while chunk := f.read(buffer_size):
                    #print("readchunk")
                    # ffmpeg_process.stdin.write(chunk)
                    # ffmpeg_process.stdin.flush()

                    # Zerlege die 16-Bit-Werte in High-Byte (R) und Low-Byte (G)
                    # Blind the last 4 or 6 bit of the low byte so as to produce 12 or 10 bit in total
                    r_data = (chunk >> 8).astype(np.uint8).tobytes()
                    #original 8 bit: g_data = (data & 0xFF).astype(np.uint8).tobytes()
                    #only 4 bit g_data = (data & 0xFF).astype(np.uint8).tobytes()
                    g_data = (chunk & 0x0C).astype(np.uint8).tobytes() #take only 2 highest bit of LO Byte --> 10 bit effective
                    # Schreibe die Daten in die FIFOs
                    fr.write(r_data)
                    fg.write(g_data)
                    fr.flush()
                    fg.flush()

            print(f"fl2k_poll: {fl2k_proc.poll()}")

        except BrokenPipeError:
            pass
        except FileNotFoundError:
            print(f"Die Datei {input_file} wurde nicht gefunden.")
        except subprocess.SubprocessError as e:
            print(f"Fehler beim Ausführen von fl2k_file: {e}")
        except Exception as e:
            print(f"Ein unerwarteter Fehler ist aufgetreten: {e}")
        finally:
            fl2k_proc.terminate()
            os.remove(fifo_r)
            os.remove(fifo_g)


    # ffmpeg_process.stdin.close()  # Wichtig: stdin schließen
    # ffmpeg_process.stdout.close()  # Falls stdout genutzt wird
    # ffmpeg_process.terminate()  # Beendet den Prozess sanft
    # ffmpeg_process.wait()  # Wartet auf das Ende
    fl2k_proc.terminate()
    os.remove(fifo_r)
    os.remove(fifo_g)
    stdout, stderr = fl2k_proc.communicate()  # Warten, bis fl2k_file beendet ist
    # Ausgabe der Ergebnisse
    print("fl2k output:")
    print(stdout.decode())
    if stderr:
        print("fl2k_file errors:")
        print(stderr.decode())

    print("DONE")

# Beispielaufruf
#TODO TODO: filepath f fl2krgb anpassen
fl2k_file_path = os.path.join(os.getcwd(),"dev_drivers/fl2k_stream/osmo-fl2k-64bit-20250105", "fl2k_file.exe")

SDRpath = "C:/Users/scharfetter_admin/Documents/MW_Aufzeichnungen/COHIRADIA/Softwareentwicklung/COHIRADIA_RFCorder/COHIRADIA_RFCorder"
filename = 'out8_20250118_224441_1100kHz.wav'
stream_to_fl2k_file(os.path.join(SDRpath,filename), 10000000, 4096*256*16*8, fl2k_file_path)

#stream_to_fl2k_file('SDRuno_20220910_095058Z_1125kHz.wav', 10000000, 4096*256*16*8, fl2k_file_path)

