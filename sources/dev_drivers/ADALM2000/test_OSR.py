import numpy as np

def maximize_OSR(SRDAC, lo_shift, sampling_rate):
    """Calculate oversampling OSR from SRDAC and required Nyquist frequency
    f_nyquist = (lo_shift+sampling_rate/2))
    OSR is tha value which divides SRDAC such that 
    (1) SRDAC/OSR >= 2 * f_nyquist
    (2) r = SRDAC/OSR is integer, ideally r is an integer multiple of sampling_rate 

    :param SRDAC: sampling rate of the ADALM DAC (clock)
    :type SRDAC: int
    :param lo_shift: central frequency f the band plus offset (LO frequency)
    :type lo_shift: int
    :param sampling_rate: bandwidth of the complex IQ signal == sampling rate of IQ file
    :type sampling_rate: int
    
    :return: oversampling rate OSR

    """
    f_nyquist = lo_shift+sampling_rate/2
    r_max = SRDAC / (2 *f_nyquist) # maximum allowable OSR
    for OSR in np.arange(int(np.floor(r_max)),1,-1):
        r = SRDAC / OSR
        if SRDAC % r == 0:
            break
    return OSR

SRDAC = 75000000
lo_shift = 1800000
sampling_rate = 1250000

OSR = maximize_OSR(SRDAC, lo_shift, sampling_rate)
print(OSR)