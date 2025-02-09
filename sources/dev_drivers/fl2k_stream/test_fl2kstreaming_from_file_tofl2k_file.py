import subprocess
import psutil
import os

def stream_to_fl2k_file(input_file, target_sampling_rate, buffer_size=4096, fl2k_file_path="fl2k_file"):
    """
    Streamt einen Bytestream aus einer Datei und übergibt ihn per stdin an fl2k_file.

    :param input_file: Pfad zur Eingabedatei.
    :param sampling_rate: Abtastrate für fl2k_file (z. B. 10000000 für 10 MS/s).
    :param fl2k_file_path: Pfad zur fl2k_file-Binärdatei.
    :param buffer_size: Puffergröße für das Streaming (Standard: 4096 Bytes).
    """
    ix = 0
    # lo_shift = 1125000
    # delay = 1/lo_shift/4*1000
    # sampling_rate = 1250000
    
    ###################
    #Starte ffmpeg Prozess:
    try:
        
        ffmpeg_cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-hide_banner",  
        "-f", "s16le", "-ar", "1250000", "-ac", "2", "-i", "-",  # Lese von stdin
        "-filter_complex",
        "[0:a]aresample=osr=10000000,channelsplit=channel_layout=stereo [FL][FR];"
        "[FL]adelay=0.00088[re];"
        "[FR]anull[im_delayed];"
        "sine=frequency=1125000:sample_rate=10000000[sine_base];"
        "[sine_base]anull[sine_sin];"
        "[sine_sin]volume=volume=-1[sine_cos];"
        "[re][sine_cos]amultiply[mod_re];"
        "[im_delayed][sine_sin]amultiply[mod_im];"
        "[mod_im]volume=volume=-200[inv_im];"
        "[mod_re]volume=volume=200[ampl_re];"
        "[ampl_re][inv_im]amix=inputs=2:duration=shortest[mixed];"
        "[mixed]anull[out]",
        "-map", "[out]", "-c:a", "pcm_s8", "-f", "caf", "-"
        ]
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
            [fl2k_file_path, "-s", str(target_sampling_rate), "-r", "0", "-"],
            stdin=ffmpeg_process.stdout,  # Hier kommt der FFmpeg-Stream an
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
stream_to_fl2k_file('SDRuno_20220910_095058Z_1125kHz.wav', 10000000, 4096*256*16, fl2k_file_path)
