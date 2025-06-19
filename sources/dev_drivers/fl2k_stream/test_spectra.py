import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import resample, lfilter, firwin, freqz
import time

# Testprogramm für die Simulation eines Upsampling/Complex modulation prozesses mit ffmpeg


# FFT-Spektrum berechnen
def plot_spectrum(signal, fs, title):
    N = len(signal)
    freq = np.fft.fftfreq(N, d=1/fs)
    spectrum = np.fft.fft(signal)
    
    plt.figure()
    plt.plot(freq, np.abs(spectrum))
    plt.xlabel("Frequenz (Hz)")
    plt.ylabel("Amplitude")
    plt.title(title)
    plt.grid()
    plt.show()

# FIR Tiefpassfilter erster Ordnung mit 45° Phasenverschiebung
def fir_lowpass(fs, f):
    T = 1 / fs
    omega = 2 * np.pi * f * T
    h0 = 1 / np.sqrt(2)
    h1 = h0 * np.exp(-1j * omega)  # 45° Phasenverschiebung
    h = np.array([h0, np.real(h1)])  # Nur reale Anteile verwenden
    return h / np.sum(h)

# FIR Hochpassfilter erster Ordnung mit 45° Phasenverschiebung
def fir_highpass(fs, f):
    T = 1 / fs
    omega = 2 * np.pi * f * T
    h0 = 1 / np.sqrt(2)
    h1 = -h0 * np.exp(-1j * omega)  # 45° Phasenverschiebung
    h = np.array([h0, np.real(h1)])  # Nur reale Anteile verwenden
    return h / np.sum(h)

# Funktion zum Verschieben eines Arrays nach rechts
def shift_array_right(arr, N, fillmode):
    if N == 0:
        return arr
    if N > 0:
        if fillmode == "zero":
            return np.concatenate((np.zeros(N), arr[:-N]))
        else:
            return np.concatenate((arr[-N:], arr[:-N]))
    else:
        if fillmode == "zero":
            return np.concatenate((arr[N:]), np.zeros(N))
        else:
            return np.concatenate((arr[N:], arr[0:N]))

##########################################################################
# Signalmodell: Summe zweier Sinussignale, die oversampled abgetastet.
# Komplex ins Basisband gemischt und downsampled werden
# Damit ist die Generierung der COHIRADIA-IQ-Files abgebildet
ds = 1  # Dauer des Signals in Sekunden
fs = 1250  # Abtastfrequenz in Hz
f1 = 65  # Frequenz des ersten Sinussignals
f2 = 120  # Frequenz des zweiten Sinussignals
phi1 = 0  # Phase des ersten Sinussignals
phi2 = np.pi / 4  # Phase des zweiten Sinussignals
flo = 112.5  # Frequenz des komplexen Sinussignals
fs_baseband = 125
downsample_factor = fs_baseband/fs  # Downsampling-Faktor after and primary sampling and mixing to baseband
# Zeitachse definieren
t = np.arange(0, ds, 1/fs)
# Sinussignale und deren Summe erzeugen
s1 = np.sin(2 * np.pi * f1 * t + phi1)
s2 = np.sin(2 * np.pi * f2 * t + phi2)
s = s1 + 0.5*s2
# Komplexes LO-Signal für die Basisband-Mischung
e = np.exp(-1j * 2 * np.pi * flo * t)
# Multiplikation --> Mischung ins Basisband
plot_spectrum(s, fs, "Doppelseitiges Spektrum Originalsignal")
s_mixed = s * e
plot_spectrum(s_mixed, fs, "Doppelseitiges Spektrum nach Mischung")
N_ds = int(np.floor(len(s_mixed) * downsample_factor))
s_downsampled = resample(s_mixed, N_ds)
fs_ds = fs * downsample_factor
plot_spectrum(s_downsampled, fs_ds, "Doppelseitiges Spektrum nach Downsampling")
######################## Signalmodell Ende ###############################

####################### Preprocessing shift Im pi/2 vs Re ####################
#
s_downsampled_shifted =s_downsampled * np.exp(1j * np.pi/2)
imshifted = np.imag(s_downsampled_shifted)
s_downsampled_crosshifted = np.real(s_downsampled) + 1j*imshifted
#
####################### End Preprocessing ####################


########################fl2k-Modell #######################################
# Upsampling auf fs_new

# Upsampling:
upsample_factor = int(1000/fs_baseband)
N_new = len(s_downsampled) * upsample_factor
s_upsampled = resample(s_downsampled, N_new)
fs_new = fs_ds * upsample_factor
plot_spectrum(s_upsampled, fs_new, "Doppelseitiges Spektrum nach Upsampling")

# LO_shift:
# Komplexes Sinussignal mit potenziellem Phasenfehler, zur Simulation des Spektrums bei
# schlechter Generierung des komplexen Sinus-Multiplikators
phierr = 0* np.pi*5/2 #error phase
tus = np.arange(0, ds, 1/fs_new)
ed = np.cos(2 * np.pi * flo * tus) + 1j*np.sin(2 * np.pi * flo * tus + phierr)
ed = np.exp(1j * 2 * np.pi * flo * tus)

###### REFERENCE  Upmixing to original band with complex exponential for reference
s_demod = s_upsampled * ed
#Theoretical signals for comparison
plot_spectrum(s_demod, fs_new, "Doppelseitiges Spektrum nach Upmixing, Referenz theoret")
s_re = np.real(s_demod)
plot_spectrum(s_re, fs_new, "Doppelseitiges Spektrum nach Upmixing, Realteil, Referenz Theoret")
# Upmixing to original band and direct calculation of real part
s_demod_re = np.real(s_upsampled)*np.real(ed) -np.imag(s_upsampled)*np.imag(ed)
plot_spectrum(s_demod_re, fs_new, "Doppelseitiges Spektrum Realteil nach Demodulation simpel")
####### END REFERENCE

# IMPLEMENTATION 1 of ffmpeg script
# Upmixing to original band and immediate extraction of real part with pure sine 
# and approx pi/2 shifted signal -imaginary versus real part; 
Nopt = 1
Nsh = int(np.round(((1+4*Nopt)*fs_new/4/flo)))
#Nsh = 0
print(f"Nsh effective: {Nsh}, nsh not rounded: {((1+4*Nopt)*fs_new/4/flo)}")
imshift = shift_array_right(np.imag(s_upsampled), Nsh, "circ")
s_upsampled_shift = np.real(s_upsampled) + 1j*imshift
s_demod_re_shift = np.real(s_upsampled_shift)* np.sin(2 * np.pi * flo * tus) + shift_array_right(np.imag(s_upsampled_shift)* np.sin(2 * np.pi * flo * tus),-Nsh, "circ") 
plot_spectrum(s_demod_re_shift, fs_new, "Doppelseitiges Spektrum Realteil nach Demodulation Shift and sine")

# IMPLEMENTATION 2 of ffmpeg script
# Upsampling of crossshifted signal and upmixing to original band with pure sine
# and immediate extraction of real part 

s_upsampled_crosssh = resample(s_downsampled_crosshifted, N_new)
s_demod_re_crosssh = (np.real(s_upsampled_crosssh) + np.imag(s_upsampled_crosssh)) * np.sin(2 * np.pi * flo * tus)
plot_spectrum(s_demod_re_crosssh, fs_new, "Doppelseitiges Spektrum Realteil nach Demodulation pre-crosshift and sine")

# Ref in upsampled case
s_upsampled_trueshift =s_upsampled * np.exp(1j * np.pi/2)
s_upsampled_truecrossshift = np.imag(s_upsampled_trueshift)
s_upsampled_crossshifted_true = np.real(s_upsampled) + 1j*s_upsampled_truecrossshift
s_demod_re_truecrosssh = (np.real(s_upsampled_crossshifted_true) + np.imag(s_upsampled_crossshifted_true)) * np.sin(2 * np.pi * flo * tus)
plot_spectrum(s_demod_re_truecrosssh, fs_new, "Doppelseitiges Spektrum Realteil nach Demodulation post-crosshift and sine")

# implem with sin and cose as filtered versions from one sine
# Berechne die FIR-Filterkoeffizienten
# Filterparameter
n = 5  # Ordnung des Filters
cutoff = flo  # Normierte Grenzfrequenz (0 bis 1, wobei 1 = Nyquist-Frequenz)
ffs = 1.0  # Abtastrate (für normierte Frequenzen nicht nötig)
h3 = firwin(n + 1, cutoff, fs=fs_new, pass_zero = True)
#a = firwin()
#coeffs2 = firwin(n + 2, cutoff, window="hamming", fs=fs, pass_zero = False)
## ALLPASS FILTER
a = (np.tan(np.pi * flo / fs_new) - 1) / (np.tan(np.pi * flo / fs_new) + 1)
b = [a, 1]      # Numerator-Koeffizienten
a_coeffs = [1, a]  # Denominator-Koeffizienten
nf = 2*np.pi*flo/fs_new
phi = -nf + 2*np.arctan(a*np.sin(nf)/(1+a*np.cos(nf)))

#h1 = fir_lowpass(fs_new, flo)
#rcos = lfilter(h1, 1.0, np.real(ed))
#rcos2 = 1/0.86*lfilter(h3, 1.0, np.real(ed))
#rcos2 = np.real(ed)
#rcos2 = np.imag(ed)
rcos2 = lfilter(b, a_coeffs, np.imag(ed))
#h2 = fir_highpass(fs_new, flo)
#rsin = 1/3*0.917/0.974*lfilter(h2, 1.0, np.real(ed))
#rsin2 = lfilter(h3, 1.0, -np.imag(ed))
rsin2 = np.imag(ed)
t_new = np.arange(0, ds, 1/fs_new)



plt.figure()
# plt.plot(t_new, rcos, label="cos")
# plt.plot(t_new, rsin, label="sin")
plt.plot(t_new, rcos2, label="cos")
plt.plot(t_new, rsin2, label="sin")
plt.xlabel("time (s)")
plt.ylabel("Amplitude")
plt.title("sin/cos")
plt.legend()
plt.grid()
plt.show()

s_demod_re_lpvers = np.real(s_upsampled) * rcos2 + np.imag(s_upsampled) * rsin2
plot_spectrum(s_demod_re_lpvers, fs_new, "Doppelseitiges Spektrum Realteil nach Demodulation filtered sin/cos")


### filtered sine version: lfilter(h, 1.0, signal)

time.sleep(1)
