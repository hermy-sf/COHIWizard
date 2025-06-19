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

# [sine_base]afir=taps='0.1|0.15|0.5|0.15|0.1'[sine_lp];
#   [sine_base]afir=taps='-0.1|-0.15|0.5|-0.15|-0.1'[sine_hp];

    try:
        
        h3 = '0.01974534|0.1324045|0.34785016|0.34785016|0.1324045|0.01974534'
        #a = -0.461006
        ffmpeg_cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-hide_banner",  
        "-f", "s16le", "-ar", str(sampling_rate), "-ac", "2", "-i", "-",  # Lese von stdin
        "-filter_complex",
        "[0:a]aresample=osr=" + str(tSR) + ",channelsplit=channel_layout=stereo [re][im];"
        "sine=frequency=" + str(lo_shift) + ":sample_rate="  + str(tSR) + "[sine_base];"
        "[sine_base] asplit=2[sine_sin1][sine_sin2];"
        "[sine_sin2]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[sine_cos];"
        #"[sine_sin2]biquad=b0=-0.461006:b1=1:b2=0:a0=1:a1=-0.461006:a2=0[sine_cos];"
        "[re][sine_cos]amultiply[mod_re];"
        "[im][sine_sin1]amultiply[mod_im];"
        "[mod_im]volume=volume=200[part_im];"
        "[mod_re]volume=volume=200[part_re];"
        "[part_re][part_im]amix=inputs=2:duration=shortest[out]",
        "-map", "[out]", "-c:a", "pcm_s8", "-f", "caf", "-"
        ]
        ## "-map", "[out]", "-c:a", "pcm_s8", "-f", "caf", "-"

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

    # Starten von fl2k_file mit den entsprechenden Parametern
    try:
        # fl2k_process = subprocess.Popen(
        #     [fl2k_file_path, "-s", str(sampling_rate), "-r", "0", "-"],
        #     stdin=subprocess.PIPE,
        #     stdout=subprocess.PIPE,
        #     stderr=subprocess.PIPE,
        # )
        # fl2k_file-Prozess starten und stdout von FFmpeg als stdin übergeben
        fl2k_process = subprocess.Popen(
            [fl2k_file_path, "-s", str(tSR), "-r", "0", "-"],
            stdin=ffmpeg_process.stdout,  # Hier kommt der FFmpeg-Stream an
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # fl2k_process = subprocess.Popen(
        #     [fl2k_file_path, "-s", str(tSR), "-r", "0", "-"],
        #     stdin=subprocess.PIPE,  # Hier kommt der FFmpeg-Stream an
        #     stdout=subprocess.PIPE,
        #     stderr=subprocess.PIPE
        # )

    except FileNotFoundError:
        print(f"Input file not found")
        return()
    except subprocess.SubprocessError as e:
        print(f"Error when executing fl2k_file: {e}")
        return()
    except Exception as e:
        print(f"Unexpected error: {e}")
        return()
    psutil.Process(fl2k_process.pid).nice(psutil.IDLE_PRIORITY_CLASS)

    while True:
        if ix > 10: break
        print (f"iteration {ix}")
        ix += 1
        try:
            # Öffnen der Eingabedatei im Binärmodus
            with open(input_file, "rb") as f:

                # ###################
                # #Starte ffmpeg Prozess:
                # try:
                    
                #     ffmpeg_cmd = [
                #     "ffmpeg", "-y", "-loglevel", "error", "-hide_banner",  
                #     "-f", "s16le", "-ar", "1250000", "-ac", "2", "-i", "-",  # Lese von stdin
                #     "-filter_complex",
                #     "[0:a]aresample=osr=10000000,channelsplit=channel_layout=stereo [FL][FR];"
                #     "[FL]adelay=2500S[re];"
                #     "[FR]anull[im_delayed];"
                #     "sine=frequency=11250000:sample_rate=10000000[sine_base];"
                #     "[sine_base]anull[sine_sin];"
                #     "[sine_sin]volume=volume=-1[sine_cos];"
                #     "[re][sine_cos]amultiply[mod_re];"
                #     "[im_delayed][sine_sin]amultiply[mod_im];"
                #     "[mod_im]volume=volume=-200[inv_im];"
                #     "[mod_re]volume=volume=200[ampl_re];"
                #     "[ampl_re][inv_im]amix=inputs=2:duration=shortest[mixed];"
                #     "[mixed]anull[out]",
                #     "-map", "[out]", "-c:a", "pcm_s8", "-f", "caf", "-"
                #     ]
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

                # # Starten von fl2k_file mit den entsprechenden Parametern
                # try:
                #     # fl2k_process = subprocess.Popen(
                #     #     [fl2k_file_path, "-s", str(sampling_rate), "-r", "0", "-"],
                #     #     stdin=subprocess.PIPE,
                #     #     stdout=subprocess.PIPE,
                #     #     stderr=subprocess.PIPE,
                #     # )
                #     # fl2k_file-Prozess starten und stdout von FFmpeg als stdin übergeben
                #     fl2k_process = subprocess.Popen(
                #         [fl2k_file_path, "-s", str(sampling_rate), "-r", "0", "-"],
                #         stdin=ffmpeg_process.stdout,  # Hier kommt der FFmpeg-Stream an
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
                # psutil.Process(fl2k_process.pid).nice(psutil.IDLE_PRIORITY_CLASS)

                # Lesen und Streamen der Datei in Blöcken
                while chunk := f.read(buffer_size):
                    #print("readchunk")
                    ffmpeg_process.stdin.write(chunk)
                    ffmpeg_process.stdin.flush()
                # Warten, bis fl2k_file beendet ist
                #ffmpeg_process.stdin.close()type(chunk)
                #stdout, stderr = ffmpeg_process.communicate()
                # ffmpeg_process.stdin.close()  # Wichtig: stdin schließen
                # ffmpeg_process.stdout.close()  # Falls stdout genutzt wird
                # ffmpeg_process.terminate()  # Beendet den Prozess sanft
                # ffmpeg_process.wait()  # Wartet auf das Ende
                # stdout, stderr = fl2k_process.communicate()  # Warten, bis fl2k_file beendet ist
                # # Ausgabe der Ergebnisse
                # print("fl2k output:")
                # print(stdout.decode())
                # if stderr:
                #     print("fl2k_file errors:")
                #     print(stderr.decode())
                print(f"ffmpeg_poll: {ffmpeg_process.poll()}")
                print(f"fl2k_poll: {fl2k_process.poll()}")


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
    stdout, stderr = fl2k_process.communicate()  # Warten, bis fl2k_file beendet ist
    # Ausgabe der Ergebnisse
    print("fl2k output:")
    print(stdout.decode())
    if stderr:
        print("fl2k_file errors:")
        print(stderr.decode())

    print("DONE")

# Beispielaufruf
fl2k_file_path = os.path.join(os.getcwd(),"dev_drivers/fl2k_stream/osmo-fl2k-64bit-20250105", "fl2k_file.exe")
stream_to_fl2k_file('SDRuno_20220910_095058Z_1125kHz.wav', 10000000, 4096*256*16*8, fl2k_file_path)
