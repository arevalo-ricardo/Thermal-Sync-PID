'Short Time Fourier Transform for Two Room system'
import pandas as pd
import numpy as np
from scipy.signal import ShortTimeFFT
from scipy.signal import stft
from scipy.signal.windows import hann
import matplotlib.pyplot as plt

df = pd.read_csv('C:/Cristian Hernandez/Python Code for Two-Room/Tests/TC_Temp_Reader_2026-02-21_08-51-46.csv') # CHANGE TO FILE PATH AND NAME Average_Temp_2025-10-13_10-35-14  24hr_Test

#Setting the time I want to see 
start_time = 24
end_time = 31

subset_df = df[(df["Time (h)"] >= start_time) & (df["Time (h)"] <= end_time)]

Room_1 = subset_df["Room 1"].values
Room_2 = subset_df["Room 2"].values
times = subset_df["Time (h)"].values

# The sampling changes everytime because the temperature code has to process the commands and send out the Smart Plug info,
# so the bottom two lines calculates the sampling rate for each csv file.
dt = np.mean(np.diff(times))
fs_real = 1 / (dt*3600)  
#print(fs_real)

#fs = 1  # Sampling frequency (Sampled every second in the test)
win_len = int(0.33*3600*fs_real)  # 20 min window length
hop = win_len // 8 # might need to change to 8 since we have small oscillations
hann_window = hann(win_len)

stft_temp = ShortTimeFFT(
    win = hann_window, 
    fs=fs_real,
    hop = hop
)

# Detrend (1-hour moving average)
def moving_average(x, win):
    return np.convolve(x, np.ones(win) / win, mode='same')

trend_win = min(int(1*3600*fs_real),len(Room_1) //2 )  # 1 hour

Room_1_d = Room_1 - moving_average(Room_1, trend_win)
Room_2_d = Room_2 - moving_average(Room_2, trend_win)

# Performing the STFT
sx1 = stft_temp.stft(Room_1_d)
sx2 = stft_temp.stft(Room_2_d)

# Setting the frequency for the y axis in cycles per hour and Time (x-axis)
freq = stft_temp.f * 3600  # cycles per hour
num_frames = sx1.shape[1]
#frame_centers = np.arange(num_frames) * hop + win_len // 2
time_stft = stft_temp.t(len(Room_1_d)) / 3600 + start_time #frame_centers / (3600* fs_real) + start_time

# Frequency band of interest
fmin, fmax = 0.5, 8.0  # cycles/hour (helps see 7.5 -2 hour periods)
freq_mask = (freq >= fmin) & (freq <= fmax)

S1 = 20 * np.log10(np.abs(sx1) / win_len + 1e-12) # Converting to dB 
S2 = 20 * np.log10(np.abs(sx2) / win_len + 1e-12)

#Debug
# print("Min time:", times.min())
# print("Max time:", times.max())
# print("Number of samples:", len(times))
# print("Computed frames:", num_frames)
# print(times[0])
# print(start_time)
# print(time_stft[0], time_stft[-1])

plt.figure(figsize=(12, 5))

plt.subplot(1, 2, 1)
plt.pcolormesh(time_stft, freq[freq_mask], S1[freq_mask, :], shading='gouraud', cmap='jet',vmin = -40,vmax=0)
plt.title("Short-Time Fourier Transform - Room 1")
plt.xlabel("Time (Hours)")
plt.ylabel("Frequency (Cycles/Hour)")
plt.colorbar(label="Spectral Magnitude (dB)")

plt.subplot(1, 2, 2)
plt.pcolormesh(time_stft, freq[freq_mask], S2[freq_mask, :], shading='gouraud', cmap='jet',vmin = -40,vmax=0)
plt.title("Short-Time Fourier Transform - Room 2")
plt.xlabel("Time (Hours)")
plt.ylabel("Frequency (Cycles/Hour)")
plt.colorbar(label="Spectral Magnitude (dB)")

plt.tight_layout()
plt.show()
