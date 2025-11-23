import numpy as np
from scipy.io.wavfile import write

def make_sound(filename, freq, duration=0.15, volume=0.5):
    sample_rate = 44100
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    wave = np.sin(freq * t * 2 * np.pi)
    audio = wave * (2**15 - 1) * volume
    audio = audio.astype(np.int16)
    write(filename, sample_rate, audio)
    print(f"{filename} created.")

# Shoot sound (laser)
make_sound("shoot.wav", freq=800)

# Explosion sound (low rumble + distortion)
def make_explosion(filename):
    sample_rate = 44100
    duration = 0.4
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    noise = np.random.normal(0, 1, t.shape)
    wave = noise * np.exp(-5 * t)  # fade out
    audio = wave * (2**15 - 1) * 0.7
    audio = audio.astype(np.int16)
    write(filename, sample_rate, audio)
    print(f"{filename} created.")

make_explosion("explosion.wav")
