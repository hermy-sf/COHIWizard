import subprocess
import psutil
import numpy as np
import os
#import time
from pathlib import Path
import re

"""Demodulate IQ-file at frequency deltaf using ffmpeg and write result to output audio file PCM16
"""

import numpy as np
import scipy.signal as signal


import numpy as np
import scipy.signal as signal

# **1️⃣ Funktion zur Berechnung von zwei Biquad-Stufen für Butterworth-Filter**
def butterworth_biquad_coeffs(order, cutoff_freq, sample_rate):
    # Berechne die Second-Order-Sections (SOS) für ein Butterworth-Tiefpassfilter
    sos = signal.butter(order, cutoff_freq / (sample_rate / 2), btype='low', output='sos')

    # Extrahiere die Biquad-Koeffizienten für die beiden Stufen
    biquads = []
    for section in sos:
        b0, b1, b2, a0, a1, a2 = section
        biquads.append((b0, b1, b2, a0, a1, a2))
    
    return biquads  # Gibt eine Liste mit zwei Tupeln zurück (jeweils eine Stufe)

def find_data_chunk(wav_file):
    with open(wav_file, "rb") as f:
        data = f.read()
        pos = data.find(b"data")  # Suche nach "data" im Header
        if pos != -1:
            print(f'"data"-Chunk gefunden an Byte-Position: {pos}')
        else:
            print('"data"-Chunk nicht gefunden.')
    return pos

def get_mean_volume(ffmpeg_execmd,input_file):
    """Misst die durchschnittliche Lautstärke (RMS) eines Audio-Files."""
    cmd = [
        ffmpeg_execmd, "-i", input_file, "-af", "volumedetect",
        "-f", "null", "-"
    ]
    
    result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    output = result.stderr  # ffmpeg schreibt volumedetect-Output in stderr

    match = re.search(r"mean_volume:\s*(-?\d+\.\d+)\s*dB", output)
    if match:
        return float(match.group(1))  # Gibt den RMS-Wert als Float zurück
    return None  # Falls kein Wert gefunden wurde

# **2️⃣ Festlegen der gewünschten Grenzf biquads[1]  # Zweite Biquad-Stufe

#TODO: replace by argparse
TEST = False # Testffmpeg für Test der Sin/Cos Komponenten
dynamic_range_margin = 1 # dB margin for dynamic range of the output audio (gain control)
format = [1, 2, 16]  # 1=PCM, 2=IEEE float, 16=16 bit, 24=24 bit, 32=32 bit
sSR = 1250000
sample_rate = sSR
#centerfreq = 1125000
centerfreq = 1100000
centerfreq = 1125000
#carrierlist = [648000,657000, 738000, 1368000]
#carrierlist = [648000, 540000, 1188000, 1251000]
#carrierlist = [657000]
#carrierlist = [648000]
carrierlist = [1422250, 756250, 900250, 657250, 1262500, 549250, 882250] #1262, 882 is a reference with noise
carrierlist = [1422250]
#carrierlist = [1089000]
carrierlist = [1251000]
gain = 1
skipbytenr = 0
filepath = "C:/Users/######/Documents/MW_Aufzeichnungen/COHIRADIA/Softwareentwicklung/COHIRADIA_RFCorder/COHIRADIA_RFCorder"
#filepath = "E:/COHIRADIA/Archiviert/unvollst_MW_30_and_31_12_2006_analogue_VR/Optional_intermediate_files/2GBSplit"
#filepath = ["E:/liblice_30_03_2025"]
#           E:\COHIRADIA\Archiviert\unvollst_MW_30_and_31_12_2006_analogue_VR\Optional_intermediate_files\2GBSplit
#filepath = "E:/COHIRADIA/Unbearbeitet_P1/Caroline_Ross_Revenge_2025_03_09/Barteczek"

# filelist = ["cohiwizard_20250309_193314Z_1125kHz.wav", "cohiwizard_20250309_194026Z_1125kHz.wav",
#             "cohiwizard_20250309_194738Z_1125kHz.wav", "cohiwizard_20250309_195450Z_1125kHz.wav",
#             "cohiwizard_20250309_200202Z_1125kHz.wav", "cohiwizard_20250309_200914Z_1125kHz.wav",
#             "cohiwizard_20250309_201626Z_1125kHz.wav", "cohiwizard_20250309_202338Z_1125kHz.wav"]

# filelist = ["cohiwizard_20250309_181401Z_1125kHz.wav",
#  "cohiwizard_20250309_182113Z_1125kHz.wav",
#  "cohiwizard_20250309_182825Z_1125kHz.wav",
#  "cohiwizard_20250309_183537Z_1125kHz.wav",
#  "cohiwizard_20250309_184249Z_1125kHz.wav",
#  "cohiwizard_20250309_185002Z_1125kHz.wav",
#  "cohiwizard_20250309_185714Z_1125kHz.wav",
#  "cohiwizard_20250309_190426Z_1125kHz.wav",
#  "cohiwizard_20250309_191138Z_1125kHz.wav",
#  "cohiwizard_20250309_191850Z_1125kHz.wav",
#  "cohiwizard_20250309_192602Z_1125kHz.wav",
#  "cohiwizard_20250309_193314Z_1125kHz.wav",
#  "cohiwizard_20250309_194026Z_1125kHz.wav",
#  "cohiwizard_20250309_194738Z_1125kHz.wav",
#  "cohiwizard_20250309_195450Z_1125kHz.wav",
#  "cohiwizard_20250309_200202Z_1125kHz.wav",
#  "cohiwizard_20250309_200914Z_1125kHz.wav",
#  "cohiwizard_20250309_201626Z_1125kHz.wav",
#  "cohiwizard_20250309_202338Z_1125kHz.wav",
#  "cohiwizard_20250309_203050Z_1125kHz.wav",
#  "cohiwizard_20250309_203802Z_1125kHz.wav",
# ]

#filelist = ["cohiwizard_20250309_200914Z_1125kHz.wav"]
#filelist = ["cohiwizard_20250309_200914Z_1125kHz_cut_20250320_064118_1125kHz.wav"]
#filelist = ["A_gaincorrSDRuno_20220910_095058Z_1125kHz.wav"]
#filelist = ["RSP_PERS_mw241_000_20230924_211257Z_1125kHz.wav"]
#filelist = ["B2006_20210801_184741_1100kHz_10_20061230_235828_1100kHz.wav"]
filelist = ["SDRuno_20250330_203858Z_1125kHz.wav"]
filelist = ["A_gaincorrSDRuno_20220910_095058Z_1125kHz.wav"]
for fcarrier in carrierlist:
    deltaf = (fcarrier - centerfreq) # consider that the complex spectrum is centered at centerfreq, so that any carrier is shifted

    for input_filename in filelist:
        print(f"next file: {input_filename}, at delaf: {deltaf}")
        output_filename = Path(input_filename).stem + "_demod" + str(int(np.ceil(fcarrier/1000))) + ".wav"
        in_path = os.path.join(filepath, input_filename)
        out_path = os.path.join(filepath, output_filename)
        filtered_out_path = os.path.join(filepath, ("filtered_" + output_filename))
        datachunkstart = find_data_chunk(in_path)
        skipbytenr = np.mod(datachunkstart,4) ####TODO TODO TODO: only correct for Sample-Align = 4
        #Lowpass filter
        iSR = 2*sSR
        tSR = iSR#10000000  #wird nicht gebraucht !
        cutoff_freq = 4500  # 4.5 kHz Tiefpass
        #sample_rate = 44100  # Audio-Sampling-Rate (kann auf 48kHz geändert werden)
        filter_sample_rate = iSR
        order = 4  # Butterworth-Filterordnung
        # **3️⃣ Berechnung der Filterkoeffizienten für beide Stufen**
        biquads = butterworth_biquad_coeffs(order, cutoff_freq, filter_sample_rate)
        # **4️⃣ Filterkoeffizienten für FFmpeg in Variablen speichern**
        (b0_1, b1_1, b2_1, a0_1, a1_1, a2_1) = biquads[0]  # Erste Biquad-Stufe
        (b0_2, b1_2, b2_2, a0_2, a1_2, a2_2) = biquads[1]  # Zweite Biquad-Stufe

        # Hochpassfilter
        # 1. Biquad-Stufe
        # f_c = 10  # Grenzfrequenz (in Hz)
        # fs = 44100  # Abtastrate (in Hz)
        # order = 2  # Filterordnung (2 für Biquad-Filter)
        # # Berechne die Biquad-Filterkoeffizienten mit dem Butterworth-Design
        # biquads_hp = signal.butter(order, f_c, btype='high', fs=fs)
        # (b0_hp, b1_hp, b2_hp) = biquads_hp[0]
        # (a0_hp, a1_hp, a2_hp) = biquads_hp[1]

        if format[0] == 1:  #PCM
            if format[2] == 16:
                formatstring = "s16le"
                preset_volume = 1*gain
            elif format[2] == 24:   #24 bit PCM
                formatstring = "f32le"
                formatstring = "s24le"
                preset_volume = 1*gain
            elif format[2] == 32:
                formatstring = "s32le"  #32 bit PCM 
                preset_volume = 1*gain
            else:
                print("error: format not supported")
        else: #IEEE float   
            if format[2] == 32:
                formatstring = "f32le"
                preset_volume = 1
            elif format[2] == 16:   #16 bit float
                formatstring = "f16le"
                preset_volume = 1
            else:
                print("error: format not supported")

                
        #fs_new = 10000000
        a = (np.tan(np.pi * deltaf / iSR) - 1) / (np.tan(np.pi * deltaf / iSR) + 1)
        b = [a, 1]      # Numerator-Koeffizienten
        a_coeffs = [1, a]  # Denominator-Koeffizienten

        if deltaf < 0:
            signstr = "-"
            signstrre = "+" #tatsächliches Signum von deltafprin
            print("#########################################case deltaf <0 #############")
        else:
            signstr = ""
            signstrre ="-"
            print("#########################################case deltaf >0 #############")

        #preset_volume_im = 0 #only real part 
        preset_volume_im = preset_volume # both parts
        #preset_volume = 0 # only imaginary part
        ffmpeg_path = "C:/Users/#####/Documents/MW_Aufzeichnungen/COHIRADIA/Softwareentwicklung/COHIWizard_2023/sources/ffmpeg-master-latest-win64-gpl-shared/bin"
        ffmpeg_execmd = os.path.join(ffmpeg_path, "ffmpeg.exe")
        if not TEST:
            ffmpeg_cmd = [
                ffmpeg_execmd, "-y", #"-loglevel", "error", "-hide_banner",
                "-skip_initial_bytes", str(skipbytenr),
                "-f", formatstring, "-ar", str(sSR), "-ac", "2", "-i", str(in_path),
                "-filter_complex",
                "[0:a]aresample=osr=" + str(iSR) + ",channelsplit=channel_layout=stereo [re][im];"
                "sine=frequency=" + str(abs(deltaf)) + ":sample_rate=" + str(iSR) + "[sine_base];"
                "[sine_base]asplit=2[rsin][rsin2];"
                "[rsin2]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[rcos];"
                #generate real part of the mixed signal
                "[rsin]asplit=[rsina][rsinb];"
                "[rcos]asplit=[rcosa][rcosb];"
                "[re]asplit=2[re1][re2];"
                "[im]asplit=2[im1][im2];"
                "[re1][rcosa]amultiply[mod_re_a];"
                "[im1][rsina]amultiply[mod_re_b];"
                "[mod_re_b]volume=volume=" + signstrre + str(preset_volume) + "[scaled_inv_re_b];"
                "[mod_re_a]volume=volume=" + str(preset_volume) + "[scaled_re_a];"
                "[scaled_re_a][scaled_inv_re_b]amix=inputs=2:duration=shortest[realp];" #caluclate real part of demodulated signal
                #generate imaginary part of the mixed signal
                "[re2][rsinb]amultiply[mod_im_a];"
                "[im2][rcosb]amultiply[mod_im_b];"
                "[mod_im_a]volume=volume=" + signstr + str(preset_volume_im) + "[scaled_im_a];"
                "[mod_im_b]volume=volume=" + str(preset_volume_im) + "[scaled_inv_im_b];"
                "[scaled_im_a][scaled_inv_im_b]amix=inputs=2:duration=shortest[imagp];" #caluclate imaginary part of demodulated signal
                f"[imagp]biquad=b0={b0_1}:b1={b1_1}:b2={b2_1}:a0={a0_1}:a1={a1_1}:a2={a2_1}[filtered1i];"
                f"[filtered1i]biquad=b0={b0_2}:b1={b1_2}:b2={b2_2}:a0={a0_2}:a1={a1_2}:a2={a2_2}[filtered2i];"
                "[filtered2i]anull[fim];"
                f"[realp]biquad=b0={b0_1}:b1={b1_1}:b2={b2_1}:a0={a0_1}:a1={a1_1}:a2={a2_1}[filtered1];"
                f"[filtered1]biquad=b0={b0_2}:b1={b1_2}:b2={b2_2}:a0={a0_2}:a1={a1_2}:a2={a2_2}[filtered2];"
                "[filtered2]anull[fre];"
                "[fre] aeval=val(0)*val(0) [real_sq];"
                "[fim] aeval=val(0)*val(0) [imag_sq];"
                "[real_sq][imag_sq] amix=inputs=2:duration=shortest [sum];"
                "[sum] aeval=sqrt(val(0)) [envelope];"
                "[envelope]aresample=osr=44100[res_e];"
                #f"[res_e]biquad=b0={b0_hp}:b1={b1_hp}:b2={b2_hp}:a0={a0_hp}:a1={a1_hp}:a2={a2_hp}[filteredaud1];"
                #f"[filteredaud1]biquad=b0={b0_2a}:b1={b1_2a}:b2={b2_2a}:a0={a0_2a}:a1={a1_2a}:a2={a2_2a}[filteredaud2];"
                #"[filteredaud2]anull[res_e_f];"
                #"[res_e]firequalizer=gain=\'-60*(f<10)+0*(f>=10)\'[res_e_f];"
                "[res_e]pan=mono|c0=0.5*FL+0.5*FR[mono];"
                "[mono]anull[out]",
                "-map", "[out]", "-c:a", "pcm_s16le", "-f", "wav", out_path
            ]
        else:
            #Test Sinus/cosinus als Stereokanäe des Output Files
            ffmpeg_cmd = [
                ffmpeg_execmd, "-y", #"-loglevel", "error", "-hide_banner",
                "-f", formatstring, "-ar", str(sSR), "-ac", "2", "-i", str(in_path),
                "-filter_complex",
                "[0:a]aresample=osr=" + str(iSR) + ",channelsplit=channel_layout=stereo [re][im];"
                "sine=frequency=" + str(abs(deltaf)) + ":sample_rate=" + str(iSR) + "[sine_base];"
                "[sine_base]asplit=2[rsin][rsin2];"
                "[rsin2]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[rcos];"
                "[re]anullsink;[im]anullsink;"
                "[rsin][rcos]amerge=inputs=2,pan=stereo|c0<c0|c1<c1[out]",
                "-map", "[out]", "-c:a", "pcm_s16le", "-f", "wav", out_path
            ]
        #-f wav -acodec pcm_f32le 
        #print("Generierter FFmpeg-Befehl:")
        #print(" ".join(ffmpeg_cmd))  # Zum Debuggen

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
            print(f"ffmpeg wurde wegen Timeout beendet für: {in_path}")
        # while ffmpeg_process.poll() is None:
        #     print(f"Waiting for ffmpeg to finish, at delaf: {deltaf} and alignment-offset: {skipbytenr}")
        #     time.sleep(1)   # Warte 1 Sekunde

        # ffmpeg_process.wait()  # Wartet auf das Ende
        # stdout, stderr = ffmpeg_process.communicate()  # Warten, bis fmpeg_file beendet ist
        # Ausgabe der Ergebnisse
        # print("ffmpeg output:")
        # print(stdout.decode())
        # if stderr:
        #     print("fmpeg_file errors:")
        #     print(stderr.decode())

        print(f"Output file: {out_path} wurde geschrieben")
        print("filter process starting")

        #determine mean volume for correct normalization in final step
        mean_volume = get_mean_volume(ffmpeg_execmd,out_path)
        print(f"Mean volume of output file: {mean_volume} dB")
        gain_wanted = -mean_volume - dynamic_range_margin

        #Bandpassfilter for DC removal and noise reduction
        #gain correction (without dynaudnorm still more dynamic range)
        ffmpeg_cmd = [
            ffmpeg_execmd, "-y", "-loglevel", "error", "-hide_banner",
            "-i", str(out_path),
            "-af", (
                "highpass=f=5, "  # Hochpassfilter at 5 Hz
                "firequalizer=gain_entry='entry(0, -80);"
                " entry(10, -3);"
                " entry(4500, -3);"
                " entry(5000, -40);"
                " entry(20000, -60)',"
                f"volume={gain_wanted:.2f}dB,"
                " dynaudnorm=p=0.99"
            ),
            str(filtered_out_path)
        ]

        try:
            # Prozess starten
            ffmpeg_process = subprocess.Popen(ffmpeg_cmd, stdout=None, stderr=None, text=True)
            ffmpeg_process.wait()  # Warten, bis der Prozess beendet ist
        except Exception as e:
            print(f"Fehler: {e}")


        print(f"Waiting for ffmpeg filter process to finish, at file: {in_path}")

        #ffmpeg_process.wait()  # Wartet auf das Ende
        try:
            stdout, stderr = ffmpeg_process.communicate()  # Timeout nach 60 Sekunden
        except subprocess.TimeoutExpired:
            ffmpeg_process.kill()
            stdout, stderr = ffmpeg_process.communicate()
            print(f"ffmpeg wurde wegen Timeout beendet für: {in_path}")
# Bandpassfiltern: ffmpeg -i input.wav -af "firequalizer=gain_entry='entry(0, -100); entry(f_lo, 0); entry(f_hi, 0); entry(20000, -100)'" output.wav

# #**FFmpeg-Kommando mit beiden Biquad-Filtern in Serie**
# ffmpeg_cmd = [
#     "ffmpeg", "-y", "-loglevel", "error", "-hide_banner",
#     "-f", formatstring, "-ar", str(sSR), "-ac", "2", "-i", str(in_path),
#     "-filter_complex",
#     "[0:a]channelsplit=channel_layout=stereo [re][im];"
#     "sine=frequency=" + str(abs(deltaf)) + ":sample_rate=" + str(sSR) + "[sine_base];"
#     "[sine_base]asplit=2[sine_sin1][sine_sin2];"
#     "[sine_sin2]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[sine_cos];"
#     #generate real part of the mixed signal
#     "[re][sine_cos]amultiply[mod_re_a];"
#     "[im][sine_sin1]amultiply[mod_re_b];"
#     "[mod_re_b]volume=volume=" + signstr + str(preset_volume) + "[scaled_inv_re_b];"
#     "[mod_re_a]volume=volume=" + str(preset_volume) + "[scaled_re_a];"
#     "[scaled_re_a][scaled_inv_re_b]amix=inputs=2:duration=shortest[mixed];" #caluclate real part of demodulated signal
#     #generate imaginary part of the mixed signal
#     # "[re][sine_sin1]amultiply[mod_im_a];"
#     # "[im][sine_cos]amultiply[mod_im_b];"
#     # "[cmod_im]volume=volume=" + signstr+ str(preset_volume) + "[cpart_im];"
#     # "[cmod_re]volume=volume=-" + str(preset_volume) + "[cinv_re];"
#     # "[cinv_re][cpart_im]amix=inputs=2:duration=shortest[cmixed];" #caluclate real part of demodulated signal
#     # **Zwei Biquad-Filter in Serie**
#     "[mixed]aresample=osr=44100[res_lo];"
#     f"[res_lo]biquad=b0={b0_1}:b1={b1_1}:b2={b2_1}:a0={a0_1}:a1={a1_1}:a2={a2_1}[filtered1];"
#     f"[filtered1]biquad=b0={b0_2}:b1={b1_2}:b2={b2_2}:a0={a0_2}:a1={a1_2}:a2={a2_2}[filtered2];"
#     "[filtered2]pan=mono|c0=0.5*FL+0.5*FR[mono];"
#     #"[res_lo]pan=mono|c0=0.5*FL+0.5*FR[mono];"
#     #"[filtered1]pan=mono|c0=0.5*FL+0.5*FR[mono];"
#     #"[mixed]anullsink;"
#     "[mono]anull[out]",
#     "-map", "[out]", "-c:a", "pcm_s16le", "-f", "wav", out_path
#     #"-map", "[out]", "-c:a", "pcm_s16le", "-f", "caf", out_path
#]

# #TODO TODO TODO: downsample result after demodulatio to 48kHz
# ffmpeg_cmd = [
# "ffmpeg", "-y", "-loglevel", "error", "-hide_banner",  
# "-f", formatstring, "-ar", str(sSR), "-ac", "2", "-i", str(filename),
# "-filter_complex",
# "[0:a]aresample=osr=" + str(tSR) + ",channelsplit=channel_layout=stereo [re][im];"
# "sine=frequency=" + str(deltaf) + ":sample_rate="  + str(tSR) + "[sine_base];"
# "[sine_base] asplit=2[sine_sin1][sine_sin2];"
# "[sine_sin2]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[sine_cos];"
# "[re][sine_cos]amultiply[mod_re];"
# "[im][sine_sin1]amultiply[mod_im];"
# "[mod_im]volume=volume=" + str(preset_volume) + "[part_im];"
# "[mod_re]volume=volume=" + str(preset_volume) + "[part_re];"
# "[part_re][part_im]amix=inputs=2:duration=shortest[out]",
# "-map", "[out]", "-c:a", "pcm_s8", "-f", "caf", output_filename
# ]

#Suggestion 1 from chatGPT:
# ffmpeg_cmd = [
#     "ffmpeg", "-y", "-loglevel", "error", "-hide_banner",
#     "-f", formatstring, "-ar", str(sSR), "-ac", "2", "-i", str(os.path.join(filepath,filename)),
#     "-filter_complex",
#     "[0:a]channelsplit=channel_layout=stereo [re][im];"
#     "sine=frequency=" + str(deltaf) + ":sample_rate=" + str(sSR) + "[sine_base];"
#     "[sine_base]asplit=2[sine_sin1][sine_sin2];"
#     "[sine_sin2]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[sine_cos];"
#     "[re][sine_cos]amultiply[mod_re];"              #demodulation
#     "[im][sine_sin1]amultiply[mod_im];"
#     "[mod_im]volume=volume=" + str(preset_volume) + "[part_im];" # volume correction
#     "[mod_re]volume=volume=" + str(preset_volume) + "[part_re];"
#     "[part_re]lowpass=f=9000:o=4[filtered];"  # Low-pass filter Butterw 4th order , cutoff at 9 kHz
#     "[filtered]aresample=osr=44100[out]",  # Resample to 48 kHz
#     "-map", "[out]", "-c:a", "pcm_s16", "-f", "wav", output_filename
# ]


# ffmpeg_cmd = [
#     "ffmpeg", "-y", "-loglevel", "error", "-hide_banner",
#     "-f", formatstring, "-ar", str(sSR), "-ac", "2", "-i", str(os.path.join(filepath,filename)),
#     "-filter_complex",
#     "[0:a]channelsplit=channel_layout=stereo [re][im];"
#     "sine=frequency=" + str(deltaf) + ":sample_rate=" + str(sSR) + "[sine_base];"
#     "[sine_base]asplit=2[sine_sin1][sine_sin2];"
#     "[sine_sin2]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[sine_cos];"
#     "[re][sine_cos]amultiply[mod_re];"
#     "[im][sine_sin1]amultiply[mod_im];"
#     "[mod_im]volume=volume=-" str(preset_volume) + "[inv_im];"
#     "[mod_re]volume=volume=" + str(preset_volume) + "[part_re];"
#     "[part_re][inv_im]amix=inputs=2:duration=shortest[mixed];"
#     # Erster Butterworth-Biquad-Filter (2. Ordnung)
#     "[mixed]biquad=b0=0.0201:b1=0.0402:b2=0.0201:a0=1:a1=-1.561:a2=0.641[filtered1];"
#     # Zweiter Butterworth-Biquad-Filter (weitere 2. Ordnung -> insgesamt 4. Ordnung)
#     "[filtered1]biquad=b0=0.0201:b1=0.0402:b2=0.0201:a0=1:a1=-1.129:a2=0.290[filtered2];"
#     # Resampling auf 44.1 kHz oder 48 kHz
#     "[filtered2]aresample=osr=44100[out];"
#     #"[part_im]anullsink",
#     "-map", "[out]", "-c:a", "pcm_s16le", "-f", "wav", str(os.path.join(filepath,output_filename))
# ]

    #deltaf = fcarrier - centerfreq hat das korrekte Vorzeichen; D
    # Der Demod exponential muss nun -deltaf als Frequenz haben
    #also, wenn deltaf negativ dann exponential positiv
    #Berechnung : (re + j im)(cos +jsin) = re*cos - im*sin + j(re*sin + im*cos)
    #re*cos - im*sin = re*cos + im*(-sin) = re*cos + im*cos(pi/2) = sqrt(re^2 + im^2) * cos(atan(im/re) - pi/2) 
    # Im aktuellen code sind sin und cos phasenrichtig
    # Der Term realp ist re*cos - im*sin mit der Frequenz -deltaf; Da der Sinus immer mit abs(deltaf) erzeugt wird
    # muss das Vorzeichen vor den Sinus gezogen werden:
    #re*cos + sign(deltaf)*im*sin
    #Beim Imagitärterm ist es umgekehrt: re*sin + im*cos muss umgeschrieben werden in:
    #sign(deltaf)*re*sin + im*cos
    #Beisp: deltaf = -100; Demodulator muss +100 im sinus haben; also re*cos - im*sin(-deltaf) =
    #re*cos + sign*im*sin(abs(deltaf)))



# ffmpeg_cmd = [
# "ffmpeg", "-i", "SDRuno_20220910_095058Z_1125kHz.wav",  
# "-filter_complex",
# "[0:a]aresample=osr=10000000,channelsplit=channel_layout=stereo [re][im];"
# "sine=frequency=1125000:sample_rate=10000000[sine_sin];"
# "[sine_sin]biquad=b0=" + str(a) + ":b1=1:b2=0:a1=" + str(a) + ":a2=0[sine_cos];"
# "[re][sine_cos]amultiply[mod_re];"
# "[im][sine_sin]amultiply[mod_im];"
# "[mod_im]volume=volume=-200[inv_im];"
# "[mod_re]volume=volume=200[ampl_re];"
# "[ampl_re][inv_im]amix=inputs=2:duration=shortest[mixed];"
# "[mixed]anull[out]",
# "-map", "[out]", "-c:a", "pcm_s8", "-f", "caf", "output.dat"
# ]
