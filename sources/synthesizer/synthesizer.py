#IMPORT WHATEVER IS NEEDED
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5 import QtGui
from PyQt5 import QtWidgets, QtGui
import numpy as np
import locale
import os
import logging
from datetime import datetime
import datetime as ndatetime
import matplotlib.pyplot as plt
#import pyfda.pyfdax
from auxiliaries import auxiliaries as auxi
#from auxiliaries import ffmpeg_installtools as ffinst
import logging
import yaml
import copy
import time
import pytz
import wave
import subprocess
import shutil
import re
import pyqtgraph as pg
#import contextlib
import struct
import soundfile as sf
from scipy.signal import sosfilt, butter, resample
from pathlib import Path
import urllib
import sys
from scipy.optimize import fsolve
import platform
import psutil
import signal


#import io
# import pydub
# from pydub import AudioSegment
#import m3u8
from auxiliaries import WAVheader_tools
from auxiliaries import ffmpeg_installtools
#BUGS:
# recognize if web not connected if htp URL import
# autodetect ffmpeg install and install
# mixed files from http and local wav/mpeg is not working properly
# allow for URL sources to be inserted interactively ??

class modulate_worker(QObject):
    """ worker class for generating modulated signals in a separate thread
    :param : no regular parameters; as this is a thread worker communication occurs via
        __slots__: Dictionary with parameters
    :return : none
    """
    __slots__ = ["carrier_frequencies", "playlists","sample_rate","block_size","cutoff_freq","modulation_depth","output_base_name","exp_num_samples","progress","logger","combined_signal_block","LO_freq","gain", "method_object","silence_duration","filesize_limit","ffmpeg_path","synthesizer_temp_path","autolevel"]
    SigFinished = pyqtSignal()
    SigPupdate = pyqtSignal()
    SigMessage = pyqtSignal(str)
    SigError = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stopix = False #TODO: check if necessary
        self.mutex = QMutex() #TODO: check if necessary
        self.CHUNKSIZE = int(1024**2) #TODO: check if necessary, not used anywhere
        self.AUDIO_MAXAMP = 0.9 #max amplitude of the audio signal
        #self.SILENCE_DURATION = 4   #Default duration of silent periods between subsequent audio files (s)

 
    def set_carrier_frequencies(self,_value):
        self.__slots__[0] = _value
    def get_carrier_frequencies(self):
        return(self.__slots__[0])
    def set_playlists(self,_value):
        self.__slots__[1] = _value
    def get_playlists(self):
        return(self.__slots__[1])
    def set_sample_rate(self,_value):
        self.__slots__[2] = _value
    def get_sample_rate(self):
        return(self.__slots__[2])
    def set_block_size(self,_value):
        self.__slots__[3] = _value
    def get_block_size(self):
        return(self.__slots__[3])
    def set_cutoff_freq(self,_value):
        self.__slots__[4] = _value
    def get_cutoff_freq(self):
        return(self.__slots__[4])
    def set_modulation_depth(self,_value):
        self.__slots__[5] = _value
    def get_modulation_depth(self):
        return(self.__slots__[5])
    def set_output_base_name(self,_value):
        self.__slots__[6] = _value
    def get_output_base_name(self):
        return(self.__slots__[6])
    def set_exp_num_samples(self,_value):
        self.__slots__[7] = _value
    def get_exp_num_samples(self):
        return(self.__slots__[7])
    def set_progress(self,_value):
        self.__slots__[8] = _value
    def get_progress(self):
        return(self.__slots__[8])
    def set_logger(self,_value):
        self.__slots__[9] = _value
    def get_logger(self):
        return(self.__slots__[9])
    def set_combined_signal_block(self,_value):
        self.__slots__[10] = _value
    def get_combined_signal_block(self):
        return(self.__slots__[10])
    def set_LO_freq(self,_value):
        self.__slots__[11] = _value
    def get_LO_freq(self):
        return(self.__slots__[11])
    def set_gain(self,_value):
        self.__slots__[12] = _value
    def get_gain(self):
        return(self.__slots__[12])
    def set_method_object(self,_value):
        self.__slots__[13] = _value
    def get_method_object(self):
        return(self.__slots__[13])
    def set_silence_duration(self,_value):
        self.__slots__[14] = _value
    def get_silence_duration(self):
        return(self.__slots__[14])  
    def set_filesize_limit(self,_value):
        self.__slots__[15] = _value
    def get_filesize_limit(self):
        return(self.__slots__[15])
    def set_ffmpeg_path(self,_value):
        self.__slots__[16] = _value
    def get_ffmpeg_path(self):
        return(self.__slots__[16])
    def set_synthesizer_temp_path(self,_value):
        self.__slots__[17] = _value
    def get_synthesizer_temp_path(self):
        return(self.__slots__[17])
    def set_autolevel(self,_value):
        self.__slots__[18] = _value
    def get_autolevel(self):
        return(self.__slots__[18])
    
    def modulate_terminate(self):
        print("modulate terminate received")
        self.stopix = True

    def start_modulator(self):
        """fetches several parameters from the main thread and starts process_multiple_carriers_blockwise
        emits SigFinished after comletion of the task for triggering termination of the worker thread
        """
        self.logger = self.get_logger()
        self.stopix = False
        carrier_frequencies = self.get_carrier_frequencies()
        playlists = self.get_playlists()
        sample_rate = self.get_sample_rate()
        block_size = self.get_block_size()
        cutoff_freq = self.get_cutoff_freq()
        modulation_depth = self.get_modulation_depth()
        output_base_name = self.get_output_base_name()
        exp_num_samples = self.get_exp_num_samples()
        init_phases = self.generate_multisine_phases(carrier_frequencies)
        self.process_multiple_carriers_blockwise(carrier_frequencies, playlists, sample_rate, block_size, cutoff_freq, modulation_depth, output_base_name, exp_num_samples,init_phases)
        self.SigFinished.emit()

    def resample_audio(self,audio_data, original_rate, target_rate):
        """
        Resample audio data to the target sample rate.
        """
        num_samples = int(len(audio_data) * target_rate / original_rate)
        return resample(audio_data, num_samples)

    def convert_to_mono(self,audio_data, num_channels):
        """
        Convert multi-channel audio to mono by averaging channels.
        """
        if num_channels > 1:
            return np.mean(audio_data, axis=1)
        return audio_data

    def process_block(self,audio_block, sos, zi):
        """Apply the low-pass filter blockwise and maintain filter state (zi)."""
        filtered_block, zi = sosfilt(sos, audio_block, zi=zi)
        return filtered_block, zi
    
    def modulate_signal(self,filtered_signal, carrier_freq, sample_rate, sample_offset, modulation_depth, phase):
        """Modulate the filtered signal onto a carrier frequency with adjustable modulation depth."""
        # time vector based on sample_offset
        t = np.arange(sample_offset, sample_offset + len(filtered_signal)) / sample_rate
        carrier = np.exp(2 * np.pi * 1j *carrier_freq * t + phase * 1j)
        modulated_signal = (1 + modulation_depth * filtered_signal) * carrier
        #print(f"mean modulated signal: {np.mean(modulated_signal)} mean real part: {np.mean(np.real(modulated_signal))} mean imag part: {np.mean(np.imag(modulated_signal))}")
        return modulated_signal
    
    def generate_multisine_phases(self,frequencies):
        """
        Generiert Schröder-Phasen für ein Multisinus-Signal .
        
        Parameters:
        - frequencies: Liste der Frequenzkomponenten (Hz)
        - amplitudes: Liste der Amplituden (gleiche Länge wie frequencies)
        - sampling_rate: Abtastrate (Hz)
        - duration: Dauer des Signals (Sekunden)
        - optimize_phases: Bool, ob Schröder-Phasen genutzt werden sollen
        
        Returns:
        - t: Zeitvektor
        - signal: Multisinus-Signal
        """
        N = len(frequencies)  # Anzahl der Frequenzkomponenten
        phases = np.array([-np.pi * k * (k - 1) / N for k in range(1, N + 1)])
        return phases


    def display_signal_level(self,signal):
        """
        calculate the RMS and peak values of a signal
        """

    def get_wav_maxlevel(self,wav_file, carrier_freq, threshold_percentile=95, spike_duration_ms=1):
        """determine expected max signal level of an audio file. Do not consider short spikes with a duration of less than a ms

        :param wav_file: path of the audio file
        :type wav_file: str
        :param threshold_percentile: allowable max signal in % of FSR, defaults to 95
        :type threshold_percentile: int, optional
        :param spike_duration_ms: max duration of a spike (will be ignored then), defaults to 1
        :type spike_duration_ms: int, optional
        :param carrier_freq: carrier frequency
        :type carrier_freq: float
        :return: expected max amp
        :rtype: float
        """
        print(f"file: {Path(wav_file).stem} level checking")
        LO_freq = self.get_LO_freq()
        self.SigMessage.emit(f"auto level @ f {str(np.ceil((carrier_freq + LO_freq)/1000))}: " + Path(wav_file).stem)
        #self.gui.label_audioset_name.setText(f"file: {Path(wav_file).stem} level checking")
        #TODO CHECK last change:data, sample_rate = sf.read(wav_file)
        method_object = self.get_method_object()
        print(f"calling method: {method_object.readsoundfile}, argument: {wav_file}")
                    #TODO TODO TODO LAST: catch error when returned False: Fils not foun o.ä. --> break loop

        errorstatus, a = method_object.readsoundfile(wav_file)
        #TODO CHECK: treat errorstatus correctly
        #if not a:
        if errorstatus:
            self.SigError.emit(str(a))
            self.SigFinished.emit()
            #TODO: make correct errorhandling chain with errorstatus, value and treat in uppermost level !
            return False
        data = a.read()
        sample_rate = a.samplerate
        # convert to Mono, if signal is stereo TODO: check: mean may be lower than individual channel values !
        if len(data.shape) > 1:
            data = data.mean(axis=1)
        # calc absolute amplitudes
        amplitudes = np.abs(data)   
        # calc sample duration in milliseconds
        sample_duration_ms = 1000 / sample_rate
        # calc number of samples which can be considered as 'short peaks'
        max_spike_samples = int(spike_duration_ms / sample_duration_ms)
        # Berechne den Schwellenwert für die Amplitude auf Basis des `threshold_percentile`-Perzentils
        threshold_value = np.percentile(amplitudes, threshold_percentile)
        # Erstelle eine Kopie der Amplituden und setze kurze Spitzen auf Null
        filtered_amplitudes = amplitudes.copy() 
        # Durchlaufe die Amplituden und setze kurze Spitzen unterhalb der max_spike_samples auf 0
        for i in range(1, len(amplitudes) - 1):
            # Wenn eine Amplitude den Schwellenwert überschreitet
            if amplitudes[i] >= threshold_value:
                # Prüfe, ob es eine kurze Spitze ist (alle Amplituden in diesem Bereich überschreiten den Schwellenwert)
                start = max(i - max_spike_samples // 2, 0)
                end = min(i + max_spike_samples // 2, len(amplitudes))
                if np.all(amplitudes[start:end] >= threshold_value):
                    # Setze die Spitzen im Bereich auf 0
                    filtered_amplitudes[start:end] = 0
        # Bestimme die erwartete maximale Amplitude nach Filterung der Spitzen
        expected_max_amp = filtered_amplitudes.max() if filtered_amplitudes.size > 0 else amplitudes.max()
        expected_RMS_amp = filtered_amplitudes.std() if filtered_amplitudes.size > 0 else amplitudes.std()
        print("ready")
        self.SigMessage.emit("----")
        return expected_max_amp, expected_RMS_amp


    def read_and_process_audio_blockwise(self, file_list, carrier_freq, target_sample_rate, ref_block_size, modulation_depth, zi, sample_offset, current_file_index, file_handles, audio_gain, silence, cumulative_time,sos, phase):
        """
        Read and process audio blockwise from the current file in the file_list, keeping the file handle open.
        Process only one block and move to the next file when the current one is finished.
        
        Args:
        - file_list: List of audio file paths for the current carrier.
        - carrier_freq: Carrier frequency for modulation.
        - target_sample_rate: Target sample rate for processing.
        - block_size: Size of the audio block to be processed.
        - cutoff_freq: Cutoff frequency for the low-pass filter.
        - modulation_depth: Depth of modulation.
        - zi: Filter state to maintain continuity across blocks.
        - sample_offset: Current sample offset for phase continuity in modulation.
        - current_file_index: Index of the current file in the file_list.
        - file_handles: Dictionary of file handles to keep files open.
        : type: dict
        - silence: flag which states whether the current block should be silent (zero audio for pauses between audio files)
        - cumulative_time: time of silence which has passed for this carrier so far

        Returns:
        - modulated_output: Modulated block of audio.
        - zi: Updated filter state.
        - sample_offset: Updated sample offset.
        - current_file_index: Updated file index (incremented if necessary).
        - silence: updated flag which states if there should remain silence at the moment
        - cumulative_time: updated time of silence which has passed for this carrier so far
        """
        #print(f"read_and_process_audio_blockwise; current_file_index: {current_file_index}, carrier_freq {carrier_freq}")
        #sos = butter(4, cutoff_freq, btype='low', fs=target_sample_rate, output='sos')
        reference_sample_rate = 44100 #56000#
        #print(f"carrier-freq: {carrier_freq}")
        threshold_percentile=95
        #define characteristics of outliers (short spikes)
        spike_duration_ms=1
        while current_file_index < len(file_list):
            file_path = file_list[current_file_index]

            # check if file open, if not: check level and power statistics, afterwards open the file and save the handles
            if (current_file_index not in file_handles) and (not silence):
                #print(f"############### index: {current_file_index} file_handles: {file_handles}, file path: {file_path}")
                print(carrier_freq)
                max_level, RMS_amp = self.get_wav_maxlevel(file_path, carrier_freq, threshold_percentile, spike_duration_ms)
                audio_gain = self.AUDIO_MAXAMP/max_level
                self.logger.debug(f"Audiofile {file_path} max_level: {max_level}, RMS_amp: {RMS_amp}, audio_gain auto: {audio_gain}")
                #file_handles[current_file_index] = sf.SoundFile(file_path, 'r')
                method_object = self.get_method_object()
               
                errorstatus, value = method_object.readsoundfile(file_path)
                file_handles[current_file_index] = value
                #TODO CHECK: read errorstatus and react
                #if not file_handles[current_file_index]:
                if errorstatus:
                    #TODO TODO TODO: connect errormessage method to SigError
                    self.SigError.emit(str(value))
                    self.SigFinished.emit()
                    return False

            if silence:
                # generate zero audio block for silence between subsequent audio files
                original_sample_rate = 44100
                block_size = int(np.floor(ref_block_size *  original_sample_rate / reference_sample_rate))
                audio_block = np.zeros(block_size)
                num_channels = 1
                cumulative_time += block_size/original_sample_rate
                print(f"make silence block at carrier {carrier_freq} until {cumulative_time}")
                # check if silence has already reached maximum length
                if cumulative_time >= self.get_silence_duration():
                    silence = False
                    cumulative_time = 0
            else:    
                #print(f"#####nextsegment##### index: {current_file_index} file_handles: {file_handles}, file path: {file_path}")
                # read next audio block from audio file
                f = file_handles[current_file_index]
                #print(f"#####nextsegment##### index: {current_file_index} cur file_handles: {f}")
                original_sample_rate = f.samplerate
                num_channels = f.channels
                #TODO: 
                block_size = int(np.floor(ref_block_size * original_sample_rate / reference_sample_rate))
                audio_block = f.read(block_size)

            if len(audio_block) == 0 and not silence:
                # Audio file is finished, close file and open next one
                print(f"close file {file_path} with index {current_file_index}; open next in list")
                f.close()

                if file_path.find("http://")>=0 or file_path.find("https://")>=0:
                    temp_file = Path(file_path).stem + ".wav"
                    #print(f"oooooooooo>>>>> worker, jump to next file, localize temp aud file {temp_file}")
                    if os.path.isfile(temp_file):
                        os.remove(temp_file)
                        #print(f"oooooooooo>>>>> worker, jump to next file, remove temp aud file {temp_file}")

                del file_handles[current_file_index]  # remove Handle
                current_file_index += 1
                silence = True
                continue  # do not modulate, continue with the next audio file

            # Mono-conversion
            audio_block = audio_gain * self.convert_to_mono(audio_block, num_channels)
            #zero pad audio block to blocksize
            if len(audio_block) < block_size:
                delta = block_size - len(audio_block)
                aux = np.zeros(block_size)
                print(f"zeropad audio block, pad length = {delta}, len audioblock: {len(audio_block)}" )
                aux[0 : len(audio_block)] = audio_block
                audio_block = aux
            # Resamplingif required
            ##### TODO: entry point for ffmpeg version: pass audio directly to ffmpeg
            if original_sample_rate != target_sample_rate:
                audio_block = self.resample_audio(audio_block, original_sample_rate, target_sample_rate)

            # Low-pass-filter audio signal
            filtered_block, zi = self.process_block(audio_block, sos, zi)

            # modulate to carrier
            phase = 0
            modulated_block = self.modulate_signal(filtered_block, carrier_freq, target_sample_rate, sample_offset, modulation_depth, phase)
            # update sample_offset for next block
            sample_offset += len(modulated_block)

            #TODO: here end of ffmpeg, which returns the modulated block directly

            return modulated_block, zi, sample_offset, current_file_index, audio_gain, silence, cumulative_time
        
        return None, zi, sample_offset, current_file_index, audio_gain, silence, cumulative_time
        
    def process_multiple_carriers_blockwise(self, carrier_frequencies, playlists, sample_rate, block_size, cutoff_freq, modulation_depth, output_base_name, exp_num_samples, phases):
        """_summary_
        Process audio from multiple playlists blockwise, each corresponding to a different carrier frequency.
        Write the combined output to multiple WAV files if the 2 GB limit is exceeded.

        :param carrier_frequencies: list of carrier frequencise
        :type carrier_frequencies: list of float
        :param playlists: _description_
        :type playlists: _type_
        :param sample_rate: sample rate
        :type sample_rate: float
        :param block_size: size of one data block for modulation
        :type block_size: int
        :param cutoff_freq: cutoff frequency of the lowpass filter for audio before modulation
        :type cutoff_freq: float
        :param modulation_depth: _description_
        :type modulation_depth: _type_
        :param output_base_name: _description_
        :type output_base_name: _type_
        :param exp_num_samples: expected number of samples
        :type exp_num_samples: integer
        """
        print(f"#######################  carrier frequencies: {carrier_frequencies}")
        self.set_progress(0)
        self.logger.debug(f"process_multiple_carriers_blockwise; carrier_frequencies:{carrier_frequencies}")
        self.stopix = False
        max_file_size = self.get_filesize_limit() #2 * 1024**3  # 2 GB in bytes
        self.logger.debug(f"max filesize set to: {max_file_size}")
        self.logger.debug(f"process_multiple_carriers_blockwise: expected overall filesize: {4*exp_num_samples}")
        max_samples_per_file = max_file_size // 4  # complex 16-bit PCM = 4 bytes per sample
        perc_progress_old = 0
        # Initialize filter states for each carrier
        filterorder = 12
        sos = butter(filterorder, cutoff_freq, btype='low', fs=sample_rate, output='sos')
        num_sections = sos.shape[0]  # calc number of section, corresp to order / 2
        zis = [np.zeros((num_sections, 2)) for _ in carrier_frequencies]  # Filter state buffer for each carrier (4th order filter)

        # Initialize sample_offset and current_file_index for each carrier
        sample_offsets = [0] * len(carrier_frequencies)
        current_file_indices = [0] * len(carrier_frequencies)  # Track current file index for each carrier
        self.logger.debug(f"synthesizer worker carrier frequencies: {carrier_frequencies}")
        # Initialize file_handles as a list of empty dictionaries for each carrier
        file_handles = [{} for _ in carrier_frequencies] 
        total_samples_written = 0
        overall_samples_written = 0
        file_index = 0
        # Open first output file to write combined signal blockwise
        output_file_name = f"{output_base_name}_{file_index}.wav"
        out_file = sf.SoundFile(output_file_name, 'w', samplerate=sample_rate, channels=1, subtype='PCM_16')
        done = False
        #write 216 - 44 =  172 Null Bytes so as to leave room for the SDR-wavheader which will finally overwrite the current header
        prephaser = np.zeros(172)
        out_file.write(prephaser)
        #generate starting timestamp for wavheader
        next_starttime = datetime.now()
        next_starttime = next_starttime.astimezone(pytz.utc)
        self.logger.debug(f"synthesizer worker sample rate before modulating: {sample_rate}")
        audio_gain = np.zeros(len(playlists))
        cumulative_time = np.zeros(len(playlists))
        silence = [False] * len(playlists)
        while not done:
            reftime = time.time()
            if self.stopix is True:
                break
            combined_signal_block = None  # Buffer for combined signal block
            done = True  # Assume done unless we find more data
            # Process each carrier for the current block
            for i, (carrier_freq, zi, phase) in enumerate(zip(carrier_frequencies, zis, phases)):
                #print(f"filehandles in modulate_worker, process mult carr blw: {file_handles}")
                if self.stopix is True:
                    break
                print(f">>>>>>>>>>>>> process mult carr block, carrier_freq: {carrier_freq}, phase {phase}:  ")
                modulated_block, new_zi, sample_offsets[i], current_file_indices[i], audio_gain[i], silence[i], cumulative_time[i] = self.read_and_process_audio_blockwise(playlists[i], carrier_freq*1000, sample_rate, block_size, modulation_depth, zi, sample_offsets[i], current_file_indices[i], file_handles[i], audio_gain[i], silence[i], cumulative_time[i],sos, phase)

                if modulated_block is None: #--> end of Playlist has been reached
                    continue
                # Dynamically adjust combined signal block size based on modulated block size

                if combined_signal_block is None or len(combined_signal_block) < len(modulated_block):
                    
                    self.logger.debug(f"modulated block is None or short  @ t = {sample_offsets[i]}, carrier = {i}")
                    if combined_signal_block is None:
                        combined_signal_block = np.zeros(len(modulated_block), dtype = np.complex128)
                        pass
                    else:
                        self.logger.debug(f"modulated block is None or short len = {len(combined_signal_block)}, ZEROPAD")
                        self.logger.debug(f"None/shortlen: diff len combined block -len mod block: {len(combined_signal_block) - len(modulated_block)}")
                        difflen = len(modulated_block) - len(combined_signal_block)  
                        zero_padding = np.zeros(difflen, dtype=np.complex128)
                        combined_signal_block = np.concatenate((combined_signal_block, zero_padding))
                    ######combined_signal_block = np.zeros(len(modulated_block), dtype = np.complex128)
                gain = self.get_gain()
                if np.abs(len(combined_signal_block) - len(modulated_block)) > 0:
                    print(f"modulated block std gain*mb = {np.std(gain*modulated_block)} , gain = {gain} @ t = {sample_offsets[i]}, carrier = {i}")
                    print(f"diff len combined block -len mod block: {len(combined_signal_block) - len(modulated_block)}")
                    self.logger.debug(f"modulated block std gain*mb = {np.std(gain*modulated_block)} , gain = {gain} @ t = {sample_offsets[i]}, carrier = {i}")
                    self.logger.debug(f"diff len combined block -len mod block: {len(combined_signal_block) - len(modulated_block)}")
                combined_signal_block[:len(modulated_block)] += gain * modulated_block
                LO_freq = self.get_LO_freq()
                self.SigMessage.emit(f"###modulating at carrier: {str(carrier_freq + LO_freq/1000)}")
                if np.std(gain*modulated_block) < 1e-3:
                    print(f"modulated block is zero, std gain*mb = {np.std(gain*modulated_block)} , gain = {gain} @ t = {sample_offsets[i]}")   
                    self.logger.debug(f"modulated block is zero, std gain*mb = {np.std(gain*modulated_block)} , gain = {gain} @ t = {sample_offsets[i]}")   
                # If we processed any blocks, we're not done
                done = False

                # Update filter state for this carrier
                zis[i] = new_zi

            # If all files are done, break the loop
            if done:
                break
            
            if self.stopix is True:
                break

            # Write the combined block to the current output file
            samples_to_write = len(combined_signal_block)
            #TODO: not exactly closing at 2GB, this is sometimes unconvenient
            if samples_to_write + total_samples_written > max_samples_per_file:
                # If the file exceeds 2GB, close the current file, enter the wav-header and start a new one
                out_file.close()
                filesize = max_samples_per_file*4
                self.logger.debug(f"process_multiple_carriers_blockwise: next starttime {next_starttime}")
                output_file_name_wavheader = output_file_name
                file_index += 1
                output_file_name = f"{output_base_name}_{file_index}.wav"
                filesize_towav = min(2 * 1024**3, filesize)
                next_starttime = self.wav_header_generator(output_file_name_wavheader,filesize_towav,sample_rate,next_starttime,output_file_name)
                print("wavheader written")
                out_file = sf.SoundFile(output_file_name, 'w', samplerate=sample_rate, channels=1, subtype='PCM_16')
                total_samples_written = 0  # Reset the sample counter for the new file

        
            #convert complex 128 into 2 x float 64
            lend=2*len(combined_signal_block)
            #TODO check if carrier zero gap arises here
            block_to_write = np.zeros(lend)
            block_to_write[1::2] = np.imag(combined_signal_block)
            block_to_write[0::2] = np.real(combined_signal_block)
            try:
                out_file.write(block_to_write)
            except:
                print("write error")
            total_samples_written += samples_to_write
            overall_samples_written += samples_to_write
            perc_progress = 100*overall_samples_written / exp_num_samples
            if perc_progress - perc_progress_old > 0.1:
                perc_progress_old = perc_progress
                self.set_progress(perc_progress)
                self.set_combined_signal_block(combined_signal_block)
                self.SigPupdate.emit()
                if perc_progress > 100:
                    break
            deltatime = time.time() - reftime
            print(f"block with size : {block_size} written, time: {deltatime}")            
        # Close the final output file
        out_file.close()
        filesize = total_samples_written*4
        self.logger.debug(f"synthesizer modulate: filesize last out file: {filesize}")

        output_file_name_wavheader = output_file_name
        self.wav_header_generator(output_file_name_wavheader,filesize,sample_rate,next_starttime,"")
        self.logger.debug(f"write last wavheader into {output_file_name_wavheader}")
        
        #TODO : Check if already completely o.k. ! write true SDRUno-Header into the first 216 bytes of the closed file
        for file_handle_dict in file_handles:
            for handle in file_handle_dict.values():
                handle.close()
        self.logger.debug(f"synthesizer modulate task completed")

    def wav_header_generator(self, output_file_name, filesize,sample_rate, starttime, next_output_file_name):
        """generate wavheader for output_file_name:
        :param: output_file_name
        """
        LO_freq = self.get_LO_freq()
        playtime = filesize/4/sample_rate
        self.mutex.lock()
        self.logger.debug(f"wav_header_generator: playtime of file {playtime}")
        self.logger.debug(f"wav_header_generator: calculated filesize of file {filesize}")
        #generate basic SDR wavheader
        wavheader = WAVheader_tools.basic_wavheader(self,0,int(np.floor(sample_rate)),LO_freq,16,filesize,starttime)
        wavheader["starttime"] = [starttime.year, starttime.month, 0, starttime.day, starttime.hour, starttime.minute, starttime.second, int(starttime.microsecond/1000)]  
        wavheader["starttime_dt"] = starttime
        wavheader["stoptime_dt"] = wavheader["starttime_dt"] + ndatetime.timedelta(seconds = np.floor(playtime))
        spt = wavheader["stoptime_dt"] 
        wavheader["stoptime"] = [spt.year, spt.month, 0, spt.day, spt.hour, spt.minute, spt.second, int(spt.microsecond/1000)] 
        wavheader["nextfilename"] = Path(next_output_file_name).stem + Path(next_output_file_name).suffix
        self.logger.debug(f"wav_header_generator: wavheader {wavheader}")

        WAVheader_tools.write_sdruno_header(self,output_file_name,wavheader,True) ##TODO TODO TODO Linux conf: self.m["f1"],self.m["wavheader"] must be in Windows format
        self.mutex.unlock()
        return wavheader["stoptime_dt"]

class modulate_worker_ffmpeg(QObject):
    """ worker class for generating modulated signals in a separate thread with ffmpeg
    :param : no regular parameters; as this is a thread worker communication occurs via
        __slots__: Dictionary with parameters
    :return : none
    """
    __slots__ = ["carrier_frequencies", "playlists","sample_rate","block_size","cutoff_freq","modulation_depth","output_base_name","exp_num_samples","progress","logger","combined_signal_block","LO_freq","gain", "method_object","silence_duration","filesize_limit","ffmpeg_path","synthesizer_temp_path", "autolevel"]
    SigFinished = pyqtSignal()
    SigPupdate = pyqtSignal()
    SigMessage = pyqtSignal(str)
    SigError = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stopix = False #TODO: check if necessary
        self.mutex = QMutex() #TODO: check if necessary
        self.CHUNKSIZE = int(1024**2) #TODO: check if necessary, not used anywhere
        self.AUDIO_MAXAMP = 0.9 #max amplitude of the audio signal
        #self.SILENCE_DURATION = 4   #Default duration of silent periods between subsequent audio files (s)

 
    def set_carrier_frequencies(self,_value):
        self.__slots__[0] = _value
    def get_carrier_frequencies(self):
        return(self.__slots__[0])
    def set_playlists(self,_value):
        self.__slots__[1] = _value
    def get_playlists(self):
        return(self.__slots__[1])
    def set_sample_rate(self,_value):
        self.__slots__[2] = _value
    def get_sample_rate(self):
        return(self.__slots__[2])
    def set_block_size(self,_value): #NOT NEEDED
        self.__slots__[3] = _value
    def get_block_size(self):#NOT NEEDED
        return(self.__slots__[3])
    def set_cutoff_freq(self,_value):
        self.__slots__[4] = _value
    def get_cutoff_freq(self):
        return(self.__slots__[4])
    def set_modulation_depth(self,_value):
        self.__slots__[5] = _value
    def get_modulation_depth(self):
        return(self.__slots__[5])
    def set_output_base_name(self,_value):
        self.__slots__[6] = _value
    def get_output_base_name(self):
        return(self.__slots__[6])
    def set_exp_num_samples(self,_value):
        self.__slots__[7] = _value
    def get_exp_num_samples(self):
        return(self.__slots__[7])
    def set_progress(self,_value):
        self.__slots__[8] = _value
    def get_progress(self):
        return(self.__slots__[8])
    def set_logger(self,_value):
        self.__slots__[9] = _value
    def get_logger(self):
        return(self.__slots__[9])
    def set_combined_signal_block(self,_value):
        self.__slots__[10] = _value
    def get_combined_signal_block(self):
        return(self.__slots__[10])
    def set_LO_freq(self,_value):
        self.__slots__[11] = _value
    def get_LO_freq(self):
        return(self.__slots__[11])
    def set_gain(self,_value):
        self.__slots__[12] = _value
    def get_gain(self):
        return(self.__slots__[12])
    def set_method_object(self,_value):
        self.__slots__[13] = _value
    def get_method_object(self):
        return(self.__slots__[13])
    def set_silence_duration(self,_value):
        self.__slots__[14] = _value
    def get_silence_duration(self):
        return(self.__slots__[14])  
    def set_filesize_limit(self,_value):
        self.__slots__[15] = _value
    def get_filesize_limit(self):
        return(self.__slots__[15])
    def set_ffmpeg_path(self,_value):
        self.__slots__[16] = _value
    def get_ffmpeg_path(self):
        return(self.__slots__[16])
    def set_synthesizer_temp_path(self,_value):
        self.__slots__[17] = _value
    def get_synthesizer_temp_path(self):
        return(self.__slots__[17])
    def set_autolevel(self,_value):
        self.__slots__[18] = _value
    def get_autolevel(self):
        return(self.__slots__[18])
    
    def modulate_terminate(self):
        print("modulate terminate received")
        self.stopix = True
    
    def generate_multisine_delays(self,frequencies,sampling_rate,alignment=4):
        """
        Generates Schröder phases for a multisine signal and convert them to delays in Samples.
        The phases are shifted so that the first entry is zero (reference phase)
        :param: frequencies: List of frequency components (Hz) 
        :type: list
        :param: sampling_rate (S/s)
        :type: int 
        :param: alignment: block alignment: typical 4
        :type: int
        :return: delays: Array of delays in samples
        :rtype: np.ndarray
        :return: phases: Array of Schröder phases
        :rtype: np.ndarray
        """
        N = len(frequencies)  # Anzahl der Frequenzkomponenten
        phases = np.array([-np.pi * k * (k - 1) / N for k in range(1, N + 1)])
        phases = phases - np.ones(len(phases)) * phases[0]  # subtract first phase --> first carrier is reference with zero phase
        #convert to delays
        delays = np.zeros(len(phases))
        for i in range(len(phases)):
            delays[i] = (phases[i] * sampling_rate * alignment) / (2 * np.pi * frequencies[i] )
            #round to nearest alignment
            delays[i] = int(np.round(delays[i] / alignment) * alignment)
        return delays, phases

# ph = w * T = w * ts * N / alignment = w/fs*N/alignment
# N = ph * fs * alignment/ (w )

    def start_modulator(self):
        """fetches several parameters from the main thread and starts process_multiple_carriers_ffmpeg
        emits SigFinished after comletion of the task for triggering termination of the worker thread
        """
        print("ffmpeg start modulator reached")
        self.logger = self.get_logger()
        self.stopix = False
        carrier_frequencies = self.get_carrier_frequencies()
        playlists = self.get_playlists()
        sample_rate = self.get_sample_rate()
        #block_size = self.get_block_size()
        cutoff_freq = self.get_cutoff_freq()
        modulation_depth = self.get_modulation_depth()
        output_base_name = self.get_output_base_name()
        exp_num_samples = self.get_exp_num_samples()
        silence_duration = self.get_silence_duration()
        #init_phases = self.generate_multisine_phases(carrier_frequencies)
        self.process_multiple_carriers_ffmpeg(carrier_frequencies, playlists, sample_rate, cutoff_freq, modulation_depth, output_base_name, exp_num_samples, silence_duration)
        self.SigFinished.emit()

    def process_and_concat_audio(self,input_files, output_path, sample_rate=44100, fc_lp=4500, silence_duration=4.0, autolevel_flag=False, max_duration_sec=None):
        """ concatenate multiple audio files with silence in between
        :param input_files: list of input files
        :type input_files: list
        :param output_path: path to output file
        :type output_path: str
        :param sample_rate: sample rate, defaults to 44100
        :type sample_rate: int, optional
        :param fc_lp: cutoff frequency for lowpass filter, defaults to 4500
        :type fc_lp: int, optional
        :param silence_duration: duration of silence between files, defaults to 4.0
        :type silence_duration: float, optional
        :param autolevel_flag: flag for automatic level adjustment, defaults to False
        :type autolevel_flag: bool, optional
        :return: None
        """
        
        assert len(input_files) > 0, "minimum one file is required"
        print("process_and_concat_audio reached")
        # 6x Lowpass-Filter for 12. order pseudo-Butterworth
        lp_filter_chain = ",".join([f"lowpass=f={fc_lp}"] * 6)
        inputs = []
        filters = []
        for idx, infile in enumerate(input_files):
            inputs.extend(["-i", str(infile)])
            if autolevel_flag:
                filters.append(
                    f"[{idx}:a]"
                    f"loudnorm=I=-16:TP=-1.5:LRA=11,"
                    #######TODO TODO TODO: implement normalization at this stage !
                    #"[outa]loudnorm=I=-16:TP=-1.5:LRA=11[out]"
                    f"aresample={sample_rate},"
                    f"pan=mono|c0=0.4*c0+0.4*c1," #TODO: 0.4 is a first rough idea against Clipping
                    f"{lp_filter_chain}"
                    f"[a{idx}]"
                )
            else:
                filters.append(
                    f"[{idx}:a]"
                    f"aresample={sample_rate},"
                    f"pan=mono|c0=0.4*c0+0.4*c1," #TODO: 0.4 is a first rough idea against Clipping
                    f"{lp_filter_chain}"
                    f"[a{idx}]"
                )                
        # silence parts
        num_silences = len(input_files) - 1
        for j in range(num_silences):
            inputs.extend([
                "-f", "lavfi", "-t", str(silence_duration),
                "-i", f"aevalsrc=0:d={silence_duration}:s={sample_rate}"
            ])
            filters.append(f"[{len(input_files) + j}:a]aresample={sample_rate}[s{j}]")
        # concatenation: [a0][s0][a1][s1][a2]...
        concat_parts = []
        for i in range(len(input_files) + num_silences):
            if i % 2 == 0:
                concat_parts.append(f"[a{i // 2}]")
            else:
                concat_parts.append(f"[s{i // 2}]")

        filter_concat = (
            ";".join(filters) + ";" + 
            "".join(concat_parts) + 
            f"concat=n={len(concat_parts)}:v=0:a=1[out]"
        )



        # FFmpeg-command
        cmd = [
            os.path.join(self.get_ffmpeg_path(), "ffmpeg"), "-y", *inputs,
            "-filter_complex", filter_concat,
            "-map", "[out]"
            # "-f", "wav", "-acodec", "pcm_s16le", #for debug
            # str(output_path)
        ]
        if max_duration_sec is not None:
            cmd.extend(["-t", str(max_duration_sec)])

        cmd.extend(["-f", "wav", "-acodec", "pcm_s16le", str(output_path)])

        self.logger.debug(f"audio cat command: {cmd}")
        #print("Running FFmpeg command:\n", " ".join(cmd))
        subprocess.run(cmd, check=True)
        self.logger.debug("audio cat completed")

    def get_aligned_block(self, filename, block_size, alignment, safety_margin):
        """reads a block of data from the end of a file, aligned to a specified byte boundary

        :param filename: _description_
        :type filename: _type_
        :param block_size: _description_
        :type block_size: _type_
        :param alignment: _description_
        :type alignment: _type_
        :param safety_margin: _description_
        :type safety_margin: _type_
        :return: _description_
        :rtype: _type_
        """
        file_size = os.path.getsize(filename)

        # Zielposition: ein Stück vor Dateiende
        max_read_pos = file_size - safety_margin
        if max_read_pos < block_size:
            self.logger.debug("short file, no valid data, return dummy array")
            return np.ones(block_size, dtype=np.complex128)  # file too small, return dummy value

        # Starte Block so, dass Anfang < max_read_pos und ausgerichtet
        #start = max_read_pos - (block_size)
        #start -= start % alignment  # Rundung auf nächstes Vielfaches von ALIGNMENT
        # determine how many blocks N fit into interval max_read_pos - block size
        # Then start = N * block_size
        start = int(np.floor(max_read_pos / block_size)) * block_size
        #start = max_read_pos - (block_size)
        start -= start % alignment  # Rundung auf nächstes Vielfaches von ALIGNMENT
        self.logger.debug(f"start position of block: {start}")

        data = np.empty(block_size, dtype=np.int16)
        with open(filename, "rb") as f:
            f.seek(start)
            f.readinto(data)
            # convert to complex
            int_data = np.frombuffer(data, dtype=np.int16)
            complex_data = (int_data[::2] + 1j * int_data[1::2]) / 32768.0
            self.logger.debug(f"get_aligned_block; return complex data of len:{len(complex_data)}")
            return complex_data
        
        
    def run_ffmpeg_with_progress(self,ffmpeg_cmd, total_duration_sec, numcarriers, percent_old, filename):
        """Start ffmpeg command with intermediate output of the progress; progress is reported in 'progress'
        :param ffmpeg_cmd: modulatingffmpeg command to be executed
        :type ffmpeg_cmd: list of str
        :param total_duration_sec: total duration of the file
        :type total_duration_sec: float
        :param numcarriers: number of carriers
        :type numcarriers: int
        :param percent_old: old progress value from previous run
        :type percent_old: float
        :param filename: name of the file to be processed
        :type filename: str
        :return: progress value after current run
        :rtype: float
        """
        errorstate = False
        value = ""
        percent = 0
        # process = subprocess.Popen(
        #     ffmpeg_cmd,
        #     stderr=subprocess.PIPE,
        #     text=True,  # entspricht universal_newlines=True
        #     encoding='utf-8',
        #     bufsize=1
        # )
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, 
            text=True,
            encoding='utf-8',
            bufsize=1
        )

        time_re = re.compile(r'time=(\d+):(\d+):(\d+).(\d+)')

        for line in process.stdout:
            sys.stdout.write(line)  # optional: zeige FFmpeg-Ausgabe live
            match = time_re.search(line)
            if match:
                h, m, s, ms = map(int, match.groups())
                elapsed = h * 3600 + m * 60 + s + ms / 100.0
                percent = (elapsed / total_duration_sec) * 100 / numcarriers + percent_old
                #print(f"\rProgress: {percent:.1f}%", end='')
                self.set_progress(percent)
                block_size = 4096 * 256           # Oder 44100 * 2 für 1 Sekunde Audio
                alignment = 4                # Blockstart must be int multiple of  4
                safety_margin = 8192         # 8kB safety margin from file end
                combined_signal_block = self.get_aligned_block(filename, 2*block_size, alignment, safety_margin)
                #spr = np.abs(np.fft.fft(combined_signal_block[0:min(2**16,len(combined_signal_block))]))
                self.set_combined_signal_block(combined_signal_block)
                self.SigPupdate.emit()
                if self.stopix:
                    while process.poll() is None:
                        self.mutex.lock()
                        self.logger.debug("********__________ffmpeg>>>>>>>>>killing process")
                        print("********__________ffmpeg>>>>>>>>>killing process")
                        #Get the process and its children
                        parent = psutil.Process(process.pid)
                        children = parent.children(recursive=True)
                        # Terminate the process and its children
                        for child in children:
                            child.terminate()
                        parent.terminate()
                        self.mutex.unlock()
                        parent.wait(timeout=20)
                        value = "terminated"
                        errorstate = True
                        return errorstate, value
                        #print(f" poll: {self.ret.poll()}")
                    self.logger.debug("********__________ffmpeg main job: terminate process on cancel")

        #process.wait()
        print("Before ffmpeg.wait()")
        retcode = process.wait()
        print(f"ffmpeg finished with code {retcode}")

        print("\nDone.")
        value = percent
        return errorstate, value

    def allpass_coeff_for_phase_shift(self, f0, fs, target_phi_rad):
        """
        calculates the coefficient a for an allpass of 1st order which has a desired phase
        at the target frequency f0.
        
        :param f0: target frequency in Hz
        :type f0: float
        :param fs: sampling rate in Hz
        :type fs: float
        :param target_phi_rad: desired phase shift in rad
        :type target_phi_rad: float array
        :return a: coefficient for allpass of 1st order
        :rtype: float
        """
        omega = 2 * np.pi * f0 / fs  # digitale Kreisfrequenz
        numerator = np.tan(omega/2) - np.tan(target_phi_rad/2)
        denominator = np.tan(omega/2) + np.tan(target_phi_rad/2)
        a = numerator / denominator
        return a


    def process_multiple_carriers_ffmpeg(self, carrier_frequencies, playlists, sample_rate, cutoff_freq, modulation_depth, output_base_name, exp_num_samples, silence_duration):
        """_summary_
        Process audio from multiple playlists blockwise, each corresponding to a different carrier frequency.
        Write the combined output to  WAV file

        :param carrier_frequencies: list of carrier frequencise
        :type carrier_frequencies: list of float
        :param playlists: _description_
        :type playlists: _type_
        :param sample_rate: sample rate
        :type sample_rate: float
        :param cutoff_freq: cutoff frequency of the lowpass filter for audio before modulation
        :type cutoff_freq: float
        :param modulation_depth: modulation depth
        :type modulation_depth: float
        :param output_base_name: filename of the SDR IQ file to be generated WITHOUT extension
        :type output_base_name: str
        :param exp_num_samples: expected number of samples #NEEDED ???
        :type exp_num_samples: int #NEEDED ???
        """
        AUTOLEVEL = self.get_autolevel() #automatic level control of concatenated audio; takes longer time; 
        # carrier frequencies ist eine liste aller LO-Offsets in kHz !
        # playlists[i][j] ist eine 2-Dim liste mit den vollen Pfaden der Audio Files, [i] ist der carrierindex, [j] ist der Audioindex einer Audioserie des carriers i
        self.set_progress(0)
        self.logger.debug(f"process_multiple_carriers_ffmpeg; carrier_frequencies:{carrier_frequencies}")
        print(f"process_multiple_carriers_ffmpeg; carrier_frequencies:{carrier_frequencies}")
        self.stopix = False
        max_file_size = self.get_filesize_limit() #2 * 1024**3  # 2 GB in bytes
        self.logger.debug(f"max filesize set to: {max_file_size}")
        self.logger.debug(f"process_multiple_carriers_ffmpeg: expected overall filesize: {4*exp_num_samples}")
        print(f"process_multiple_carriers_ffmpeg: expected overall filesize: {4*exp_num_samples}")
        abs_carrier_frequencies = carrier_frequencies * 1000 + np.ones(len(carrier_frequencies)) * self.get_LO_freq()
        self.logger.debug(f"absolute carrier frequencies: {abs_carrier_frequencies}") 
        alignment = 4                                                              
        delays, phases = self.generate_multisine_delays(abs_carrier_frequencies,sample_rate,alignment)
        phases = phases%np.pi/2
        self.logger.debug(f"Schröder phases : {phases} and delays: {delays} @ sampling rate: {sample_rate} and frequencies: {abs_carrier_frequencies}")
        #TODO TODO TODO: implement delays in ffmpeg filter chain


        total_duration_sec = exp_num_samples / sample_rate
        pregain = 10 * self.get_gain()
        self.logger.debug(f"pregain: {pregain}")
        firstround = True
        percent_old = 0
        for ix, carrierf in enumerate(carrier_frequencies):
        # loop over all carriers in list carrier_frequencies
            self.logger.debug("################################")
            self.logger.debug(f"modulation round: {ix}")
            lo_shift = - carrierf*1000
            #generate path and filenames for output and temp files
            output_IQ_filename = f"{output_base_name}.raw"   ###########TODO TODO TODO: change temp path to subdir of output path
            temp_path = self.get_synthesizer_temp_path()
            temp_wav_cat_file = os.path.join(temp_path, "audio_cat_file.wav")
            self.logger.debug(f"debug process_multiple_carriers_ffmpeg, temporary-file-path: {temp_path}")
            self.logger.debug(f"debug process_multiple_carriers_ffmpeg, output-file-name: {output_IQ_filename}")
            # generate concatenated autio file for carrier #
            audio_sample_rate = 41100 #TODO: shift definition to more central location
            self.SigMessage.emit(f"concatenate playlist @ f {str(np.ceil((carrier_frequencies[ix] + self.get_LO_freq()/1000)))}")                

#Rem after tests 11-05            #self.SigMessage.emit(f"concatenating playlist @ f {str(np.ceil((carrier_frequencies[ix])))}")
            if str(output_base_name).find("preview_temp_000") > 0:
                max_duration = 20
                self.logger.debug(f"max duration during concat: {max_duration} s")
            else:
                max_duration = None
            self.process_and_concat_audio(playlists[ix], temp_wav_cat_file, audio_sample_rate, cutoff_freq, silence_duration, AUTOLEVEL, max_duration)
            self.logger.debug(f"proc. mult. carr. ffmpeg: carrier: {carrier_frequencies[ix]} Hz, LO_freq: {self.get_LO_freq()} Hz")
            #configure allpass for sin/cos shift
            a90 = (np.tan(np.pi * abs(lo_shift) / sample_rate) - 1) / (np.tan(np.pi * abs(lo_shift) / sample_rate) + 1)
            sinus_sign = np.sign(lo_shift)  
            #TODO: calculate allpass filter coeffs for 90° phase shift
            a = self.allpass_coeff_for_phase_shift(abs(lo_shift), sample_rate, np.pi/2)
            #TODO: calculate allpass filter coeffs for Schröder phase shift,  CHECK what really happens for negative frequencies !
            a1 = self.allpass_coeff_for_phase_shift(abs(lo_shift), sample_rate, phases[ix])
            #idea: shift sine by schröder phase with allpass(a1) --> ref sine
            # shift sine by schröder phase + pi/2 for cosine

            self.logger.debug(f"allpass a1 coeffs: {a1}")
            self.logger.debug(f"allpass a coeff for 90° {a90}")
            self.logger.debug(f"allpass a coeff for 90° from coeffanalyticfunction: {a}")
            ffmpeg_cmd = []

            # rename out file to temp file if exists
            temp_outfile_copy = os.path.join(temp_path, "temp_out.raw")

            if ix > 0:
                #move previous output file to temp_out.raw                
                try:
                    os.remove(temp_outfile_copy)  #TODO define good temp path
                except:
                    pass
                try:
                    os.rename(output_IQ_filename, temp_outfile_copy)  #TODO define good temp path
                    print(f"Renamed {output_IQ_filename} to {temp_outfile_copy}")
                except:
                    pass
            
            pregain = 10 * self.get_gain()

            #TODO TODO TODO: shift cmd generation to extra function !
            #generate cmd for ffmpeg
            ffmpeg_cmd1 = [
                os.path.join(self.get_ffmpeg_path(), "ffmpeg"), "-y", "-nostdin", #"-loglevel", "error", "-hide_banner",
                "-ss", "0", "-t", str(total_duration_sec), 
                "-i", temp_wav_cat_file
            ]

            if not firstround:
                mixterm = "[outre][outim]amerge=inputs=2[merged];[1:a]highpass=f=1000[filtered_input1];[filtered_input1][merged]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[udated_iq_out]"
                #mixterm = "[outre][outim]amerge=inputs=2[merged];[1:a][merged]amix=inputs=2:duration=shortest:dropout_transition=0:normalize=0[udated_iq_out]"
            else:
                mixterm = "[outre][outim]amerge=inputs=2[merged];[merged]pan=stereo|c0=0.5*c0|c1=0.5*c1[iq_out]"

            ffmpeg_cmd2 = [
                "-filter_complex",
                # FILTERCHAIN
                # 1. Downmix zu Mono, Resampling, Normalisierung
                "[0:a]aformat=sample_fmts=s16:channel_layouts=stereo,aresample=osr=" + str(sample_rate) +
                ",pan=mono|c0=.5*c0+.5*c1" +
                ",volume=1.0" +
                # ",lowpass=f=" + str(cutoff_freq) +
                # ",lowpass=f=" + str(cutoff_freq) +
                # ",lowpass=f=" + str(cutoff_freq) +
                # ",lowpass=f=" + str(cutoff_freq) +
                "[mono_lp];"
                # 2. Sinus-Generator, Cosinus über Allpassfilter (biquad)
                "sine=frequency=" + str(abs(lo_shift)) + ":sample_rate=" + str(sample_rate) + ":d=" + str(total_duration_sec) + "[sine_base0];"
                "[sine_base0]biquad=b0=" + str(a1) + ":b1=1:b2=0:a0=1:a1=" + str(a1) + ":a2=0[sine_base1];"
                "[sine_base1]biquad=b0=" + str(a1) + ":b1=1:b2=0:a0=1:a1=" + str(a1) + ":a2=0[sine_base];"
                "[sine_base]asplit=2[sine_for_sin][sine_for_cos];"
                "[sine_for_sin]volume=volume=" + str(sinus_sign) + "[sine_sin_raw];"
                ##DEBUG##"[sine_sin_raw]asplit=3[sine_sin][carrier_sin][carrier_sin_deb];"
                "[sine_sin_raw]asplit=2[sine_sin][carrier_sin];"
                "[sine_for_cos]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[sine_cos_base];"
                ##DEBUG##"[sine_cos_base]asplit=3[sine_cos][carrier_cos][carrier_cos_deb];"
                "[sine_cos_base]asplit=2[sine_cos][carrier_cos];"
                # # 3. Modulation (1 + modulation_factor * Y)
                # modulation part:
                "[mono_lp]volume=volume=" + str(modulation_depth) + "[modsig];"
                "[modsig]asplit=2[modsig1][modsig2];"
                "[modsig1][sine_cos]amultiply[mod_re_component];"
                "[modsig2][sine_sin]amultiply[mod_im_component];"
                # 4. Add carrier part = sin/cos-Anteil (1 * sin(t) bzw. 1 * cos(t))

                "[mod_re_component][carrier_cos]amix=inputs=2:duration=shortest[modre];"
                "[mod_im_component][carrier_sin]amix=inputs=2:duration=shortest[modim];"
                ##DEBUG##"[carrier_cos_deb]anullsink;"
                ##DEBUG##"[carrier_sin_deb]anullsink;"
                # 5. apply Pregain anwenden
                "[modre]volume=volume=" + str(pregain) + "[outre];"
                "[modim]volume=volume=" + str(pregain) + "[outim];" + str(mixterm)
            ]

            ffmpeg_cmd3 = [
                
                "-c:a", "pcm_s16le",
                "-f", "s16le",   # reines RAW-PCM
                output_IQ_filename
                #DEBUG LINES
                #"-map", "[mod_debug_stereo]", "-c:a", "pcm_s16le", "-f", "wav", "debug_modre_modim.wav"
            ]

            # move output file of previous run to temp_out.raw

            if firstround:
                ffmpeg_intb = ["-map", "[iq_out]"]
                ffmpeg_cmd = ffmpeg_cmd1 + ffmpeg_cmd2 + ffmpeg_intb + ffmpeg_cmd3
                #print(ffmpeg_cmd)
            else:
                ffmpeg_inta = ["-f", "s16le", "-ar",  str(sample_rate), "-ac",  "2", "-i", temp_outfile_copy] #TODO: make this line dependent on run; this is not for run 0
                #ffmpeg_intb = ["-shortest", "-map", "[udated_iq_out]"
                ffmpeg_intb = ["-map", "[udated_iq_out]"
                ]
                ffmpeg_cmd = ffmpeg_cmd1+ ffmpeg_inta + ffmpeg_cmd2 + ffmpeg_intb + ffmpeg_cmd3

            self.logger.debug("Generierter FFmpeg-Befehl:")
            self.logger.debug(" ".join(ffmpeg_cmd))  # Zum Debuggen
            self.SigMessage.emit(f"modulate c. {str(ix+1)}/{len(carrier_frequencies)} @ f {str(np.ceil((carrier_frequencies[ix] + self.get_LO_freq()/1000)))}, SP: {np.round(phases[ix]/np.pi*180*2,1)}")                
            self.logger.debug(f"################ number of carriers: {len(carrier_frequencies)})")
            errorstate, value = self.run_ffmpeg_with_progress(ffmpeg_cmd, total_duration_sec,len(carrier_frequencies), percent_old, output_IQ_filename)
            
            firstround = False
            #print("synthesis completed, cleanup residuals")
            self.SigMessage.emit("CLEANUP")

            # Finally delete temp file
            try:
                os.remove(temp_outfile_copy)  #remove temporary out IQ file
            except OSError as e:
                print(f"Error deleting file: {e}")
            try:
                os.remove(temp_wav_cat_file)  #remove temporary audio concatenations

            except OSError as e:
                print(f"Error deleting file: {e}")

                    # generate sdr-raw file for carrier # and write to out file
                    # remove temp file if exists 
            if errorstate:
                break
            percent_old = value

        self.logger.debug(f"synthesizer worker carrier frequencies: {carrier_frequencies}")
        # Initialize file_handles as a list of empty dictionaries for each carrier
        # file_handles = [{} for _ in carrier_frequencies] 
        # total_samples_written = 0
        # overall_samples_written = 0
        # file_index = 0
        # audio_gain = np.zeros(len(playlists))

        file_stats = os.stat(output_IQ_filename)
        filesize = file_stats.st_size
        #self.logger.debug(f"synthesizer modulate: filesize last out file: {filesize}")
        output_file_name_with_wavheader = os.path.join(os.path.dirname(output_IQ_filename),Path(output_IQ_filename).stem)
        output_file_name_with_wavheader += ".wav"
        #check if file exists and delete it before renaming the new file
        try:
            os.remove(output_file_name_with_wavheader)
        except:
            pass
        os.rename(output_IQ_filename, output_file_name_with_wavheader)
        production_starttime = datetime.now()
        production_starttime = production_starttime.astimezone(pytz.utc)
        self.logger.debug(f"process multiple carriers ffmpeg: generate wavheader, filename: {output_file_name_with_wavheader} ")
        self.wav_header_generator(output_file_name_with_wavheader,filesize,sample_rate, production_starttime,"")
        # self.logger.debug(f"write last wavheader into {output_file_name_wavheader}")
        
        # #TODO : Check if already completely o.k. ! write true SDRUno-Header into the first 216 bytes of the closed file
        # for file_handle_dict in file_handles:
        #     for handle in file_handle_dict.values():
        #         handle.close()
        self.logger.debug(f"synthesizer ffmpeg modulate task completed, only raw IQ file written")
        self.SigMessage.emit("JOB COMPLETED")

    def wav_header_generator(self, output_file_name, filesize,sample_rate, starttime, next_output_file_name):
        """generate wavheader for output_file_name:
        :param: output_file_name
        """
        LO_freq = self.get_LO_freq()

        playtime = filesize/4/sample_rate
        self.mutex.lock()
        self.logger.debug(f"wav_header_generator: playtime of file {playtime}")
        self.logger.debug(f"wav_header_generator: calculated filesize of file {filesize}")
        #generate basic SDR wavheader
        wavheader = WAVheader_tools.basic_wavheader(self,0,int(np.floor(sample_rate)),LO_freq,16,filesize,starttime)
        wavheader["starttime"] = [starttime.year, starttime.month, 0, starttime.day, starttime.hour, starttime.minute, starttime.second, int(starttime.microsecond/1000)]  
        wavheader["starttime_dt"] = starttime
        wavheader["stoptime_dt"] = wavheader["starttime_dt"] + ndatetime.timedelta(seconds = np.floor(playtime))
        spt = wavheader["stoptime_dt"] 
        wavheader["stoptime"] = [spt.year, spt.month, 0, spt.day, spt.hour, spt.minute, spt.second, int(spt.microsecond/1000)] 
        wavheader["nextfilename"] = Path(next_output_file_name).stem + Path(next_output_file_name).suffix
        self.logger.debug(f"wav_header_generator: wavheader {wavheader}")

        WAVheader_tools.write_sdruno_header(self,output_file_name,wavheader,True) ##TODO TODO TODO Linux conf: self.m["f1"],self.m["wavheader"] must be in Windows format
        self.mutex.unlock()
        return wavheader["stoptime_dt"]


class synthesizer_m(QObject):
    SigModelXXX = pyqtSignal()

    def __init__(self):
        super().__init__()
        # Constants
        self.CONST_SAMPLE = 0 # sample constant
        self.mdl = {}
        self.mdl["sample"] = 0
        self.mdl["_log"] = False
        self.mdl["fileopened"] = False
        self.mdl["playlist_active"] = False
        self.mdl["sample"] = 0
        self.mdl["TEST"] = False
        self.mdl["Buttloop_pressed"] = False
        self.mdl["errorf"] = False
        self.mdl["icorr"] = 0
        self.mdl["gain"] = 1
        self.mdl["audioBW"] = 4.5
        self.mdl["carrier_distance"] = 9
        self.mdl["carrier_ix"] = 0
        self.mdl["carrierarray"] = np.arange(0, 1, 1)
        self.mdl["cancelflag"] = True
        self.mdl["sample_rate"] = 0
        self.mdl["LO"] = 0
        self.mdl["SR_currindex"] = 0
        self.mdl["modfactor"] = 0.8
        self.mdl["ffmpeg_autocheck"] = True
        self.mdl["preview"] = False
        # try:
        #     subprocess.run("ffmpeg -version", stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        #     #self.logger.debug(f"__init_ m check for ffmpeg , installation found")
        #     self.mdl["ffmpeg_path"] = ""
        # except FileNotFoundError:
        #     pass
        #     #self.mdl["ffmpeg_path"] = os.path.join(os.getcwd(), "ffmpeg-master-latest-win64-gpl", "bin")
        #     #self.logger.debug(f"__init_ m check for ffmpeg_path: {self.mdl["ffmpeg_path"]}, file not found")
        self.mdl["user_agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        self.mdl["proj_loaded"] = False
        # Create a custom logger
        logging.getLogger().setLevel(logging.DEBUG)
        # Erstelle einen Logger mit dem Modul- oder Skriptnamen
        self.logger = logging.getLogger(__name__)
        # Create handlers
        warning_handler = logging.StreamHandler()
        debug_handler = logging.FileHandler("system_log.log")
        warning_handler.setLevel(logging.WARNING)
        debug_handler.setLevel(logging.DEBUG)

        # Create formatters and add it to handlers
        warning_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        debug_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        warning_handler.setFormatter(warning_format)
        debug_handler.setFormatter(debug_format)

        # Add handlers to the logger
        self.logger.addHandler(warning_handler)
        self.logger.addHandler(debug_handler)

        self.logger.debug('Init logger in abstract method reached')

class synthesizer_c(QObject):
    """_view method
    """
    SigAny = pyqtSignal()
    SigRelay = pyqtSignal(str,object)
    SigActivateOtherTabs = pyqtSignal(str,str,object)

    def __init__(self, synthesizer_m): #TODO: remove gui
        super().__init__()

        self.m = synthesizer_m.mdl
        self.logger = synthesizer_m.logger
        standardpath = os.getcwd()  #TODO TODO: take from core module via rxh; on file open core sets that to:
        #self.m["project_path"] = os.path.dirname(standardpath) + "\\sources\\.synthesizer_projects"
        #self.m["project_path"] = standardpath + "\\.synthesizer_projects"
        self.m["project_path"] = os.path.join(standardpath,".synthesizer_projects")
        if not os.path.exists(self.m["project_path"]):
            # Verzeichnis erstellen
            os.makedirs(self.m["project_path"])
        #self.m["temp_path"] = os.path.dirname(standardpath) + "\\sources\\.synthesizer_temp"
        self.m["temp_path"] = os.path.join(standardpath, ".synthesizer_temp")
        #self.m["temp_path"] = standardpath + "\\.synthesizer_temp"
        if not os.path.exists(self.m["temp_path"]):
            # Verzeichnis erstellen
            os.makedirs(self.m["temp_path"])



    def dummy(self):
        print("hello from superclass")

    def checkdiskspace(self,expected_filesize, _dir):
        """check if free diskspace is sufficient for writing expeczed_filesize bytes on directory _dir
        :param: expected_filesize
        :type: int
        :param: _dir
        :type: str
        ...
        :raises: none
        ...
        :return: True if enough space, False else
        :rtype: Boolean
        """
        total, used, free = shutil.disk_usage(_dir)
        if free < expected_filesize:
            errorstatus = True
            value = f"not enough diskspace for this process (including temporary files), please free at least {expected_filesize - free} bytes"
        else:
            errorstatus = False
            value = ""
        return(errorstatus, value)

        
    def readsoundfile(self,file_path,*argv):
        """read sound stream either from file or URL; 
        for URL the stream must be written to a local temp file before
        then open the file with Soundfile and return soundfile object
        for file check if the format is wav or other format (mp3). 
        If the file has another format --> first convert to wav (as for URL)

        :param file_path: file path, either a local path or a http(s) URL
        :type file_path: str
        :param *argv: variable number of args; argv[1]: checkflag, if set "c" then write only a short temp file for URL sources in order to save time and memory
        :type argv[1]: str
        :return: errorstatus: True or False, True if error, value: errorstring or soundfile object
        :rtype: Boolean, soundfile object (sf.Soundfile) or str (on error)
        """
        checkflag = False
        errorstatus = False
        value = None
        if len(argv) > 0:
            c = argv[0]
            print(f"argv in read_soundfile: {argv}")
            if c.find("c") == 0:
                checkflag = True

        parsed = urllib.parse.urlparse(file_path)
        #true_tempfile = self.m["temp_path"] + "\\" + Path(file_path).stem + ".wav"
        true_tempfile = os.path.join(self.m["temp_path"], Path(file_path).stem + ".wav")
        #print(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> true tempfile path: {true_tempfile}, basispath: {self.m["temp_path"]}")
        if parsed.scheme == "http" or parsed.scheme == "https":
            try:
                
                ffmpeg_command = [
                    os.path.join(self.m["ffmpeg_path"], "ffmpeg"),
                    "-user_agent", self.m["user_agent"],
                    "-y", "-i", file_path,
                    "-c:a", "pcm_s16le",      # Audiocodec
                    "-qscale:a", "2",   # Audio quality for MP3 (ignored for WAV)
                    true_tempfile
                ]
                #print(f">>>>>>>>>ooooooooooooooo############. ffmpeg_command: {ffmpeg_command}")
                print("\nstart subprocess")
                subprocess.run(ffmpeg_command, check=True)
                print("\nsubprocess terminated")
            ############ ALTERNATIVE SOUNDFILE TREATMENT see appendix SFBUF

            except subprocess.CalledProcessError as e:
                # Fehlercode und ffmpeg-Fehlermeldungen ausgeben
                print(f"ffmpeg-Fehler: Rückgabecode {str(e.returncode)}")
                print("Fehlermeldung:", str(e.stderr))
                print("stdout output: ", str(e.stdout))
                try:
                    if "404 Not Found" in e.stderr:
                        print("Fehler: URL nicht gefunden (404).")
                        value = f" Error 404: URL {file_path} cannot be found ffmpeg returncode {str(e.returncode)}."
                    elif "Connection refused" in e.stderr or "Connection timed out" in e.stderr:
                        print("Fehler: Verbindung zur URL fehlgeschlagen.")
                        value = f" Connection to URL {file_path} refused or timed out ffmpeg returncode {str(e.returncode)}."
                    else:
                        print("Unbekannter Fehler beim Zugriff auf die URL.")
                        value = f"Unknown error when trying to connect to URL {file_path}. RTROPT"
                except:
                    print("error with no return values")
                    value = "Unknown error when trying to connect to URL {file_path}. RTROPT"
                errorstatus = True
                return(errorstatus, value)
            value = sf.SoundFile(true_tempfile, 'r')
        else:
            if os.path.exists(file_path):
                value = sf.SoundFile(file_path, 'r')
            else:
                value = f"Error: Cannot find file {file_path}"
                errorstatus = True
                return(errorstatus, value)
            if value.format.find("WAV") == 0:
                pass
            else:
                #convert to wav to be on the safe side to prevent improper mp3 encodings
                errorstatus, value = self.convert_to_wav_stereo(file_path, true_tempfile, 44100)
                if not errorstatus:
                    value = sf.SoundFile(true_tempfile, 'r')
        return(errorstatus, value)

    def convert_to_wav_stereo(self, input_file, output_file, target_sampling_rate=44100):
        """convert MP3 to WAV with target samplingrate and force stereo output

        :param input_file: path/filename of audiofile to be converted 
        :type input_file: str
        :param output_file: path/filename of target wav audiofile 
        :type output_file: str

        :return: errorstatus: True or False, True if error
        :rtype: Boolean      
        :return: value: if no error: ###############
                        if error: errorstring
        :rtype: ##### or str           
        """
        errorstatus = False
        try:
            # get sampling rate and number of channels of input file
            errorstatus, value = self.get_audio_properties(input_file)
            if errorstatus == False:
                current_sampling_rate, current_channels = value[0], value[1]
            else:
                return(errorstatus, value)
            # initialize ffmpeg command
            ffmpeg_cmd = [os.path.join(self.m["ffmpeg_path"], 'ffmpeg'), '-y', '-i', input_file]
            # force to target sampling rate
            if current_sampling_rate != target_sampling_rate:
                ffmpeg_cmd += ['-ar', str(target_sampling_rate)]
            # force to stereo
            if current_channels == 1:
                ffmpeg_cmd += ['-ac', '2']
            # append output file path
            ffmpeg_cmd.append(output_file)
            # execute ffmpeg
            subprocess.run(ffmpeg_cmd, check=True)
            print(f"conversion accomplished: {output_file}")
        except subprocess.CalledProcessError as e:
            errorstatus = True
            if str(e) == None:
                value = f"Unknown Error when converting {output_file} to wav-format"
            else:
                value = f"Error when converting {output_file} to wav-format, Errormessage: {str(e)}"
        except Exception as e:
            errorstatus = True
            if str(e) == None:
                value = f"Unknown Error when converting {output_file} to wav-format"
            else:
                value = f"Error when converting {output_file} to wav-format, Errormessage: {str(e)}"
        return(errorstatus, value)


    def get_audio_properties(self, input_file):
        """checking sampling rate and number of channels in audio file

        :param input file: path/filename of audiofile to be checked 
        :type input file: str
        :return: errorstatus: True or False, True if error
        :rtype: Boolean      
        :return: value: if no error: list of the form [samplingrate, channels]
                        if error: errorstring
        :rtype: list or str           
        """
        errorstatus = False
        try:
            # check sampling rate
            sampling_rate = subprocess.run(
                [os.path.join(self.m["ffmpeg_path"], 'ffprobe'), '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=sample_rate',
                '-of', 'default=noprint_wrappers=1:nokey=1', input_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            ).stdout.strip()
            
            # Abfrage der Kanalanzahl
            channels = subprocess.run(
                [os.path.join(self.m["ffmpeg_path"], 'ffprobe'), '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=channels',
                '-of', 'default=noprint_wrappers=1:nokey=1', input_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            ).stdout.strip()
            errorstatus = False
            value = [int(sampling_rate), int(channels)]
            
            #return int(sampling_rate), int(channels)
        except Exception as e:
            #print(f"Fehler beim Abrufen der Audioeigenschaften: {e}")
            errorstatus = True
            if str(e) == None:
                value = f"Error when checking: {input_file}: unknown type of exception."
            else:
                value = f"Error when checking: {input_file}: exception type: {str(e)}"
        return(errorstatus, value)


class synthesizer_v(QObject):
    """_view methods for resampling module
    TODO: gui.wavheader --> something less general ?
    """

    SigAny = pyqtSignal()
    SigCancel = pyqtSignal()
    SigUpdateGUI = pyqtSignal(object)
    SigSyncGUIUpdatelist = pyqtSignal(object)
    SigRelay = pyqtSignal(str,object)
    SigActivateOtherTabs = pyqtSignal(str,str,object)

    def __init__(self, gui, synthesizer_c, synthesizer_m):
        super().__init__()

        self.m = synthesizer_m.mdl
        self.synthesizer_c = synthesizer_c
        self.headerlength = 44 #read audio wav after first 44bytes of header info; could be generalized by searching the next data chunk
        self.SORTCRITERION = 'name' #Sorting criterion for filelist: 'date': sort caa to date in ascending order, 'name': alphabetical 
        self.FILTER_OVERLAP = 800  #overlap samples due to filter delay
        self.READ_BIAS = -100     # pre-read audio samples to enable filter delay compensation
        #self.CANVAS == False    # allow for building monitor canvas. Flag is set True once built, then no new build should occur on call for canvas initialization
        self.SILENCE_DURATION = 4
        self.AUTOSCALE_RF = 0     # Set to 1 to select autoscale mode causing exact RF levelling to max, otherwise set to 0 for fixed RF levelling  
        self.FIXSCALE_FAKTOR_RF = 0.8 # guard factor for fixed RF levelling: assumed max. RF level: #carriers * (1+C_m) * C_FIXSCALE_FAKTOR_RF. RF overload may occur if C_FIXSCALE_FAKTOR_RF < 1 
        self.NO2GBSPLITTING = False # if True suppress 2 GB splitting of outputfiles
        self.NOPLAYLISTUPDATE = False
        self.DATABLOCKSIZE = 1024*32
        self.STD_AUDIOBW = "4.5"
        self.STD_CARRIERDISTANCE = "9"
        self.STD_fclow = "783"
        self.STD_LO = "1125"
        self.DEF_NUMCARRIERS = 2
        self.cf_HI = int(self.STD_fclow) + int(self.STD_CARRIERDISTANCE) * self.DEF_NUMCARRIERS
        self.GAINOFFSET = 80
        self.FIRSTPREVIEW = True #label for marking the first run of a creation task (incl previews)  
        self.gui = gui
        self.synthesizer_c = synthesizer_c
        #self.norepeat = False
        self.m["carrier_distance"] = float(self.STD_CARRIERDISTANCE)
        self.m["fc_low"] = int(self.STD_fclow)
        self.m["audioBW"] = float(self.STD_AUDIOBW)
        self.m["TEST"] = False
        self.m["wavheader"] = {}
        self.m["wavheader"]['centerfreq'] = 0
        self.m["icorr"] = 0
        self.m["cancelflag"] = False
        self.m["LO"] = 1125 
        
        self.rule_viol = False
        self.blinkstate = False         
        self.logger = synthesizer_m.logger
        self.synthesizer_c.SigRelay.connect(self.rxhandler)
        self.synthesizer_c.SigRelay.connect(self.SigRelay.emit)

        #self.DATABLOCKSIZE = 1024*32
        self.gui = gui #gui_state["gui_reference"]#system_state["gui_reference"]
        self.logger = synthesizer_m.logger
        self.syntesisrunning = False
        self.load_index = False
        self.m["numcarriers"] = self.gui.spinBox_numcarriers.value()
        self.m["carrier_ix"] = 0
        self.init_synthesizer_ui()
        self.canvasbuild()
        self.readFileList = []
        self.oldFileList = []
        self.readFilePath = []
        self.autosave = False
        self.m3uflag = False
        self.toggle = False
        #datetime.now()
        self.oldtime = datetime.now()

        #difftime = (ctime - self.oldtime).seconds

        for self.m["carrier_ix"] in range(0,2):
            self.readFileList.append([])
            self.readFileList[self.m["carrier_ix"]] = []
            self.oldFileList.append([])
            self.oldFileList[self.m["carrier_ix"]] = []
            self.readFilePath.append([])
            self.readFilePath[self.m["carrier_ix"]] = []
        self.m["carrier_ix"] = 0

        try:
            stream = open("config_wizard.yaml", "r")
            self.m["metadata"] = yaml.safe_load(stream)
            stream.close()
            self.ismetadata = True
        except:
            self.ismetadata = False
        try:
            self.default_directory = self.m["metadata"]["last_audiosource_path"]
        except:
            self.default_directory = ""
        try:
            self.m["rootpath"] = self.m["metadata"]["rootpath"]
        except:
            self.m["rootpath"] = os.getcwd()
        try:
            self.m["ffmpeg_path"] = self.m["metadata"]["ffmpeg_path"]
        except:
            self.m["ffmpeg_path"] = ""


        self.m["carrierarray"] = []
        #self.m["carrierarray"] = np.arange(0, 1, 1)
        self.m["carrierarray"] = np.arange(783, 801, 9)
        self.remove_temp_audiofiles()
        self.m["ffmpeg_autocheck"] = False

    def init_synthesizer_ui(self):
        self.m["SR_currindex"] = 5
        self.gui.comboBox_targetSR.setCurrentIndex(self.m["SR_currindex"])
        self.gui.lineEdit_LO.setText("1125")
        preset_time = QTime(00, 30, 00)
        self.create_duration = preset_time
        self.gui.timeEdit_reclength.setTime(preset_time)
        self.gui.lineEdit_fc_low.setText("783")

        #self.gui.listWidget_sourcelist.setHeaderLabel("Directory tree")
        #self.gui.listWidget_sourcelist.itemClicked.connect(self.on_tree_item_clicked)
        #self.gui.listWidget_sourcelist.itemDoubleClicked.connect(self.on_tree_item_double_clicked)
        self.gui.pushButton_select_source.clicked.connect(self.select_tree)
        self.gui.listWidget_playlist.clear()
        item = QtWidgets.QListWidgetItem()
        self.gui.listWidget_sourcelist.addItem(item)
        self.gui.lineEdit_audiocutoff_freq.setText(self.STD_AUDIOBW)
        self.gui.lineEdit_carrierdistance.setText(self.STD_CARRIERDISTANCE)
        self.gui.spinBox_pauseseconds.setProperty("value", self.SILENCE_DURATION)

        #self.gui.spinBox_numcarriers.editingFinished.connect(self.freq_carriers_update)
        #react to arrows press
        self.gui.spinBox_numcarriers.valueChanged.connect(self.on_value_changed)
        self.gui.spinBox_numcarriers.setProperty("value", self.DEF_NUMCARRIERS)
        # react only to key input
        self.gui.spinBox_numcarriers.editingFinished.connect(self.on_editing_finished)
        self.gui.pushButton_CustomCarriers.setEnabled(False)
        self.gui.lineEdit_carrierdistance.editingFinished.connect(self.carrierdistance_update)
        self.gui.lineEdit_audiocutoff_freq.editingFinished.connect(self.audioBW_update)
        self.gui.lineEdit_fc_low.editingFinished.connect(self.fc_low_update)
        self.gui.lineEdit_LO.editingFinished.connect(self.LO_update)
        self.gui.lineEdit_modfactor.editingFinished.connect(self.modfactor_update)
        self.gui.comboBox_targetSR_2.setCurrentIndex(1)
        self.gui.comboBox_targetSR_2.currentIndexChanged.connect(self.preset_SR_LO)
        self.gui.comboBox_targetSR.currentIndexChanged.connect(self.RecBW_update)
        self.gui.listWidget_playlist.model().rowsInserted.connect(self.playlist_update_delayed)
        self.gui.listWidget_playlist.model().rowsRemoved.connect(self.playlist_update_delayed) 
        self.gui.listWidget_playlist.setSelectionMode(QListWidget.ExtendedSelection)
        self.gui.listWidget_playlist.setContextMenuPolicy(Qt.CustomContextMenu)
        self.gui.listWidget_playlist.customContextMenuRequested.connect(self.show_context_menu)
        self.gui.listWidget_playlist.model().rowsMoved.connect(self.on_rows_moved)
        self.gui.comboBox_cur_carrierfreq.currentIndexChanged.connect(self.carrier_ix_changed)
        self.gui.pushButton_saveproject.clicked.connect(self.save_project)
        self.gui.pushButton_loadproject.clicked.connect(self.load_project)
        self.gui.pushButton_clearproject.clicked.connect(self.clear_project)
        self.gui.synthesizer_pushbutton_create.clicked.connect(self.create_slot)
        self.gui.synthesizer_pushbutton_preview.clicked.connect(self.preview)
        #self.gui.synthesizer_pushbutton_create.clicked.connect(self.create_band)
        self.gui.timeEdit_reclength.timeChanged.connect(self.carrier_ix_changed)
        self.gui.synthesizer_pushbutton_cancel.clicked.connect(self.cancel_modulate)
        self.gui.verticalSlider_Gain.setProperty("value", 76) #percent
        self.gui.pushButton_CustomCarriers.clicked.connect(self.open_table_dialog)
        self.gui.radiobutton_CustomCarriers.toggled.connect(self.customcarrier_handler)  
        self.gui.pushButton_importProject.clicked.connect(self.import_m3u)    
        self. gui.synthesizer_radioBut_no2GBsplitting.toggled.connect(self.setno2GBsplitting)
        self. gui.synthesizer_radioBut_SuppressPlaylistinfo.toggled.connect(self.setsuppressplaylistinfo)
        self.gui.verticalSlider_Gain.valueChanged.connect(self.setgain)
        self.previous_value = self.gui.spinBox_numcarriers.value()
        self.RecBW_update()
        standardpath = os.getcwd()
        self.logger.debug(f"synthesizer_v.__init__ path infos: standardpath: {standardpath}, project path: {self.m['project_path']}")
        #self.gui.lineEdit_carrierdistance.textEdited.connect(self.carriedistance_update)

    def reinitialize_gui(self):
        self.cf_HI = int(self.STD_fclow) + int(self.STD_CARRIERDISTANCE) * self.DEF_NUMCARRIERS
        self.m["carrier_distance"] = float(self.STD_CARRIERDISTANCE)
        self.m["fc_low"] = int(self.STD_fclow)
        self.m["audioBW"] = float(self.STD_AUDIOBW)
        self.m["TEST"] = False
        self.m["wavheader"] = {}
        self.m["wavheader"]['centerfreq'] = 0
        self.m["icorr"] = 0
        self.m["cancelflag"] = False
        self.m["LO"] = 1125 
        self.toggle = False
        self.rule_viol = False
        self.blinkstate = False         
        self.syntesisrunning = False
        self.load_index = False
        self.m["carrier_ix"] = 0
        self.readFileList = []
        self.oldFileList = []
        self.readFilePath = []
        self.autosave = False
        self.m3uflag = False
        for self.m["carrier_ix"] in range(0,2):
            self.readFileList.append([])
            self.readFileList[self.m["carrier_ix"]] = []
            self.oldFileList.append([])
            self.oldFileList[self.m["carrier_ix"]] = []
            self.readFilePath.append([])
            self.readFilePath[self.m["carrier_ix"]] = []
        self.m["carrier_ix"] = 0
        #self.m["carrierarray"] = []
        #self.m["carrierarray"] = np.arange(0, 1, 1)
        self.m["carrierarray"] = np.arange(783, 801, 9)


        self.m["SR_currindex"] = 5
        self.gui.comboBox_targetSR.setCurrentIndex(self.m["SR_currindex"])
        self.gui.lineEdit_LO.setText("1125")
        preset_time = QTime(00, 30, 00)
        self.create_duration = preset_time
        self.gui.timeEdit_reclength.setTime(preset_time)
        self.gui.lineEdit_fc_low.setText("783")
        self.gui.listWidget_playlist.clear()
        # item = QtWidgets.QListWidgetItem()
        # self.gui.listWidget_sourcelist.addItem(item)
        #newline
        #newline
        self.gui.lineEdit_audiocutoff_freq.setText(self.STD_AUDIOBW)
        self.gui.lineEdit_carrierdistance.setText(self.STD_CARRIERDISTANCE)
        self.gui.spinBox_numcarriers.setProperty("value", self.DEF_NUMCARRIERS)
        self.gui.pushButton_CustomCarriers.setEnabled(False)
        self.gui.comboBox_targetSR_2.setCurrentIndex(1)
        self.gui.verticalSlider_Gain.setProperty("value", 76) #percent
        self.previous_value = self.gui.spinBox_numcarriers.value()        
        self.m["numcarriers"] = self.gui.spinBox_numcarriers.value()
        self.gui.synthesizer_pushbutton_create.setStyleSheet("background-color: lightgray; color: black;")
        self.gui.synthesizer_radioBut_no2GBsplitting.setEnabled(True)
        self.gui.synthesizer_radioBut_no2GBsplitting.setChecked(False)
        try:
            self.gui.synthesizer_pushbutton_create.clicked.connect(self.create_slot)
            self.gui.synthesizer_pushbutton_preview.clicked.connect(self.preview)
        except:
            pass

    def setno2GBsplitting(self):
        """suppress splitting of recordings into 2GB tranches, generate one big file; 
        This is accomplished by setting a flag variable self.NO2GBSPLITTING. When False then 
        max filesize is set to 1000 GB in self.create_band_thread()
        """
        if self.gui.synthesizer_radioBut_no2GBsplitting.isChecked():
            self.gui.synthesizer_radioBut_no2GBsplitting.setEnabled(True)
            self.NO2GBSPLITTING = True
        else:
            self.gui.synthesizer_radioBut_no2GBsplitting.setEnabled(True)
            self.NO2GBSPLITTING = False

    def setsuppressplaylistinfo(self):
        """suppress update of playlist and playlength info during project import
        """
        if self.gui.synthesizer_radioBut_SuppressPlaylistinfo.isChecked():
            self.gui.synthesizer_radioBut_SuppressPlaylistinfo.setEnabled(True)
            self.NOPLAYLISTUPDATE = True
        else:
            self.gui.synthesizer_radioBut_SuppressPlaylistinfo.setEnabled(True)
            self.NOPLAYLISTUPDATE = False

    def customcarrier_handler(self):
        """handles further settings when custom table
        """
        if self.gui.radiobutton_CustomCarriers.isChecked():
            self.gui.pushButton_CustomCarriers.setEnabled(True)
            #self.gui.lineEdit_carrierdistance.setEnabled(False)
            self.gui.lineEdit_fc_low.setEnabled(False)
            self.gui.spinBox_numcarriers.setEnabled(False)
            
        else:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Question)
            msg.setText("Warning")
            msg.setInformativeText(f"you are about to delete the custom carrier playlists; Status will be reset to default values and lists will be removed. Do you want to proceed ?")
            msg.setWindowTitle("Delete carriers")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.buttonClicked.connect(self.popup)
            msg.exec_()

            if self.yesno == "&Yes":
                self.gui.pushButton_CustomCarriers.setEnabled(False)
                #self.gui.lineEdit_carrierdistance.setEnabled(True)
                self.gui.lineEdit_fc_low.setEnabled(True)
                self.gui.spinBox_numcarriers.setEnabled(True)
                self.m["carrierarray"] = [] # TODO: check if appropriate: if  custom carriers is unchecked, the table of custom defined carrier freqs is deleted
                self.clear_project()
                self.freq_carriers_update()
            else:
                if self.gui.radiobutton_CustomCarriers.isChecked():
                    self.gui.pushButton_CustomCarriers.setChecked(True)
                else:
                    self.gui.pushButton_CustomCarriers.setChecked(False)
                return


    def clear_project(self):
        #errorstatus, value = self.checkffmpeg_install()
        # if errorstatus:
        #     self.errorhandler("NOCLEAR" + value)
        #     return
        self.m3uflag = False
        #self.init_synthesizer_ui()
        self.reinitialize_gui()
        self.gui.listWidget_sourcelist.clear()
        self.readFileList = []
        self.oldFileList = []
        self.readFilePath = []
        self.m["carrierarray"] = []
        self.autosave = False
        self.m["proj_loaded"] = False
        self.gui.progressBar_fillPlaylist.setValue(0)
        #self.m["carrierarray"] = []
        #self.m["carrierarray"] = np.arange(783, 801, 2)
        self.m["carrierarray"] = np.arange(783, 801, 9)
        
        for self.m["carrier_ix"] in range(0,2):
            self.readFileList.append([])
            self.readFileList[self.m["carrier_ix"]] = []
            self.oldFileList.append([])
            self.oldFileList[self.m["carrier_ix"]] = []
            self.readFilePath.append([])
            self.readFilePath[self.m["carrier_ix"]] = []
        self.m["carrier_ix"] = 0
        self.SigActivateOtherTabs.emit("synthesizer","activate",["Synthesizer"])
        self.gui.progressBar_synth.setValue(0)

        self.activate_control_elements(True)
        self.display_worker_message('')

    def setgain(self):
        """set gain which is set by the gain slider and pass it to the modulator worker
        """
        gain = 10**((self.gui.verticalSlider_Gain.value()/100*90 - self.GAINOFFSET)/20)
        #print(f"synthesizer gain: {gain}, slidervalue: {self.gui.verticalSlider_Gain.value()}")
        self.logger.debug("cb_setgain, gain: %f %i",gain,self.gui.verticalSlider_Gain.value())
        try:
            self.modulate_worker.set_gain(gain)
        except:
            pass
        #print(f"synthesizer, set gain: {gain}")


    def showRFdata(self):
        """_take over datasegment from player loop worker and caluclate from there the signal volume and present it in the volume indicator
        read gain value and present it in the player Tab on the 'progressbar' Widget 'progressBar_volume'
        Parameters: a = length form top to 0dB tick
        b = length between -80 and 0 dB ticks
        c = length between bottom and -80dB tick
        a+b+c = total length of the indicator and hence of the progress-bar volume 
        GUI Element
        :return: _False if error, True on succes_
        :rtype: _Boolean_
        """
        # geometry scaling; absolute numbers are not relevant, only relative lengths
        #a = #10/139.5 #7/86  
        scal_Rescaling = True
        c = 11/89 #16.5/139.5 #8/86
        b = 72/89 #(139.5 - 10 -16.5)/139.5 #(86 -7 -8)/86
        data = self.modulate_worker.get_combined_signal_block()
        #use RMS value as indicator for signal strength 
        if scal_Rescaling:
            span = 100
            b = 80/100
            c = 15/100
        else:
            span = 80

        refvol = 0.71 #could be used for rescaling to amplitude values
        volume = np.linalg.norm(data)/refvol/np.sqrt(len(data))
        #self.logger.debug(f"synthesizer showRFdata volume: {volume} ")
        #span = 80
        #vol = 1.5*np.std(volume)/scl/refvol
        dBvol = 20*np.log10(volume)
        rawvol = c + b + dBvol/span*b
        if dBvol > 0:
            dispvol = min(100, rawvol*100)
        elif (dBvol < 0) and (dBvol > -span):
            dispvol = rawvol*100
        elif dBvol < -span:
            dispvol = c*0.8*100
        if np.any(np.isnan(dispvol)):
            return
        #print(f"vol: {vol} dB: {dBvol} std: {np.std(cv)/scl} dispvol: {dispvol} rv: {np.std(cv)/scl}")
        self.gui.progressBar_volume.setValue(int(np.floor(dispvol*10))) 
        if dBvol > -3:
            self.gui.progressBar_volume.setStyleSheet("QProgressBar::chunk "
                    "{"
                        "background-color: red;"
                    "}")
        elif dBvol < -40:
            self.gui.progressBar_volume.setStyleSheet("QProgressBar::chunk "
                    "{"
                        "background-color: yellow;"
                    "}")           
        else:
            self.gui.progressBar_volume.setStyleSheet("QProgressBar::chunk "
                    "{"
                        "background-color: green;"
                    "}")

    def cancel_modulate(self):
        """Cancel synthesis job by terminating the modulate_worker thread
        """
        #TODO check how to handle and delete after change to model
        #schedule_objdict = self.m["schedule_objdict"]
        #TODO: look why that was used self.SigDisconnectExternalMethods.emit("cancel_resampling")
        self.gui.synthesizer_pushbutton_cancel.clicked.disconnect(self.cancel_modulate)
        if self.m["cancelflag"]:
            self.logger.debug("cancel_modulation: **** suppressed because cancelflag ___cancel_resamp reached")
            self.gui.synthesizer_pushbutton_cancel.clicked.connect(self.cancel_modulate)
            return
        self.m["cancelflag"] = True
        time.sleep(0.001)
        for i in range(5):
            self.logger.debug("**** 5 x BLOCK *****___cancel_synthesizer reached")
        try:
            self.modulate_worker.modulate_terminate()
        except:
            self.logger.debug("cancel synthesizer modulation: modulate worker could not be terminated")
            pass
        #TODO TODO TODO: delete out files produced so far ? or leave them ?
        self.gui.synthesizer_pushbutton_cancel.clicked.connect(self.cancel_modulate)
        self.remove_temp_audiofiles()
        #self.cleanup()

    def canvasbuild(self):
        """
        sets up a pyQTgraph canvas to which curves can be plotted
        """
        #if self.CANVAS == False:
        self.plot_widget = pg.PlotWidget()
        self.gui.gridLayout_synthesizer.addWidget(self.plot_widget,0,7,3,3)
        self.plot_widget.getAxis('left').setStyle(tickFont=pg.QtGui.QFont('Arial', 6))
        self.plot_widget.getAxis('bottom').setStyle(tickFont=pg.QtGui.QFont('Arial', 6))
        self.plot_widget.setBackground('w')
            #self.CANVAS = True

    def preset_gain(self):
        """determine optimal gain and set gain slider accordingly
        """
        numcar = self.gui.spinBox_numcarriers.value()
        wanted_gain = 0.568 /2/ np.sqrt(numcar)*0.5  # 0.568 is the product of a safety margin 0.8 and the RMS of 1 Vp, i.e. 0.71
        #wanted_gain = 0.568 /2/numcar  # 0.568 is the product of a safety margin 0.8 and the RMS of 1 Vp, i.e. 0.71; sqrt ( nucar) is obviously not valid, there are correlations due to phase synchrony
        #improvement: phase scrambling for multisinus approach
        slider = (20*np.log10(wanted_gain) + self.GAINOFFSET)*10/9
        self.gui.verticalSlider_Gain.setProperty("value", float(slider))

    def preview(self):
        """
        generate short preview of the SDR file                               
        """
        self.gui.synthesizer_pushbutton_preview.clicked.disconnect(self.preview)
        preset_time = QTime(0,0,20) 
        self.create_duration = self.gui.timeEdit_reclength.time()
        self.gui.timeEdit_reclength.setTime(preset_time)
        #self.preset_gain()
        if self.FIRSTPREVIEW:

            self.preset_gain()  #gain is set indirectly by setting the gain slider position
            self.FIRSTPREVIEW = False
        self.m["preview"] = True
        self.create_band_thread()
        
        
        #self.m["preview"] = False

    def create_slot(self):
        """slot function for the CREATE button
        pre-set gain, check some conditions. 
        Then configure and start worker thread 'modulate_worker' for synthesis

        """
        self.gui.synthesizer_pushbutton_create.clicked.disconnect(self.create_slot)
        time.sleep(0.5)
        self.activate_control_elements(False)
        # if self.m["preview"]:
        #     self.gui.timeEdit_reclength.setTime(self.create_duration)
        #     self.m["preview"] = False

        
        palette = self.gui.synthesizer_pushbutton_create.palette()
        self.cancel_background_color = palette.color(self.gui.synthesizer_pushbutton_create.backgroundRole())
        if self.FIRSTPREVIEW:
            self.preset_gain()  #gain is set indirectly by setting the gain slider position
            self.FIRSTPREVIEW = True
        self.m["preview"] = False
        self.create_band_thread()
        #self.gui.synthesizer_pushbutton_create.clicked.connect(self.create_slot)

    def create_band_thread(self):
        """slot function for the CREATE button
        pre-set gain, check some conditions. 
        Then configure and start worker thread 'modulate_worker' for synthesis

        """
        errorstatus = False
        value = ""

        # if not ffmpeg_installtools.is_ffmpeg_installed():  
        #     errorstatus = True
        #     value = "NOCLEAR"
        #     self.errorhandler(value)
        #     return(errorstatus,value)        
        
        try:
            self.gui.synthesizer_pushbutton_create.clicked.disconnect(self.create_slot)
        except:
            pass
        try:
            self.gui.synthesizer_pushbutton_preview.clicked.disconnect(self.preview)
        except:
            pass
        time.sleep(0.1)
        self.activate_control_elements(False)
        palette = self.gui.synthesizer_pushbutton_create.palette()
        self.cancel_background_color = palette.color(self.gui.synthesizer_pushbutton_create.backgroundRole())
        self.syntesisrunning = False
        #self.gui.label_audioset_name.setText("Create Job")
        self.display_worker_message("Create Job")
        self.gui.label_audioset_name.setStyleSheet("background-color: #FFFFFF; color: black;")  # weiss

        # save settings to temp project
         #re-load the same project (patch bug with direct create)
        total_reclength = self.get_reclength()
        exp_num_samples = total_reclength * self.m["sample_rate"]*1000 
        expected_filesize = (exp_num_samples * 4)*1.5 #1.5 is safety margin, may still be insufficient in extreme cases
        if self.gui.synthesizer_radioBut_FAST_mode.isChecked():
            expected_filesize *= 2 # double space needed because of intermediate temp files with full recording length

        try:
            errorstatus, value = self.synthesizer_c.checkdiskspace(expected_filesize, self.m["recording_path"])
        except:
            errorstatus = True
            value = "Error when checking disk space, please make sure that the recording path (set in player Tab) is correct"
        if errorstatus:
            self.logger.debug(errorstatus)
            self.FIRSTPREVIEW = True
            self.gui.synthesizer_pushbutton_create.clicked.connect(self.create_slot)
            self.gui.synthesizer_pushbutton_preview.clicked.connect(self.preview)
            auxi.standard_errorbox(value)
            self.clear_project()
            return

        if not self.m["proj_loaded"]:
            self.autosave = True
            # necessary only if no project has been loaded previously 
            self.save_project()
            print("save temporary project file")
            time.sleep(0.5)
            errorstatus, value = self.load_project()
            if errorstatus:
                self.FIRSTPREVIEW = True
                self.gui.synthesizer_pushbutton_create.clicked.connect(self.create_slot)
                self.gui.synthesizer_pushbutton_preview.clicked.connect(self.preview)
                self.errorhandler(value)
                return
            self.autosave = False
        

        #if self.gui.radiobutton_AGC.isChecked():
        #TODO TODO TODO: implement AGC method and AUTO clipping repair or clipping warning
            #gain = 10**((self.gui.verticalSlider_Gain.value()/100*90 - self.GAINOFFSET)/20)

        #TODO TODO TODO: exit if no project defined
        #print("recording path received")
        #print(self.m["recording_path"])
        playlists = [[f"{path.rstrip('/')}/{file}" for file, path in zip(files, paths)] for files, paths in zip(self.readFileList, self.readFilePath)]
        cumlen = 0
        for elem in playlists:
            cumlen = cumlen + len(elem)
        if cumlen == 0:
            auxi.standard_errorbox("no playlists defined yet, cannot create anything")
            self.FIRSTPREVIEW = True
            self.gui.synthesizer_pushbutton_create.clicked.connect(self.create_slot)
            self.gui.synthesizer_pushbutton_preview.clicked.connect(self.preview)
            return
        self.SigActivateOtherTabs.emit("synthesizer","inactivate",["Synthesizer"])
        self.gui.progressBar_synth.setValue(0)
        #self.activate_control_elements(False)
        self.logger.debug("modulate: configure modulate_worker thread et al")
        self.m["cancelflag"] = False
        modulation_depth = float(self.gui.lineEdit_modfactor.text())  # Modulation depth
        playlists = [[f"{path.rstrip('/')}/{file}" for file, path in zip(files, paths)] for files, paths in zip(self.readFileList, self.readFilePath)]
        LO_frequency = int(np.round(self.m["LO"]*1000))
        fclow_frequency = int(np.round(float(self.gui.lineEdit_fc_low.text()))*1000)
        self.m["fclow"] = fclow_frequency
        #TODO TODO TODO: maybe correct for no carrier at frequency 0, make that correct ! subtract BW/2
        carrier_frequencies = self.m["carrierarray"] - self.m["LO"]
        existcheck = True
        if not self.m["preview"]:
            while existcheck:
                options = QFileDialog.Options()
                #options |= QFileDialog.DontUseNativeDialog
                #TODO: why does it take so long to display the existing file list ?
                output_base_name, _ = QFileDialog.getSaveFileName(self.m["QTMAINWINDOWparent"], 
                                                        "Save File", 
                                                        self.m["recording_path"],  # Standard rec path, Standardmäßig kein voreingestellter Dateiname
                                                        "wav Files (*.wav)",  # Filter for data type wav
                                                        options=options)
                if output_base_name:
                    if (os.path.exists(output_base_name) or os.path.exists(str(Path(output_base_name).with_suffix("")) + "_0.wav")):
                        msg = QMessageBox()
                        msg.setIcon(QMessageBox.Question)
                        msg.setText("overwrite file")
                        msg.setInformativeText("you are about to overwrite an existing file. Do you really want to proceed ?")
                        msg.setWindowTitle("overwrite")
                        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                        msg.buttonClicked.connect(self.popup)
                        msg.exec_()
                        if self.yesno == "&Yes":
                            existcheck = False
                    else:
                        existcheck = False
                else:
                    existcheck = False
                    self.gui.synthesizer_pushbutton_create.clicked.connect(self.create_slot)
                    self.gui.synthesizer_pushbutton_preview.clicked.connect(self.preview)
                    self.FIRSTPREVIEW = True
                    self.logger.debug("create_band_thread: no output file name given, cancel creation")
                    self.activate_control_elements(True)
                    return(False)
        else:
            output_base_name = os.path.join(self.m["recording_path"],"preview_temp_000.wav")

        #TODO TODO: modify output base name so that it doesn't contain any extension and no _# at the end


        block_size = 2**18   # Maximum block length
        #total_reclength = self.get_reclength()
        #exp_num_samples = total_reclength * self.m["sample_rate"]*1000
        synthesizer_temp_path = os.path.join(os.path.dirname(Path(output_base_name)),"temp")
        if not os.path.exists(synthesizer_temp_path):
            os.makedirs(synthesizer_temp_path)
        
        self.toggle = False
        self.modulate_thread = QThread(parent = self)
        if self.gui.synthesizer_radioBut_FAST_mode.isChecked():
            self.modulate_worker = modulate_worker_ffmpeg() #TODO TODO TODO: test new worker
        else:
            self.modulate_worker = modulate_worker()
        if self.gui.synthesizer_radioBut_FAST_autolevel.isChecked():
            self.modulate_worker.set_autolevel(True)
        else:
            self.modulate_worker.set_autolevel(False)       

        self.modulate_worker.moveToThread(self.modulate_thread)
        self.modulate_worker.set_carrier_frequencies(carrier_frequencies)
        self.modulate_worker.set_synthesizer_temp_path(synthesizer_temp_path)
        self.modulate_worker.set_ffmpeg_path(self.m["ffmpeg_path"])
        self.modulate_worker.set_playlists(playlists)
        self.modulate_worker.set_sample_rate(int(self.m["sample_rate"]*1000))
        self.modulate_worker.set_block_size(block_size)
        self.modulate_worker.set_cutoff_freq(self.m["audioBW"]*1000)
        self.modulate_worker.set_modulation_depth(modulation_depth)
        self.modulate_worker.set_output_base_name(Path(output_base_name).with_suffix(""))
        self.modulate_worker.set_exp_num_samples(exp_num_samples)
        self.modulate_worker.set_logger(self.logger)
        self.modulate_worker.set_LO_freq(LO_frequency)
        self.modulate_worker.set_method_object(self.synthesizer_c)
        self.modulate_worker.set_silence_duration(self.gui.spinBox_pauseseconds.value())
        if self.NO2GBSPLITTING:
            self.modulate_worker.set_filesize_limit(2**10 * 1024**3)  # 1024 GB in bytes
        else:
            self.modulate_worker.set_filesize_limit(2 * 1024**3)  # 2 GB in bytes
        #print(f"createbandthread: method_object {self.synthesizer_c}")
        self.setgain()
        self.modulate_thread.started.connect(self.modulate_worker.start_modulator)
        self.modulate_worker.SigPupdate.connect(self.PupdateSignalHandler)
        self.modulate_worker.SigMessage.connect(self.display_worker_message)
        self.modulate_worker.SigError.connect(self.errorhandler)
        self.modulate_worker.SigFinished.connect(self.modulate_thread.quit)
        #self.modulate_worker.SigFinished.connect(lambda: print("#####>>>>>>>>>>>>>>>>>modulateworker SigFinished_arrived"))
        self.modulate_worker.SigFinished.connect(self.cleanup)
        self.modulate_worker.SigFinished.connect(self.modulate_worker.deleteLater)
        self.modulate_thread.finished.connect(self.modulate_thread.deleteLater)

        self.m["progress"] = 0
        self.m["blinkstate"] = True #TODO: not yet used
        self.m["actionlabelbg"] ="cyan" #TODO: not yet used
        self.m["blinking"] = False #TODO: not yet used

        time.sleep(0.0001)
        self.modulate_thread.start()
        if self.modulate_thread.isRunning():
            self.logger.debug("modulate: modulate_ thread started")
            self.syntesisrunning = True
        time.sleep(0.5) # wait state for worker to start up
        self.gui.synthesizer_pushbutton_create.clicked.connect(self.create_slot)
        self.gui.synthesizer_pushbutton_preview.clicked.connect(self.preview)
        
        return(True)

    def query(self,query):
        """Query for automatic installation
 
        :param query: string with the query
        :type query: str
        """
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Question)
        msg.setText("Question")
        msg.setInformativeText(query)
        msg.setWindowTitle("autoinstall ffmpeg")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.buttonClicked.connect(self.popup)
        msg.exec_()

        if self.yesno == "&Yes":
            return True
        else:
            return False

    def ffmpeg_install_handler(self):
        #self.m["ffmpeg_path"]
        #root_dir = os.path.dirname(os.path.abspath(__file__))
        errorstatus = False
        value = ""
        ffmpeg_dir = os.getcwd()        
        system = platform.system().lower()
        if system == "linux":
            errorstatus, value = ffmpeg_installtools.install_ffmpeg_linux(ffmpeg_installtools,ffmpeg_dir)
        elif system == "windows":
            errorstatus, value = ffmpeg_installtools.install_ffmpeg_windows(ffmpeg_installtools,ffmpeg_dir)
        else:
            print("This OS is not being supported")
            errorstatus = True
            value = "This OS is not being supported"
            return(errorstatus, value)
        
        print("Installation has been completed.")
        return(errorstatus, value)
    
    def checkffmpeg_install(self):
        errorstatus = False
        value = None
        errorstatus, value = ffmpeg_installtools.is_ffmpeg_installed(self.m["ffmpeg_path"]) 
        if not errorstatus:
            self.m["ffmpeg_path"] = value
            errorstatus = False
            value = ""
            return(errorstatus,value)
        querystr = "ffmpeg is not installed on this computer. \n This 3rd party software is required for running the synthesizer module. \n \n Would you like it to be installed now by COHIWizard ?"
        if self.query(querystr):
            self.logger.debug("try to install ffmpeg")
            errorstatus, value = self.ffmpeg_install_handler()
            if errorstatus:
                self.activate_control_elements(False)
                self.errorhandler("NOCLEAR \n" + value)
            else:
                ffmpeg_exepath = value[0]
                self.m["ffmpeg_path"] = value[1]
            self.m["metadata"]["ffmpeg_path"] = self.m["ffmpeg_path"]
            stream = open("config_wizard.yaml", "w")
            yaml.dump(self.m["metadata"], stream)
            stream.close()
        else:
            ffmpeg_link = "https://www.ffmpeg.org/download.html"
            #ffmpeg_link = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            #TODO TODO TODO: place this URL in a more general place like config_wizard.yaml for easy exchange
            pathinfo = os.path.join(os.getcwd(), "ffmpeg-master-latest-win64-gpl")
            infotext = "<font size = 8> Synthesizer requires ffmpeg to be installed on your computer; <br> Please install ffmpeg manually in folder  <br> ~rootpath/Xffmpeg-master-latest-win64-gpl-shared/ <br> Download from: <a href='%s'>ffmpeg </a> <br> <br> Synthesizer will be inactivated until ffmpeg is available. Please be sure to install a version which supports soxR (compiled with libsoxr) </font>" % ffmpeg_link
            self.logger.error(infotext)
            self.logger.error(pathinfo)
            auxi.standard_errorbox(infotext)
            self.activate_control_elements(False)
            errorstatus = True
            value = infotext
        return(errorstatus,value)


    def errorhandler(self,value):
        """handles errors when methods return errormessages on errorstate == True
        (1) displays errormessage conveyed in 'value', clears GUI and writes error to logfile
        (2) if 'value' contains the keyword 'NOCLEAR' at the initial position, the GUI is not cleared. This is important for calls from functions
        which themselves call errorhandler; otherwise an endless loop would emerge.

        :param value: error description which is to be displayed in the errormessage
        :type value: str
        """
        self.logger.error(str(value))
        #self.m["metadata"]["rootpath"]    
        #do other stuff on more detailed evaluation of value
        
        #preliminary handling of the lack of ffmpeg

        #TODO: future versions: autoinstall with routines in Autoinstall_ffmpeg_import os.py
        try: 
            value.find("NOCLEAR") == 0
            self.activate_control_elements(False)
            auxi.standard_errorbox(str(value[7:]))
        except:
            if str(value) == "None":
                value = "unknown error, maybe the internet connection was required and could not be established. Please check."
            auxi.standard_errorbox(str(value))
            self.clear_project()

    def display_worker_message(self,s):
        """display messages from the worker in the message window of the GUI"""
        self.gui.label_audioset_name.setText(s)
        self.gui.label_audioset_name.setFont(QFont("Arial", 12))
        if s.find("----") == 0:
            self.gui.label_audioset_name.setText('modulating')
            self.gui.label_audioset_name.setStyleSheet("background-color: #FFFFFF; color: black;")
        ctime = datetime.now()
        difftime = (ctime - self.oldtime).seconds

        if s.find("###m") == 0 and difftime >= 1:
            self.gui.label_audioset_name.setText(s)
            self.gui.label_audioset_name.setStyleSheet("background-color: #FFFFFF; color: black;")
        if self.toggle: 
            self.gui.label_audioset_name.setStyleSheet("background-color: #ADD8E6; color: black;")  # Blassblau (#ADD8E6)
        else:
           self.gui.label_audioset_name.setStyleSheet("background-color: #FFDAB9; color: black;")  # Blassorange (#FFDAB9)
        QApplication.processEvents()
        self.toggle = not self.toggle
        self.oldtime = ctime

    def cleanup(self):
        self.syntesisrunning = False
        self.activate_control_elements(True)
        self.SigActivateOtherTabs.emit("synthesizer","activate",[])
        auxi.standard_infobox("synthesis has been completed, files can be found in the recording path defined on the Player tab")
        self.gui.progressBar_synth.setValue(0)
        self.gui.synthesizer_pushbutton_create.setStyleSheet("background-color: lightgray; color: black;")
        self.remove_temp_audiofiles()
        self.display_worker_message('Job finished, ready for new job')
        self.gui.timeEdit_reclength.setTime(self.create_duration)

    def remove_temp_audiofiles(self):
        """delete all temporary *.wav files
        """
        time.sleep(0.5)
        for filename in os.listdir(self.m["temp_path"]):
            if filename.endswith('.wav'):
                file_path = os.path.join(self.m["temp_path"], filename)
                try:
                    os.remove(file_path)
                    print(f"temp file deleted: {file_path}")
                except Exception as e:
                    print(f"Error when deleting temporary file: {file_path}: {str(e)}")

    def preset_SR_LO(self):
        """auto-define LO frequency and Rec bandwidth (= sampling rate) for pre-defined broadcasting bands on LW, MW and SW
        """
        text = self.gui.comboBox_targetSR_2.currentText()
        if text.find("LW") == 0:
            self.gui.lineEdit_LO.setText("220")
            self.gui.comboBox_targetSR.setCurrentIndex(3)
        if text.find("MW") == 0:
            self.gui.lineEdit_LO.setText("1125")
            self.gui.comboBox_targetSR.setCurrentIndex(5)
        if text.find("SW 49m") == 0:
            self.gui.lineEdit_LO.setText("6050")
            self.gui.comboBox_targetSR.setCurrentIndex(4)
        if text.find("SW 41m") == 0:
            self.gui.lineEdit_LO.setText("7325")
            self.gui.comboBox_targetSR.setCurrentIndex(3)
        if text.find("SW 31m") == 0:
            self.gui.lineEdit_LO.setText("9650")
            self.gui.comboBox_targetSR.setCurrentIndex(4)
        if text.find("SW 25m") == 0:
            self.gui.lineEdit_LO.setText("11850")
            self.gui.comboBox_targetSR.setCurrentIndex(4)
        if text.find("SW 22m") == 0:
            self.gui.lineEdit_LO.setText("13720")
            self.gui.comboBox_targetSR.setCurrentIndex(4)
        if text.find("SW 19m") == 0:
            self.gui.lineEdit_LO.setText("15450")
            self.gui.comboBox_targetSR.setCurrentIndex(5)
        self.LO_update()



    def activate_control_elements(self,value):
        """enable or disable all control elements of the tab via value
        value = True: enable
        value = False: disable
        :param: value
        :type: Boolean
        """  
        #self.gui.verticalSlider_Gain.setEnabled(value)
        self.gui.synthesizer_pushbutton_create.setEnabled(value)
        self.gui.synthesizer_pushbutton_preview.setEnabled(value)
        self.gui.comboBox_cur_carrierfreq.setEnabled(value)
        self.gui.pushButton_saveproject.setEnabled(value)
        self.gui.pushButton_loadproject.setEnabled(value)
        self.gui.pushButton_select_source.setEnabled(value)
        self.gui.comboBox_targetSR.setEnabled(value)
        self.gui.lineEdit_LO.setEnabled(value)
        self.gui.pushButton_importProject.setEnabled(value)

        self.gui.comboBox_targetSR_2.setEnabled(value)
        self.gui.lineEdit_fc_low.setEnabled(value)
        self.gui.lineEdit_carrierdistance.setEnabled(value)
        self.gui.lineEdit_modfactor.setEnabled(value)
        self.gui.spinBox_numcarriers.setEnabled(value)
        self.gui.lineEdit_audiocutoff_freq.setEnabled(value)
        self.gui.timeEdit_reclength.setEnabled(value)
        #self.gui.synthesizer_radioBut_Spectrum.setEnabled(value)
        #self.gui.radiobutton_AGC.setEnabled(value)
        self.gui.synthesizer_radioBut_no2GBsplitting.setEnabled(value)
        

    def PupdateSignalHandler(self):
        """
        update progress bar and handle other state display elements
        """
        progress = self.modulate_worker.get_progress()
        #print(f"progress: {progress}")
        combined_signal_block = self.modulate_worker.get_combined_signal_block()
        self.gui.progressBar_synth.setValue(min(100,int(np.floor(progress))))
        ts = 1/self.m["sample_rate"]/1000
        # clipping limits festlegen (Y-Werte)
        upper_limit = 0.7
        lower_limit = -0.7
        self.plot_widget.clear()
        if self.gui.synthesizer_radioBut_Spectrum.isChecked():
            self.logger.debug(f"percentage completed: {str(progress)}")
            spr = np.abs(np.fft.fft(combined_signal_block[0:min(2**16,len(combined_signal_block))]))
            N = len(spr)
            spr = np.fft.fftshift(spr)/N
            flo = self.m["LO"] - self.m["sample_rate"]/2 #+ #self.m["fclow"] - self.m["sample_rate"]*1000/2
            freq0  = np.linspace(0,self.m["sample_rate"],N)
            freq = freq0 + flo
            datax = (freq)
            self.plot_widget.setXRange(flo, freq[-1])
            self.plot_widget.setYRange(-120, 0)
            datay = 20*np.log10(spr)
            self.plot_widget.plot(datax, datay, pen=pg.mkPen('k'))

        else:
            datay = np.real(combined_signal_block[0:min(2**16,len(combined_signal_block))])
            datay = datay - np.mean(datay)
            tax = np.linspace(0,1,len(datay))
            datax = tax * ts
            self.plot_widget.setXRange(0, datax[-1])
            self.plot_widget.setYRange(-1,1)
            # clipping limits
            region = pg.LinearRegionItem(values=(lower_limit, upper_limit), orientation='horizontal')
            region.setBrush(pg.mkBrush(0, 255, 0, 30))  # pale green rectangle (RGBA: (0, 255, 0, 30) for transparency)
            self.plot_widget.addItem(region)
            upper_line = pg.InfiniteLine(pos=upper_limit, angle=0, pen=pg.mkPen('r', width=2))
            lower_line = pg.InfiniteLine(pos=lower_limit, angle=0, pen=pg.mkPen('r', width=2))
            self.plot_widget.addItem(upper_line)
            self.plot_widget.addItem(lower_line)
            self.plot_widget.plot(datax, datay, pen=pg.mkPen('k'))
            #print(f"mean value: {np.mean(datay)}")

        self.showRFdata()

    def save_project(self):
        """_save current settings and all playlists to a project file (*.proj) via intermediate dictionary pr
        *.proj files are have yaml format

        :param: none
        :returns: none
        : raises: none

        """
        pr = {}
        pr["projectdata"] = {}
        pr["projectdata"]["readFilePath"] = self.readFilePath
        pr["projectdata"]["readFileList"] = self.readFileList
        pr["projectdata"]["numcarriers"] = self.m["numcarriers"]
        pr["projectdata"]["carrier_distance"] = self.m["carrier_distance"]
        pr["projectdata"]["carrier_f_low"] = self.m["fc_low"]
        pr["projectdata"]["LO"] = self.m["LO"]
        pr["projectdata"]["audio_BW"] = self.m["audioBW"]
        #pr["projectdata"]["sample_rate"] = self.m["sample_rate"]
        if not self.m3uflag:
            try:
                pr["projectdata"]["current_listdir"] = self.current_listdir
            except:
                auxi.standard_errorbox("no playlist specified, project file will not be written")
                return
        else:
            pr["projectdata"]["current_listdir"] = ""
        pr["projectdata"]["targetSR_index"] = self.gui.comboBox_targetSR.currentIndex()
        pr["projectdata"]["presetband_index"] = self.gui.comboBox_targetSR_2.currentIndex()
        #pr["projectdata"]["preset_time"] = 
        #TODO TODO TODO: add all settings to be saved:
        #self.comboBox_targetSR_2.setCurrentIndex(###)
        pr["projectdata"]["modfactor"] = self.gui.lineEdit_modfactor.text()
        #pr["projectdata"]["carrier_low"] = self.gui.lineEdit_fc_low.text()
        #Target filename
        qtimeedit = self.gui.timeEdit_reclength
        time_from_qtimeedit = qtimeedit.time()
        pr["projectdata"]["preset_time"] = [time_from_qtimeedit.hour(), time_from_qtimeedit.minute(), time_from_qtimeedit.second()]
        if not self.autosave:
            filename = self.save_file_dialog()
        else:
            filename = "temp.proj"
        pr["projectdata"]["carrier_array"] = self.m["carrierarray"].tolist()
        if self.gui.radiobutton_CustomCarriers.isChecked():
            pr["projectdata"]["custom_carriers_active"] = "True"
        else:
            pr["projectdata"]["custom_carriers_active"] = "False"

        stream = open(filename, "w") ###replace project.yaml with filename
        yaml.dump(pr["projectdata"], stream)
        stream.close()

    def load_project(self):
        """_load project file (*.proj) and read the settings of that project to dictionary pr
        fill playlists and re-initialize all settings according to loaded project.
        *.proj files are have yaml format

        :param: none
        :returns: none
        : raises: none

        """
        errorstatus = False
        value = None
        self.m3uflag = False
        self.gui.listWidget_sourcelist.clear()
        self.gui.pushButton_loadproject.clicked.disconnect(self.load_project)
        pr = {}
        pr["projectdata"] = {}
        self.activate_control_elements(False)
        if not self.autosave:
            filename = self.load_file_dialog()
        else:
            filename = "temp.proj"
        try:
            stream = open(filename, "r")
            pr["projectdata"] = yaml.safe_load(stream)
            stream.close()
            #self.m["sample_rate"] = pr["projectdata"]["sample_rate"]
            self.readFileList = pr["projectdata"]["readFileList"]
            self.readFilePath = pr["projectdata"]["readFilePath"]
            self.m["LO"] = pr["projectdata"]["LO"]
            #self.oldFileList = pr["projectdata"]["readFileList"]
            self.oldFileList = copy.deepcopy(pr["projectdata"]["readFileList"])
            self.gui.lineEdit_fc_low.setText(str(pr["projectdata"]["carrier_f_low"]))
            self.gui.lineEdit_LO.setText(str(pr["projectdata"]["LO"]))
            self.m["audioBW"]= pr["projectdata"]["audio_BW"]
            self.gui.lineEdit_audiocutoff_freq.setText(str(pr["projectdata"]["audio_BW"]))
            self.gui.lineEdit_carrierdistance.setText(str(pr["projectdata"]["carrier_distance"]))
            self.m["carrier_distance"] = pr["projectdata"]["carrier_distance"]
            self.m["numcarriers"] = pr["projectdata"]["numcarriers"]
            
            #self.gui.spinBox_numcarriers.valueChanged.disconnect(self.freq_carriers_update)
            self.gui.spinBox_numcarriers.valueChanged.disconnect(self.on_value_changed)
            self.gui.spinBox_numcarriers.editingFinished.disconnect(self.on_editing_finished)
            self.gui.spinBox_numcarriers.setProperty("value", self.m["numcarriers"])
            #self.gui.spinBox_numcarriers.valueChanged.connect(self.freq_carriers_update)
            self.gui.spinBox_numcarriers.valueChanged.connect(self.on_value_changed)
            self.gui.spinBox_numcarriers.editingFinished.connect(self.on_editing_finished)            
            self.m["carrier_ix"] = 0
            self.gui.comboBox_cur_carrierfreq.setCurrentIndex(self.m["carrier_ix"])
            #######preset_time = QTime(00, 30, 00) 
            aux_preset_time = pr["projectdata"]["preset_time"]
            preset_time = QTime(aux_preset_time[0],aux_preset_time[1],aux_preset_time[2]) 
            self.gui.timeEdit_reclength.setTime(preset_time)
            self.m["fc_low"] = pr["projectdata"]["carrier_f_low"]
            self.gui.comboBox_targetSR.setCurrentIndex(pr["projectdata"]["targetSR_index"])
            self.gui.comboBox_targetSR_2.setCurrentIndex(pr["projectdata"]["presetband_index"])
            self.gui.lineEdit_modfactor.setText(str(pr["projectdata"]["modfactor"])) 
            self.load_index = True
            try:
                self.gui.radiobutton_CustomCarriers.toggled.disconnect(self.customcarrier_handler)
            except:
                pass 
            if pr["projectdata"]["custom_carriers_active"] == "True":
                #self.custom_carriers = self.m["carrierarray"]
                self.m["carrierarray"] =  np.array(pr["projectdata"]["carrier_array"])
                self.gui.radiobutton_CustomCarriers.setChecked(True)
            else:
                self.m["carrierarray"] = []
                self.gui.radiobutton_CustomCarriers.setChecked(False)
            self.gui.radiobutton_CustomCarriers.toggled.connect(self.customcarrier_handler)  
            errorstatus, value = self.fillplaylist()
            if errorstatus:
                auxi.standard_errorbox(value + ".\n\nPlaylist is inconsistent with other settings, project file invalid, check project file")
                self.gui.pushButton_loadproject.clicked.connect(self.load_project)
                errorstatus = True
                self.errorhandler(value)
                return(errorstatus, value)
            self.current_listdir = pr["projectdata"]["current_listdir"]
            #########TODO TODO TODO: listdir = "" in case of URL --> fillsourcelist cannot be carried out
            if len(self.current_listdir) > 0: 
                self.fillsourcelist(self.current_listdir)
            #call GUI apdaters withoud calling playlist updates (option "nup")

            # self.m3uflag = False
            # self.m["numcarriers"] = len(self.readFileList)
            # self.freq_carriers_update(self,custom_carriers)
            # self.fc_low_update()
            if pr["projectdata"]["custom_carriers_active"] == 'True':
                custom_carriers = list(map(str, self.m["carrierarray"]))
                self.freq_carriers_update(self,custom_carriers)
            else:
                self.freq_carriers_update()
            self.RecBW_update("nup")
            self.LO_update("nup")
            self.carrierdistance_update("nup")
            self.audioBW_update("nup")
            self.fc_low_update("nup")
            self.carrierselect_update("nup")
            self.load_index = False

            #TODO TODO TODO copy custom carriers to custom table
            #import custom carriers correctly
            #self.comboBox_targetSR_2.setCurrentIndex(###) Preset menu
            #modulation factor

            #Target filename

        except Exception as e:
            errormessage = f"Error when loading project file. Please check the consistency of {filename}. Offending command: "
            self.errorhandler(errormessage + str(e))
        try:
            self.gui.pushButton_loadproject.clicked.disconnect(self.load_project)
        except:
            pass
        time.sleep(0.1)
        self.gui.pushButton_loadproject.clicked.connect(self.load_project)
        #print("##")
        self.activate_control_elements(True)
        self.m["proj_loaded"] = True
        return(errorstatus, value)


    def save_file_dialog(self):
        # Erstellen des Datei-Speicher-Dialogs
        filters = "project files (*.proj);;all files (*)"
        selected_filter = "project files (*.proj)"
        options = QFileDialog.Options()
        #options |= QFileDialog.DontUseNativeDialog  # Verwende das Qt-eigene Dialogfenster
        file_name, _ = QFileDialog.getSaveFileName(self.m["QTMAINWINDOWparent"], 
                                                   "Save File",
                                                   os.path.join(self.m["project_path"], "*.proj"),
                                                   #self.m["project_path"] + "\\*.proj",  # Standardmäßig kein voreingestellter Dateiname
                                                   "proj Files (*.proj);;All Files (*)",  # Filter für Dateitypen
                                                   options=options)
        if file_name:
            return file_name
        else:
            return None

    def load_file_dialog(self):
        # self.standardpath = os.getcwd()  #TODO TODO: take from core module via rxh; on file open core sets that to:
        # self.project_path = os.path.dirname(self.standardpath) + "\\projects"
        # if not os.path.exists(self.project_path):
        #     # Verzeichnis erstellen
        #     os.makedirs(self.project_path)

        #        self.SigRelay.emit("cm_all_",["standardpath",self.standardpath]); 
        ########### SET DEDICATED PROJECT FOLDER !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

        filters = "project files (*.proj);;all files (*)"
        selected_filter = "project files (*.proj)"
        options = QFileDialog.Options()
        #options |= QFileDialog.DontUseNativeDialog  # Verwende das Qt-eigene Dialogfenster
        file_name, _ = QFileDialog.getOpenFileName(self.m["QTMAINWINDOWparent"], 
                                                "Open project File", 
                                                self.m["project_path"],
                                                filters,  # Filter für Dateitypen
                                                selected_filter,
                                                #"all files (*)",
                                                options=options)
        if file_name:
            return file_name
        else:
            return None


    def get_wav_info(self,wav_file):
        """opens wav header of the sepcified file and reads out important information
        returns a dict with the keys:
         {
                'duration_seconds': duration,
                'n_channels': n_channels,
                'framerate': framerate,
                'sampwidth_bytes': sampwidth,
                'data_format': data_format
        }
        Example:
        file_path = 'your_audio_file.wav'
        wav_info = get_wav_info(file_path)

        print(f"playtime: {wav_info['duration_seconds']} Sekunden")
        print(f"sampling rate: {wav_info['framerate']} Hz")
        print(f"Data format: {wav_info['data_format']}")
        
        :param: wav_file
        :type: str
        :returns: dictionary with the information
        :rtype: dict
        """
        # open WAV-file
        with open(wav_file, 'rb') as file:
            # Lese den RIFF-Header (die ersten 12 Bytes)
            riff_header = file.read(12)
            
            # Lese den fmt-Chunk-Header (die nächsten 8 Bytes)
            fmt_chunk_header = file.read(8)
            
            # Extrahiere die Subchunk-ID und die Größe des fmt-Chunks
            subchunk_id = fmt_chunk_header[:4].decode('ascii')
            subchunk_size = struct.unpack('<I', fmt_chunk_header[4:])[0]
            
            # Lese den fmt-Chunk basierend auf der Größe
            fmt_chunk = file.read(subchunk_size)
            
            # Entpacke das Audioformat aus dem fmt-Chunk
            audio_format = struct.unpack('<H', fmt_chunk[:2])[0]

            # Mapping des Audioformats zu einer menschlich lesbaren Bezeichnung
            if audio_format == 1:
                data_format = f"PCM{8 * struct.unpack('<H', fmt_chunk[2:4])[0]}"
            elif audio_format == 3:
                sampwidth = struct.unpack('<H', fmt_chunk[2:4])[0] // 8
                if sampwidth == 4:
                    data_format = "Float32"
                elif sampwidth == 8:
                    data_format = "Float64"
                else:
                    data_format = "Unknown Float Format"
            else:
                data_format = f"Unknown Format Code: {audio_format}"

            # Anzahl der Kanäle, Abtastrate und weitere Informationen
            n_channels = struct.unpack('<H', fmt_chunk[2:4])[0]
            framerate = struct.unpack('<I', fmt_chunk[4:8])[0]
            sampwidth = struct.unpack('<H', fmt_chunk[2:4])[0] // 8

        # Nutze die `wave`-Bibliothek, um weitere Informationen zu extrahieren
        with wave.open(wav_file, 'rb') as wav:
            n_frames = wav.getnframes()
            duration = n_frames / float(framerate)            # return info
            
            return {
                'duration_seconds': duration,
                'n_channels': n_channels,
                'framerate': framerate,
                'sampwidth_bytes': sampwidth,
                'data_format': data_format
            }

    def get_reclength(self):
        qtimeedit = self.gui.timeEdit_reclength
        time_from_qtimeedit = qtimeedit.time()       
        # Zeit aus dem QTimeEdit-Objekt zu aktuellen Datum hinzufügen
        hours = time_from_qtimeedit.hour()
        minutes = time_from_qtimeedit.minute()
        seconds = time_from_qtimeedit.second()
        total_reclength = hours*3600 + minutes * 60 + seconds
        return total_reclength

    def show_fillprogress(self,duration):
        """show completion percentage of the current carrier track

        """
        total_reclength = self.get_reclength()
        progfract = duration/total_reclength * 100

        self.gui.progressBar_fillPlaylist.setValue(min(100,int(np.floor(progfract))))
        if progfract > 100:
            self.gui.progressBar_fillPlaylist.setStyleSheet("QProgressBar::chunk "
                    "{"
                        "background-color: red;"
                    "}")
        elif progfract > 90:
            self.gui.progressBar_fillPlaylist.setStyleSheet("QProgressBar::chunk "
                    "{"
                        "background-color: yellow;"
                    "}")           
        else:
            self.gui.progressBar_fillPlaylist.setStyleSheet("QProgressBar::chunk "
                    "{"
                        "background-color: green;"
                    "}")

    def carrier_ix_changed(self):
        """_slot function of comboBox_cur_carrierfreq
        get corresponding carrier index and call playlist update
        """
        self.m["carrier_ix"] = self.gui.comboBox_cur_carrierfreq.currentIndex()
        if not self.NOPLAYLISTUPDATE:
            errorstatus, value = self.fillplaylist()
        else:
            errorstatus = False
            value = ""
        if errorstatus:
            self.errorhandler(value)
            return

        
        #print(f"carrier index changed to: {self.m['carrier_ix']}")


    def fillplaylist(self):
        """update playlist of carrier with index self.m['carrier_ix']; clear old list and write new one

         :param: none

         :returns: none 
         """
        errorstatus = False
        value = None
        try:
            self.gui.listWidget_playlist.model().rowsInserted.disconnect(self.playlist_update_delayed)
        except:
            pass

        self.gui.listWidget_playlist.clear()
        #ix = 0
        try:
            for ix, x in enumerate(self.readFileList[self.m["carrier_ix"]]):
                #testpath = self.readFilePath[self.m["carrier_ix"]][ix] + "/" + x #TODO: prepared for testing existence of paths, but not valid for URLs
                item = QtWidgets.QListWidgetItem()
                self.gui.listWidget_playlist.addItem(item)
                _item = self.gui.listWidget_playlist.item(ix)
                _item.setText(x)
                fnt = _item.font()
                fnt.setPointSize(11)
                _item.setFont(fnt)
                #ix += 1
                #self.current_listdir = self.readFileList[self.m["carrier_ix"]]
        except:
            print("dummy")

        if len(self.readFileList[self.m["carrier_ix"]]) < 1:
            value = "read File List empty"
            self.gui.listWidget_playlist.model().rowsInserted.connect(self.playlist_update_delayed)
            return(errorstatus,value)
        errorstatus, value = self.show_playlength()
        if errorstatus:
            self.errorhandler(value)
            self.gui.listWidget_playlist.model().rowsInserted.connect(self.playlist_update_delayed)
            return(errorstatus,value)
        duration = value
        #self.display_worker_message('')
        time.sleep(0.2)
        QApplication.processEvents()
        # if not duration:
        #     return False
        self.show_fillprogress(duration)
        self.gui.listWidget_playlist.model().rowsInserted.connect(self.playlist_update_delayed)
        return(errorstatus,value)

    def show_context_menu(self, position):
        context_menu = QMenu(self.gui.listWidget_playlist)
        delete_action = context_menu.addAction("Delete")
        delete_action.triggered.connect(self.delete_selected_items)
        context_menu.exec_(self.gui.listWidget_playlist.viewport().mapToGlobal(position))

    def delete_selected_items(self):
        for item in self.gui.listWidget_playlist.selectedItems():
            self.gui.listWidget_playlist.takeItem(self.gui.listWidget_playlist.row(item))


    def on_rows_moved(self, parent, start, end, destinationParent, destinationRow):
        # calculate new position of the shifted items
        for i in range(start, end + 1):
            if destinationRow > start:
                new_index = destinationRow + (i - start) - 1
            else:
                new_index = destinationRow + (i - start)

            element = self.gui.listWidget_playlist.item(new_index).text()
            #print(f"Element '{element}' shifted from {i} to {new_index}")

        

    def show_playlength(self):
        """_update progress bar for total playlength for carrier with index [self.m['carrier_ix']


        :return errorstatus : False if o.k., True if error
        :rtype: Boolean
        :value :
        :rtype : any
        """
        errorstatus = False
        value = None
        # if not ffmpeg_installtools.is_ffmpeg_installed():
        #     errorstatus = True
        #     value = "NOCLEAR"
        #     return(errorstatus,value)
        ix = 0
        duration = 0
        self.toggle = True
        self.display_worker_message(f'loading playlist items, please wait, this can take a while')
        QApplication.processEvents()
        for x in self.readFileList[self.m["carrier_ix"]]:
            try:
                file_path =  self.readFilePath[self.m["carrier_ix"]][ix] + "/" + x
            except Exception as e:
                #print(f"show readFilePath index out of range at index: {self.m['carrier_ix']} [{ix}]")
                print(e)
                errorstatus = True
                errorstring = f"Error when calculating playlength. Exception: {str(e)}"
                return(errorstatus, errorstring)
            if not len(file_path) < 1:
                #wav_info = self.get_wav_info(file_path)
                #duration += wav_info['duration_seconds']
                #if duration Blödsinn, das kann passieren !
                #a = self.synthesizer_c.readsoundfile(file_path,"c")
                time.sleep(0.02)
                self.toggle = True

                if file_path.find("http://")>=0 or file_path.find("https://")>=0:
                    # if not ffmpeg_installtools.is_ffmpeg_installed():
                    #     errorstatus = True
                    #     value = "NOCLEAR"
                    #     break

                #TODO TODO TODO: Anzeige, dass nun ein länger dauernder Prozess startet (Read from URL)
                    ctime = datetime.now()
                    print(f"start read URL list @ {ctime}")
                    #TODO TODO TODO: Ermitteln, of ffmpeg installiert ist. Wenn nein:autoinstall
                    errorstatus, aux = self.get_stream_duration(file_path)
                    if errorstatus:
                        #auxi.standard_errorbox(f"Error when determining duration of {file_path}. Giving up")
                        self.clear_project()
                        return(errorstatus, value)
                    duration += aux
                    value = duration
                    print(f"end read URL list @ {ctime}, duration: {duration}")
                #self.gui.label_audioset_name.setText("")
                #self.gui.label_audioset_name.setStyleSheet("background-color: #FFFFFF; color: black;")  # weiss
                else:
                    errorstatus, a = self.synthesizer_c.readsoundfile(file_path)
                    #TODO TODO TODO LAST: catch error when returned False: Fils not foun o.ä. --> break loop
                    if errorstatus:
                        value = a
                        print("show_playlength, return error and break")
                        break
                    #print("show_playlength: ########### current point of development reached, proceed from here###########")
                    duration += a.frames/a.samplerate
                    value = duration
                    a.close()
                #self.display_worker_message('')
                #QApplication.processEvents()
                #self.display_worker_message('')
                #QApplication.processEvents()
                self.toggle = False
            else: #TODO: check and replace by more meaningfull actions
                print("NNNNNNNNNN")
                # errorstatus = True
                # value = " length of reaffilelist < 1"
            ix += 1

        # print(f"Spieldauer: {wav_info['duration_seconds']} Sekunden")
        # print(f"Anzahl der Kanäle: {wav_info['n_channels']}")
        # print(f"Abtastrate: {wav_info['framerate']} Hz")
        # print(f"Sample-Breite: {wav_info['sampwidth_bytes']} Bytes")
        # print(f"Datenformat: {wav_info['data_format']}")
        #print(f"full duration of this carrier track: {duration}")
        return(errorstatus, value)

    def get_stream_duration(self,url):
        """_summary_

        :param url: URL of the streamed audiofile
        :type url: str
        :return: _description_
        :rtype: _type_
        """
        errorstatus = False
        ffmpeg_command = [
            os.path.join(self.m["ffmpeg_path"], "ffmpeg"),
            "-user_agent", self.m["user_agent"],
            "-i", url,
            "-hide_banner"  # hide unnecessary info outputs
        ]        
        process = subprocess.Popen(ffmpeg_command, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        stdout, stderr = process.communicate()

        match1 = re.search(r"Failed to resolve", stderr.decode())
        match2 = re.search(r"Error opening input file", stderr.decode())
        if match1 or match2:
            errortext_suffix = f"Error when trying to connect to URL {url}. Aborting procedure"
            #auxi.standard_errorbox(errortext_suffix + " Aborting procedure ")
            value = errortext_suffix + " Aborting procedure "
            errorstatus = True
            return(errorstatus, value)
        # Dauer aus der ffmpeg-Ausgabe extrahieren
        match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", stderr.decode())
        if match:
            hours, minutes, seconds = map(float, match.groups())
            value = hours * 3600 + minutes * 60 + seconds  # Dauer in Sekunden
        else:
            value = "Error when trying to get duration of stream {url}. Aborting procedure "
            errorstatus = True
            return(errorstatus, value)
        return(errorstatus, value)

    # # Beispielaufruf
    # stream_url = "https://example.com/audio.mp3"
    # duration = get_stream_duration(stream_url)
    # if duration:
    #     print(f"Die Gesamtdauer beträgt: {duration:.2f} Sekunden")
    # else:
    #     print("Dauer konnte nicht ermittelt werden.")


    def carrierselect_update(self,*argv):
        """updates ccarrier selector combobox with new carrier frequencies
        if argv[0] is passed and contains the vale 'custom_carriers', the carrier frequencies are taken from the custom carrier table

        """
        #generate combobox entry list
        if len(self.m["carrierarray"]) > 0 and len(argv) > 0:
            #carrier_array = np.array(self.m["carrierarray"])
            if argv[0] == "nup":
                carrier_array = np.array(self.m["carrierarray"])
                pass
            else:
                carrier_array = np.array(argv[0])
            #carrierselector = carrier_array.tolist()
        else:
            carrier_array = np.arange(self.m["fc_low"], self.cf_HI+1, self.m["carrier_distance"])
        #carrier_array = TODO: entrypoint for individual carrierfrequencies, read array from editor
        # flex_carrier_table
        carrierselector = carrier_array.tolist()
        self.gui.comboBox_cur_carrierfreq.clear()
        for cf in carrierselector:
            self.gui.comboBox_cur_carrierfreq.addItem(str(cf))
        self.m["carrierarray"] = carrier_array

    def on_value_changed(self, value):
        # Reagiere sofort, wenn der Wert geändert wird und die Spinbox nicht den Fokus hat
        print(f"###########Focus unlear")
        if self.gui.spinBox_numcarriers.value() != self.previous_value:
            print(f"Wert durch Pfeiltasten geändert: {value}")
            # Aktualisiere den vorherigen Wert
            self.previous_value = value
            self.freq_carriers_update()

    def on_editing_finished(self):
        """slot function of spinbox self.gui.spinBox_numcarriers
        initiates updating of the number of carriers
        """
        self.freq_carriers_update()
        print("on editing finished")

    def freq_carriers_update(self,*argv):
        """
        append or remove i elements to/from carrier list, i being the difference between the old number and
        the new number either selected with Spinbox or taken from custom carrier table

        (1) gets number of carriers from Spinbox or custom carrier table

        (2) validates the number

        (3) initializes or removes i new elements in self.readFileList

        (4) transfers new number to model variable self.m["numcarriers"]  

        (5) sets lowest and highest carrier frequencies 

        (6) calls self.carrierselect_update()

        :parameters : *argv, variable number of args
        : 1st arg: custom_carriers: list of custom carrier frequencies in kHz
        :type : list
        :return: False on failure
        :rtype: Boolean
        """
        # TODO test what happens if empty ? check if not empty; if populated, re-read values into current table
        # (1) check if empty  >>>>DONE
        # (2) check if deviates from old list >>>>DONE
        # (3) import of URL playlists: same files on all carriers, check ; also interruptions possible
        # (4) clear sourcelists when importing m3u playlists >>>>> DONE
        # (5) emit info message on slowness when reading from URLs because of temp files
        #TODO TODO TODO: good errorhandling einbauen
        custom_flag = False
        self.numcarriers_old = self.m["numcarriers"]
        custom_carriers = []
        if len(argv) > 1:
            custom_flag = True
            for x in argv[1]:
                if len(x) > 0:
                    if self.isnumeric(x)[0]: ###########TODO: chars are a problem
                        custom_carriers.append(float(x))
                        self.m["carrierarray"] = custom_carriers
                    elif len(x) > 0:
                        auxi.standard_errorbox("custom carrier table contains non-numeric values, please correct !")
                        return False
            numcar = len(custom_carriers)
            if len(self.m["carrierarray"]) > 1:
                # determine the minimum difference between two carrier frequencies in a non-equally spaced list
                mindifference = np.min(np.diff(custom_carriers))
                #set the carrierdistance field to the minimum value for later validation
                self.gui.lineEdit_carrierdistance.setText(str(mindifference))
            self.gui.spinBox_numcarriers.valueChanged.disconnect(self.on_value_changed)
            self.gui.spinBox_numcarriers.setProperty("value", numcar)
            self.gui.spinBox_numcarriers.valueChanged.connect(self.on_value_changed)
            if len(self.m["carrierarray"]) > 0: #TODO: check what happens if only 1 carrier is selected --> catch in validator
                fc_low = float(self.m["carrierarray"][0])
                self.cf_HI = float(self.m["carrierarray"][-1])
                self.gui.lineEdit_fc_low.setText(str(fc_low))

        else:
            numcar = self.gui.spinBox_numcarriers.value()
        #TODO: make dependent on whether customcarriers or not ! >>>> DONE ?

        valid, errortext = self.validate_params()
        if not valid:
            self.gui.spinBox_numcarriers.valueChanged.disconnect(self.on_value_changed)
            self.gui.spinBox_numcarriers.editingFinished.disconnect(self.on_editing_finished)
            auxi.standard_errorbox(errortext)
            self.gui.spinBox_numcarriers.setProperty("value", self.numcarriers_old)
            time.sleep(0.1)
            self.gui.spinBox_numcarriers.valueChanged.connect(self.on_value_changed)
            self.gui.spinBox_numcarriers.editingFinished.connect(self.on_editing_finished)
            if len(argv) > 1:
                self.open_table_dialog()
            return False

        if numcar > self.numcarriers_old:
            #extend list
            curlen = self.numcarriers_old
            delta = numcar - self.numcarriers_old
            #TODO: Filelist wird hier aus m3u um 1 Zeile gekürzt
            for i in range(delta):
                self.readFileList.append([])
                self.readFileList[curlen + i] = [] #TODO TODO TODO: CHECK: voher hatte ich -1 , hier wird eine m3u Liste gekürzt
                self.oldFileList.append([])
                self.oldFileList[curlen + i] = []
                self.readFilePath.append([])
                self.readFilePath[curlen + i] = []
        elif numcar < self.numcarriers_old:
            delta = self.numcarriers_old - numcar
            if not self.load_index:
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Question)
                msg.setText("Warning")
                msg.setInformativeText(f"you are about to delete the last {delta} carriers. The corresponding playlists will be removed. Do you want to proceed")
                msg.setWindowTitle("Delete carriers")
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msg.buttonClicked.connect(self.popup)
                msg.exec_()

                if self.yesno == "&Yes":
                    for i in range(delta):
                        try:
                            del self.readFileList[self.numcarriers_old - 1 - i]
                        except:
                            pass
                        try:
                            del self.oldFileList[self.numcarriers_old - 1 - i]
                        except:
                            pass
                        try:
                            del self.readFilePath[self.numcarriers_old - 1 - i]
                        except:
                            pass
                else:
                    #self.gui.spinBox_numcarriers.editingFinished.disconnect(self.freq_carriers_update)
                    self.gui.spinBox_numcarriers.valueChanged.disconnect(self.on_value_changed)
                    self.gui.spinBox_numcarriers.editingFinished.disconnect(self.on_editing_finished)
                    self.gui.spinBox_numcarriers.setProperty("value", self.numcarriers_old)
                    time.sleep(0.1)
                    #self.gui.spinBox_numcarriers.editingFinished.connect(self.freq_carriers_update)
                    self.gui.spinBox_numcarriers.valueChanged.connect(self.on_value_changed)
                    self.gui.spinBox_numcarriers.editingFinished.connect(self.on_editing_finished)
                    return False
            else:
                for i in range(delta):
                    del self.readFileList[self.numcarriers_old - 1 - i]
                    del self.oldFileList[self.numcarriers_old - 1 - i]
                    del self.readFilePath[self.numcarriers_old - 1 - i]

        self.m["numcarriers"] = numcar
        #### TODO TODO TODO if custom table --> custom_flag needs to be True
        if len(self.m["carrierarray"]) > 0 and custom_flag: #TODO: simplify
            pass
        else:
            fc_low = float(self.gui.lineEdit_fc_low.text())#TODO make this visible to validator
            self.cf_HI = fc_low + (self.m["numcarriers"] - 1) * self.m["carrier_distance"]
        if custom_flag:
            self.carrierselect_update(custom_carriers)
        else:
            self.carrierselect_update()
        return True
    
    def popup(self,i):
        """
        """
        self.yesno = i.text()

    def isfloat(self,num):
        try:
            float(num)
            return True
        except ValueError:
            auxi.standard_errorbox("invalid characters, must be numeric float value !")
            return False

    def isint(self,num):
        try:
            int(num)
            return True
        except ValueError:
            auxi.standard_errorbox("invalid characters, must be numeric integer value !")
            return False

    def isnumeric(self,s):
        # Versuche, das deutsche Locale zu verwenden (Komma als Dezimaltrennzeichen)
        locale.setlocale(locale.LC_NUMERIC, 'de_DE.UTF-8')  # Für deutsches Format
        try:
            a = locale.atof(s)  # Parst eine Zahl mit deutschem Format
            return True, ""
        except ValueError:
            pass  # Wenn es nicht im deutschen Format ist, versuche es im englischen Format

        # Zurück zum englischen Locale für das Standardformat (Punkt als Dezimaltrennzeichen)
        locale.setlocale(locale.LC_NUMERIC, 'en_US.UTF-8')
        try:
            a = locale.atof(s)  # Parst eine Zahl mit englischem Format
            return True, ""
        except ValueError:
            errortext = "value is not numeric"
            return False, errortext

    def validate_params(self,*argv):
        """_validates certain parameter conditions which must be fulfilled for meaningful settings,
        e.g. carrier distance > 2* Audio-BW_
        :return: valid: True if all conditions met, else False
        :rtype: boolean
        :return: errortext: string specifying the type of violation
        :rtype: str
        """
        cc_LABEL = False
        if len(argv) > 1: #TODO DUMMY so far
            if argv[2].find("custom_carrier") == 0:
               cc_LABEL = True
               pass
            pass
        audioBW = float(self.gui.lineEdit_audiocutoff_freq.text())
        carrier_distance = float(self.gui.lineEdit_carrierdistance.text())
        sample_rate = int(self.gui.comboBox_targetSR.currentText())
        f_LO = float(self.gui.lineEdit_LO.text())
        fc_low = float(self.gui.lineEdit_fc_low.text())
        numcarriers = self.gui.spinBox_numcarriers.value()
        modfactor = float(self.gui.lineEdit_modfactor.text())
        if (carrier_distance < 2*audioBW):# and not self.load_index: ????
            self.rule_viol = True
            errortext = "carrier spacing is less than 2*audio bandwidth, this is not allowed, please either increase carrier spacing or reduce audio bandwidth"
            #self.gui.lineEdit_carrierdistance.setText(str(self.m["carrier_distance"]))
            #self.gui.lineEdit_audiocutoff_freq.setText(str(self.m["audioBW"]))
            print("return false from validate")
            return False, errortext
        #Fclow + numcarriers * DeltaC <  LO + BW/2 - AudioBW
        highlimit = f_LO + sample_rate/2 - audioBW
        lowlimit = f_LO - sample_rate/2 + audioBW
        violate_low = fc_low < lowlimit
        #violate_high = fc_low + carrier_distance * numcarriers > highlimit
        violate_high = self.cf_HI > highlimit
        if violate_low or violate_high :# and not self.load_index: ????
            self.rule_viol = True
            #Fclow > f_LO – samplerate/2 + AudioBW 
            if violate_low:
                errortext = "lowest carrier frequency is below the lowest edge of the band ()" + str(lowlimit) +"), please correct one or more of the following parameters: LO frequency, Rec-Bandwidth, lowest carrier frequency, carrier distance or audio cutoff frequency"
            if violate_high:
                errortext = "highest carrier frequency (" + str(fc_low + carrier_distance * numcarriers) + ") is above the highest edge of the band " + str(highlimit) +", please correct one or more of the following parameters: LO frequency, Rec-Bandwidth, lowest carrier frequency, carrier distance, number of carriers or audio cutoff frequency"
            if violate_low and violate_high:
                errortext = "lowest and highest carrier frequency are out of the band. Low limit: " + str(lowlimit) + ", please correct one or more of the following parameters: LO frequency, Rec-Bandwidth, lowest carrier frequency, carrier distance, number of carriers or audio cutoff frequency"

            print("return false from validate")
            return False, errortext
        if modfactor < 0.01 or modfactor > 1:
            errortext = "Modulation factor out of range, value must be >= 0.01 and <= 1"
            return False, errortext
        return True, ""

    def RecBW_update(self,*argv):
        """slot function for the recording Bandwidth (=SR) combobox; sets the model parameter self.m['sample_rate'] and triggers validation"""
        RecBW = int(self.gui.comboBox_targetSR.currentText()) #TODO: redundant ?
        valid, errortext = self.validate_params()
        if not valid:
            auxi.standard_errorbox(errortext)
            self.gui.comboBox_targetSR.setCurrentIndex(self.m["SR_currindex"])
            return False
        self.m["sample_rate"] = int(self.gui.comboBox_targetSR.currentText())
        self.m["SR_currindex"] = self.gui.comboBox_targetSR.currentIndex()
        #self.freq_carriers_update()

    def audioBW_update(self,*argv):
        """slot function for the audio Bandwidth line_edit; sets the model parameter m['audioBW'] and triggers validation"""
        audioBW = self.gui.lineEdit_audiocutoff_freq.text()
        if not self.isnumeric(audioBW):
            auxi.standard_errorbox("invalid characters, must be numeric value !")
            self.gui.lineEdit_audiocutoff_freq.setText(str(self.m["audioBW"]))
            return False
        # else: TODO: remove after tests
        #     self.m["audioBW"] = float(self.gui.lineEdit_audiocutoff_freq.text())
        if (float(audioBW) < 2.5) or (float(audioBW) > 16):
            auxi.standard_errorbox("audio bandwidth outside the range 2.5 - 16 kHz. Value must be in this interval, please cahnge")
            self.gui.lineEdit_audiocutoff_freq.setText(str(self.m["audioBW"]))
            return False
        valid, errortext = self.validate_params()
        if not valid:
            auxi.standard_errorbox(errortext)
            self.gui.lineEdit_audiocutoff_freq.setText(str(self.m["audioBW"]))
            return False
        self.m["audioBW"] = float(self.gui.lineEdit_audiocutoff_freq.text())
        if len(argv) > 0:
            c = argv[0]
            print(f"argv in AudioBWupdate: {argv}")
            if c.find("nup") == 0:
                return
        self.freq_carriers_update()
        #print(f"carrier spacing: {self.m['audioBW']}")

    def LO_update(self,*argv):
        """slot function for the LO frequency line_edit; sets the model parameter m['LO'] and triggers validation"""
        cf_LO = self.gui.lineEdit_LO.text()
        if not self.isnumeric(cf_LO):
            auxi.standard_errorbox("invalid characters, must be numeric value !")
            self.gui.lineEdit_LO.setText(str(self.m["LO"]))
            return False
        valid, errortext = self.validate_params()
        if not valid:
            auxi.standard_errorbox(errortext)
            self.gui.lineEdit_LO.setText(str(self.m["LO"]))
            return False
        self.m["LO"] = float(self.gui.lineEdit_LO.text())
        if len(argv) > 0:
            c = argv[0]
            print(f"argv in LO_update: {argv}")
            if c.find("nup") == 0:
                return
        self.freq_carriers_update()

    def modfactor_update(self,*argv):
        """slot function for the modulation factor line_edit; sets the model parameter m['modfactor'] and triggers validation"""
        self.gui.lineEdit_modfactor.editingFinished.disconnect(self.modfactor_update)
        modfactor = self.gui.lineEdit_modfactor.text()
        if not self.isnumeric(modfactor):
            auxi.standard_errorbox("invalid characters in modulation factor, must be numeric value !")
            self.gui.lineEdit_modfactor.setText(str(self.m["modfactor"]))
            self.gui.lineEdit_modfactor.editingFinished.connect(self.modfactor_update)
            return False
        valid, errortext = self.validate_params()
        if not valid:
            auxi.standard_errorbox(errortext)
            self.gui.lineEdit_modfactor.setText(str(self.m["modfactor"]))
            self.gui.lineEdit_modfactor.editingFinished.connect(self.modfactor_update)
            return False
        self.m["modfactor"] = float(self.gui.lineEdit_modfactor.text())
        #self.freq_carriers_update()
        self.gui.lineEdit_modfactor.editingFinished.connect(self.modfactor_update)

    def fc_low_update(self,*argv):
        """slot function for the low carrier frequency line_edit; sets the model parameter m['fc_low'] 
        and triggers validation"""
        #self.gui.lineEdit_fc_low.setText(str(self.cf_LO)) TODO: remove self.cf_LO
        fc_low = self.gui.lineEdit_fc_low.text()
        if not self.isnumeric(fc_low):
            auxi.standard_errorbox("invalid characters, must be numeric value !")
            self.gui.lineEdit_fc_low.setText(str(self.m["fc_low"]))
            return False
        valid, errortext = self.validate_params()
        if not valid:
            auxi.standard_errorbox(errortext)
            self.gui.lineEdit_fc_low.setText(str(self.m["fc_low"]))
            return False
        self.m["fc_low"] = float(self.gui.lineEdit_fc_low.text())
        if len(argv) > 0:
            c = argv[0]
            print(f"argv in fc_low_update: {argv}")
            if c.find("nup") == 0:
                return
        #####TODO TODO TODO: check if argv necessary otherwise no custom carrier treatment
        self.freq_carriers_update()
        #print(f"carrier spacing: {self.m['fc_low']}")

    def carrierdistance_update(self,*argv):
        """slot function for the carrier distance line_edit; sets the model parameter m["carrier_distance"] and triggers validation"""
        self.gui.lineEdit_carrierdistance.editingFinished.disconnect(self.carrierdistance_update)
        old_carrierdistance = self.m["carrier_distance"]
        carrier_delta = self.gui.lineEdit_carrierdistance.text()
        if not self.isnumeric(carrier_delta):
            auxi.standard_errorbox("invalid characters, must be numeric float value !")
            self.logger.error("plot_res_spectrum: wrong format of carrier distance")
            self.gui.lineEdit_carrierdistance.setText(str(self.m["carrier_distance"]))
            self.gui.lineEdit_carrierdistance.editingFinished.connect(self.carrierdistance_update)
            return False
        # if float(carrier_delta) < 0.1: #TODO: redundant, carrier_delta must be > 2*audioBW, audioBW must be > 2.5
        #     auxi.standard_errorbox("invalid carrier spacing, must be numeric float value > 0.1!")
        #     self.logger.error("plot_res_spectrum: wrong value of carrier distance")
        #     self.gui.lineEdit_carrierdistance.setText(str(self.m["carrier_distance"]))
        #     return False
        valid, errortext = self.validate_params()
        if not valid:
            auxi.standard_errorbox(errortext)
            self.gui.lineEdit_carrierdistance.setText(str(old_carrierdistance))
            self.gui.lineEdit_carrierdistance.editingFinished.connect(self.carrierdistance_update)
            return False
        
        nup = False
        self.m["carrier_distance"] = float(self.gui.lineEdit_carrierdistance.text())
        if len(argv) > 0:
            c = argv[0]
            print(f"argv in fc_low_update: {argv}")
            if c.find("nup") == 0:
                nup = True
        if not nup:       
            self.freq_carriers_update()
        self.load_index = False
        self.gui.lineEdit_carrierdistance.editingFinished.connect(self.carrierdistance_update)
        #print(f"carrier spacing: {self.m['carrier_distance']}")
        return True
    
    def select_tree(self):
        """
        initiates buildup of file selection tree
        :param : none
        :raises [ErrorType]:none
        :returns: none
        """  
        self.gui.pushButton_select_source.clicked.disconnect(self.select_tree)
        root_directory = QFileDialog.getExistingDirectory(self.m["QTMAINWINDOWparent"], "Please chose source file directory", self.default_directory)
        if root_directory:
            self.fillsourcelist(root_directory)
            self.m["metadata"]["last_audiosource_path"] = root_directory
            stream = open("config_wizard.yaml", "w")
            yaml.dump(self.m["metadata"], stream)
            stream.close()
        self.gui.pushButton_select_source.clicked.connect(self.select_tree)


    def add_children(self, parent, directory):
        for name in QDir(directory).entryList(QDir.NoDotAndDotDot | QDir.AllDirs):
            path = QDir(directory).absoluteFilePath(name)
            child = QTreeWidgetItem(parent, [name])
            child.setData(0, Qt.UserRole, path)
            self.add_children(child, path)

    # def on_tree_item_clicked(self, item, column):
    #     path = item.data(0, Qt.UserRole)
    #     #self.gui.listWidget_playlist.clear()
    #     for name in QDir(path).entryList(QDir.NoDotAndDotDot | QDir.Files):
    #         self.gui.listWidget_playlist.addItem(name)

    def fillsourcelist(self, rootdir):
        self.gui.listWidget_sourcelist.clear()
        item = QtWidgets.QListWidgetItem()
        self.gui.listWidget_sourcelist.addItem(item)
        ix = 0
        self.current_listdir = ""
        for x in os.listdir(rootdir):

            if x.endswith(".wav") or x.endswith(".mp3"):
                if True: #x != (self.m["my_filename"] + self.m["ext"]): #TODO: obsolete old form when automatically loading opened file to playlist
                    _item = self.gui.listWidget_sourcelist.item(ix)
                    _item.setText(x)
                    fnt = _item.font()
                    fnt.setPointSize(11)
                    _item.setFont(fnt)
                    item = QtWidgets.QListWidgetItem()
                    self.gui.listWidget_sourcelist.addItem(item)
                    ix += 1
                    self.current_listdir = rootdir

    def playlist_update_delayed(self,dum,first,last):
        """intermediate function to call playlist_update() with a delay of 0.1 seconds

        :param dum: dummy parameter
        :type dum: not specified
        :param first: dummy parameter
        :type first: not specified
        :param last: dummy parameter
        :type last: not specified
        """
        #print(f"playlist_update, signal addrow: first ix: {first}, last ix: {last}")
        QTimer.singleShot(0, self.playlist_update)

    def playlist_update(self):
        """_currently loaded playlist in self.gui.listWidget_playlist is bering transferred 
        to the central list of playlists self.readFileList[self.m["carrier_ix"]]. Then playlist_purge()
        is called
        """
        try:
            self.gui.listWidget_playlist.model().rowsInserted.disconnect(self.playlist_update_delayed)
        except:
            pass
        try:
            self.oldFileList[self.m["carrier_ix"]] = copy.deepcopy(self.readFileList[self.m["carrier_ix"]])
            #TODO TODO TODO: Bei Indexerhöhung muss ein dummy self.oldFileList[self.m["carrier_ix"]] mit dem erhöhten Index angelegt werden, sonst stürzt später due diff-Methode in purge ab
        except:
            self.oldFileList = []

        self.readFileList[self.m["carrier_ix"]] = [self.gui.listWidget_playlist.item(i).text() for i in range(self.gui.listWidget_playlist.count())]
        self.playlist_purge()
        errorstate, value = self.show_playlength()
        if errorstate:
            self.errorhandler(value)
            self.gui.listWidget_playlist.model().rowsInserted.connect(self.playlist_update_delayed)
            return
        duration = value
        self.display_worker_message("playlist up to date")
        QApplication.processEvents()
        # if not duration:
        #     return False
        self.show_fillprogress(duration)
        self.gui.listWidget_playlist.model().rowsInserted.connect(self.playlist_update_delayed)
        #print("playlist_update")
        # try:
        #     for file in readFileList:
        #         with open(file) as lstf:
        #             filesRead = lstf.read()
        #             print(filesRead)
        #             # return(filesReaded)

        # except Exception as e:
        #     print("the selected file is not readable because :  {0}".format(e)) 

    def playlist_purge(self):
        """_update path information in self.readFilePath for the corresponding readFileList at index  self.m['carrier_ix']
        """
        ix_diff = self.find_first_difference(self.oldFileList[self.m["carrier_ix"]] , self.readFileList[self.m["carrier_ix"]] )
        try:
            if len(self.readFileList[self.m["carrier_ix"]] ) <= len(self.oldFileList[self.m["carrier_ix"]] ):
                self.readFilePath[self.m["carrier_ix"]] = self.delete_at_index(self.readFilePath[self.m["carrier_ix"]], ix_diff)
            else:
                self.readFilePath[self.m["carrier_ix"]] = self.insert_or_append(self.readFilePath[self.m["carrier_ix"]], ix_diff, self.current_listdir)
            #print(f"playlist purge: change index: {ix_diff}, playlist: {self.readFileList[self.m['carrier_ix']] }, pathlist: {self.readFilePath[self.m['carrier_ix']]}")
        except:
            print("playlist purge: no difference, no action")

    def insert_or_append(self,pathlist, ix, element):

        if ix < len(pathlist):
            pathlist.insert(ix, element)
        else:
            pathlist.append(element)
        return pathlist

    def delete_at_index(self,pathlist, ix):
        if 0 <= ix < len(pathlist):
            del pathlist[ix]
        return pathlist

    def find_first_difference(self, list1, list2):
        min_length = min(len(list1), len(list2))

        for i in range(min_length):
            if list1[i] != list2[i]:
                return i

        if len(list1) != len(list2):
            return min_length

        return None  # Die Listen sind identisch
    
    def rxhandler(self,_key,_value):
        """
        handles remote calls from other modules via Signal SigRX(_key,_value)
        :param : _key
        :type : str
        :param : _value
        :type : object
        :raises [ErrorType]: [ErrorDescription]
        :return: none
        :rtype: none
        """
        if _key.find("cm_synthesizer") == 0 or _key.find("cm_all_") == 0:
            #set mdl-value
            self.m[_value[0]] = _value[1]
            if _value[0] == "recording_path":
                print("recording path received")
                print(_value)
                print(self.m["recording_path"])
        if _key.find("cui_synthesizer") == 0:
            _value[0](_value[1]) #STILL UNCLEAR
        # if _key.find("cexex_canvasbuild") == 0 or _key.find("cexex_all_") == 0:
        #     if  _value[0].find("canvasbuild") == 0:
        #         print("resize action triggered in synthesizer")
        #         _value[1].resize_initialize()
        if _key.find("cexex_synthesizer") == 0  or _key.find("cexex_all_") == 0:
            if  _value[0].find("updateGUIelements") == 0:
                self.updateGUIelements()
            if  _value[0].find("reset_GUI") == 0:
                self.reset_GUI()
            if  _value[0].find("logfilehandler") == 0:
                self.logfilehandler(_value[1])
            if  _value[0].find("timertick") == 0:
                if not self.m["ffmpeg_autocheck"]:
                    #print(f"timertick: value of self.m['ffmpeg_autocheck'] {self.m["ffmpeg_autocheck"]}")
                    #self.m["ffmpeg_autocheck"] = True
                    #self.checkffmpeg_install()
                    pass
<<<<<<< HEAD
=======
            if  _value[0].find("resizeaction") == 0:
                #print("resize action triggered in resampler")
                _value[1].resize_initialize()

>>>>>>> b20af23e7c8bce856c7bced8a85f6faabe118299

                #print(f"timertick: value of self.m['ffmpeg_autocheck'] {self.m["ffmpeg_autocheck"]}")
                if self.syntesisrunning:
                    self.blinkstate = self.blinksynth(self.blinkstate)
                    #self.PupdateSignalHandler()

    def logfilehandler(self,_value):
        if _value is False:
            self.logger.debug("abstract module: INACTIVATE LOGGING")
            self.logger.setLevel(logging.ERROR)
        else:
            self.logger.debug("abstract module: REACTIVATE LOGGING")
            self.logger.setLevel(logging.DEBUG)

    def blinksynth(self,state):
        """
        let create button blink
        """
        if state:
            self.gui.synthesizer_pushbutton_create.setStyleSheet("background-color: " + self.cancel_background_color.name() + "; color: gray;")
        else:
            self.gui.synthesizer_pushbutton_create.setStyleSheet("background-color: lightblue; color: gray;")
        state = not state
        return state


    def updateGUIelements(self):
        """
        updates GUI elements , usually triggered by a Signal SigTabsUpdateGUIs to which 
        this method is connected in the __main__ of the core module
        :param : none
        :type : none
        :raises [ErrorType]: [ErrorDescription]
        :return: flag False or True, False on unsuccessful execution
        :rtype: Boolean
        """
        #print("synthesizer: updateGUIelements")
        #self.gui.DOSOMETHING

    def reset_GUI(self):
        pass


    def open_table_dialog(self):
        """
        opens a Dialogue widget as a floating TableWidget,which allows to enter individual carrier frequencies. On pressin enter, the row data are returned
        :params : none
        :returns: row
        :rtype : list
        """
        dialog = TableDialog(None)
        self.populate_table(dialog.table, self.m["carrierarray"])

        if dialog.exec_() == QDialog.Accepted:  # Wenn der Benutzer auf 'Enter' klickt
            #dialog.set_table_data()
            #self.custom_carriers  
            custom_carriers = dialog.get_table_data()
            print("Eingegebene Daten:")
            for row in custom_carriers:
                print(row)
        self.freq_carriers_update(self,custom_carriers)
        self.fc_low_update('nup')

    def populate_table(self, table, values):
        rows = len(values)
        #table.setRowCount(rows)

        # Tabelle mit Float-Werten füllen
        for i, value in enumerate(values):
            item = QTableWidgetItem(f"{value:.2f}")  # Float-Wert formatieren
            table.setItem(i, 0, item)  # (Zeile, Spalte)


    def import_m3u(self):
        """import an m3u playlist with special format containing fields of the form
        #EXTGRP: <carrierfrequency>
        where <carrierfrequency> is a number specifying the carrier frequency in kHz for the following sub-playlist

        (1) read last importpath, if not found set to current directory

        (2) open m3u file, parse lines and compose self.readFileList and self.readFilePath

        (3) call update of carrier frequencies
        """
        #TODO: good errorhandling
        self.clear_project()
        self.activate_control_elements(False)
        self.m3uflag = True
        self.m["proj_loaded"] = True
        self.gui.listWidget_sourcelist.clear()
        self.gui.pushButton_importProject.clicked.disconnect(self.import_m3u)
        try:
            stream = open("config_wizard.yaml", "r")
            self.m["metadata"] = yaml.safe_load(stream)
            stream.close()
            if "last_m3u_path" in self.m["metadata"]:
                self.m["last_m3u_path"] = self.m["metadata"]["last_m3u_path"]
            else:
                self.m["metadata"]["last_m3u_path"] = os.getcwd()
        except:
            self.m["metadata"]["last_m3u_path"] = os.getcwd()

        filters = "m3u files (*.m3u);; all files (*.*)"
        selected_filter = "m3u files (*.m3u)"

        filename =  QtWidgets.QFileDialog.getOpenFileName(self.m["QTMAINWINDOWparent"],
                                                        "Open data file"
                                                        ,self.m["metadata"]["last_m3u_path"] , filters, selected_filter)

        self.m["metadata"]["last_m3u_path"] = Path(filename[0]).parent.as_posix()
        stream = open("config_wizard.yaml", "w")
        yaml.dump(self.m["metadata"], stream)
        stream.close()

        #with open(filename, 'r', encoding='utf-8') as f:
        with open(filename[0], 'r') as f:
            playlist_content = f.read()

        # Initialize variables
        sub_playlists = []  # This will hold the sub-playlists
        headers = []        # This will hold the associated headers
        # Temporary variables to store the current sub-playlist and header
        current_playlist = []
        current_header = None
        #clear and iniialize playlist
        self.readFileList = []
        current_filelist = []
        self.readFilePath = []
        current_filepath = []
        # Iterate through each line in the playlist content
        for line in playlist_content.splitlines():
            # Look for #EXTGRP lines
            if line.startswith('#EXTGRP:'):
                # If there's already a current sub-playlist, store it
                if current_playlist:
                    sub_playlists.append(current_playlist)
                    headers.append(current_header)
                # Extract the index from the #EXTGRP line (example: #EXTGRP: sometext_1)
                # You can split on the underscore or colon based on your format
                group_info = line.split(':')[1].strip()  # sometext_index
                current_header = (group_info.split('_')[-1])  # Extract the index part
                # # Set the new current header and reset current_playlist
                # current_header = {'index': index}
                # index = 0 #TODO: only testindex
                for element in current_playlist:
                    current_filelist.append(Path(element).stem + Path(element).suffix)
                    if element.find("http") == 0:
                        pp = element[0:element.find(Path(element).stem)-1]
                        current_filepath.append(pp)
                    else:
                        current_filepath.append(Path(element).parent.as_posix())
                current_playlist = []  # Reset the current playlist
                if len(current_filelist) > 0:
                    self.readFileList.append(current_filelist)
                    self.readFilePath.append(current_filepath)
                current_filelist = []
                current_filepath = []
            else:
                # Add playlist entries (e.g., media URLs) to the current sub-playlist
                if line.startswith('#') and line:  # Ignoriere Kommentare und leere Zeilen
                    #print(line)  # Mediendateipfad
                    pass
                if not line.startswith('#') and line:  # Ignoriere Kommentare und leere Zeilen
                    current_playlist.append(line)

        # Append the last sub-playlist after the loop has ended
        #TODO: not elegant, shift to strategically optimal point !
        if current_playlist:
            sub_playlists.append(current_playlist)
            headers.append(current_header)
            for element in current_playlist:
                current_filelist.append(Path(element).stem + Path(element).suffix)
                if element.find("http") == 0:
                    pp = element[0:element.find(Path(element).stem)-1]
                    current_filepath.append(pp)
                else:
                    current_filepath.append(Path(element).parent.as_posix())
            self.readFileList.append(current_filelist)
            self.readFilePath.append(current_filepath)

        # Now, sub_playlists holds the segmented playlists and headers contains the associated index for each
        print(sub_playlists)
        #print(headers)
        custom_carriers = []
        for ix in range(len(headers)):#TODO necessary ?
            #custom_carriers.append(headers[ix]["index"])
            custom_carriers.append(headers[ix])
        #TODO: validate, if headers is consistent and has the same length as sub_playlists
        #if not: return without success
        #if success: call method for integrating into current playlists:
        #   copy sub_playlists into internal playlist structure:
        #self.readFilePath[ix]: list
        #self.readFileList[ix]: list for carrier ix
        #   copy carriers to custom carriertable >>>>>> DONE
        #   set custom carrier button Checked without triggering table edit 
        #   carry out GUI update and validation by accessing the slot function of table edit OK

        self.m["numcarriers"] = len(self.readFileList)
        self.freq_carriers_update(self,custom_carriers)
        #self.fc_low_update()
        self.gui.radiobutton_CustomCarriers.setChecked(True)
        self.activate_control_elements(True)
        self.gui.pushButton_importProject.clicked.connect(self.import_m3u)

class TableDialog(QDialog):
    """Class for generating a popup TableWidget for entering the custom values"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Table Dialog")
        self.setGeometry(200, 200, 400, 300)

        # Layout for Dialogue
        layout = QVBoxLayout(self)

        # create floating TableWidget
        self.table = QTableWidget()
        self.table.setRowCount(10)
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["frequency (Hz)"])
        self.table.setContextMenuPolicy(3)  # activate user defined context menu
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.table)

        # add ButtonBox with 'Enter' und 'Cancel'
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)  # close dialogue and return OK
        buttons.rejected.connect(self.reject)  # close dialogue and return Cancel
        layout.addWidget(buttons)

        # fill first row with empty item
        self.table.setItem(0, 0, QTableWidgetItem(""))

        # connect cellChanged signal
        self.table.cellChanged.connect(self.handle_cell_changed)

    def handle_cell_changed(self, row, column):
        # If the changed cell is in the last row, append a new empty row
        if row == self.table.rowCount() - 1:
            self.table.blockSignals(True)  # avoid recursive signal
            self.table.insertRow(self.table.rowCount())
            self.table.setItem(self.table.rowCount() - 1, 0, QTableWidgetItem(""))
            self.table.blockSignals(False)

    def get_table_data(self):
        """
        returns data of the custom carrier frequency table
        :returns : list of strings with custom carrier frequencies, frequencies in kHz
        :rtype : list of str
        """
        data = []
        for row in range(self.table.rowCount()):
            row_data = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                row_data.append(item.text() if item else "")  # Leerstring, wenn keine Daten vorhanden
            data.append(row_data[0])
        return data


    def show_context_menu(self, position):
        """show right mouse click context menu for custom carrier frequency table

        :param position: _description_
        :type position: _type_
        """
        # bulid context menu
        context_menu = QMenu(self)

        # add menu options
        add_row_action = context_menu.addAction("Add Row")
        remove_row_action = context_menu.addAction("Remove Row")

        # ask for user request
        action = context_menu.exec_(self.table.viewport().mapToGlobal(position))

        # carry out context action
        if action == add_row_action:
            self.add_row()
        elif action == remove_row_action:
            self.remove_selected_row()

    def add_row(self):
        # add new row to custom carrier table by context menu
        row_count = self.table.rowCount()
        self.table.insertRow(row_count)

        # optional: enter text in table element
        for col in range(self.table.columnCount()):
            #self.table.setItem(row_count, col, QTableWidgetItem(f"Zeile {row_count + 1}, Spalte {col + 1}"))
            self.table.setItem(row_count, col, QTableWidgetItem(""))

    def remove_selected_row(self):
        # remove currently selected row from custom carrier table by context menu
        selected_row = self.table.currentRow()
        if selected_row >= 0:
            self.table.removeRow(selected_row)



# playlist = m3u8.loads(playlist_content)
# for segment in playlist.segments:

#     print(segment.uri)

#     #Zugriffe:
# playlist.segments[1].uri
# playlist.segments[1].duration
# playlist.segments[1].title

# #playlist.segments[1].playlist_type
# playlist.segments[1].media_sequence


#TODO: 
# test = WAVheader_tools.get_sdruno_header(self,self.m["f1"],'audio')
# import numpy as np
# from scipy.signal import iirnotch, lfilter_zi, lfilter

# def design_notch_filter(fn, BN, fs):
#     """
#     Entwirft einen Notch-Filter bei Mittenfrequenz fn mit Bandbreite BN.

#     Parameters:
#     - fn: Mittenfrequenz des Notch-Filters (Hz)
#     - BN: Notch-Bandbreite (Hz)
#     - fs: Abtastrate (Hz)

#     Returns:
#     - b, a: Notch-Filterkoeffizienten
#     """
#     Q = fn / BN  # Berechnung des Qualitätsfaktors Q
#     b, a = iirnotch(fn / (fs / 2), Q)
#     return b, a

# def process_block(input_block, b, a, zi_real, zi_imag):
#     """
#     Filtert einen Datenblock mit dem Notch-Filter und verwendet den Filterzustand.

#     Parameters:
#     - input_block: Block von komplexen Daten (1D-Array)
#     - b, a: Notch-Filterkoeffizienten
#     - zi_real, zi_imag: Filterzustände für Real- und Imaginärteil

#     Returns:
#     - Gefilterter Block von komplexen Daten (1D-Array)
#     - Neuer Filterzustand für den nächsten Block
#     """
#     # Filterung des Realteils und Aktualisierung des Filterzustands
#     filtered_real, zi_real = lfilter(b, a, np.real(input_block), zi=zi_real)
    
#     # Filterung des Imaginärteils und Aktualisierung des Filterzustands
#     filtered_imag, zi_imag = lfilter(b, a, np.imag(input_block), zi=zi_imag)
    
#     # Rückgabe des gefilterten komplexen Signals und des neuen Zustands
#     filtered_block = filtered_real + 1j * filtered_imag
#     return filtered_block, zi_real, zi_imag

# def notch_filter_file(input_file, output_file, fn, BN, fs, block_size=1024):
#     """
#     Liest ein komplexes Zeit-Signal blockweise, filtert es mit einem Notch-Filter
#     und speichert das Ergebnis in eine Datei. Der Filterzustand wird zwischen
#     den Blöcken gespeichert.

#     Parameters:
#     - input_file: Pfad zur Eingabedatei (komplexe Rohdaten im Binary-Format).
#     - output_file: Pfad zur Ausgabedatei (gefilterte Daten).
#     - fn: Mittenfrequenz des Notch-Filters (Hz).
#     - BN: Bandbreite des Notch-Filters (Hz).
#     - fs: Abtastrate des Signals (Hz).
#     - block_size: Anzahl der Samples pro Block (Standard: 1024).
#     """
#     # Entwerfen des Notch-Filters
#     b, a = design_notch_filter(fn, BN, fs)
    
#     # Initialisierung des Filterzustands (zi) für Real- und Imaginärteil
#     zi_real = lfilter_zi(b, a) * 0  # Nullinitialisierung
#     zi_imag = lfilter_zi(b, a) * 0

#     # Öffne die Input- und Output-Dateien im Binärmodus
#     with open(input_file, 'rb') as f_in, open(output_file, 'wb') as f_out:
#         while True:
#             # Blockweises Lesen der Daten
#             input_block = np.fromfile(f_in, dtype=np.complex64, count=block_size)
            
#             # Wenn keine Daten mehr vorhanden sind, beenden
#             if len(input_block) == 0:
#                 break

#             # Filtere den Datenblock und aktualisiere den Filterzustand
#             filtered_block, zi_real, zi_imag = process_block(input_block, b, a, zi_real, zi_imag)

#             # Schreibe den gefilterten Block in die Ausgabedatei
#             filtered_block.astype(np.complex64).tofile(f_out)

# # Beispielaufruf
# input_file = 'input_signal.dat'   # Pfad zur Eingabedatei
# output_file = 'filtered_signal.dat' # Pfad zur Ausgabedatei
# fs = 1000.0  # Abtastrate in Hz
# fn = 60.0    # Mittenfrequenz des Notch-Filters in Hz
# BN = 1.0     # Bandbreite des Notch-Filters in Hz
# block_size = 4096  # Größe der zu lesenden Blöcke

# notch_filter_file(input_file, output_file, fn, BN, fs, block_size)


    # def read_audio_stream(self,url, block_size_samples, sample_rate=44100, channels=2, dtype="float32"):
    #     # Berechne die Blockgröße in Bytes (pro Block)
    #     block_size_bytes = block_size_samples * channels * np.dtype(dtype).itemsize

    #     # ffmpeg-Befehl vorbereiten
    #     # ffmpeg_command =  "ffmpeg-master-latest-win64-gpl/bin/ffmpeg -y -i " + output_file +  " -c:a libmp3lame -qscale:a 2 " + true_tempfile
    #     self.m["user_agent"]
    #     ffmpeg_command = [
    #         self.m["ffmpeg_path"] + "ffmpeg",
    #         "-user_agent", self.m["user_agent"],
    #         "-i", url,
    #         "-f", "f32le",          # Rohformat: 32-Bit Float, Little Endian
    #         "-ac", str(channels),   # Kanäle
    #         "-ar", str(sample_rate),# Abtastrate
    #         "-"
    #     ]

    #     # ffmpeg-Prozess starten
    #     process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)

    #     try:
    #         while True:
    #             # Lese einen Block von Rohdaten
    #             raw_audio = process.stdout.read(block_size_bytes)

    #             # Überprüfen, ob der Stream endet
    #             if not raw_audio:
    #                 break

    #             # Konvertiere Rohdaten in ein NumPy-Array
    #             audio_block = np.frombuffer(raw_audio, dtype=dtype).reshape(-1, channels)

    #             # Hier kannst du mit dem Block weiterarbeiten (z. B. speichern, analysieren, etc.)
    #             yield audio_block
    #     finally:
    #         # Prozess sicher beenden
    #         process.terminate()
    #         process.wait()


################### CODE for reading audio blockwise from URL


    # def convert_to_mp3(input_file, output_file):
    #     audio = AudioSegment.from_file(input_file)
    #     audio.export(output_file, format="mp3", bitrate="192k")

################### CODE for determining Playlength from URL

# import subprocess
# import re

# def get_stream_duration(url):
#     # ffmpeg-Befehl, um die Metadaten der Datei auszulesen
#     ffmpeg_command = [
#         self.m["ffmpeg_path"],
#         "ffmpeg",
#         "-i", url,
#         "-hide_banner"  # Verbirgt unnötige Informationen
#     ]

#     # Prozess starten und Fehlerausgabe analysieren (da ffmpeg die Metadaten dort ausgibt)
#     process = subprocess.Popen(ffmpeg_command, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
#     stdout, stderr = process.communicate()

#     # Dauer aus der ffmpeg-Ausgabe extrahieren
#     match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", stderr.decode())
#     if match:
#         hours, minutes, seconds = map(float, match.groups())
#         return hours * 3600 + minutes * 60 + seconds  # Dauer in Sekunden
#     else:
#         return None  # Keine Dauer gefunden

# # Beispielaufruf
# stream_url = "https://example.com/audio.mp3"
# duration = get_stream_duration(stream_url)
# if duration:
#     print(f"Die Gesamtdauer beträgt: {duration:.2f} Sekunden")
# else:
#     print("Dauer konnte nicht ermittelt werden.")



###########Appendix SFBUF

                # with urllib.request.urlopen(request) as response:
                #     # write stream to local temp file and open with sf.Soundfile, return soundfile object 
                #     #output_file = "local_temp.aud"
                #     output_file = Path(file_path).stem + ".aud"
                #     ### only for pydub: ### 
                #     true_tempfile = Path(file_path).stem + ".mp3"
                #     ### only for pydub: ### 
                #     print(f"temporary output_file: {output_file}, true temp file: {true_tempfile}")
                #     #print(f"temporary output_file: {output_file}")
                #     if not os.path.isfile(output_file):
                #         with open(output_file, "wb") as f:
                #             if checkflag:
                #                 f.write(response.read(10000))
                #                 print(">>>>>>>>>>>>>>>>>>>> readsoundfile write short buffer file")
                #             else:
                #                 f.write(response.read())
                #                 ### only for pydub: ### self.convert_to_mp3(output_file, true_tempfile)
                #                 ### only for pydub: ### Path(output_file).unlink()
                #                egeg_command =  self.m["ffmpeg_path"] + "ffmpeg -user_agent " + self.m["user_agent"] + " -y -i " + output_file +  " -c:a libmp3lame -qscale:a 2 " + true_tempfile
                #                 subprocess.run(ffmpeg_command, check=True)
                #                 #Path(output_file).unlink()

    # def is_ffmpeg_installed(self):
    #     """check if ffmpeg is available on the system"""
    #     try:
    #         #check for global installation with PATH set in the OS
    #         subprocess.run("ffmpeg -version", stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    #         self.logger.debug(f"check for ffmpeg , installation found")
    #         self.m["ffmpeg_path"] = ""
    #         return True
    #     except FileNotFoundError:
    #         #check for local installation in ffmpeg standardpath of the COHIWIzard filesystem
    #         self.m["ffmpeg_path"] = os.path.join(os.getcwd(), "ffmpeg-master-latest-win64-gpl", "bin")
    #         #self.logger.debug(f"__init_ m check for ffmpeg_path: {self.mdl["ffmpeg_path"]}, file not found")
    #         try:
    #             subprocess.run(os.path.join(self.m["ffmpeg_path"],"ffmpeg") + " -version", stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    #             self.logger.debug(f"check for ffmpeg_path: {self.m["ffmpeg_path"]}, file found")
    #             return True
    #         except FileNotFoundError:
    #             self.logger.debug(f"check for ffmpeg_path: {self.m["ffmpeg_path"]}, file not found")
    #             return False
