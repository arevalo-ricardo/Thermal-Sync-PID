# Standard deviation and median 
import pandas as pd
import matplotlib.pyplot as plt


df = pd.read_csv("C:/Cristian Hernandez/Python Code for Two-Room/Tests/TC_Temp_Reader_2025-12-05_15-32-40.csv")  

time = df['Time (h)']
room_1 = df[['Channel 0', 'Channel 1', 'Channel 16', 'Channel 17', 'Channel 30','Channel 31']]
room_2 = df[['Channel 2', 'Channel 5', 'Channel 18', 'Channel 20', 'Channel 27','Channel 29']]
avg_room_1 = df['Room 1']
avg_room_2 = df['Room 2']

# Room 1 median and Standard deviation
median_1 = room_1.median(axis = 1)
std_1 = room_1.std(axis =1)
# Room 2 median and Standard deviation
median_2 = room_2.median(axis = 1)
std_2 = room_2.std(axis =1)
plt.figure()

# Room 1
plt.plot(time, median_1, color='red', linestyle='--', label='Room 1 Median')
plt.fill_between(time, median_1 - std_1, median_1 + std_1, color='red', alpha=0.2, label='Room 1 ±1 SD')
plt.plot(time, avg_room_1, color='red', label= "Room 1 Average")

# Room 2
plt.plot(time, median_2, color='blue', linestyle='--', label='Room 2 Median')
plt.fill_between(time, median_2 - std_2, median_2 + std_2, color='blue', alpha=0.2, label='Room 2 ±1 SD')
plt.plot(time, avg_room_2, color='blue', label= "Room 2 Average")


plt.xlabel('Time')
plt.ylabel('Temperature (F)')
plt.title('Average, Median, and STD Temperature Across Rooms Over Time')
plt.legend()
plt.grid(True)
plt.show()
