import msgParser
import carState
import carControl
import joblib
import xgboost as xgb
import numpy as np
# from tensorflow import keras
# from sklearn.ensemble import RandomForestRegressor
import os

class autoDriver(object):
    '''
    A model-based driver for TORCS using a trained neural network
    '''

    def __init__(self, stage):
        self.stage = stage
        self.parser = msgParser.MsgParser()
        self.state = carState.CarState()
        self.control = carControl.CarControl()

        # Load scaler and model
        controller_dir = os.path.join(os.path.dirname(__file__), "controller")
        self.scaler = joblib.load(os.path.join(controller_dir, "G-Speedway_controller_scaler.joblib"))
        self.model = joblib.load(os.path.join(controller_dir, "G-Speedway_controller_xgb.joblib"))
        
        # The order of features expected by the model
        self.input_features = [
            'angle', 'distFromStart', 'distRaced','focus_0', 'focus_1', 'focus_2', 'focus_3', 'focus_4',
            'rpm', 'speedX', 'speedY', 'speedZ', 'trackPos', 'track_0',
            'track_1', 'track_10', 'track_11', 'track_12', 'track_13', 'track_14',
            'track_15', 'track_16', 'track_17', 'track_18', 'track_2', 'track_3',
            'track_4', 'track_5', 'track_6', 'track_7', 'track_8', 'track_9',
            'wheelSpinVel_0', 'wheelSpinVel_1', 'wheelSpinVel_2', 'wheelSpinVel_3','z'
        ]

    def init(self):
        '''Return init string with rangefinder angles'''
        self.angles = [0 for x in range(19)]
        for i in range(5):
            self.angles[i] = -90 + i * 15
            self.angles[18 - i] = 90 - i * 15
        for i in range(5, 9):
            self.angles[i] = -20 + (i-5) * 5
            self.angles[18 - i] = 20 - (i-5) * 5
        self.angles[9] = 0
        return self.parser.stringify({'init': self.angles})

    def drive(self, msg):
        '''Process sensor data and return control commands'''
        # Parse and update car state
        self.state.setFromMsg(msg)
        
        # Extract features for the model
        features = self.extract_features()
        if features is not None:
            try:
                # Scale and predict
                X = self.scaler.transform([features])
                print("Feature vector length:", len(features))
                print("Expected input length:", len(self.input_features))
                prediction = self.model.predict(X)[0]  # [accel, brake, clutch, gear, steer]
                
                # Apply predictions to controls by adding to previous values
                current_accel = self.control.accel if hasattr(self.control, 'accel') else 0
                current_brake = self.control.brake if hasattr(self.control, 'brake') else 0
                current_clutch = self.control.clutch if hasattr(self.control, 'clutch') else 0
                current_steer = self.control.steer if hasattr(self.control, 'steer') else 0
                current_gear = self.control.gear if hasattr(self.control, 'gear') else 1
                current_focus = self.control.focus if hasattr(self.control, 'focus') else 0
                current_meta = self.control.meta if hasattr(self.control, 'meta') else 0

                # Add new values to current values and clip to valid ranges
                self.control.setAccel(float(np.clip(current_accel + prediction[0], 0, 1)))
                self.control.setBrake(float(np.clip(prediction[1], 0, 1)))
                self.control.setClutch(0)
                
                
                gear = int(np.round(prediction[3]))
                self.control.setGear(int(np.clip(gear, 1, 6)))
                
                self.control.setSteer(float(np.clip(prediction[4], -1, 1)))
                self.control.focus = current_focus + 0  # Add to current focus
                self.control.meta = current_meta + 0   # Add to current meta

                # Print current state and controls for debugging
                print("\nCurrent State:")
                print(f"Speed: {self.state.speedX:.2f}")
                print(f"RPM: {self.state.rpm:.2f}")
                print(f"Gear: {self.control.gear}")
                print(f"Track Position: {self.state.trackPos:.2f}")
                
                print("\nControl Outputs:")
                print(f"Accel: {self.control.accel:.2f}")
                print(f"Brake: {self.control.brake:.2f}")
                print(f"Steer: {self.control.steer:.2f}")
                print(f"Clutch: {self.control.clutch:.2f}")

            except Exception as e:
                print(f"Error in model prediction: {e}")
                self.set_safe_controls()
        else:
            print("Error extracting features")
            self.set_safe_controls()

        # Return control message using carControl's toMsg method
        return self.control.toMsg()

    def set_safe_controls(self):
        '''Set safe default control values'''
        # Get current values
        current_accel = self.control.accel if hasattr(self.control, 'accel') else 0
        current_brake = self.control.brake if hasattr(self.control, 'brake') else 0
        current_steer = self.control.steer if hasattr(self.control, 'steer') else 0
        current_clutch = self.control.clutch if hasattr(self.control, 'clutch') else 0
        current_focus = self.control.focus if hasattr(self.control, 'focus') else 0
        current_meta = self.control.meta if hasattr(self.control, 'meta') else 0

        # Gradually reduce values to safe defaults
        self.control.setAccel(float(np.clip(current_accel - 0.1, 0, 1)))
        self.control.setBrake(float(np.clip(current_brake + 0.1, 0, 1)))
        self.control.setSteer(float(np.clip(current_steer * 0.5, -1, 1)))
        self.control.setClutch(float(np.clip(current_clutch - 0.1, 0, 1)))
        self.control.setGear(1)  # Set gear directly to 1 for safety
        self.control.focus = current_focus + 0  # Add to current focus
        self.control.meta = current_meta + 0   # Add to current meta

    def extract_features(self):
        """
        Extracts the required features from the current car state.
        Returns a list of features in the correct order, or None if any are missing.
        """
        try:
            # Get sensor data using direct attribute access
            focus = self.state.focus if self.state.focus is not None else [-1]*5
            track = self.state.track if self.state.track is not None else [0]*19
            wheel = self.state.wheelSpinVel if self.state.wheelSpinVel is not None else [0]*4

            # Convert all values to float to ensure proper scaling
            feature_dict = {
                'angle': float(self.state.angle if self.state.angle is not None else 0),
                'distFromStart': float(self.state.distFromStart if self.state.distFromStart is not None else 0),
                'distRaced': float(self.state.distRaced if self.state.distRaced is not None else 0),
                'focus_0': float(focus[0]),
                'focus_1': float(focus[1]),
                'focus_2': float(focus[2]),
                'focus_3': float(focus[3]),
                'focus_4': float(focus[4]),
                'rpm': float(self.state.rpm if self.state.rpm is not None else 0),
                'speedX': float(self.state.speedX if self.state.speedX is not None else 0),
                'speedY': float(self.state.speedY if self.state.speedY is not None else 0),
                'speedZ': float(self.state.speedZ if self.state.speedZ is not None else 0),
                'trackPos': float(self.state.trackPos if self.state.trackPos is not None else 0),
                'track_0': float(track[0]),
                'track_1': float(track[1]),
                'track_2': float(track[2]),
                'track_3': float(track[3]),
                'track_4': float(track[4]),
                'track_5': float(track[5]),
                'track_6': float(track[6]),
                'track_7': float(track[7]),
                'track_8': float(track[8]),
                'track_9': float(track[9]),
                'track_10': float(track[10]),
                'track_11': float(track[11]),
                'track_12': float(track[12]),
                'track_13': float(track[13]),
                'track_14': float(track[14]),
                'track_15': float(track[15]),
                'track_16': float(track[16]),
                'track_17': float(track[17]),
                'track_18': float(track[18]),
                'wheelSpinVel_0': float(wheel[0]),
                'wheelSpinVel_1': float(wheel[1]),
                'wheelSpinVel_2': float(wheel[2]),
                'wheelSpinVel_3': float(wheel[3]),
                'z': float(self.state.z if self.state.z is not None else 0),
            }

            # Return features in the correct order
            return [feature_dict[k] for k in self.input_features]
        except Exception as e:
            print(f"Feature extraction error: {e}")
            return None

    def onShutDown(self):
        print('Client Shutdown')

    def onRestart(self):
        print('Client Restart')