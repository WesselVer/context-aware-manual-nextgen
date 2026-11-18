"""The sound of the car: a sporty electric drive tone, with road and wind noise.

CARLA's own car sound comes from the server and stutters when the server is
late, so the server runs with -nosound and the sound is made here instead.
Everything is generated at the start as seamless loops, which SDL's audio
thread plays by itself. The drive only changes their volumes, so a late frame
or a stalled server can't interrupt the sound: it holds until the next update.

The drive tone is present without being harsh: a warm low voice, the same an
octave up, and a faint third voice, all rising with the speed, growing with the
load and with a more dynamic drive mode. A loop can't change pitch, so each
voice fades along a row of narrow bands of noise, a little higher each, all
playing at once: the two nearest its pitch are heard, which makes it glide.

The dashboard's chimes matter more than the car: duck() turns the car down
while one sounds.
"""

import math
import time

import numpy as np
import pygame

RATE = 44100
# Samples of audio SDL keeps ahead: 46 ms.
BUFFER = 2048

# The low voice's pitch: Hz at standstill, and Hz more per m/s (about 305 Hz at
# 100 km/h). The voices are this pitch times VOICES' ratio, each with its volume
# with no load and at full load.
TONE_HZ = 55.0
TONE_HZ_PER_MS = 9.0
VOICES = [(1.0, 0.07, 0.17), (2.0, 0.025, 0.10), (3.0, 0.0, 0.035)]
# The bands, from TONE_HZ up: the step from one to the next, how many, and each
# one's width as a share of its pitch.
BAND_RATIO = 1.06
BANDS = 60
BAND_WIDTH = 0.018
# How much of the tone each drive mode gets.
MODE_TONE = {'Eco': 0.7, 'Normal': 1.0, 'Dynamic': 1.3}

# Volumes, 0 to 1: the standing hum; road and wind at REFERENCE_MS (100 km/h),
# each with the most it may reach.
HUM = 0.035
ROAD = 0.28
ROAD_MAX = 0.40
WIND = 0.06
WIND_MAX = 0.14
REFERENCE_MS = 27.8
# Seconds the speed and the load take to be followed. A frame longer than
# MAX_STEP counts as MAX_STEP, so the sound glides after a stall, not jumps.
SPEED_LAG = 0.08
LOAD_LAG = 0.15
MAX_STEP = 0.05
# Under a dashboard chime: the share of the volume left, for how long (s), and
# how fast it goes down and comes back (s).
DUCK_LEVEL = 0.45
DUCK_SECONDS = 1.6
DUCK_DOWN = 0.05
DUCK_UP = 0.4


def _loop(seconds, power, seed, modulate=None):
    """A stereo loop of noise with this power spectrum. Made in the frequency
    domain, so its end runs exactly into its start."""
    n = int(RATE * seconds)
    freq = np.fft.rfftfreq(n, 1.0 / RATE)
    channels = []
    for side in range(2):
        rng = np.random.default_rng(seed + side)
        spectrum = np.sqrt(power(freq)) * np.exp(2j * np.pi * rng.random(freq.size))
        spectrum[0] = 0.0
        samples = np.fft.irfft(spectrum, n)
        if modulate is not None:
            samples *= modulate(np.arange(n) / n)
        channels.append(samples)
    samples = np.stack(channels, axis=1)
    samples /= np.abs(samples).max()
    return pygame.mixer.Sound(buffer=(samples * 32000).astype(np.int16).tobytes())


def _peak(freq, centre, width):
    return np.exp(-0.5 * ((freq - centre) / width) ** 2)


def _hum(freq):
    return _peak(freq, 100, 1.5) + 0.4 * _peak(freq, 200, 2.0) + 0.1 * _peak(freq, 300, 3.0)


def _road(freq):
    return 1.0 / (1.0 + (freq / 250.0) ** 2) / (1.0 + (35.0 / (freq + 1.0)) ** 4)


def _wind(freq):
    return 1.0 / (1.0 + (freq / 1000.0) ** 4) / (1.0 + (250.0 / (freq + 1.0)) ** 2)


def _gusts(t):
    # Whole numbers of cycles, so the loop stays seamless.
    return 1.0 + 0.10 * np.sin(2 * np.pi * t + 1.0) + 0.06 * np.sin(2 * np.pi * 3 * t)


def _band(centre):
    def power(freq):
        return _peak(freq, centre, max(1.0, BAND_WIDTH * centre))
    return power


class CarSound(object):
    """Plays the car's sound; update() every frame."""

    @staticmethod
    def prepare():
        """Before pygame.init(), which opens the audio device."""
        pygame.mixer.pre_init(RATE, -16, 2, BUFFER)

    def __init__(self, volume=1.0):
        self._volume = volume
        self._speed = 0.0
        self._load = 0.0
        self._duck = 1.0
        self._duck_until = 0.0
        self._last = time.monotonic()
        self._band_volumes = [0.0] * BANDS
        pygame.mixer.pause()
        pygame.mixer.set_num_channels(BANDS + 3)
        self._hum = self._start(0, _loop(6.0, _hum, 10))
        self._road = self._start(1, _loop(6.0, _road, 20))
        self._wind = self._start(2, _loop(6.0, _wind, 30, _gusts))
        self._bands = [self._start(3 + i, _loop(3.0, _band(TONE_HZ * BAND_RATIO ** i), 40 + 2 * i))
                       for i in range(BANDS)]
        pygame.mixer.unpause()

    @staticmethod
    def _start(index, sound):
        channel = pygame.mixer.Channel(index)
        channel.play(sound, loops=-1)
        channel.set_volume(0.0)
        return channel

    def duck(self):
        """A dashboard chime is sounding: the car steps back for a moment."""
        self._duck_until = time.monotonic() + DUCK_SECONDS

    def update(self, speed, control, mode='Normal'):
        """speed in m/s, control the car's carla.VehicleControl, mode the drive mode's name."""
        now = time.monotonic()
        step = min(now - self._last, MAX_STEP)
        self._last = now
        load = max(control.throttle, min(1.0, 2.0 * control.brake))
        self._speed += (abs(speed) - self._speed) * (1.0 - math.exp(-step / SPEED_LAG))
        self._load += (load - self._load) * (1.0 - math.exp(-step / LOAD_LAG))
        ducked = now < self._duck_until
        lag = DUCK_DOWN if ducked else DUCK_UP
        self._duck += ((DUCK_LEVEL if ducked else 1.0) - self._duck) * (1.0 - math.exp(-step / lag))
        volume = self._volume * self._duck

        share = self._speed / REFERENCE_MS
        self._hum.set_volume(volume * HUM)
        self._road.set_volume(volume * min(ROAD_MAX, ROAD * share ** 1.3))
        self._wind.set_volume(volume * min(WIND_MAX, WIND * share ** 2.4))

        wanted = [0.0] * BANDS
        pitch = TONE_HZ + TONE_HZ_PER_MS * self._speed
        # It comes in as the car starts to roll.
        rolling = min(1.0, max(0.0, (self._speed - 0.5) / 3.5))
        for ratio, idle, full in VOICES:
            place = math.log(pitch * ratio / TONE_HZ) / math.log(BAND_RATIO)
            if place >= BANDS - 1:
                continue
            low = int(place)
            fade = place - low
            level = (volume * rolling * MODE_TONE.get(mode, 1.0) * (idle + (full - idle) * self._load))
            wanted[low] += level * math.cos(fade * math.pi / 2)
            wanted[low + 1] += level * math.sin(fade * math.pi / 2)
        for i, level in enumerate(wanted):
            if level != self._band_volumes[i]:
                self._bands[i].set_volume(min(1.0, level))
                self._band_volumes[i] = level

    def close(self):
        pygame.mixer.fadeout(250)
