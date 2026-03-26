"""
File:                       TC Temperature Reader.py
Library Call Demonstrated:  mcculw.ul.t_in()
Purpose:                    Reads multiple temperature input channels.
Demonstration:              Displays the temperature input.
Other Library Calls:        mcculw.ul.release_daq_device()
"""
from __future__ import absolute_import, division, print_function
from builtins import *  # @UnusedWildImport

import asyncio
from kasa import Discover
import smtplib
from email.mime.text import MIMEText
import time
import serial
import csv
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from mcculw import ul
from mcculw.enums import TempScale
from mcculw.device_info import DaqDeviceInfo

try:
    from console_examples_util import config_first_detected_device
except ImportError:
    from .console_examples_util import config_first_detected_device


async def Two_Room_Thermo_Sync():
    # By default, the example detects and displays all available devices and
    # selects the first device listed. Use the dev_id_list variable to filter
    # detected devices by device ID (see UL documentation for device IDs).
    # If use_device_detection is set to False, the board_num variable needs to
    # match the desired board number configured with Instacal. (This comes from the MCC Example code)
    use_device_detection = True
    dev_id_list = []
    board_num = 0

    plug_rm1 = await Discover.discover_single("10.42.0.87")  # replace with your plug's IP 
    plug_rm2 = await Discover.discover_single("10.42.0.252")
    
    arduino = serial.Serial('COM3',9600, timeout=1) # Arduino serial communication 
    await asyncio.sleep(2)

    try:
        if use_device_detection:
            config_first_detected_device(board_num, dev_id_list) # checks for device

        daq_dev_info = DaqDeviceInfo(board_num)

        print('\nActive DAQ device: ', daq_dev_info.product_name, ' (',
              daq_dev_info.unique_id, ')\n', sep='')

        ai_info = daq_dev_info.get_ai_info()
        if ai_info.num_temp_chans <= 0:
            raise Exception('Error: The DAQ device does not support '
                            'temperature input')
        
        
        #channels = list(range(64)) # For future use when 50 channels are used
        # Heaters
        heater1 = False
        heater2 = False
        channels = [0,1,2,5,16,17,18,20,27,29,30,31,44,47,52] # NOTE: can't have open TCs, so insert each channel individually
        room1_chs = [0,1,16,17,30,31]
        room2_chs = [2,5,18,20,27,29]

        samples = 1 # seconds
        total_time = 216500 # seconds ( Still need to convert to hours), see line 134 (60 Hours)
        readings = total_time // samples

        # Lists to store time and temperatures
        timestamps = []
        temperatures = {channel: [] for channel in channels}

        avg_timestamps = []
        avg_rm1_temps = []
        avg_rm2_temps = []

        # To prevent frequent email alerts per channel
        last_alert_time = {ch: 0 for ch in channels}
        alert_cooldown = 150  # seconds (2.5 minutes)

        # Heater states
        heater1_state = []
        heater2_state = []

        # store energy consumption
        energy_consumption1 = []
        current_consumption1 = []
        current1 = []
        voltage1 = []

        energy_consumption2 = []
        current_consumption2 = []
        current2 = []
        voltage2 = []
 
        # Calibration time of TCs. (30 minutes)
        calibration = 1800 #(30 minutes in seconds)
        heater_control = False

        start_time = time.time()
        last_save_time = 0
        last_save_idx = 0

        # Creating CSV file 
        timestamp_save = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"C:/Cristian Hernandez/Python Code for Two-Room/Tests/TC_Temp_Reader_{timestamp_save}.csv" 
        state_filename = f"C:/Cristian Hernandez/Python Code for Two-Room/Tests/Heater_States_{timestamp_save}.csv"
        energy_filename = f"C:/Cristian Hernandez/Python Code for Two-Room/Tests/Energy_Consumption_{timestamp_save}.csv"
        Avg_Temp_filename = f"C:/Cristian Hernandez/Python Code for Two-Room/Tests/Average_Temp_{timestamp_save}.csv"

        #Headers for files
        with open(filename,'w', newline='') as f:
            csv.writer(f).writerow(["Time (h)"] + [f"Channel {ch}" for ch in channels])
        with open(state_filename, 'w', newline='') as f:
            csv.writer(f).writerow(["Time (h)", "Heater 1", "Heater 2"])
        with open(energy_filename, 'w', newline='') as f:
            csv.writer(f).writerow(["Time (h)", "Total Energy 1 (kWh)", "Current Consumption 1 (W)", "Current 1 (A)", "Voltage 1 (V)", "Total Energy 2 (kWh)", "Current Consumption 2 (W)", "Current 2 (A)", "Voltage 2 (V)"])
        with open(Avg_Temp_filename, 'w', newline='') as f:
            csv.writer(f).writerow(["Time (h)", "Room 1", "Room 2"])

        #Set up for Temperature graph
        plt.ion()
        fig, ax = plt.subplots()
        lines = {}
        #colormap = cm.get_cmap('tab20', 12) # Need to change amout of colors for 64 channels later
        #colors = [colormap(i) for i in range(12)] # Need to change range later
        colors = ['b','g','r','c','m','y','k','orange','brown','hotpink','dodgerblue','olive','gold','goldenrod','peru']
        # Setup for each channel to be plotted
        for idx, ch in enumerate(channels):
            line, = ax.plot([], [], label=f"Channel {ch}", color=colors[idx])
            lines[ch] = line

        ax.set_title("Temperatures of Two-Room (Bang-Bang Controller) (\u00b0F)")
        ax.set_xlabel("Time (Hours)")
        ax.set_ylabel("Temperature (\u00b0F)")
        ax.grid(True)
        ax.legend()

        # Set up for Heater State Plot
        fig_heaters, (ax_heater1, ax_heater2) = plt.subplots(2,1)
        line_heater1, = ax_heater1.plot([],[], label="Heater 1", color = 'r')
        line_heater2, = ax_heater2.plot([],[], label="Heater 2", color = 'b')

        ax_heater1.set_title("Heater 1 State Over Time")
        ax_heater1.set_xlabel("Time (Hours)")
        ax_heater1.set_ylabel("Heater State")
        ax_heater1.grid(True)
        ax_heater1.legend()

        ax_heater2.set_title("Heater 2 State Over Time")
        ax_heater2.set_xlabel("Time (Hours)")
        ax_heater2.set_ylabel("Heater State")
        ax_heater2.grid(True)
        ax_heater2.legend()

        # Energy consumption plot
        fig_energy, ax_energy = plt.subplots()
        line_energy1, = ax_energy.plot([], [], label="Plug 1 (Room 2) Total Energy (kWh)", color='purple')
        line_energy2, = ax_energy.plot([], [], label="Plug 2 (Room 1) Total Energy (kWh)", color='orange')
        ax_energy.set_title("Total Energy Consumption Over Time")
        ax_energy.set_xlabel("Time (Hours)")
        ax_energy.set_ylabel("Energy (kWh)")
        ax_energy.grid(True)
        ax_energy.legend()

        # Avg Room Temp plot
        fig_avg, ax_avg = plt.subplots()
        line_avg_rm1, = ax_avg.plot([],[], label= "Room 1", color = 'r')
        line_avg_rm2, = ax_avg.plot([],[], label= "Room 2", color = 'b')

        ax_avg.set_title("Average Room Temperatures Over Time")
        ax_avg.set_xlabel("Time (Hours)")
        ax_avg.set_ylabel("Temperature (\u00b0F)")
        ax_avg.grid(True)
        ax_avg.legend()

       
        # loop to start collecting the data and timestamp it
        i = 0
        while (time.time() - start_time) < total_time:
            loop_start = time.time()
            current_time = time.time() - start_time
            timestamps.append(current_time / 3600) # divide by 3600 to convert to hours
            
            try:
                await plug_rm1.update()# Update readings of KASA Plug
                await plug_rm2.update()
            except Exception:
                plug_rm1 = await Discover.discover_single("10.42.0.87")
                await plug_rm1.update()
                plug_rm2 = await Discover.discover_single("10.42.0.252")
                await plug_rm2.update()


            energy_consumption1.append(plug_rm1.features["consumption_total"].value)
            current_consumption1.append(plug_rm1.features["current_consumption"].value)
            current1.append(plug_rm1.features["current"].value)
            voltage1.append(plug_rm1.features["voltage"].value)

            energy_consumption2.append(plug_rm2.features["consumption_total"].value)
            current_consumption2.append(plug_rm2.features["current_consumption"].value)
            current2.append(plug_rm2.features["current"].value)
            voltage2.append(plug_rm2.features["voltage"].value)

            # Enabling control logic after calibration
            if not heater_control and current_time >= calibration:
                heater_control = True
                print("\n Calibration Complete, Controller on. \n")

            print(f"\nReading {i+1}/{readings} at {current_time:.1f} seconds:")

            for channel in channels:
                # Get the value from the device
                value = ul.t_in(board_num, int(channel), TempScale.FAHRENHEIT)
                temperatures[channel].append(value)
                # Display the value
                print('Channel', channel, 'Value (deg F):', f"{value:.2f}")
                lines[channel].set_xdata(timestamps)
                lines[channel].set_ydata(temperatures[channel])

                # Check for over-temperature and send alert if needed
                if value > 88.00:
                    time_since_last_alert = current_time - last_alert_time[channel]
                    if time_since_last_alert > alert_cooldown:
                        send_email_alert(channel, value)
                        last_alert_time[channel] = current_time
                        await plug_rm1.turn_off()
                        await plug_rm2.turn_off()

            # Bang-Bang Controller
            if heater_control:
                # Seperated the channels by room and took the average to help with controller settings.
                temp_rm1 = [temperatures[j][-1] for j in room1_chs]
                temp_rm2 = [temperatures[j][-1] for j in room2_chs]
                avg_rm1 = sum(temp_rm1) / len(temp_rm1)
                avg_rm2 = sum(temp_rm2) / len(temp_rm2)

                avg_timestamps.append(current_time/3600)
                avg_rm1_temps.append(avg_rm1)
                avg_rm2_temps.append(avg_rm2)

                line_avg_rm1.set_xdata(avg_timestamps)
                line_avg_rm1.set_ydata(avg_rm1_temps)
                line_avg_rm2.set_xdata(avg_timestamps)
                line_avg_rm2.set_ydata(avg_rm2_temps)

                ax_avg.relim()
                ax_avg.autoscale_view()
                fig_avg.canvas.draw()
                fig_avg.canvas.flush_events()

                print(f'Average Temperature of RM1: {avg_rm1:.2f}')
                print(f'Average Temperature of RM2: {avg_rm2:.2f}')
                
                print(plug_rm1.features['current'])
                print(plug_rm1.features["voltage"])

                print(plug_rm2.features['current'])
                print(plug_rm2.features["voltage"])
    
                await asyncio.sleep(0.5)  

                # Checking which heater to turn on/off based temp.
                if not heater1 and not heater2:
                    if avg_rm1 < 79.00 and avg_rm2 < 79.00:
                        arduino.write(b'6')  # Heater 1 and 2 ON
                        heater1 = True
                        heater2 = True
                        print('Both Heaters ON')
                    elif avg_rm1 < 79.00:
                        arduino.write(b'1') # Heater 1 on
                        heater1 = True  
                        print('Heater 1 ON')
                    elif avg_rm2 < 79.00:
                        arduino.write(b'3') # Heater 2 on
                        heater2 = True  
                        print('Heater 2 ON')
                else:
                    if not heater1 and avg_rm1 < 79.00:
                        arduino.write(b'1') # Heater 1 on
                        heater1 = True  
                        print('Heater 1 ON')

                    if not heater2 and avg_rm2 < 79.00:
                        arduino.write(b'3') # Heater 2 on
                        heater2 = True  
                        print('Heater 2 ON')

                if heater1 and avg_rm1 > 81.00:
                    arduino.write(b'2') # Heater 1 off
                    heater1 = False  
                    print('Heater 1 OFF')

                if heater2 and avg_rm2 > 81.00:
                    arduino.write(b'4') # Heater 2 off
                    heater2 = False  
                    print('Heater 2 OFF')

            heater1_state.append(1 if heater1 else 0)
            heater2_state.append(1 if heater2 else 0)

            line_heater1.set_xdata(timestamps)
            line_heater1.set_ydata(heater1_state)
            line_heater2.set_xdata(timestamps)
            line_heater2.set_ydata(heater2_state)

            # Update energy consumption plot 
            line_energy1.set_xdata(timestamps)
            line_energy1.set_ydata(energy_consumption1)

            line_energy2.set_xdata(timestamps)
            line_energy2.set_ydata(energy_consumption2)

            ax.relim()
            ax.autoscale_view()
            fig.canvas.draw()
            fig.canvas.flush_events()
            ax_heater1.relim()
            ax_heater1.autoscale_view()
            ax_heater2.relim()
            ax_heater2.autoscale_view()
            fig_heaters.canvas.draw()
            fig_heaters.canvas.flush_events()
            ax_energy.relim()
            ax_energy.autoscale_view()
            fig_energy.canvas.draw()
            fig_energy.canvas.flush_events()
            
            # if 15 minutes has elapsed since we last saved:
            # write lists to CSVs
            if current_time - last_save_time >= 900: 
                        new_idx = range(last_save_idx, len(timestamps))
                        #Temperature file save
                        with open(filename, 'a', newline = '') as f:
                            w = csv.writer(f)
                            for k in new_idx:
                                row = [f"{timestamps[k]:.2f}"] + [ f"{temperatures[ch][k]:.2f}"
                                        if k < len(temperatures[ch])
                                        else "" 
                                        for ch in channels 
                                    ]
                                w.writerow(row)
                
                        # Controller State file save
                        with open(state_filename, 'a', newline='') as f:
                                w = csv.writer(f)
                                for k in new_idx:
                                    w.writerow([f"{timestamps[k]:.2f}", heater1_state[k], heater2_state[k]])
                   
                        # Energy file save
                        with open(energy_filename, 'a', newline='') as f:
                                w = csv.writer(f)
                                for k in new_idx:
                                    w.writerow([f"{timestamps[k]:.2f}", energy_consumption1[k], current_consumption1[k], current1[k], voltage1[k], energy_consumption2[k], current_consumption2[k], current2[k], voltage2[k]])      

                        # Average Temperature Save
                        with open(Avg_Temp_filename, 'a', newline='') as f:
                                w = csv.writer(f)
                                for k in new_idx:
                                    if k < len(avg_rm1_temps):
                                        w.writerow([f"{timestamps[k]:.2f}", f"{avg_rm1_temps[k]:.2f}", f"{avg_rm2_temps[k]:.2f}"])

                        print(f"Average Temperature data saved to { Avg_Temp_filename}") 
                        print(f"Energy consumption data saved to {energy_filename}")  
                        print(f"Heater states data saved to {state_filename}")  
                        print(f"\nData saved to {filename}")  
                    
                        last_save_time = current_time
                        last_save_idx = len(timestamps)

            # Fix loop to stop close to desired hour
            elapsed = time.time() - loop_start
            sleep_time = samples - elapsed
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            i += 1

    except Exception as e:
        print('\n', e)
    finally:
        if use_device_detection:
            ul.release_daq_device(board_num)
       
        try:
            fig.savefig(f"C:/Cristian Hernandez/Python Code for Two-Room/Tests/Temperature_Plot_{timestamp_save}.png")
            fig_heaters.savefig(f"C:/Cristian Hernandez/Python Code for Two-Room/Tests/Heater_States_Plot_{timestamp_save}.png")
            fig_energy.savefig(f"C:/Cristian Hernandez/Python Code for Two-Room/Tests/Energy_Consumption_Plot_{timestamp_save}.png")
            fig_avg.savefig(f"C:/Cristian Hernandez/Python Code for Two-Room/Tests/Avg_Temperatures_Plot_{timestamp_save}.png")
            print("All plots saved successfully.")
        except Exception as e:
             print(f"Failed to save one or more plots: {e}")

        if arduino and arduino.is_open:
            arduino.write(b'5') # relays off
            arduino.close()

        # To display graph
        plt.ioff()
        plt.show()

def send_email_alert(channel, temp):
    try:
        from_email = "criststest10@gmail.com"
        from_pw = 'yjqh wmed vopt ppcy'
        to_email = 'crishdez00@gmail.com'
        subject = f"High Temp Alert on Channel {channel}!"
        body = (f"Warning!\n\n"
                f"Channel {channel} has exceeded the safe temperature limit.\n"
                f"Current Temperature: {temp:.2f} F\n"
                f"Threshold: 88 F\n"
                f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        message = MIMEText(body)
        message["Subject"] = subject
        message["From"] = from_email
        message["To"] = to_email

        gmail = smtplib.SMTP('smtp.gmail.com', 587)
        gmail.ehlo()
        gmail.starttls()

        gmail.login(from_email,from_pw)

        gmail.send_message(message)
        print('Email sent successfully')

    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == '__main__':
    asyncio.run(Two_Room_Thermo_Sync())

