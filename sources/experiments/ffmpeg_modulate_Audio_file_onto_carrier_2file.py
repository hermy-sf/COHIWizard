import subprocess
#import psutil
import numpy as np
import os
import time
from pathlib import Path
import numpy as np
#import scipy.signal as signal
import re
import sys

"""read audio file ,complex modulate to carrier and write result to a IQ-File.
write the resulting IQ-File to output audio file PCM16
filelist 1: List of filenames of the master trace
filelist 2: List of filenames of the slave trace to be attenuated by gain dB
"""

def get_duration(input_file):
    """Chat GPT suggestion for getting the duration of an audio file

    :param input_file: _description_
    :type input_file: _type_
    :return: _description_
    :rtype: _type_
    """
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        input_file
    ], stdout=subprocess.PIPE, text=True)
    return float(result.stdout.strip())
import subprocess
from pathlib import Path

def process_and_concat_audio(input_files, output_path, sample_rate=44100, fc_lp=4500, silence_duration=4.0):
    assert len(input_files) > 0, "Mindestens eine Eingabedatei erforderlich"

    # 6x Lowpass-Filter für 12. Ordnung Butterworth
    lp_filter_chain = ",".join([f"lowpass=f={fc_lp}"] * 6)

    inputs = []
    filters = []

    for idx, infile in enumerate(input_files):
        inputs.extend(["-i", str(infile)])
        filters.append(
            f"[{idx}:a]"
            f"aresample={sample_rate},"
            f"pan=mono|c0=0.4*c0+0.4*c1," #TODO: 0.4 ist nur ein Versuch gegen Clipping
            f"{lp_filter_chain}"
            f"[a{idx}]"
        )

    # Stille als zusätzliche Inputs
    num_silences = len(input_files) - 1
    for j in range(num_silences):
        inputs.extend([
            "-f", "lavfi", "-t", str(silence_duration),
            "-i", f"aevalsrc=0:d={silence_duration}:s={sample_rate}"
        ])
        filters.append(f"[{len(input_files) + j}:a]aresample={sample_rate}[s{j}]")


    # Verkettung: [a0][s0][a1][s1][a2]...
    concat_parts = []
    for i in range(len(input_files) + num_silences):
        if i % 2 == 0:
            concat_parts.append(f"[a{i // 2}]")
        else:
            concat_parts.append(f"[s{i // 2}]")

    filter_concat = ";".join(filters) + ";" + "".join(concat_parts) + f"concat=n={len(concat_parts)}:v=0:a=1[outa]"


    # # Verkettung (concat)
    # filter_concat = ";".join(filters) + ";" + f"{''.join([f'[a{i}]' for i in range(len(input_files))])}concat=n={len(input_files)}:v=0:a=1[outa]"

    # FFmpeg-Kommando
    cmd = [
        "ffmpeg", "-y", *inputs,
        #"ffmpeg", "-y", "-loglevel", "debug", *inputs,
        "-filter_complex", filter_concat,
        "-map", "[outa]",
        #"-f", "s16le", "-acodec", "pcm_s16le", # for raw output
        "-f", "wav", "-acodec", "pcm_s16le", #for debug
        str(output_path)
    ]


    print("Running FFmpeg command:\n", " ".join(cmd))
    subprocess.run(cmd, check=True)


def run_ffmpeg_with_progress(ffmpeg_cmd, total_duration_sec):
    """Start ffmpeg command with intermediate output of the progress; progress is reported in 'progress'
    

    :param ffmpeg_cmd: _description_
    :type ffmpeg_cmd: _type_
    :param total_duration_sec: _description_
    :type total_duration_sec: _type_
    """
    process = subprocess.Popen(
        ffmpeg_cmd,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        bufsize=1
    )

    time_re = re.compile(r'time=(\d+):(\d+):(\d+).(\d+)')

    for line in process.stderr:
        sys.stderr.write(line)  # optional: zeige FFmpeg-Ausgabe live
        match = time_re.search(line)
        if match:
            h, m, s, ms = map(int, match.groups())
            elapsed = h * 3600 + m * 60 + s + ms / 100.0
            percent = (elapsed / total_duration_sec) * 100
            print(f"\rProgress: {percent:.1f}%", end='')
            #TODO TODO: send update signal for GUI progress bar here
    process.wait()
    print("\nDone.")

formatstring = "s16le"
tSR = 1250000
fcenter = 1125000
fcarrier = 1400000
#fcarrier = 800000
# lo_shift = (fcenter - fcarrier) #TODO: if lo_shift < 0 --> set sine sign in complex filter -1, or sine_sign = sign(lo_shift)
# sinus_sign = np.sign(lo_shift)  

modulation_factor = 0.8
pregain = 0.15 #TODO TODO: choose pregain according to expected total signal
#format = self.get_formattag()

#####True pathnames are not published here !
filepath = "C:/#####"

#TODO: Filestart durch die sequenz '-skip_initial_bytes N', N = Byteoffset  genau trimmen
output_filename = "test_output.raw"
out_path = os.path.join(filepath, output_filename)

reft = time.time()
file_list = [Path("C:/####.wav"),
             Path("C:/###.mp3"),
             "http://####/#/#/####.mp3"]

#ACHTUNG: lokale Dateinamen mit Path(), URLs bitte OHNE sonst error !

carrier_list = [1400000, 800000, 900000, 540000,738000]
skipbytenr = 0
lp_freq = 4500

###############################################

output_file = os.path.join(filepath, "audio_cat_file.raw")
output_file = os.path.join(filepath, "audio_cat_file.wav") #NUR FÜR TEST
sample_rate = 41100
silence_duration = 4.0

# generate the concatenated audio file for carrier #
#TODO: generate the cat file for each carrier individually
process_and_concat_audio(file_list, output_file, sample_rate, lp_freq, silence_duration)
cat_file_list = [output_file,output_file, output_file, output_file,output_file]

# generate synthesis file sequentially for each carrier

total_duration_sec = 500
total_duration = str(total_duration_sec)
#TODO TODO: get total duration of source audio

testduration = get_duration(file_list[0])
firstround = True
ffmpeg_cmd = []


for ix,inputfile in enumerate(cat_file_list):
    lo_shift = (fcenter - carrier_list[ix]) #TODO: if lo_shift < 0 --> set sine sign in complex filter -1, or sine_sign = sign(lo_shift)
    print(f"carrier: {carrier_list[ix]} Hz, lo_shift: {lo_shift} Hz")
    a = (np.tan(np.pi * abs(lo_shift) / tSR) - 1) / (np.tan(np.pi * abs(lo_shift) / tSR) + 1)
    sinus_sign = np.sign(lo_shift)  
    ffmpeg_cmd = []
    if ix > 0:
    #move previous output file to temp_out.raw
        previous_outfile = os.path.join(filepath, "temp_out.raw")
        try:
            os.remove(previous_outfile)  #TODO define good temp path
        except:
            pass
        os.rename(out_path, previous_outfile)  #TODO define good temp path
        print(f"Renamed {out_path} to {previous_outfile}")

    ffmpeg_cmd1 = [
        "ffmpeg", "-y", #"-loglevel", "error", "-hide_banner",
        "-ss", "0", "-t", total_duration, #30s von 0 weg verarbeiten 
        "-i", inputfile  # Lies direkt vom Webstream
    ]

    if not firstround:
        mixterm = "[outre][outim]amerge=inputs=2[merged];[1:a][merged]amix=inputs=2:duration=shortest:dropout_transition=0:normalize=0[udated_iq_out]"
    else:
        mixterm = "[outre][outim]amerge=inputs=2[merged];[merged]pan=stereo|c0=0.5*c0|c1=0.5*c1[iq_out]"

    ffmpeg_cmd2 = [
        "-filter_complex",
        # FILTERCHAIN
        # 1. Downmix zu Mono, Resampling, Normalisierung
        "[0:a]aformat=sample_fmts=s16:channel_layouts=stereo,aresample=osr=" + str(tSR) +
        ",pan=mono|c0=.5*c0+.5*c1" +
        ",volume=1.0" +
        ",lowpass=f=" + str(lp_freq) +
        ",lowpass=f=" + str(lp_freq) +
        ",lowpass=f=" + str(lp_freq) +
        ",lowpass=f=" + str(lp_freq) +
        "[mono_lp];"
        # ",pan=mono|c0=.5*c0+.5*c1,volume=1.0[mono];"
        # 2. Sinus-Generator, Cosinus über Allpassfilter (biquad)
        "sine=frequency=" + str(abs(lo_shift)) + ":sample_rate=" + str(tSR) + "[sine_base];"
        "[sine_base]asplit=2[sine_for_sin][sine_for_cos];"
        "[sine_for_sin]volume=volume=" + str(sinus_sign) + "[sine_sin_raw];"
        "[sine_sin_raw]asplit=3[sine_sin][carrier_sin][carrier_sin_deb];"
        "[sine_for_cos]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[sine_cos_base];"
        "[sine_cos_base]asplit=3[sine_cos][carrier_cos][carrier_cos_deb];"
        # # 3. Modulation (1 + modulation_factor * Y)
        # modulation part:
        "[mono_lp]volume=volume=" + str(modulation_factor) + "[modsig];"
        "[modsig]asplit=2[modsig1][modsig2];"
        "[modsig1][sine_cos]amultiply[mod_re_component];"
        "[modsig2][sine_sin]amultiply[mod_im_component];"
        # 4. Add carrier part = sin/cos-Anteil (1 * sin(t) bzw. 1 * cos(t))

        "[mod_re_component][carrier_cos]amix=inputs=2:duration=shortest[modre];"
        "[mod_im_component][carrier_sin]amix=inputs=2:duration=shortest[modim];"
        "[carrier_cos_deb]anullsink;"
        "[carrier_sin_deb]anullsink;"
        # 5. apply Pregain anwenden
        "[modre]volume=volume=" + str(pregain) + "[outre];"
        "[modim]volume=volume=" + str(pregain) + "[outim];" + str(mixterm)
    ]

    ffmpeg_cmd3 = [
        
        "-c:a", "pcm_s16le",
        "-f", "s16le",   # reines RAW-PCM
        out_path
        #DEBUG LINES
        #"-map", "[mod_debug_stereo]", "-c:a", "pcm_s16le", "-f", "wav", "debug_modre_modim.wav"
    ]

    # move output file of previous run to temp_out.raw

    if firstround:
        ffmpeg_intb = ["-map", "[iq_out]"]
        ffmpeg_cmd = ffmpeg_cmd1 + ffmpeg_cmd2 + ffmpeg_intb + ffmpeg_cmd3
        print(ffmpeg_cmd)
    else:
        ffmpeg_inta = ["-f", "s16le", "-ar",  str(tSR), "-ac",  "2", "-i", previous_outfile] #TODO: make this line dependent on run; this is not for run 0
        ffmpeg_intb = ["-map", "[udated_iq_out]"
        ]
        ffmpeg_cmd = ffmpeg_cmd1+ ffmpeg_inta + ffmpeg_cmd2 + ffmpeg_intb + ffmpeg_cmd3

    print("Generierter FFmpeg-Befehl:")
    print(" ".join(ffmpeg_cmd))  # Zum Debuggen


    run_ffmpeg_with_progress(ffmpeg_cmd, total_duration_sec)


    firstround = False

    #delete previous_outfile in the last run

    if ix == len(file_list) - 1:
        try:
            os.remove(previous_outfile)
            print(f"Removed temporary intermediate product {previous_outfile}")
        except OSError as e:
            print(f"Error deleting file: {e}")

# Finally delete temp file
try:
    os.remove(previous_outfile)  #TODO define good temp path
except OSError as e:
    print(f"Error deleting file: {e}")

st = time.time()
et = st - reft
print(f"ffmpeg synthesis finished in {et} seconds")
####TODO TODO TODO: generate wav header for raw file