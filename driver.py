import msgParser
import carState
import carControl
from pynput import keyboard
import time
import math

class Driver(object):
    '''
    A keyboard-controlled driver for TORCS with gradual controls and proper state management
    '''

    def __init__(self, stage):
        '''Constructor'''
        self.stage = stage
        
        self.parser = msgParser.MsgParser()
        self.state = carState.CarState()
        self.control = carControl.CarControl()
        
        # Control change rates (adjust these values for desired sensitivity)
        self.accel_rate = 0.05 
        self.brake_rate = 0.1
        self.steer_rate = 0.005  # Reduced from 0.01 for less sensitive steering
        self.steer_center_rate = 0.02  # Reduced from 0.05 for smoother centering

        # Current control states
        self.current_accel = 0.0
        self.current_brake = 0.0
        self.current_steer = 0.0
        
        self.steer_lock = 0.785398  # Max steer angle in radians for TORCS (approx 45 degrees)
        self.max_speed = 100
        self.prev_rpm = None
        
        self.input_keys = {"w": False, "s": False, "a": False, "d": False}
        self.manual_gear = 1
       

        # Start listening for keyboard input in a separate thread
        listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        listener.start()

    def init(self):
        '''Return init string with rangefinder angles'''
        self.angles = [0 for x in range(19)]
        
        # Set sensor angles for better track coverage
        for i in range(5):
            self.angles[i] = -90 + i * 15
            self.angles[18 - i] = 90 - i * 15
        
        for i in range(5, 9):
            self.angles[i] = -20 + (i-5) * 5
            self.angles[18 - i] = 20 - (i-5) * 5
        
        # Center sensor
        self.angles[9] = 0

        return self.parser.stringify({'init': self.angles})
    
    def drive(self, msg):
        '''Receive telemetry, apply user input, and return control commands'''
        # Update car state from message
        self.state.setFromMsg(msg)
        
        # Get current state values
        speed = self.state.getSpeedX()
        rpm = self.state.getRpm()
        track_pos = self.state.getTrackPos()
        track_sensors = self.state.getTrack()
        
        # Apply user inputs to controls gradually
        self.update_controls(speed, rpm, track_pos, track_sensors)

        # Update control values
        self.control.setAccel(self.current_accel)
        self.control.setBrake(self.current_brake)
        self.control.setSteer(self.current_steer)
        self.control.setGear(self.manual_gear)
        
        # Add clutch control for smoother gear changes
        if self.prev_rpm is not None and abs(rpm - self.prev_rpm) > 1000:
            self.control.setClutch(0.5)  # Engage clutch during rapid RPM changes
        else:
            self.control.setClutch(0.0)
        
        self.prev_rpm = rpm

        # Return the control message string
        return self.control.toMsg()

    def update_controls(self, speed, rpm, track_pos, track_sensors):
        '''Updates car controls gradually based on keyboard input and car state'''
        
        # --- Acceleration and Braking ---
        if self.input_keys["w"]:
            # Reduce braking force quickly
            self.current_brake = max(0.0, self.current_brake - self.brake_rate * 2)
            
            # Manual acceleration control
            if self.manual_gear != -1:  # Forward gears
                self.current_accel = min(1.0, self.current_accel + self.accel_rate)
            else:  # Reverse gear
                self.current_accel = min(0.5, self.current_accel + self.accel_rate * 0.5)
        else:
            # Coasting/engine braking
            self.current_accel = max(0.0, self.current_accel - self.accel_rate * 1.5)

        # --- Braking ---
        if self.input_keys["s"]:
            # Reduce acceleration quickly
            self.current_accel = max(0.0, self.current_accel - self.accel_rate * 2)
            # Manual braking control with immediate response
            self.current_brake = min(1.0, self.current_brake + self.brake_rate * 2)  # Doubled brake rate
        else:
            # Gradually reduce braking
            self.current_brake = max(0.0, self.current_brake - self.brake_rate)

        # --- Steering ---
        target_steer = 0.0
        
        # Manual steering control
        if self.input_keys["a"]:
            target_steer = self.steer_lock
        elif self.input_keys["d"]:
            target_steer = -self.steer_lock

        # Gradually move current steer towards target
        if self.current_steer < target_steer:
            rate = self.steer_rate if target_steer > 0 else self.steer_center_rate
            self.current_steer = min(target_steer, self.current_steer + rate)
        elif self.current_steer > target_steer:
            rate = self.steer_rate if target_steer < 0 else self.steer_center_rate
            self.current_steer = max(target_steer, self.current_steer - rate)

        # Ensure steer stays within bounds
        self.current_steer = max(-self.steer_lock, min(self.steer_lock, self.current_steer))

    def on_press(self, key):
        '''Handle key press events'''
        try:
            k = key.char.lower()
            if k in self.input_keys:
                self.input_keys[k] = True
            elif k == 'e':  # Gear Up
                if self.manual_gear < 6:
                    self.manual_gear += 1
                    print(f"Gear Up: {self.manual_gear}")
            elif k == 'q':  # Gear Down
                if self.manual_gear > -1:
                    self.manual_gear -= 1
                    print(f"Gear Down: {self.manual_gear}")
        except AttributeError:
            pass

    def on_release(self, key):
        '''Handle key release events'''
        try:
            k = key.char.lower()
            if k in self.input_keys:
                self.input_keys[k] = False
        except AttributeError:
            pass
    
    def onShutDown(self):
        '''Called when TORCS sends a shutdown message'''
        print('Client Shutdown')
    
    def onRestart(self):
        '''Called when TORCS sends a restart message'''
        print('Client Restart')
        # Reset control states
        self.current_accel = 0.0
        self.current_brake = 0.0
        self.current_steer = 0.0
        self.manual_gear = 1
        self.prev_rpm = None
