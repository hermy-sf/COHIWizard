import subprocess
import psutil
import numpy as np
import os
import time
from pathlib import Path
import numpy as np
import scipy.signal as signal
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

def process_and_concat_audio(input_files, output_path, sample_rate=48000, fc_lp=4000):
    assert len(input_files) > 0, "Mindestens eine Eingabedatei erforderlich"

    filters = []
    inputs = []

    for idx, f in enumerate(input_files):
        inputs.extend(["-i", f])

        # Mono + Resample + Butterworth LPF (12. Ordnung ≈ 6x 2. Ordnung)
        filter_chain = (
            f"[{idx}:a]aresample={sample_rate},"
            f"pan=mono|c0=0.5*c0+0.5*c1,"
            f"lowpass=f={fc_lp},lowpass=f={fc_lp},"
            f"lowpass=f={fc_lp},lowpass=f={fc_lp},"
            f"lowpass=f={fc_lp},lowpass=f={fc_lp}"
            f"[a{idx}]"
        )
        filters.append(filter_chain)

    # Verkettung aller bearbeiteten Audios [a0][a1][a2]...
    astreams = ''.join(f"[a{idx}]" for idx in range(len(input_files)))
    filters.append(f"{astreams}concat=n={len(input_files)}:v=0:a=1[outa]")

    cmd = ["ffmpeg", "-y", *inputs,
           "-filter_complex", ';'.join(filters),
           "-map", "[outa]",
           "-f", "s16le", "-acodec", "pcm_s16le",
           output_path]

    print("Running FFmpeg command:")
    print(" ".join(cmd))
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
pregain = 0.3 #TODO TODO: choose pregain according to expected total signal
#format = self.get_formattag()


#filepath = "C:/Users/scharfetter_admin/Documents/MW_Aufzeichnungen/COHIRADIA/Softwareentwicklung/COHIRADIA_RFCorder/COHIRADIA_RFCorder"
filepath = "C:/Users/scharfetter_admin/Downloads"

#TODO: Filestart durch die sequenz '-skip_initial_bytes N', N = Byteoffset  genau trimmen
filelist1 = ["AUDIOFILE"]
output_filename = "test_output.raw"
out_path = os.path.join(filepath, output_filename)

# # Beispielaufruf:
# if __name__ == "__main__":
#     input_files = [
#         "audio1.wav",
#         "audio2.mp3",
#         "https://example.com/remoteaudio.mp3"
#     ]
#     output_file = "merged_output.raw"
#     process_and_concat_audio(input_files, output_file, sample_rate=48000, fc_lp=4000)




stream_url = "http://ght.phonomuseum.at/Sound/x/pa_0002-6918.mp3"  # Dein Webstream-URL
#stream_url = "C:/Users/scharfetter_admin/Downloads/Test_ffmpeg_modulator_JUST.wav"
#stream_url = "C:/Users/scharfetter_admin/Downloads/01-They can't take that away from me.wav"
stream_url = "C:/Users/scharfetter_admin/Eigene Musik/Camerata Vocal Group/Just/03-Nobody knows.mp3"
#stream_url = "C:/Users/scharfetter_admin/Eigene Musik/Camerata Vocal Group/Just/01-They can't take that away from me.mp3"
stream_url = "C:/Users/scharfetter_admin/Eigene Musik/Camerata Vocal Group/Just/01-They can't take that away from me.wav"
#stream_url = "C:/Users/scharfetter_admin/Downloads/test_long.wav"

file_list = ["C:/Users/scharfetter_admin/Eigene Musik/Camerata Vocal Group/Just/01-They can't take that away from me.wav","C:/Users/scharfetter_admin/Eigene Musik/Camerata Vocal Group/Just/03-Nobody knows.mp3"]
carrier_list = [1400000, 800000]
skipbytenr = 0
lp_freq = 4500


# first run
total_duration = "30.0"

#TODO TODO: get total duration of source audio
testduration = get_duration(stream_url)
print(f"Testduration: {testduration}")

firstround = True
ffmpeg_cmd = []


for ix,inputfile in enumerate(file_list):

    lo_shift = (fcenter - carrier_list[ix]) #TODO: if lo_shift < 0 --> set sine sign in complex filter -1, or sine_sign = sign(lo_shift)
    print(f"carrier: {carrier_list[ix]} Hz, lo_shift: {lo_shift} Hz")

    a = (np.tan(np.pi * abs(lo_shift) / tSR) - 1) / (np.tan(np.pi * abs(lo_shift) / tSR) + 1)
    sinus_sign = np.sign(lo_shift)  
    ffmpeg_cmd = []
    if ix > 0:

    #move previous output file to temp_out.raw
        previous_outfile = os.path.join(filepath, "temp_out.raw")
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

    reft = time.time()
    run_ffmpeg_with_progress(ffmpeg_cmd, total_duration_sec=120.0)
    st = time.time()
    et = st - reft
    print(f"ffmpeg finished in {et} seconds")
    firstround = False

    #delete previous_outfile in the last run

    if ix == len(file_list) - 1:
        try:
            os.remove(previous_outfile)
            print(f"Removed temporary intermediate product {previous_outfile}")
        except OSError as e:
            print(f"Error deleting file: {e}")

# ffmpeg_cmd = [
#     "ffmpeg", "-y", #"-loglevel", "error", "-hide_banner",
#     "-ss", "0", "-t", total_duration, #30s von 0 weg verarbeiten 
#     "-i", stream_url,  # Lies direkt vom Webstream
#     "-i", previous_outfile, #TODO: make this line dependent on run; this is not for run 0
#     "-filter_complex",
#     # FILTERCHAIN
#     # 1. Downmix zu Mono, Resampling, Normalisierung
#     "[0:a]aformat=sample_fmts=s16:channel_layouts=stereo,aresample=osr=" + str(tSR) +
#     ",pan=mono|c0=.5*c0+.5*c1" +
#     ",volume=1.0" +
#     ",lowpass=f=" + str(lp_freq) +
#     ",lowpass=f=" + str(lp_freq) +
#     ",lowpass=f=" + str(lp_freq) +
#     ",lowpass=f=" + str(lp_freq) +
#     "[mono_lp];"
#      # ",pan=mono|c0=.5*c0+.5*c1,volume=1.0[mono];"
#     # 2. Sinus-Generator, Cosinus über Allpassfilter (biquad)
#     "sine=frequency=" + str(abs(lo_shift)) + ":sample_rate=" + str(tSR) + "[sine_base];"
#     "[sine_base]asplit=2[sine_for_sin][sine_for_cos];"
#     "[sine_for_sin]volume=volume=" + str(sinus_sign) + "[sine_sin_raw];"
#     "[sine_sin_raw]asplit=3[sine_sin][carrier_sin][carrier_sin_deb];"
#     "[sine_for_cos]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[sine_cos_base];"
#     "[sine_cos_base]asplit=3[sine_cos][carrier_cos][carrier_cos_deb];"
#     # # 3. Modulation (1 + modulation_factor * Y)
#     # Modulationsanteil:
#     "[mono_lp]volume=volume=" + str(modulation_factor) + "[modsig];"
#     "[modsig]asplit=2[modsig1][modsig2];"
#     "[modsig1][sine_cos]amultiply[mod_re_component];"
#     "[modsig2][sine_sin]amultiply[mod_im_component];"
#     #DEBUG LINES
#     #"[mod_re_component]asplit=2[mod_re_component1][modre2];"
#     #"[mod_im_component]asplit=2[mod_im_component1][modim2];"

#     # 4. Add DC = sin/cos-Anteil (1 * sin(t) bzw. 1 * cos(t))
#     # 4. Trägeranteil zu Modulationsanteil addieren
#     "[mod_re_component][carrier_cos]amix=inputs=2:duration=shortest[modre];"
#     "[mod_im_component][carrier_sin]amix=inputs=2:duration=shortest[modim];"
#     "[carrier_cos_deb]anullsink;"
#     "[carrier_sin_deb]anullsink;"
#     # 5. Pregain anwenden
#     "[modre]volume=volume=" + str(pregain) + "[outre];"
#     "[modim]volume=volume=" + str(pregain) + "[outim];"
#     "[outre][outim]amerge=inputs=2[merged];[merged]pan=stereo|c0=0.5*c0|c1=0.5*c1[stereoout]", #TODO: rename stereoout to iq_out

#     ################ mix with previously generated IQ file out1.raw
#     "[1:a][stereoout]amix=inputs=2:duration=shortest:dropout_transition=0:normalize=0[final]",

#     #DEBUG LINES
#     #"[modre2][modim2]amerge=inputs=2[mod_debug_stereo]",
#     #"-map", "[stereoout]", "-c:a", "pcm_s16le", "-f", "wav", out_path
#     #################replace direct output of stereoout with mixed final signal
#     #"-map", "[stereoout]",
#     "-map", "[final]",
#     "-c:a", "pcm_s16le",
#     "-f", "s16le",   # reines RAW-PCM
#     out_path
#     #DEBUG LINES
#     #"-map", "[mod_debug_stereo]", "-c:a", "pcm_s16le", "-f", "wav", "debug_modre_modim.wav"
# ]

# try:
#     # Prozess starten
#     ffmpeg_process = subprocess.Popen(ffmpeg_cmd,  
#         stdout=None, 
#         stderr=None,
#         text=True
#     )

# except FileNotFoundError:
#     print(f"Input file not found")
# except subprocess.SubprocessError as e:
#     print(f"Error when executing ffmpeg_file: {e}")
# except Exception as e:
#     print(f"Unexpected error: {e}")
# #psutil.Process(ffmpeg_process.pid).nice(psutil.IDLE_PRIORITY_CLASS)


# try:
#     stdout, stderr = ffmpeg_process.communicate()  # Timeout nach 60 Sekunden
# except subprocess.TimeoutExpired:
#     ffmpeg_process.kill()
#     stdout, stderr = ffmpeg_process.communicate()
#     print(f"ffmpeg wurde wegen Timeout beendet")

