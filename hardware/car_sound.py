"""The sound of the car: a quiet electric motor, with road and wind noise.

CARLA's own car sound comes from the server and stutters when the server is
late, so the server runs with -nosound and the sound is made here instead.
Everything is generated at the start as seamless loops, which SDL's audio
thread plays by itself. The drive only changes their volumes, so a late frame
or a stalled server can't interrupt the sound: it holds until the next update.

A loop can't change pitch, so the motor's whine is a row of narrow bands of
noise, each a little higher than the last, all playing at once; the two nearest
the motor's pitch are heard, and fading from one pair to the next makes it glide.
"""

import math
import time

import numpy as np
import pygame

RATE = 44100
# Samples of audio SDL keeps ahead: 46 ms.
BUFFER = 2048

# The whine's pitch: Hz at standstill, and Hz more per m/s.
WHINE_HZ = 110.0
WHINE_HZ_PER_MS = 28.0
# The bands, from WHINE_HZ up: the step from one to the next, how many, and
# each one's width as a share of its pitch.
BAND_RATIO = 1.12
BANDS = 31
BAND_WIDTH = 0.03

# Volumes, 0 to 1: the standing hum; the whine at full load; road and wind at
# REFERENCE_MS (100 km/h), each with the most it may reach.
HUM = 0.06
WHINE = 0.20
ROAD = 0.45
ROAD_MAX = 0.60
WIND = 0.09
WIND_MAX = 0.20
REFERENCE_MS = 27.8
# Seconds the speed and the load take to be followed. A frame longer than
# MAX_STEP counts as MAX_STEP, so the sound glides after a stall, not jumps.
SPEED_LAG = 0.08
LOAD_LAG = 0.15
MAX_STEP = 0.05


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
        width = BAND_WIDTH * centre
        return _peak(freq, centre, width) + 0.08 * _peak(freq, 2 * centre, 2 * width)
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
        self._last = time.monotonic()
        pygame.mixer.pause()
        pygame.mixer.set_num_channels(BANDS + 3)
        self._hum = self._start(0, _loop(6.0, _hum, 10))
        self._road = self._start(1, _loop(6.0, _road, 20))
        self._wind = self._start(2, _loop(6.0, _wind, 30, _gusts))
        self._bands = [self._start(3 + i, _loop(3.0, _band(WHINE_HZ * BAND_RATIO ** i), 40 + 2 * i))
                       for i in range(BANDS)]
        pygame.mixer.unpause()

    @staticmethod
    def _start(index, sound):
        channel = pygame.mixer.Channel(index)
        channel.play(sound, loops=-1)
        channel.set_volume(0.0)
        return channel

    def update(self, speed, control):
        """speed in m/s, control the car's carla.VehicleControl."""
        now = time.monotonic()
        step = min(now - self._last, MAX_STEP)
        self._last = now
        load = max(control.throttle, min(1.0, 2.0 * control.brake))
        self._speed += (abs(speed) - self._speed) * (1.0 - math.exp(-step / SPEED_LAG))
        self._load += (load - self._load) * (1.0 - math.exp(-step / LOAD_LAG))

        share = self._speed / REFERENCE_MS
        self._hum.set_volume(self._volume * HUM)
        self._road.set_volume(self._volume * min(ROAD_MAX, ROAD * share ** 1.3))
        self._wind.set_volume(self._volume * min(WIND_MAX, WIND * share ** 2.4))

        pitch = WHINE_HZ + WHINE_HZ_PER_MS * self._speed
        place = min(BANDS - 1.001, math.log(pitch / WHINE_HZ) / math.log(BAND_RATIO))
        low = int(place)
        fade = place - low
        # It comes in as the car starts to roll, and softens as it gets high.
        level = (self._volume * WHINE * (0.35 + 0.65 * self._load)
                 * min(1.0, max(0.0, (self._speed - 0.5) / 3.5))
                 / math.sqrt(1.0 + (pitch / 2500.0) ** 2))
        for i, channel in enumerate(self._bands):
            if i == low:
                channel.set_volume(level * math.cos(fade * math.pi / 2))
            elif i == low + 1:
                channel.set_volume(level * math.sin(fade * math.pi / 2))
            elif channel.get_volume() > 0.0:
                channel.set_volume(0.0)

    def close(self):
        pygame.mixer.fadeout(250)
