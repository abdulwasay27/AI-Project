import sys
import argparse
import socket
import driver
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
car_name = "c" or input("Enter car name: ").strip()
track_name = "c" or input("Enter track name: ").strip()
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

d = driver.Driver(arguments.stage)

# CSV File Setup
csv_filename = "torcs_data.csv"
csv_headers = None  # Will be determined dynamically

# Function to extract values from data string
def extract_data(data_string):
    """Parses a data string in the format '(key value)(key value)' into a dictionary."""
    pattern = r'\((\w+) ([^()]+)\)'
    return dict(re.findall(pattern, data_string))

# Check if CSV file exists and read headers if present
if os.path.exists(csv_filename):
    with open(csv_filename, mode="r", newline="") as f:
        reader = csv.reader(f)
        existing_headers = next(reader, None)
        if existing_headers:
            csv_headers = existing_headers

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
            print('Received: ', buf)
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
                
                # Only log if car is moving (speed > 0.1) or engine is running (rpm > 500)
                if abs(speed) > 0.1 or rpm > 500:
                    # Ensure "Track" column is included
                    received_data["Track"] = arguments.track

                    combined_data = {"Car": car_name, "track": track_name, **received_data, **sending_data}  # Merge both dictionaries
                    
                    # Ensure headers are consistent
                    if csv_headers is None:
                        csv_headers = ["Track"] + sorted(set(combined_data.keys()))  # Sort keys for consistency
                        with open(csv_filename, mode="w", newline="") as f:
                            writer = csv.DictWriter(f, fieldnames=csv_headers)
                            writer.writeheader()
                    
                    # Append data row
                    with open(csv_filename, mode="a", newline="") as f:
                        writer = csv.DictWriter(f, fieldnames=csv_headers)
                        writer.writerow(combined_data)
            except (ValueError, IndexError) as e:
                if verbose:
                    print(f"Error processing data: {e}")
                continue

        if buf:
            try:
                sock.sendto(buf.encode(), (arguments.host_ip, arguments.host_port))
            except socket.error:
                print("Failed to send data...Exiting...")
                sys.exit(-1)

    curEpisode += 1
    
    if curEpisode == arguments.max_episodes:
        shutdownClient = True

sock.close()
