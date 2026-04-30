"""
The main control change is:
- old: Python decided ON/OFF bang-bang and sent relay commands
- new: Python sends average building temperature to Arduino
- Arduino runs PID + time-proportioning and reports back duty / heater state
"""

from __future__ import absolute_import, division, print_function
from builtins import *

import asyncio
from kasa import Discover
import smtplib
from email.mime.text import MIMEText
import os
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


def parse_arduino_status(line):
    result = {}
    try:
        parts = line.strip().split(',')
        for part in parts:
            if '=' in part:
                k, v = part.split('=', 1)
                result[k.strip()] = v.strip()
    except Exception:
        return {}
    return result


def send_email_alert(channel, temp):
    try:
        from_email = os.getenv("TEMP_ALERT_FROM")
        from_pw = os.getenv("TEMP_ALERT_APP_PASSWORD")
        to_email = os.getenv("TEMP_ALERT_TO")

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
        gmail.login(from_email, from_pw)
        gmail.send_message(message)
        print('Email sent successfully')
    except Exception as e:
        print(f"Failed to send email: {e}")


async def Two_Room_Thermo_Sync():
    use_device_detection = True
    dev_id_list = []
    board_num = 0

    plug_rm1 = await Discover.discover_single("10.42.0.87")
    plug_rm2 = await Discover.discover_single("10.42.0.252")

    arduino = serial.Serial('COM5', 9600, timeout=0.2)
    await asyncio.sleep(2)
    arduino.reset_input_buffer()
    arduino.reset_output_buffer()

    try:
        if use_device_detection:
            config_first_detected_device(board_num, dev_id_list)

        daq_dev_info = DaqDeviceInfo(board_num)
        print('\nActive DAQ device: ', daq_dev_info.product_name, ' (',
              daq_dev_info.unique_id, ')\n', sep='')

        ai_info = daq_dev_info.get_ai_info()
        if ai_info.num_temp_chans <= 0:
            raise Exception('Error: The DAQ device does not support temperature input')

        heater1 = False
        heater2 = False
        heater1_output = 0.0
        heater2_output = 0.0

        channels = [0, 1, 2, 5, 16, 17, 18, 20, 27, 29, 30, 31, 44, 47, 52]
        room1_chs = [0, 1, 16, 17, 30, 31]
        room2_chs = [2, 5, 18, 20, 27, 29]

        samples = 1
        total_time = 216500
        readings = total_time // samples

        timestamps = []
        temperatures = {channel: [] for channel in channels}

        avg_timestamps = []
        avg_rm1_temps = []
        avg_rm2_temps = []
        building_temps = []

        last_alert_time = {ch: 0 for ch in channels}
        alert_cooldown = 150
        heater1_state = []
        heater2_state = []
        heater1_output_hist = []
        heater2_output_hist = []

        energy_consumption1 = []
        current_consumption1 = []
        current1 = []
        voltage1 = []

        energy_consumption2 = []
        current_consumption2 = []
        current2 = []
        voltage2 = []

        calibration = 60 # Seconds
        heater_control = False

        # Overwrite Firmware Setpoint and Gain (Applies after calibration)
        setpoint_building = 80.0
        gains_building = (20.0, 0.02, 0.0)
        sent_pid_setup = False

        start_time = time.time()
        last_flush_time = 0
        last_checkpoint_time = 0

        # Creating CSV File
        timestamp_save = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"C:/Users/rareva14/Documents/PID_Testing/Data Plots/TC_Temp_Reader_{timestamp_save}.csv"
        state_filename = f"C:/Users/rareva14/Documents/PID_Testing/Data Plots/Heater_States_{timestamp_save}.csv"
        energy_filename = f"C:/Users/rareva14/Documents/PID_Testing/Data Plots/Energy_Consumption_{timestamp_save}.csv"
        Avg_Temp_filename = f"C:/Users/rareva14/Documents/PID_Testing/Data Plots/Average_Temp_{timestamp_save}.csv"

        # Headers for Files
        temp_file = open(filename, 'w', newline='', buffering=1)
        state_file = open(state_filename, 'w', newline='', buffering=1)
        energy_file = open(energy_filename, 'w', newline='', buffering=1)
        avg_file = open(Avg_Temp_filename, 'w', newline='', buffering=1)

        temp_writer = csv.writer(temp_file)
        state_writer = csv.writer(state_file)
        energy_writer = csv.writer(energy_file)
        avg_writer = csv.writer(avg_file)

        temp_writer.writerow(["Time (h)"] + [f"Channel {ch}" for ch in channels])
        state_writer.writerow([
            "Time (h)",
            "Heater 1 State",
            "Heater 2 State",
            "Output 1 (%)",
            "Output 2 (%)"
        ])
        energy_writer.writerow([
            "Time (h)",
            "Total Energy 1 (kWh)",
            "Current Consumption 1 (W)",
            "Current 1 (A)",
            "Voltage 1 (V)",
            "Total Energy 2 (kWh)",
            "Current Consumption 2 (W)",
            "Current 2 (A)",
            "Voltage 2 (V)"
        ])
        avg_writer.writerow(["Time (h)", "Room 1", "Room 2"])

        temp_file.flush()
        state_file.flush()
        energy_file.flush()
        avg_file.flush()

        os.fsync(temp_file.fileno())
        os.fsync(state_file.fileno())
        os.fsync(energy_file.fileno())
        os.fsync(avg_file.fileno())

        plt.ion()
        fig, ax = plt.subplots()
        lines = {}
        colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'orange', 'brown', 'hotpink', 'dodgerblue', 'olive', 'gold', 'goldenrod', 'peru']
        for idx, ch in enumerate(channels):
            line, = ax.plot([], [], label=f"Channel {ch}", color=colors[idx])
            lines[ch] = line

        ax.set_title("Temperatures of Two-Room (PID Controller Input) (°F)")
        ax.set_xlabel("Time (Hours)")
        ax.set_ylabel("Temperature (°F)")
        ax.grid(True)
        ax.legend()

        fig_heaters, (ax_heater1, ax_heater2) = plt.subplots(2, 1)
        line_heater1, = ax_heater1.plot([], [], label="Heater 1", color='r')
        line_heater2, = ax_heater2.plot([], [], label="Heater 2", color='b')

        ax_heater1.set_title("Heater 1 Duty Cycle Over Time")
        ax_heater1.set_xlabel("Time (Hours)")
        ax_heater1.set_ylabel("Duty Cycle (%)")
        ax_heater1.set_ylim(0,100)
        ax_heater1.grid(True)
        ax_heater1.legend()

        ax_heater2.set_title("Heater 2 Duty Cycle Over Time")
        ax_heater2.set_xlabel("Time (Hours)")
        ax_heater2.set_ylabel("Duty Cycle (%)")
        ax_heater2.set_ylim(0,100)
        ax_heater2.grid(True)
        ax_heater2.legend()

        fig_energy, ax_energy = plt.subplots()
        line_energy1, = ax_energy.plot([], [], label="Plug 1 (Room 2) Total Energy (kWh)", color='purple')
        line_energy2, = ax_energy.plot([], [], label="Plug 2 (Room 1) Total Energy (kWh)", color='orange')
        ax_energy.set_title("Total Energy Consumption Over Time")
        ax_energy.set_xlabel("Time (Hours)")
        ax_energy.set_ylabel("Energy (kWh)")
        ax_energy.grid(True)
        ax_energy.legend()

        fig_avg, ax_avg = plt.subplots()
        line_avg_rm1, = ax_avg.plot([], [], label="Room 1", color='r')
        line_avg_rm2, = ax_avg.plot([], [], label="Room 2", color='b')
        line_avg_building, = ax_avg.plot([], [], label ="Building Avg", color='k')
        ax_avg.set_title("Average Room Temperatures Over Time")
        ax_avg.set_xlabel("Time (Hours)")
        ax_avg.set_ylabel("Temperature (°F)")
        ax_avg.grid(True)
        ax_avg.legend()

        i = 0
        while (time.time() - start_time) < total_time:
            loop_start = time.time()
            current_time = time.time() - start_time
            timestamps.append(current_time / 3600)

            try:
                await plug_rm1.update()
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

            if not heater_control and current_time >= calibration:
                heater_control = True
                print("\n Calibration Complete, Controller on. \n")

            print(f"\nReading {i+1}/{readings} at {current_time:.1f} seconds:")

            for channel in channels:
                value = ul.t_in(board_num, int(channel), TempScale.FAHRENHEIT)
                temperatures[channel].append(value)
                print('Channel', channel, 'Value (deg F):', f"{value:.2f}")
                lines[channel].set_xdata(timestamps)
                lines[channel].set_ydata(temperatures[channel])

                if value > 88.00:
                    time_since_last_alert = current_time - last_alert_time[channel]
                    if time_since_last_alert > alert_cooldown:
                        send_email_alert(channel, value)
                        last_alert_time[channel] = current_time
                        await plug_rm1.turn_off()
                        await plug_rm2.turn_off()

            temp_rm1 = [temperatures[j][-1] for j in room1_chs]
            temp_rm2 = [temperatures[j][-1] for j in room2_chs]
            avg_rm1 = sum(temp_rm1) / len(temp_rm1)
            avg_rm2 = sum(temp_rm2) / len(temp_rm2)
            building_temp = (avg_rm1 + avg_rm2) / 2.0

            avg_timestamps.append(current_time / 3600)
            avg_rm1_temps.append(avg_rm1)
            avg_rm2_temps.append(avg_rm2)
            building_temps.append(building_temp)

            line_avg_rm1.set_xdata(avg_timestamps)
            line_avg_rm1.set_ydata(avg_rm1_temps)

            line_avg_rm2.set_xdata(avg_timestamps)
            line_avg_rm2.set_ydata(avg_rm2_temps)

            line_avg_building.set_xdata(avg_timestamps)
            line_avg_building.set_ydata(building_temps)

            ax_avg.relim()
            ax_avg.autoscale_view()
            fig_avg.canvas.draw()
            fig_avg.canvas.flush_events()

            print(f'Average Temperature of RM1: {avg_rm1:.2f}')
            print(f'Average Temperature of RM2: {avg_rm2:.2f}')
            print(f'Average Temperature of Building: {building_temp:.2f}')
            print(plug_rm1.features['current'])
            print(plug_rm1.features['voltage'])
            print(plug_rm2.features['current'])
            print(plug_rm2.features['voltage'])

            if heater_control:
                if not sent_pid_setup:
                    arduino.write(f"SP={setpoint_building:.2f}\n".encode())
                    arduino.write(f"G={gains_building[0]:.4f},{gains_building[1]:.4f},{gains_building[2]:.4f}\n".encode())
                    
                    #arduino.write(f"SP1={setpoint_rm1:.2f},SP2={setpoint_rm2:.2f}\n".encode())
                    #arduino.write(f"G1={gains_rm1[0]:.4f},{gains_rm1[1]:.4f},{gains_rm1[2]:.4f}\n".encode())
                    #arduino.write(f"G2={gains_rm2[0]:.4f},{gains_rm2[1]:.4f},{gains_rm2[2]:.4f}\n".encode())
                    sent_pid_setup = True
                    
                arduino.write(f"T1={avg_rm1:.2f},T2={avg_rm2:.2f}\n".encode())
                arduino.write(f"TB={building_temp:.2f}\n".encode())
                await asyncio.sleep(0.1)

                while arduino.in_waiting:
                    status_line = arduino.readline().decode(errors='ignore').strip()
                    if not status_line:
                        continue
                    print(f"Arduino: {status_line}")
                    status = parse_arduino_status(status_line)
                    if 'OUT' in status:
                        heater1_output = float(status['OUT1'])
                        heater2_output = float(status['OUT2'])

                    if 'H1' in status:
                        heater1 = bool(int(float(status['H1'])))
                    if 'H2' in status:
                        heater2 = bool(int(float(status['H2'])))
            else:
                heater1 = False
                heater2 = False
                heater1_output = 0.0
                heater2_output = 0.0

            heater1_state.append(1 if heater1 else 0)
            heater2_state.append(1 if heater2 else 0)
            heater1_output_hist.append(heater1_output)
            heater2_output_hist.append(heater2_output)

            line_heater1.set_xdata(timestamps)
            line_heater1.set_ydata(heater1_output_hist)
            line_heater2.set_xdata(timestamps)
            line_heater2.set_ydata(heater2_output_hist)

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

            # Write one new row to each CSV every loop
            temp_row = [f"{timestamps[-1]:.2f}"] + [f"{temperatures[ch][-1]:.2f}" for ch in channels]
            temp_writer.writerow(temp_row)

            state_writer.writerow([
                f"{timestamps[-1]:.2f}",
                heater1_state[-1],
                heater2_state[-1],
                f"{heater1_output_hist[-1]:.1f}",
                f"{heater2_output_hist[-1]:.1f}"
            ])

            energy_writer.writerow([
                f"{timestamps[-1]:.2f}",
                energy_consumption1[-1],
                current_consumption1[-1],
                current1[-1],
                voltage1[-1],
                energy_consumption2[-1],
                current_consumption2[-1],
                current2[-1],
                voltage2[-1]
            ])

            if avg_rm1_temps and avg_rm2_temps:
                avg_writer.writerow([
                    f"{timestamps[-1]:.2f}",
                    f"{avg_rm1_temps[-1]:.2f}",
                    f"{avg_rm2_temps[-1]:.2f}"
                ])

            # Flush buffered data to disk every 10 seconds
            if current_time - last_flush_time >= 10:
                for fh in [temp_file, state_file, energy_file, avg_file]:
                    fh.flush()
                    os.fsync(fh.fileno())
                print("CSV data flushed to disk.")
                last_flush_time = current_time

            # 10-minute checkpoint message
            if current_time - last_checkpoint_time >= 600:
                print(f"10-minute checkpoint reached at {current_time / 60:.1f} minutes.")
                last_checkpoint_time = current_time

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

        for fh in [temp_file, state_file, energy_file, avg_file]:
            try:
                fh.flush()
                os.fsync(fh.fileno())
                fh.close()
            except Exception as e:
                print(f"Failed to close a data file cleanly: {e}")

        try:
            fig.savefig(f"C:/Users/rareva14/Documents/PID_Testing/Data Plots/Temperature_Plot_{timestamp_save}.png")
            fig_heaters.savefig(f"C:/Users/rareva14/Documents/PID_Testing/Data Plots/Heater_States_Plot_{timestamp_save}.png")
            fig_energy.savefig(f"C:/Users/rareva14/Documents/PID_Testing/Data Plots/Energy_Consumption_Plot_{timestamp_save}.png")
            fig_avg.savefig(f"C:/Users/rareva14/Documents/PID_Testing/Data Plots/Avg_Temperatures_Plot_{timestamp_save}.png")
            print("All plots saved successfully.")
        except Exception as e:
            print(f"Failed to save one or more plots: {e}")

        if arduino and arduino.is_open:
            try:
                arduino.write(b"T1=0.00,T2=0.00\n")
            except Exception:
                pass
            arduino.close()

        plt.ioff()
        plt.show()


if __name__ == '__main__':
    asyncio.run(Two_Room_Thermo_Sync())
