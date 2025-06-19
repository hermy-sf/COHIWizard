import subprocess
import psutil
import numpy as np
import os
import time

flo = 1125000
fs_new = 10000000
a = (np.tan(np.pi * flo / fs_new) - 1) / (np.tan(np.pi * flo / fs_new) + 1)
b = [a, 1]      # Numerator-Koeffizienten
a_coeffs = [1, a]  # Denominator-Koeffizienten


ffmpeg_cmd = [
"ffmpeg", "-i", "SDRuno_20220910_095058Z_1125kHz.wav",  
"-filter_complex",
"[0:a]aresample=osr=10000000,channelsplit=channel_layout=stereo [re][im];"
"sine=frequency=1125000:sample_rate=10000000[sine_sin];"
"[sine_sin]biquad=b0=" + str(a) + ":b1=1:b2=0:a1=" + str(a) + ":a2=0[sine_cos];"
"[re][sine_cos]amultiply[mod_re];"
"[im][sine_sin]amultiply[mod_im];"
"[mod_im]volume=volume=-200[inv_im];"
"[mod_re]volume=volume=200[ampl_re];"
"[ampl_re][inv_im]amix=inputs=2:duration=shortest[mixed];"
"[mixed]anull[out]",
"-map", "[out]", "-c:a", "pcm_s8", "-f", "caf", "output.dat"
]

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
    print(f"Error when executing fl2k_file: {e}")
   
except Exception as e:
    print(f"Unexpected error: {e}")
  
psutil.Process(ffmpeg_process.pid).nice(psutil.IDLE_PRIORITY_CLASS)

while ffmpeg_process.poll() is None:
    print("Waiting for ffmpeg to finish")
    time.sleep(1)   # Warte 1 Sekunde

ffmpeg_process.wait()  # Wartet auf das Ende
stdout, stderr = ffmpeg_process.communicate()  # Warten, bis fl2k_file beendet ist
# Ausgabe der Ergebnisse
print("fl2k output:")
print(stdout.decode())
if stderr:
    print("fl2k_file errors:")
    print(stderr.decode())
