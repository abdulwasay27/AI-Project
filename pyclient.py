import sys
import argparse
import socket
import autoDriver
import csv
import os
import re

if __name__ == '__main__':
    pass

# Configure the argument parser
parser = argparse.ArgumentParser(description='Python client to connect to the TORCS SCRC server.')

parser.add_argument('--host', action='store', dest='host_ip', default='localhost',
                    help='Host IP address (default: localhost)')
parser.add_argument('--port', action='store', type=int, dest='host_port', default=3001,
                    help='Host port number (default: 3001)')
parser.add_argument('--id', action='store', dest='id', default='SCR',
                    help='Bot ID (default: SCR)')
parser.add_argument('--maxEpisodes', action='store', dest='max_episodes', type=int, default=1,
                    help='Maximum number of learning episodes (default: 1)')
parser.add_argument('--maxSteps', action='store', dest='max_steps', type=int, default=0,
                    help='Maximum number of steps (default: 0)')
parser.add_argument('--track', action='store', dest='track', default=None,
                    help='Name of the track')
parser.add_argument('--stage', action='store', dest='stage', type=int, default=3,
                    help='Stage (0 - Warm-Up, 1 - Qualifying, 2 - Race, 3 - Unknown)')

arguments = parser.parse_args()

# Take track name and car name as input when the game starts
# track_name = input("Enter track name: ").strip()
# car_name = input("Enter car name: ").strip()

# # Create the CSV filename based on the track and car name
# csv_filename = f"{track_name}_{car_name}.csv"

# # Ensure headers are consistent
# csv_headers = None

# if not os.path.exists(csv_filename):
#     # If the file doesn't exist, create it and write the headers
#     with open(csv_filename, mode="w", newline="") as f:
#         csv_headers = None  # Reset headers to ensure they are written later

# Print summary
print('Connecting to server host ip:', arguments.host_ip, '@ port:', arguments.host_port)
print('Bot ID:', arguments.id)
print('Maximum episodes:', arguments.max_episodes)
print('Maximum steps:', arguments.max_steps)
print('Track:', arguments.track)
print('Stage:', arguments.stage)
print('*********************************************')

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
except socket.error:
    print('Could not make a socket.')
    sys.exit(-1)

sock.settimeout(1.0)  # one second timeout

shutdownClient = False
curEpisode = 0

verbose = True

# Initialize the autoDriver instead of manual driver
d = autoDriver.autoDriver(arguments.stage)

# Function to extract values from data string
def extract_data(data_string):
    """Parses a data string in the format '(key value)(key value)' into a dictionary."""
    pattern = r'\((\w+) ([^()]+)\)'
    return dict(re.findall(pattern, data_string))

# Function to update CSV headers dynamically
def update_csv_headers(new_data, csv_headers, csv_filename):
    """Update CSV headers if new keys are found in the data."""
    new_keys = set(new_data.keys()) - set(csv_headers)
    if new_keys:
        csv_headers.extend(new_keys)  # Add new keys to the headers
        # Rewrite the CSV file with updated headers
        with open(csv_filename, mode="w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=csv_headers)
            writer.writeheader()
            print(f"CSV headers updated: {csv_headers}")
    return csv_headers

while not shutdownClient:
    while True:
        buf = arguments.id + d.init()
        
        try:
            sock.sendto(buf.encode(), (arguments.host_ip, arguments.host_port))
        except socket.error:
            print("Failed to send data...Exiting...")
            sys.exit(-1)       
        try:
            buf, addr = sock.recvfrom(1000)
            buf = buf.decode()
        except socket.error:
            print("didn't get response from server...")
    
        if buf.find('***identified***') >= 0:
            # print('Received response: ', buf)
            break

    currentStep = 0
    
    while True:
        buf = None
        try:
            buf, addr = sock.recvfrom(1000)
            buf = buf.decode()
        except socket.error:
            print("didn't get response from server...")

        # if verbose and buf:
        #     print('Received: ', buf)

        # Handle shutdown or restart
        if buf and '***shutdown***' in buf:
            d.onShutDown()
            shutdownClient = True
            print('Client Shutdown')
            break

        if buf and '***restart***' in buf:
            d.onRestart()
            print('Client Restart')
            break

        # Process Received Data
        received_data = extract_data(buf) if buf else {}
        # print(buf)
        currentStep += 1
        if currentStep != arguments.max_steps:
            if buf:
                buf = d.drive(buf)
        else:
            buf = '(meta 1)'

        # Process Sending Data
        sending_data = extract_data(buf) if buf else {}
        
        # Only log data if car is connected and moving
        if received_data and sending_data:
            try:
                # Check if car is connected and moving
                speed_str = received_data.get('speedX', ['0'])[0]
                rpm_str = received_data.get('rpm', ['0'])[0]
                
                # Handle invalid values
                speed = 0.0
                rpm = 0.0
                
                if speed_str != '-':
                    speed = float(speed_str)
                if rpm_str != '-':
                    rpm = float(rpm_str)
                
                # Only log if car is moving (speed > 0.1) or engine is running (rpm > 100)
                # if abs(speed) > 0.1 or rpm > 100:
                    # Expand multi-value fields into separate columns
                    # def expand_multi_values(data, key_prefix):
                    #     """Expand multi-value fields into separate columns."""
                    #     expanded = {}
                    #     if key_prefix in data:
                    #         values = data[key_prefix].split()
                    #         for i, value in enumerate(values):
                    #             expanded[f"{key_prefix}_{i}"] = value
                    #         del data[key_prefix]  # Remove the original multi-value field
                    #     return expanded

                    # # Expand multi-value fields
                    # received_data.update(expand_multi_values(received_data, "opponents"))
                    # received_data.update(expand_multi_values(received_data, "track"))
                    # received_data.update(expand_multi_values(received_data, "focus"))
                    # received_data.update(expand_multi_values(received_data, "wheelSpinVel"))

                    # # Merge received and sending data
                    # combined_data = {**received_data, **sending_data}

                    # # Update CSV headers dynamically
                    # if csv_headers is None:
                    #     csv_headers = sorted(combined_data.keys())  # Initialize headers
                    #     with open(csv_filename, mode="w", newline="") as f:
                    #         writer = csv.DictWriter(f, fieldnames=csv_headers)
                    #         writer.writeheader()
                    # else:
                    #     csv_headers = update_csv_headers(combined_data, csv_headers, csv_filename)

                    # # Append data row
                    # with open(csv_filename, mode="a", newline="") as f:
                    #     writer = csv.DictWriter(f, fieldnames=csv_headers)
                    #     writer.writerow(combined_data)

            except (ValueError, IndexError) as e:
                print(f"Error processing data: {e}")

        if buf:
            try:
                print(buf)
                sock.sendto(buf.encode(), (arguments.host_ip, arguments.host_port))
            except socket.error:
                print("Failed to send data...Exiting...")
                sys.exit(-1)

    curEpisode += 1
    
    if curEpisode == arguments.max_episodes:
        shutdownClient = True

sock.close()
