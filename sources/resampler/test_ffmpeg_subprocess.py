import subprocess
import time

soxstring = 'ffmpeg -y -f s16le -ar 1250000 -ac 2 -i C:/Users/scharfetter_admin/Documents/MW_Aufzeichnungen/COHIRADIA/Softwareentwicklung/COHIRADIA_RFCorder/COHIRADIA_RFCorder/SDRuno_20220910_095058Z_1125kHz.wav -af "aresample=resampler=soxr" -f s16le -ar 500000 C:/Users/scharfetter_admin/Documents/MW_Aufzeichnungen/COHIRADIA/Softwareentwicklung/COHIRADIA_RFCorder/COHIRADIA_RFCorder/temp/temp_0.dat'


try:
    ret = subprocess.Popen(soxstring, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
except FileNotFoundError:
    print(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>Input file not found")
except subprocess.SubprocessError as e:
    print(f"#################Error when executing fl2k_file: {e}")
except Exception as e:
    print(f"oooooooooooooooooooo Unexpected error: {e}")

stdout, stderr = ret.communicate()
print(stderr.decode())

print(f" ________ sox worker poll at init: poll: {ret.poll()}")
time.sleep(1)

# try:
#     process = subprocess.Popen(
#         ["fl2k_file", "-s", str(sampling_rate), "-"],
#         stdin=subprocess.PIPE,
#         stdout=subprocess.PIPE,
#         stderr=subprocess.PIPE,
#         bufsize=0
#     )
