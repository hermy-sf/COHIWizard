

# soxstring = 'ffmpeg -y -f '+ ffmpeg_type +' -ar ' + str(self.m["sSR"]) + ' -ac 2 -i "'  + source_fn  + '" -af ' + '"aresample=resampler=soxr, volume=' + str(self.m["resampling_gain"]) + 'dB"' + ' -f ' + ffmpeg_target_type + ' -ar ' + str(int(tSR))  + ' "' + target_fn + '"'

# ffmpeg_cmd = [
# "ffmpeg", "-y",  
# "-f", formatstring, "-ar", str(self.m["sSR"])), "-ac", "2", "-i", "-",
# [0:a]aresample=resampler=soxr" + str(tSR) + ",channelsplit=channel_layout=stereo [re][im];"
# "sine=frequency=" + str(lo_shift) + ":sample_rate="  + str(tSR) + "[sine_base];"
# "[sine_base] asplit=2[sine_sin1][sine_sin2];"
# "[sine_sin2]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[sine_cos];"
# "[re][sine_cos]amultiply[mod_re];"
# "[im][sine_sin1]amultiply[mod_im];"
# "[mod_im]volume=volume=200[part_im];"
# "[mod_re]volume=volume=200[part_re];"
# "[part_re][part_im]amix=inputs=2:duration=shortest[out]",
# "-map", "[out]", "-c:a", "pcm_s8", "-f", "caf", "-"
# ] 


# ffmpeg_process = subprocess.Popen(ffmpeg_cmd, 
#     stdin=subprocess.PIPE, 
#     stdout=subprocess.PIPE, 
#     stderr=subprocess.PIPE
# )

# except FileNotFoundError:
# print(f"Input file not found")
# return()
# except subprocess.SubprocessError as e:
# print(f"Error when executing fl2k_file: {e}")
# return()    
# except Exception as e:
# print(f"Unexpected error: {e}")
# return()    


import subprocess
import numpy as np

# Beispielwerte für ffmpeg-Parameter
ffmpeg_type = "f32le"  # Eingangsformat (z. B. float32 little-endian)
ffmpeg_target_type = "f32le"  # Ziel-Format (z. B. float32)
input_sample_rate = 2400000  # Eingangs-Samplerate
target_sample_rate = 500000  # Ziel-Samplerate
resampling_gain = 10  # Verstärkung in dB

# FFMPEG-Befehl für die Resampling-Pipeline
ffmpeg_cmd = [
    "ffmpeg",
    "-y",
    "-f", ffmpeg_type,
    "-ar", str(input_sample_rate),
    "-ac", "2",
    "-i", "pipe:0",  # Eingangsdaten von stdin (Pipes)
    "-af", f"aresample=resampler=soxr, volume={resampling_gain}dB",
    "-f", ffmpeg_target_type,
    "-ar", str(target_sample_rate),
    "-ac", "2",
    "pipe:1"  # Ausgabe nach stdout (Pipes)
]

# Starte den FFMPEG-Prozess
process = subprocess.Popen(
    ffmpeg_cmd,
    stdin=subprocess.PIPE,  # Eingangsdaten über stdin
    stdout=subprocess.PIPE,  # Ausgabe über stdout
    stderr=subprocess.DEVNULL,  # Optional: Verstecke FFMPEG-Logs
    bufsize=0
)

def process_and_send(data):
    """Sendet Daten an ffmpeg, resampled sie und sendet sie weiter an den TCP-Socket."""
    global process

    # Konvertiere das numpy-Array in Binärdaten (float32 little-endian)
    raw_data = data.astype(np.float32).tobytes()

    try:
        # Daten an ffmpeg senden
        process.stdin.write(raw_data)
        process.stdin.flush()

        # Resampelte Daten aus ffmpeg lesen
        resampled_data = process.stdout.read(len(raw_data))  # Lesen mit passender Puffergröße

        # Daten über den TCP-Socket senden
        self.stemlabcontrol.data_sock.send(resampled_data)

    except BrokenPipeError:
        print("FFMPEG-Prozess beendet oder Pipe geschlossen. Neustart erforderlich.")

