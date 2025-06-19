import subprocess
import psutil
import numpy as np
import os
import time


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

# **2️⃣ Festlegen der gewünschten Grenzf biquads[1]  # Zweite Biquad-Stufe

#TODO: replace by argparse
TEST = False # Testffmpeg für Test der Sin/Cos Komponenten
format = [1, 2, 16]  # 1=PCM, 2=IEEE float, 16=16 bit, 24=24 bit, 32=32 bit
sSR = 1250000
sample_rate = sSR
centerfreq = 1125000

fcarrier = 648000
fcarrier = 540000
#fcarrier = 1188001
fcarrier = 1251000
deltaf = -(fcarrier - centerfreq) # consider that the complex spectrum is centered at centerfreq, so that any carrier is shifted
filepath = "C:/Users/scharfetter_admin/Documents/MW_Aufzeichnungen/COHIRADIA/Softwareentwicklung/COHIRADIA_RFCorder/COHIRADIA_RFCorder"
input_filename = "A_gaincorrSDRuno_20220910_095058Z_1125kHz.wav"
output_filename = "output.wav"
in_path = os.path.join(filepath, input_filename)
out_path = os.path.join(filepath, output_filename)

#Lowpass filter
iSR = sSR
tSR = iSR#10000000
cutoff_freq = 4500  # 4.5 kHz Tiefpass
#sample_rate = 44100  # Audio-Sampling-Rate (kann auf 48kHz geändert werden)
filter_sample_rate = iSR
order = 4  # Butterworth-Filterordnung
# **3️⃣ Berechnung der Filterkoeffizienten für beide Stufen**
biquads = butterworth_biquad_coeffs(order, cutoff_freq, filter_sample_rate)
# **4️⃣ Filterkoeffizienten für FFmpeg in Variablen speichern**
(b0_1, b1_1, b2_1, a0_1, a1_1, a2_1) = biquads[0]  # Erste Biquad-Stufe
(b0_2, b1_2, b2_2, a0_2, a1_2, a2_2) = biquads[1]  # Zweite Biquad-Stufe


if format[0] == 1:  #PCM
    if format[2] == 16:
        formatstring = "s16le"
        preset_volume = 1
    elif format[2] == 24:   #24 bit PCM
        formatstring = "f32le"
        formatstring = "s24le"
        preset_volume = 1
    elif format[2] == 32:
        formatstring = "s32le"  #32 bit PCM 
        preset_volume = 1
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
    signstrre = "-" #tatsächliches Signum von deltaf
else:
    signstr = "-"
    signstrre =""

#preset_volume_im = 0 #only real part 
preset_volume_im = preset_volume # both parts
#preset_volume = 0 # only imaginary part

if not TEST:
    ffmpeg_cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-hide_banner",
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
        "[res_e]pan=mono|c0=0.5*FL+0.5*FR[mono];"
        "[mono]anull[out]",
        "-map", "[out]", "-c:a", "pcm_s16le", "-f", "wav", out_path
    ]
else:
    #Test Sinus/cosinus als Stereokanäe des Output Files
    ffmpeg_cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-hide_banner",
        "-f", formatstring, "-ar", str(sSR), "-ac", "2", "-i", str(in_path),
        "-filter_complex",
        "[0:a]aresample=osr=" + str(iSR) + ",channelsplit=channel_layout=stereo [re][im];"
        "sine=frequency=" + str(abs(deltaf)) + ":sample_rate=" + str(iSR) + "[sine_base];"
        "[sine_base]asplit=2[rsin][rsin2];"
        "[rsin2]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[rcos];"
        "[re]anullsink;[im]anullsink;"
        #"[rsin][rcos]amerge=inputs=2,pan=stereo|c0<c0|c1<c1[out]",
        "[rsin][rcos]amerge=inputs=2[out]",
        "-map", "[out]", "-c:a", "pcm_s16le", "-f", "wav", out_path
    ]

print("Generierter FFmpeg-Befehl:")
print(" ".join(ffmpeg_cmd))  # Zum Debuggen

try:
    # Prozess starten
    ffmpeg_process = subprocess.Popen(ffmpeg_cmd, 
        stdin=subprocess.PIPE, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE
    )

except FileNotFoundError:
    print(f"Input file not found")

except subprocess.SubprocessError as e:
    print(f"Error when executing ffmpeg_file: {e}")
   
except Exception as e:
    print(f"Unexpected error: {e}")
  
psutil.Process(ffmpeg_process.pid).nice(psutil.IDLE_PRIORITY_CLASS)

while ffmpeg_process.poll() is None:
    print("Waiting for ffmpeg to finish")
    time.sleep(1)   # Warte 1 Sekunde

ffmpeg_process.wait()  # Wartet auf das Ende
stdout, stderr = ffmpeg_process.communicate()  # Warten, bis fmpeg_file beendet ist
# Ausgabe der Ergebnisse
print("ffmpeg output:")
print(stdout.decode())
if stderr:
    print("fmpeg_file errors:")
    print(stderr.decode())


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
