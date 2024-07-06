import logging
import minimalmodbus
import serial.tools.list_ports

from watlow_f4_registers import WatlowF4Registers, profile_name_enum_dict
import program_handler as ph

class WatlowF4:
    def __init__(self, slave_address: int, com_port: str=None):
        self.slave_address = slave_address
        self.com_port = com_port
        self.instrument = None
        self.logger = self.setup_logger()

        self.find_and_connect(self.com_port)

    def setup_logger(self):
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler(f'{self.__class__.__name__}.log')
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def find_and_connect(self, com_port:str=None):
        if com_port:
            if self.try_port(com_port):
                return True
            raise Exception(f"Watlow F4 not found on {com_port}")
        else:
            ports = list(serial.tools.list_ports.comports())

            for port in ports:
                if self.try_port(port.device):
                    return True
                
            raise Exception("Watlow F4 not found on any available COM port")

    def try_port(self, com_port: str):
        try:
            self.logger.debug(f"Trying port: {com_port}")
            self.instrument = minimalmodbus.Instrument(com_port, self.slave_address)
            self.instrument.serial.baudrate = 9600
            self.instrument.serial.bytesize = 8
            self.instrument.serial.parity = minimalmodbus.serial.PARITY_NONE
            self.instrument.serial.stopbits = 1
            self.instrument.serial.timeout = 1

            # Try to read a register to confirm the connection
            self.read_register(100)
            self.logger.info(f"Found Watlow F4 on port: {com_port}")
            return True
        except Exception as e:
            self.logger.error(f"Error connecting to port {com_port}: {e}")
            return False

    def read_register(self, register: WatlowF4Registers):
        try:
            value = self.instrument.read_register(register)
            self.logger.debug(f"Read register {register}: {value}")
            return value
        except Exception as e:
            self.logger.error(f"Error reading register {register}: {e}")
            raise

    def set_temperature_setpoint(self, temperature: float):
        msb = int(temperature * 10) // 256
        lsb = int(temperature * 10) % 256
        try:
            self.instrument.write_register(WatlowF4Registers.VALUE_SET_POINT_1, msb * 256 + lsb)
            self.logger.info(f"Set static temperature setpoint to {temperature}C")
        except Exception as e:
            self.logger.error(f"Error setting temperature setpoint to {temperature}C: {e}")
            raise

    def set_event(self, event_number: int, state: int):
        register = 2000 + event_number * 10
        try:
            self.instrument.write_register(register, state)
            self.logger.info(f"Set event {event_number} to state {state}")
        except Exception as e:
            self.logger.error(f"Error setting event {event_number} to state {state}: {e}")
            raise
    
    #Profile and Configuration
    def save_changes_to_eeprom(self):
        try:
            self.instrument.write_register(WatlowF4Registers.SAVE_CHANGES_TO_EEPROM, 0)
            self.logger.info(f"EEPROM Saved")
        except Exception as e:
            self.logger.error(f"Error saving EEPROM: {e}")
            raise
    
    #select profile
    def select_profile(self, profile_number: int):
        try:
            self.instrument.write_register(WatlowF4Registers.PROFILE_NUMBER, profile_number)
            self.logger.info(f"Set selected profile to {profile_number}")
        except Exception as e:
            self.logger.error(f"Error selecting profile {profile_number}: {e}")
            raise

    def select_step(self, step_number: int):
        try:
            self.instrument.write_register(WatlowF4Registers.PROFILE_STEP_NUMBER, step_number)
            self.logger.info(f"Set selected step to {step_number}")
        except Exception as e:
            self.logger.error(f"Error selecting step {step_number}: {e}")
            raise

    def insert_step(self, step_number: int, step: ph.StepDetail):
        """
            Assumes the watlow has the desired profile selected already
            The command to save to EEPROM must be used to make changes permenant
        """
        self.select_step(step_number)

        try:
            #set to step to edit
            self.instrument.write_register(WatlowF4Registers.PROFILE_EDIT_ACTION, 2)
            self.logger.debug(f"Selected step for editing {step_number}")

            #configure step
            if type(step) == ph.RampTime:
                self.instrument.write_register(WatlowF4Registers.PROFILE_WAIT_FOR, int(step.wait_for))
                self.logger.debug(f"Set Wait For to {step.wait_for}")

                for idx, enabled_state in enumerate(step.event_output_states):
                    self.instrument.write_register(idx+WatlowF4Registers.PROFILE_EVENT_OUTPUT_1, enabled_state)
                self.logger.debug(f"Set Event Output {idx+1} to {enabled_state}")

                for idx, enabled_state in enumerate(step.event_output_states):
                    self.instrument.write_register(idx+WatlowF4Registers.PROFILE_EVENT_OUTPUT_1, enabled_state)
                self.logger.debug(f"Set Event Output {idx+1} to {enabled_state}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_RAMP_SETPOINT_CHANNEL_1, step.ch1_temp_setpoint)
                self.logger.debug(f"Set Channel 1  PID to {step.ch1_temp_setpoint}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_RAMP_SETPOINT_CHANNEL_2, step.ch2_temp_setpoint)
                self.logger.debug(f"Set Channel 2 PID to {step.ch2_temp_setpoint}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_PID_SET_CHANNEL_1, step.ch1_pid_selection)
                self.logger.debug(f"Set Channel 1  PID to {step.ch1_pid_selection}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_PID_SET_CHANNEL_2, step.ch2_pid_selection)
                self.logger.debug(f"Set Channel 2 PID to {step.ch2_pid_selection}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_GUARANTEED_SOAK_CHANNEL_1, int(step.guaranteed_soak_1))
                self.logger.debug(f"Set Channel 1  PID to {step.guaranteed_soak_1}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_GUARANTEED_SOAK_CHANNEL_2, int(step.guaranteed_soak_2))
                self.logger.debug(f"Set Channel 2 PID to {step.guaranteed_soak_2}")

            elif type(step) == ph.RampRate:
                self.instrument.write_register(WatlowF4Registers.PROFILE_STEP_TYPE, step.type_enum)
                self.logger.debug(f"set Step Type to {step.type_enum}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_WAIT_FOR, int(step.wait_for))
                self.logger.debug(f"Set Wait For to {step.wait_for}")

                for idx, enabled_state in enumerate(step.event_output_states):
                    self.instrument.write_register(idx+WatlowF4Registers.PROFILE_EVENT_OUTPUT_1, enabled_state)
                self.logger.debug(f"Set Event Output {idx+1} to {enabled_state}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_RATE_RAMP_RATE_STEP, step.rate)
                self.logger.debug(f"Set Ramp Rate to {step.rate}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_RAMP_SETPOINT_CHANNEL_1, step.ch1_temp_setpoint)
                self.logger.debug(f"Set Ramp Target to {step.ch1_temp_setpoint}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_PID_SET_CHANNEL_1, step.ch1_pid_selection)
                self.logger.debug(f"Set Channel PID to {step.ch1_pid_selection}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_GUARANTEED_SOAK_CHANNEL_1, int(step.guaranteed_soak_1))
                self.logger.debug(f"Set Guaranteed Soak to {step.guaranteed_soak_1}")

            elif type(step) == ph.Soak:
                self.instrument.write_register(WatlowF4Registers.PROFILE_STEP_TYPE, step.type_enum)
                self.logger.debug(f"set Step Type to {step.type_enum}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_WAIT_FOR, int(step.wait_for))
                self.logger.debug(f"Set Wait For to {step.wait_for}")

                for idx, enabled_state in enumerate(step.event_output_states):
                    self.instrument.write_register(idx+WatlowF4Registers.PROFILE_EVENT_OUTPUT_1, enabled_state)
                self.logger.debug(f"Set Event Output {idx+1} to {enabled_state}")

                soak_hours, soak_minutes, soak_seconds = ph.timedelta_to_hours_minutes_seconds(step.duration)
                self.instrument.write_register(WatlowF4Registers.PROFILE_SOAK_STEP_TIME_HOURS, soak_hours)
                self.logger.debug(f"Set soak time hours to {soak_hours}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_SOAK_STEP_TIME_MINUTES, soak_minutes)
                self.logger.debug(f"Set soak time hours to {soak_minutes}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_SOAK_STEP_TIME_SECONDS, soak_seconds)
                self.logger.debug(f"Set soak time hours to {soak_seconds}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_PID_SET_CHANNEL_1, step.ch1_pid_selection)
                self.logger.debug(f"Set Channel 1  PID to {step.ch1_pid_selection}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_PID_SET_CHANNEL_2, step.ch2_pid_selection)
                self.logger.debug(f"Set Channel 2 PID to {step.ch2_pid_selection}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_GUARANTEED_SOAK_CHANNEL_1, int(step.guaranteed_soak_1))
                self.logger.debug(f"Set Guaranteed Soak Channel 1 to {step.guaranteed_soak_1}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_GUARANTEED_SOAK_CHANNEL_2, int(step.guaranteed_soak_2))
                self.logger.debug(f"Set Guaranteed Soak Channel 2 to {step.guaranteed_soak_2}")

            elif type(step) == ph.Jump:
                self.instrument.write_register(WatlowF4Registers.PROFILE_STEP_TYPE, step.type_enum)
                self.logger.debug(f"set Step Type to {step.type_enum}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_JUMP_TO_PROFILE, step.jump_to_profile)
                self.logger.debug(f"set Step Type to {step.type_enum}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_JUMP_TO_STEP, step.jump_to_step)
                self.logger.debug(f"set Step Type to {step.type_enum}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_JUMP_REPEATS, step.number_of_repeats)
                self.logger.debug(f"set Step Type to {step.type_enum}")

            elif type(step) == ph.End:
                self.instrument.write_register(WatlowF4Registers.PROFILE_STEP_TYPE, step.type_enum)
                self.logger.debug(f"set Step Type to {step.type_enum}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_END_ACTION, step.end_action)
                self.logger.debug(f"set end step to to set {step.end_action}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_END_IDLE_SETPOINT_CHANNEL_1, step.ch1_idle_setpoint)
                self.logger.debug(f"set end step to to set {step.ch1_idle_setpoint}")
                
                self.instrument.write_register(WatlowF4Registers.PROFILE_END_IDLE_SETPOINT_CHANNEL_2, step.ch2_idle_setpoint)
                self.logger.debug(f"set end step to to set {step.ch2_idle_setpoint}")

            self.logger.debug(f"Successfully modified step {step_number}")
        except Exception as e:
            self.logger.error(f"Error editing step {step_number}: {e}")
            raise

    def set_profile_name(self, profile_name: str, profile_num: int = 40):
        now_register = profile_name_enum_dict[profile_num]
        for idx, char in enumerate(profile_name): 
            
            self.instrument.write_register(now_register, char.encode('ascii'))

            if idx % 10 == 0: #only 10 characters allowed per register, up to 10 registers per profile
                now_register = now_register + 1
        
        #terminate profile name
        self.instrument.write_register(WatlowF4Registers.SAVE_CHANGES_TO_EEPROM, 0)

        self.logger.debug(f"Successfully set profile name to {profile_name}")

    def delete_profile(self, profile_number: int):
        self.select_profile(profile_number)
        
        try:
            self.instrument.write_register(WatlowF4Registers.PROFILE_EDIT_ACTION, 3)
            self.logger.info(f"Profile deleted: {profile_number}")
        except Exception as e:
            self.logger.error(f"Error selecting profile {profile_number}: {e}")
            raise

        self.save_changes_to_eeprom()
    
    def run_profile(self, profile_number: int):
        self.select_profile(profile_number)
        self.select_step(1)

        try:
            self.instrument.write_register(WatlowF4Registers.PROFILE_EDIT_ACTION, 5)
            self.logger.info(f"Profile started: {profile_number}")
        except Exception as e:
            self.logger.error(f"Error starting profile: {e}")
            raise

    def configure_profile(self, program: ph.Program,  profile_num: int):
        self.select_profile(profile_num)
        
        self.set_profile_name(program.name)

        for i, step in enumerate(program):
            self.insert_step(i, step)

        self.save_changes_to_eeprom()