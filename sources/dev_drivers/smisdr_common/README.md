# smisdr drivers (smiSDR / parlioSDR)

Four **playback** drivers for [smiSDR / parlioSDR](https://github.com/radiolab81/smisdr) (https://github.com/radiolab81/parlioSDR), ported from the
hardware-tested backends of COHI-Player-Universal (GPL-3.0, Claus Peter Gallenmiller / radiolab81):

| driver                 | signal | wire format | listed in modes |
|------------------------|--------|-------------|-----------------|
| `smisdr_iq`            | IQ file | baseband I/Q, 14 bit, tagged 16 bit words with in-band signalling (`S` NCO shift, `R` input rate); FPGA (DUC) converts to RF | band only |
| `smisdr_raw`           | IQ file | finished RF samples (8 bit, 8-in-16, 10/12/14 bit), 5 / 10 / 12.5 MSps; host converts with `cohi_native_upconverter` | band only |
| `smisdr_iq_universal`  | IQ file **and / or live stations** | as `smisdr_iq` | band and audio, audio only |
| `smisdr_raw_universal` | IQ file **and / or live stations** | as `smisdr_raw` | band and audio, audio only |

Network devices: the IP address field of the Player tab is used. `smisdr_common/` holds the shared
code and is not a driver itself (no `cohi_playrecworker.py`).

## Live mode (`*_universal`)

The live drivers use **the signal chain of `stemlab_universal`** (their worker is a subclass of it):
ffmpeg per station -> UDP -> `libdspflmod` NCO engine -> mixer -> float32 I/Q. Station lists (csv /
extended m3u), modulation depth, mix level, the mixer slider, AGC and the modes *band and audio* /
*audio only* therefore behave exactly as with `stemlab_universal`; only the destination is the smiSDR
output stage (`sinks.py`) instead of the STEMLAB socket. Consequences:

* needs `ffmpeg` and `libdspflmod` as the other universal drivers (note: the shipped `libdspflmod`
  is linked against `libosmo-fl2k`, so that library must be installed even though no FL2K is used)
* in *audio only* mode the LO and the sample rate come from the fields of the recorder tab, like with
  the other universal drivers. The carriers must lie inside `centre +- rate/2`; for `smisdr_iq_universal`
  the rate must be 250 k, 500 k or 1.25 M
* IQ file + stations: all files of a chain must have the same centre frequency and sample rate (the
  carriers are fixed to the first file) - otherwise the chain is stopped with a message. Without
  stations (*band only*) such chains are fine, the device is reconfigured per file
* supported file formats: 16 bit PCM and 32 bit float (what the inherited worker reads correctly);
  `smisdr_iq` / `smisdr_raw` additionally play 24 bit and 32 bit PCM
* the drivers report `RX: true` (like `stemlab_universal`) so that the recorder-tab fields stay
  editable; recording itself is refused with a message
* before the first block and when nothing is sent for 0.3 s (pause, start of the station streams) the
  output stage sends silence, so that DAC / DUC never hold the last value (an unmodulated carrier)
* the log lines of the inherited code say `[stemlab_universal]`

## Settings (`config_wizard.yaml`, all optional)

```yaml
smisdr_data_port: 1234            # TCP data port
smisdr_control_port: 5000         # TCP control port; 0 / off: nothing is sent to it
smisdr_iq_ref_clock: 50000000     # *_iq*: DUC reference clock (limits the usable frequency)
smisdr_sample_rate: auto          # *_raw*: 5 | 10 | 12.5 (MSps) | auto (needs the control port)
smisdr_format: 8                  # *_raw*: 8 | 816 (8 bit in 16 bit) | 10 | 12 | 14
smisdr_offset: false              # *_raw*, format 8: unsigned 8 bit (DC offset +128)
smisdr_upconverter_path: ""       # *_raw*: default = smisdr_common/upconverter/ or PATH
smisdr_limiter: true              # peak limiter in front of the DAC stage (see below)
smisdr_mode_switch: true          # parlioSDR: switch the mode on the control port (see below)
smisdr_iq_dsp: auto               # *_iq*: auto | soft | fpga (see below)
smisdr_duc_commands: []           # *_iq*: extra soft-DUC settings, e.g.
                                  #   ["duc width 8", "duc offset on", "duc gain auto"]
```
Invalid values are reported with the key name in the usual error box. The audio settings of the live
drivers (`audioplaylist`, `audio_mod_index`, `ffmpeg_path` ...) are those of `stemlab_universal`.

## parlioSDR: operating mode on the control port

parlioSDR (ESP32-P4) has two modes, switched on port 5000 (see its README): `mode duc` - the ESP32
mixes the I/Q stream up in software and replaces the FPGA - and `mode raw` - the stream is passed 1:1
to the DAC (finished RF samples, or I/Q with in-band signalling for a real FPGA behind the ESP32).
The drivers ask `mode` first and switch **before** the data connection is opened (a switch ends a
running data connection):

| driver / setting | device in `raw` | device in `duc` | device without modes (smiSDR on a Pi) |
|---|---|---|---|
| `smisdr_iq*`, `smisdr_iq_dsp: auto` (default) | `mode duc`, no width / rate, `smisdr_duc_commands` | as is, `smisdr_duc_commands` | `width 16`, `rate` as before |
| `smisdr_iq*`, `soft` | as `auto` | as `auto` | **error** (no software DUC) |
| `smisdr_iq*`, `fpga` | `width 16`, `rate` (in-band signalling goes to the FPGA) | `mode raw`, then `width 16`, `rate` | as before |
| `smisdr_raw*` | `width`, `rate` | `mode raw` (waits up to 6 s for the answer), then `width`, `rate` | as before |

`smisdr_mode_switch: false` switches all of this off. DAC width, offset and gain of the soft DUC are
settings of the ESP32 (`duc width 8|16`, `duc offset on|off`, `duc gain auto|<x>`); they persist there, or
are sent with every start through `smisdr_duc_commands`. Everything but `duc gain` takes effect with the
next data connection - which is why they are sent before it.

## Level: the peak limiter

COHIWizard's AVC regulates the gain until its volume figure (`1.5 * std(|x|) / 0.71`) reaches the target
0.9. For a typical band signal that is 10-14 dB **above** digital full scale: with a simulated MW band the
steady state had peaks of 4.8 x full scale and 24 % of the samples clipped (a single AM carrier: up to
65 %). Hard clipping at the 14 bit word (or at the DAC) destroys the signal although the stream looks fine
at the device. A slow peak limiter therefore sits in front of both output stages: a block whose peak would
exceed the ceiling is scaled down at once (faded over 128 pairs), the gain returns by 1.0 per second, and
`smisdr_limiter: false` turns it off. Ceiling: +-1.0 per component for `*_iq*`; for `*_raw*` the magnitude
|I+jQ| is limited to 0.24, because `cohi_native_upconverter` reaches the DAC full scale (127 at 8 bit,
2^(n-1)-1 at 10/12/14 bit) at an input magnitude of 0.25 (measured; this is why the player uses a gain
of 0.4). The log shows the level every 5 s (`peak .. % of full scale, .. samples clipped`, and by how
many dB the limiter acted); more than 0.1 % clipped samples is a warning.
With the soft DUC the ESP32 has its own AGC (target 50 % peak), the I/Q words are 14 bit two's
complement (the DUC scales them back to 16 bit).

## Behaviour of the file players (`smisdr_iq`, `smisdr_raw`)

* Input: 2-channel I/Q wav, 16 / 24 bit PCM, 32 bit PCM or 32 bit float; the centre frequency of every
  file comes from its `auxi` / `rcvr` header, so nextfile chains with changing parameters work.
* `smisdr_iq`: only 250 k, 500 k and 1.25 MSps (what the gateware supports) - use the Resample tab
  for other rates. Output is paced to the I/Q rate; files with identical parameters play gapless
  on one connection, otherwise the device is reconfigured (control commands + new connection + `S`/`R`).
* `smisdr_raw`: any input rate up to the output rate; the tool paces the output itself.
* The ppm correction (`icorr`) is applied to the centre frequency as in the STEMLAB driver.
* Pause sends silence; stop and end of play leave the output at zero.

## Changes outside the new directories

* `player/playrec.py`: (1) `device_boots_server()` - drivers that put `"server_boot": False` in
  `identify()` skip the 5 s server-boot wait and the startup notice; (2) the audio-only filters accept
  every `*_universal` driver instead of a list of three names (identical result for the existing ones).
* `cohi_setup.py`: manifest entries for the four drivers; keys `also_dirs` (shared code), `requires`
  (the live drivers install `stemlab_universal` with them) and `build_tool` (the up-conversion tool is
  built with `make` on Linux, again after an update; on Windows the user gets a hint).

## Build of the up-conversion tool (smisdr_raw, smisdr_raw_universal)

```
cd dev_drivers/smisdr_common/upconverter && make     # Linux; Windows (MSYS2): make EXE=.exe
```
`-march=native` binaries run only on the CPU model they were built on (`make MARCH=` for a portable one).

## Tests

```
cd sources && python -m unittest discover -s tests -t . -v
```
No hardware or PyQt5 needed (fake smiSDR / parlioSDR on localhost, Qt stand-in if PyQt5 is missing). The
raw tests compile the real upconverter; the live tests run the real chain (ffmpeg, `libdspflmod` built from
its source with a stand-in for the fl2k header, mixer) and check the spectrum of the output: station carrier
at the right frequency with AM sidebands, file tone, silence on pause, clean stop without leftover processes.
The fake parlioSDR answers `mode` / `duc ...` like `main.c` and ends the data connection on a mode change.
Tests are skipped without g++ / ffmpeg.

Optional, with the sources of the two other projects:

* `COHI_PLAYER_SRC=<COHI-Player-Universal>/sources` compares the wire format byte for byte with the
  original implementation.
* `PARLIOSDR_SRC=<parlioSDR>/main` builds `tests/firmware_duc_sim.c` against `duc_proto.c`, `sdr_plan.c` and
  `sdr_dsp.c` of the firmware and runs the stream the driver recorded through the firmware's parser,
  planner and DSP on the host: no dropped / bad words, rate and shift as sent, every I/Q pair arrived, the RF
  carrier at the exact frequency, and the overdriven stream is clean only with the limiter.


