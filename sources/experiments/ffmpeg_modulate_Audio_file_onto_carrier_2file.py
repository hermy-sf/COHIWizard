import subprocess
import psutil
import numpy as np
import os
import time
from pathlib import Path
import numpy as np
import scipy.signal as signal

"""read audio file ,complex modulate to carrier and write result to a IQ-File.
write the resulting IQ-File to output audio file PCM16
filelist 1: List of filenames of the master trace
filelist 2: List of filenames of the slave trace to be attenuated by gain dB
"""

def find_data_chunk(wav_file):
    try:
        with open(wav_file, "rb") as f:
            data = f.read()
            pos = data.find(b"data")  # Suche nach "data" im Header
            if pos != -1:
                print(f'"data"-Chunk gefunden an Byte-Position: {pos}')
            else:
                print('"data"-Chunk nicht gefunden.')
        return pos
    except:
        print(f"File {wav_file} cannot be read regularly.")  
        return -1


formatstring = "s16le"
tSR = 1250000
fcenter = 1125000
fcarrier = 1400000
#fcarrier = 800000
lo_shift = (fcenter - fcarrier) #TODO: if lo_shift < 0 --> set sine sign in complex filter -1, or sine_sign = sign(lo_shift)
sinus_sign = np.sign(lo_shift)  

modulation_factor = 0.8
pregain = 1
#format = self.get_formattag()
a = (np.tan(np.pi * abs(lo_shift) / tSR) - 1) / (np.tan(np.pi * abs(lo_shift) / tSR) + 1)

#a = (np.tan(np.pi * deltaf / iSR) - 1) / (np.tan(np.pi * deltaf / iSR) + 1)
b = [a, 1]      # Numerator-Koeffizienten
a_coeffs = [1, a]  # Denominator-Koeffizienten
#filepath = "C:/Users/scharfetter_admin/Documents/MW_Aufzeichnungen/COHIRADIA/Softwareentwicklung/COHIRADIA_RFCorder/COHIRADIA_RFCorder"
filepath = "C:/Users/scharfetter_admin/Downloads"

# filelist1 = ["cohiwizard_20250309_200914Z_1125kHz.wav"]
# filelist2 = ["synth_caro_spur6_0.wav"]
#TODO: Filestart durch die sequenz '-skip_initial_bytes N', N = Byteoffset  genau trimmen
filelist1 = ["AUDIOFILE"]
output_filename = "test_output.raw"
out_path = os.path.join(filepath, output_filename)
# for ix, input_filename in enumerate(filelist1):
#     input_filename1 = filelist1[ix]
#     print(f"next audio file: {input_filename1}")
#     output_filename = "remix_" + Path(input_filename).stem + ".wav"
#     in_path1 = os.path.join(filepath, input_filename1)
#     out_path = os.path.join(filepath, output_filename)
#     datachunkstart1 = find_data_chunk(in_path1)     #TODO: modify for general read from mp3 or wav
#     ffmpeg_path = "C:/Users/scharfetter_admin/Documents/MW_Aufzeichnungen/COHIRADIA/Softwareentwicklung/COHIWizard_2023/sources/ffmpeg-master-latest-win64-gpl-shared/bin"
#     ffmpeg_execmd = os.path.join(ffmpeg_path, "ffmpeg.exe")


        #######################################################
        #
        # TASK: read data from an audio stream from elsewhere in form of 16bit PCM audio data
        # if mp3: read mp3 via appropriate ffmpeg command
        # if wav: read wav via appropriate ffmpeg command
        # if format == stereo: join the two channels to one channel
        # if format == mono: do nothing
        # if format == 24bit: convert to 16bit PCM
        # if format == 32bit: convert to 16bit PCM 
        # if format == 32bit float: convert to 16bit PCM
        # 
        # 

            #     # Prozess starten
            #     ffmpeg_process = subprocess.Popen(ffmpeg_cmd, 
            #         stdin=subprocess.PIPE, 
            #         stdout=subprocess.PIPE, 
            #         stderr=subprocess.PIPE,
            #         bufsize=10**7)
            #     print(f"ffmpeg_command: {ffmpeg_cmd}")
            # except FileNotFoundError:
            #     print(f"Input file not found, probably ffmpeg path is wrong")
            #     return()
            # except subprocess.SubprocessError as e:
            #     print(f"Error when executing ffmpeg: {e}")
            #     return()    
            # except Exception as e:
            #     print(f"Unexpected error: {e}")
            #     return()    
            
            # if os.name.find("posix") >= 0:
            #     pass
            # else:
            #     psutil.Process(ffmpeg_process.pid).nice(psutil.HIGH_PRIORITY_CLASS)
            #     pass


# Konfigurierbare Parameter

stream_url = "http://ght.phonomuseum.at/Sound/x/pa_0002-6918.mp3"  # Dein Webstream-URL
#stream_url = "C:/Users/scharfetter_admin/Downloads/Test_ffmpeg_modulator_JUST.wav"
#stream_url = "C:/Users/scharfetter_admin/Downloads/01-They can't take that away from me.wav"
#stream_url = "C:/Users/scharfetter_admin/Eigene Musik/Camerata Vocal Group/Just/03-Nobody knows.mp3"
#stream_url = "C:/Users/scharfetter_admin/Eigene Musik/Camerata Vocal Group/Just/01-They can't take that away from me.mp3"
#stream_url = "C:/Users/scharfetter_admin/Eigene Musik/Camerata Vocal Group/Just/01-They can't take that away from me.wav"
#stream_url = "C:/Users/scharfetter_admin/Downloads/test_long.wav"

# datachunkstart = find_data_chunk(stream_url)
skipbytenr = 0
# if datachunkstart >=0:
#     skipbytenr = np.mod(datachunkstart,2) ####TODO TODO TODO: only correct for Sample-Align = 4
# #unklar: Manchmal startet das erzeugte File mit 2 byte Offset, abhängig vom Original-Audiofile. Wieso passiert das ?
# # Das heisst ja, dass real und Imaginärteil verkehrt herum starten, also verkehrt erzeugt werden.
# #output_file = "output.caf"     # Output-Datei

ffmpeg_cmd = [
    "ffmpeg", "-y", "-loglevel", "error", "-hide_banner",
    "-skip_initial_bytes", str(skipbytenr),
    "-i", stream_url,  # Lies direkt vom Webstream
    "-filter_complex",
    # FILTERCHAIN
    # 1. Downmix zu Mono, Resampling, Normalisierung
    "[0:a]aformat=sample_fmts=s16:channel_layouts=stereo,aresample=osr=" + str(tSR) + ",pan=mono|c0=.5*c0+.5*c1,volume=1.0[mono];"
    # 2. Sinus-Generator, Cosinus über Allpassfilter (biquad)
    "sine=frequency=" + str(abs(lo_shift)) + ":sample_rate=" + str(tSR) + "[sine_base];"
    "[sine_base]asplit=2[sine_for_sin][sine_for_cos];"
    "[sine_for_sin]volume=volume=" + str(sinus_sign) + "[sine_sin_raw];"
    "[sine_sin_raw]asplit=3[sine_sin][carrier_sin][carrier_sin_deb];"
    "[sine_for_cos]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[sine_cos_base];"
    "[sine_cos_base]asplit=3[sine_cos][carrier_cos][carrier_cos_deb];"
    
    # # 3. Modulation (1 + modulation_factor * Y)
    # Modulationsanteil:
    "[mono]volume=volume=" + str(modulation_factor) + "[modsig];"
    "[modsig]asplit=2[modsig1][modsig2];"
    "[modsig1][sine_cos]amultiply[mod_re_component];"
    "[modsig2][sine_sin]amultiply[mod_im_component];"
    #DEBUG LINES
    #"[mod_re_component]asplit=2[mod_re_component1][modre2];"
    #"[mod_im_component]asplit=2[mod_im_component1][modim2];"

    # 4. Add DC = sin/cos-Anteil (1 * sin(t) bzw. 1 * cos(t))
    # 4. Trägeranteil zu Modulationsanteil addieren

    "[mod_re_component][carrier_cos]amix=inputs=2:duration=shortest[modre];"
    "[mod_im_component][carrier_sin]amix=inputs=2:duration=shortest[modim];"
    "[carrier_cos_deb]anullsink;"
    "[carrier_sin_deb]anullsink;"
    # 5. Pregain anwenden

    "[modre]volume=volume=" + str(pregain) + "[outre];"
    "[modim]volume=volume=" + str(pregain) + "[outim];"
    "[outre][outim]amerge=inputs=2[merged];[merged]pan=stereo|c0=0.5*c0|c1=0.5*c1[stereoout]",
    #DEBUG LINES
    #"[modre2][modim2]amerge=inputs=2[mod_debug_stereo]",
    #"-map", "[stereoout]", "-c:a", "pcm_s16le", "-f", "wav", out_path
    "-map", "[stereoout]",
    "-c:a", "pcm_s16le",
    "-f", "s16le",   # reines RAW-PCM
    out_path
    #DEBUG LINES
    #"-map", "[mod_debug_stereo]", "-c:a", "pcm_s16le", "-f", "wav", "debug_modre_modim.wav"

    # ➕ Zusätzliche Ausgaben zur Analyse:
    #"-map", "[carrier_cos_deb]", "-c:a", "pcm_s16le", "-f", "wav", "debug_carrier_cos.wav",
    #"-map", "[carrier_sin_deb]", "-c:a", "pcm_s16le", "-f", "wav", "debug_carrier_sin.wav"
    # "-map", "[modsig]", "-c:a", "pcm_s16le", "-f", "wav", "debug_modsig.wav",
    # "-map", "[modre]", "-c:a", "pcm_s16le", "-f", "wav", "debug_modre.wav",
    # "-map", "[modim]", "-c:a", "pcm_s16le", "-f", "wav", "debug_modim.wav",
]

print("Generierter FFmpeg-Befehl:")
print(" ".join(ffmpeg_cmd))  # Zum Debuggen

reft = time.time()
try:
    # Prozess starten
    ffmpeg_process = subprocess.Popen(ffmpeg_cmd,  
        stdout=None, 
        stderr=None,
        text=True
    )

except FileNotFoundError:
    print(f"Input file not found")
except subprocess.SubprocessError as e:
    print(f"Error when executing ffmpeg_file: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
#psutil.Process(ffmpeg_process.pid).nice(psutil.IDLE_PRIORITY_CLASS)

try:
    stdout, stderr = ffmpeg_process.communicate()  # Timeout nach 60 Sekunden
except subprocess.TimeoutExpired:
    ffmpeg_process.kill()
    stdout, stderr = ffmpeg_process.communicate()
    print(f"ffmpeg wurde wegen Timeout beendet")

st = time.time()
et = st - reft
print(f"ffmpeg finished in {et} seconds")