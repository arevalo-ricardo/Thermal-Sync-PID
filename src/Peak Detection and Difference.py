import pandas as pd
import numpy as np
from scipy.signal import find_peaks
import matplotlib.pyplot as plt
import matplotlib as mpl
import matplotlib.animation as animation
import seaborn as sns

df = pd.read_csv('C:/Cristian Hernandez/Python Code for Two-Room/Tests/TC_Temp_Reader_2025-11-08_07-29-42.csv') # CHANGE TO FILE PATH AND NAME Average_Temp_2025-10-13_10-35-14  24hr_Test

#Setting the x-axis as time (hours)
#x = df.iloc[:,0] # For the peaks

start_time = 12
end_time = 24

subset_df = df[(df["Time (h)"] >= start_time) & (df["Time (h)"] <= end_time)]

# Room_1 = df["Room 1"]
# Room_2 = df["Room 2"]
# time_duration = df["Time (h)"]

sns.set_theme(style='whitegrid')

fig1, ax1 = plt.subplots()

norm = mpl.colors.Normalize(vmin = subset_df["Time (h)"].min(), vmax = subset_df["Time (h)"].max())
cmap= plt.cm.viridis
#colors = cmap(norm(time_duration))

sns.scatterplot(
    data = subset_df,
    x = "Room 1",
    y = "Room 2",
    hue = "Time (h)",
    palette = cmap,
    legend = False,
    s=60,
    ax = ax1
 )

# Colormap
sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
sm.set_array([])
cbar = fig1.colorbar(sm,ax = ax1)
cbar.set_label('Time (h)')

plt.title('Room 1 vs Room 2 Temperatures Over Time')
plt.xlabel('Room 1 Temperature  (\u00b0F)')
plt.ylabel('Room 2 Temperature (\u00b0F)')
plt.grid(True)
plt.tight_layout()

#-----------------------------------------------------------------------------------------------------------------------------

# # Find peaks
# peaks1, _ = find_peaks(Room_1, height=81.14, distance=100, prominence=1)
# peaks2, _ = find_peaks(Room_2, height=81.14, distance=100, prominence=1)

# # Plot Room Temperatures with Peaks
# fig, ax = plt.subplots()
# ax.plot(x, Room_1, label='Room 1', color='r')
# ax.plot(x.iloc[peaks1], Room_1.iloc[peaks1], 'x', label='Room 1 Peaks', color='r', markersize=8)
# ax.plot(x, Room_2, label='Room 2', color='b')
# ax.plot(x.iloc[peaks2], Room_2.iloc[peaks2], 'x', label='Room 2 Peaks', color='b', markersize=8)

# ax.set_title('Average Room Temperatures with Peaks')
# ax.set_xlabel('Time (Hours)')
# ax.set_ylabel('Temperature (\u00b0F)')
# ax.grid(True)
# ax.legend()

#-------------------------------------------------------------------------------------------------
# Creating Animation/GIF of data 
# fig, ax = plt.subplots()
# sc = ax.scatter([], [], s=60, c=[], cmap=cmap, vmin=norm.vmin, vmax=norm.vmax)
# ax.set_xlim(subset_df["Room 1"].min() - 1, subset_df["Room 1"].max() + 1)
# ax.set_ylim(subset_df["Room 2"].min() - 1, subset_df["Room 2"].max() + 1)
# ax.set_title('Room 1 vs Room 2 Temperatures Over Time')
# ax.set_xlabel('Room 1 Temperature (F)')
# ax.set_ylabel('Room 2 Temperature (F)')

# sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
# sm.set_array([])
# cbar = fig.colorbar(sm, ax=ax)
# cbar.set_label('Time (h)')

# def init():
#     sc.set_offsets(np.empty((0,2)))
#     sc.set_array([])
#     return sc,

# def update(frame):
#     data = subset_df.iloc[:frame+1]
#     coords = np.atleast_2d(data[["Room 1", "Room 2"]].to_numpy())
#     sc.set_offsets(coords)
#     sc.set_array(data["Time (h)"].to_numpy())
#     return sc,

# ani = animation.FuncAnimation(fig, update, frames=len(subset_df),init_func=init, blit=True, interval=5)
# # Saving GIF can take some time to run
# ani.save("RoomTemp.gif", writer = 'pillow',fps=15) # Use file path for folder to save in
#plt.tight_layout()
#--------------------------------------------------------------------------------------------------

plt.show()
#plt.close(fig) # Only needed for the animation section 
