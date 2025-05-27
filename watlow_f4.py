import logging
from datetime import datetime as dt
import serial.tools.list_ports
from dataclasses import dataclass
from typing import Optional, Dict
from enum import StrEnum

import minimalmodbus

from watlow_f4_registers import WatlowF4Registers
import program_handler as ph

# PID Parameter Engineering Limits (derived from manual's Modbus value ranges and scaling)
@dataclass(frozen=True)
class ParamSpec:
    min: float
    max: float
    num_decimals: int

PB_ENG_PARAM = ParamSpec(0, 30000, 0)
INTEGRAL_SI_ENG_PARAM = ParamSpec(0.00, 300.00, 2)
DERIVATIVE_SI_ENG_PARAM = ParamSpec(0.00, 9.99, 2)
RESET_US_ENG_PARAM = ParamSpec(0.00, 99.99, 2)
RATE_US_ENG_PARAM = ParamSpec(0, 9.99, 2)
DB_ENG_PARAM = ParamSpec(0, 30000, 0)
HYST_ENG_PARAM = ParamSpec(1, 30000, 0)

class OutputSidesEnum(StrEnum):
    A = 'A'
    B = 'B'

@dataclass
class PIDParameters:
    proportional_band: float
    dead_band: float
    hysteresis: float
    integral: Optional[float] = None
    derivative: Optional[float] = None
    reset: Optional[float] = None
    rate: Optional[float] = None

class WatlowF4:
    def __init__(self, slave_address: int, com_port: str = None):
        self.slave_address = slave_address
        self.com_port = com_port
        self.instrument = None
        self.logger = self.setup_logger()
        self.find_and_connect(self.com_port)

    def setup_logger(self):
        logger = logging.getLogger(self.__class__.__name__)
        if not logger.handlers:
            logger.setLevel(logging.DEBUG)
            handler = logging.StreamHandler() # Changed to StreamHandler for console output
            # handler = logging.FileHandler(f'{self.__class__.__name__}.log', mode='w')
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger

    def find_and_connect(self, com_port: str = None):
        if self.instrument and self.instrument.serial.is_open:
            self.logger.info(f"Already connected to Watlow F4 on {self.instrument.serial.port}")
            return True
        
        if com_port:
            if self.try_port(com_port):
                return True
            self.logger.critical(f"Watlow F4 not found on specified port {com_port}")
            raise ConnectionError(f"Watlow F4 not found on {com_port}")
        else:
            ports = list(serial.tools.list_ports.comports())
            if not ports:
                self.logger.critical("No COM ports found on this system.")
                raise ConnectionError("No COM ports found.")
            for port_info in ports:
                if self.try_port(port_info.device):
                    return True
            self.logger.critical("Watlow F4 not found on any available COM port.")
            raise ConnectionError("Watlow F4 not found on any available COM port")

    def try_port(self, com_port: str) -> bool:
        try:
            self.logger.debug(f"Trying port: {com_port}")
            self.instrument = minimalmodbus.Instrument(com_port, self.slave_address)
            self.instrument.serial.baudrate = 9600
            self.instrument.serial.bytesize = 8
            self.instrument.serial.parity = minimalmodbus.serial.PARITY_NONE
            self.instrument.serial.stopbits = 1
            self.instrument.serial.timeout = 1  # seconds
            self.instrument.mode = minimalmodbus.MODE_RTU
            self.instrument.clear_buffers_before_each_transaction = True

            # Try to read a common register to confirm the connection
            # Reading Input 1 Value (register 100, scaled by 10 from manual)
            temp_reg_val = self.instrument.read_register(WatlowF4Registers.STATUS_INPUT_1_VALUE.value, number_of_decimals=1)
            self.logger.info(f"Successfully connected to Watlow F4 on port: {com_port}. Input 1 raw: {temp_reg_val}")
            self.com_port = com_port 
            return True
        except minimalmodbus.NoResponseError:
            self.logger.warning(f"No response from Watlow F4 on port {com_port}.")
            if self.instrument and self.instrument.serial:
                self.instrument.serial.close()
            self.instrument = None
            return False
        except Exception as e:
            self.logger.error(f"Error connecting to Watlow F4 on port {com_port}: {e}")
            if self.instrument and self.instrument.serial:
                self.instrument.serial.close()
            self.instrument = None
            return False

    def read_register(self, register: WatlowF4Registers, number_of_decimals: int = 0, functioncode: int = 3, signed: bool = False) -> int | float:
        if not self.instrument or not self.instrument.serial.is_open:
            self.logger.error("Not connected to Watlow F4. Call find_and_connect() first.")
            raise ConnectionError("Not connected to Watlow F4.")
        try:
            # Use .value for IntEnum members when passing to minimalmodbus
            value = self.instrument.read_register(
                registeraddress=register.value, 
                number_of_decimals=number_of_decimals,
                functioncode=functioncode,
                signed=signed
            )
            self.logger.debug(f"Read register {register.name} ({register.value}): {value}")
            return value
        except Exception as e:
            self.logger.error(f"Error reading register {register.name} ({register.value}): {e}")
            raise
    
    def write_register(self, register: WatlowF4Registers, value: int | float, number_of_decimals: int = 0, functioncode: int = 16) -> None:
        if not self.instrument or not self.instrument.serial.is_open:
            self.logger.error("Not connected to Watlow F4. Call find_and_connect() first.")
            raise ConnectionError("Not connected to Watlow F4.")
        try:
            # Use .value for IntEnum members
            self.instrument.write_register(
                registeraddress=register.value,
                value=value,
                number_of_decimals=number_of_decimals,
                functioncode=functioncode,
                signed=False 
            )
            self.logger.debug(f"Wrote to register {register.name} ({register.value}): {value} (decimals: {number_of_decimals})")
        except Exception as e:
            self.logger.error(f"Error writing to register {register.name} ({register.value}) with value {value}: {e}")
            raise

    def read_temperature(self) -> float:
        temp = self.read_register(WatlowF4Registers.STATUS_INPUT_1_VALUE, number_of_decimals=1)
        self.logger.info(f"Read Temperature (Input 1): {temp}°")
        return float(temp)

    def set_temperature_setpoint(self, temperature: float):
        self.write_register(WatlowF4Registers.VALUE_SET_POINT_1, temperature, number_of_decimals=1)
        self.logger.info(f"Set static temperature setpoint (SP1) to {temperature}°")
        self.save_changes_to_eeprom()
    
    def get_pid_units_mode(self) -> str:
        value = self.read_register(WatlowF4Registers.SYSTEM_PID_UNITS)
        if value == 1: # 1 is SI according to manual pg 7-7
            self.logger.info("PID Units Mode: SI (Integral/Derivative)")
            return "SI"
        else: # 0 (or other) is US
            self.logger.info("PID Units Mode: US (Reset/Rate)")
            return "US"

    def _get_pid_registers(self, pid_set_number: int, channel: int, output_side: OutputSidesEnum = OutputSidesEnum.A) -> tuple[WatlowF4Registers, ...]:
        prefix = f"PID_CHANNEL_{channel}{output_side}_SET_{pid_set_number}_"
        suffixes = [
            "PROPORTIONAL_BAND", "INTEGRAL", "RESET",
            "DERIVATIVE", "RATE", "DEAD_BAND", "HYSTERESIS"
        ]

        try:
            return tuple(
                getattr(WatlowF4Registers, prefix + suffix)
                for suffix in suffixes
            )
        except AttributeError as e:
            raise ValueError(f"Invalid register combination: {e}")

    def read_pid_parameters(self, pid_set_number: int = 1, channel: int = 1, output_side: OutputSidesEnum = OutputSidesEnum.A) -> PIDParameters:
        self.logger.info(f"Reading PID parameters for Set {pid_set_number}, Ch{channel}, Side {output_side}")
        
        regs = self._get_pid_registers(pid_set_number, channel, output_side)
        reg_pb, reg_int_si, reg_rst_us, reg_der_si, reg_rte_us, reg_db, reg_hyst = regs

        pb = float(self.read_register(reg_pb, number_of_decimals=0))
        db = float(self.read_register(reg_db, number_of_decimals=0))
        hyst = float(self.read_register(reg_hyst, number_of_decimals=0))

        pid_units_mode = self.get_pid_units_mode()
        if pid_units_mode == "SI":
            integral = float(self.read_register(reg_int_si, number_of_decimals=2))
            derivative = float(self.read_register(reg_der_si, number_of_decimals=2))
            result = PIDParameters(proportional_band=pb, integral=integral, derivative=derivative, dead_band=db, hysteresis=hyst)
        else:
            reset = float(self.read_register(reg_rst_us, number_of_decimals=2))
            rate = float(self.read_register(reg_rte_us, number_of_decimals=2))
            result = PIDParameters(proportional_band=pb, reset=reset, rate=rate, dead_band=db, hysteresis=hyst)

        self.logger.info(f"Successfully read PID parameters: {result}")
        return result

    def write_pid_parameters(
        self,
        pid_params: PIDParameters,
        pid_set_number: int = 1,
        channel: int = 1,
        output_side: OutputSidesEnum = OutputSidesEnum.A,
    ) -> None:
        self.logger.info(
            f"Attempting to write PID for Set {pid_set_number}, Ch{channel}, Side {output_side}: {pid_params}"
        )

        regs = self._get_pid_registers(pid_set_number, channel, output_side)
        reg_pb, reg_int_si, reg_rst_us, reg_der_si, reg_rte_us, reg_db, reg_hyst = regs

        pid_units_mode = self.get_pid_units_mode()

        pb_val = float(pid_params.proportional_band)
        if pb_val < PB_ENG_PARAM.min:
            self.logger.warning(f"PB {pb_val} < min {PB_ENG_PARAM.min}. Clamping.")
            pb_val = PB_ENG_PARAM.min
        elif pb_val > PB_ENG_PARAM.max:
            self.logger.warning(f"PB {pb_val} > max {PB_ENG_PARAM.max}. Clamping.")
            pb_val = PB_ENG_PARAM.max
        self.write_register(reg_pb, int(round(pb_val)), number_of_decimals=PB_ENG_PARAM.num_decimals)

        if pid_units_mode == "SI":
            if pid_params.integral is not None:
                val = float(pid_params.integral)
                if val < INTEGRAL_SI_ENG_PARAM.min:
                    self.logger.warning(f"Integral {val} < min {INTEGRAL_SI_ENG_PARAM.min}. Clamping.")
                    val = INTEGRAL_SI_ENG_PARAM.min
                if val > INTEGRAL_SI_ENG_PARAM.max:
                    self.logger.warning(f"Integral {val} > max {INTEGRAL_SI_ENG_PARAM.max}. Clamping.")
                    val = INTEGRAL_SI_ENG_PARAM.max
                self.write_register(reg_int_si, val, number_of_decimals=INTEGRAL_SI_ENG_PARAM.num_decimals)

            if pid_params.derivative is not None:
                val = float(pid_params.reset)
                if val < DERIVATIVE_SI_ENG_PARAM.min:
                    self.logger.warning(f"Derivative {val} < min {DERIVATIVE_SI_ENG_PARAM.min}. Clamping.")
                    val = DERIVATIVE_SI_ENG_PARAM.min
                if val > DERIVATIVE_SI_ENG_PARAM.max:
                    self.logger.warning(f"Derivative {val} > max {DERIVATIVE_SI_ENG_PARAM.max}. Clamping.")
                    val = DERIVATIVE_SI_ENG_PARAM.max
                self.write_register(reg_rst_us, val, number_of_decimals=DERIVATIVE_SI_ENG_PARAM.num_decimals)

        else:  # US units
            if pid_params.reset is not None:
                val = float(pid_params.derivative)
                if val < RESET_US_ENG_PARAM.min:
                    self.logger.warning(f"Reset {val} < min {RESET_US_ENG_PARAM.min}. Clamping.")
                    val = RESET_US_ENG_PARAM.min
                if val > RESET_US_ENG_PARAM.max:
                    self.logger.warning(f"Reset {val} > max {RESET_US_ENG_PARAM.max}. Clamping.")
                    val = RESET_US_ENG_PARAM.max
                self.write_register(reg_der_si, val, number_of_decimals=RESET_US_ENG_PARAM.num_decimals)

            if pid_params.rate is not None:
                val = float(pid_params.rate)
                if val < RATE_US_ENG_PARAM.min:
                    self.logger.warning(f"Rate {val} < min {RATE_US_ENG_PARAM.min}. Clamping.")
                    val = RATE_US_ENG_PARAM.min
                if val > RATE_US_ENG_PARAM.max:
                    self.logger.warning(f"Rate {val} > max {RATE_US_ENG_PARAM.max}. Clamping.")
                    val = RATE_US_ENG_PARAM.max
                self.write_register(reg_rte_us, val, number_of_decimals=RATE_US_ENG_PARAM.num_decimals)

        if pid_params.dead_band is not None:
            val = float(pid_params.dead_band)
            if val < DB_ENG_PARAM.min:
                self.logger.warning(f"DeadBand {val} < min {DB_ENG_PARAM.min}. Clamping.")
                val = DB_ENG_PARAM.min
            if val > DB_ENG_PARAM.max:
                self.logger.warning(f"DeadBand {val} > max {DB_ENG_PARAM.max}. Clamping.")
                val = DB_ENG_PARAM.max
            self.write_register(reg_db, int(round(val)), number_of_decimals=DB_ENG_PARAM.num_decimals)

        if pid_params.hysteresis is not None:
            if int(round(pb_val)) == 0:
                val = float(pid_params.hysteresis)
                if val < HYST_ENG_PARAM.min:
                    self.logger.warning(f"Hysteresis {val} < min {HYST_ENG_PARAM.min}. Clamping.")
                    val = HYST_ENG_PARAM.min
                if val > HYST_ENG_PARAM.max:
                    self.logger.warning(f"Hysteresis {val} > max {HYST_ENG_PARAM.max}. Clamping.")
                    val = HYST_ENG_PARAM.max
                self.write_register(reg_hyst, int(round(val)), number_of_decimals=HYST_ENG_PARAM.num_decimals)
            else:
                self.logger.info(f"Hysteresis ({pid_params.hysteresis}) provided but not written as PB is not 0.")

        self.save_changes_to_eeprom()
        self.logger.info(
            f"PID parameters written and saved for Set {pid_set_number}, Ch{channel}, Side {output_side}."
        )

    def save_changes_to_eeprom(self):
        try:
            self.write_register(WatlowF4Registers.SAVE_CHANGES_TO_EEPROM, 0) 
            self.logger.info("SAVE_CHANGES_TO_EEPROM command sent.")
        except Exception as e:
            self.logger.error(f"Error sending SAVE_CHANGES_TO_EEPROM command: {e}")

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
            if type(step) is ph.RampTime:
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
                self.logger.debug(f"set end action to set to {step.end_action}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_END_IDLE_SETPOINT_CHANNEL_1, step.ch1_idle_setpoint)
                self.logger.debug(f"set channel 1 idle temperature setpoint set to {step.ch1_idle_setpoint}")
                
                self.instrument.write_register(WatlowF4Registers.PROFILE_END_IDLE_SETPOINT_CHANNEL_2, step.ch2_idle_setpoint)
                self.logger.debug(f"set channel 2 idle temperature setpoint set to {step.ch2_idle_setpoint}")
            
            elif type(step) == ph.Autostart:
                self.instrument.write_register(WatlowF4Registers.PROFILE_STEP_TYPE, step.type_enum)
                self.logger.debug(f"set Step Type to {step.type_enum}")

                #set for date vs autostart check
                self.instrument.write_register(WatlowF4Registers.PROFILE_AUTOSTART_DATE_OR_DAY, 0)
                self.logger.debug(f"set autostart date or day {'date' if 0 == 0 else 'day'}")

                # set the date to now
                now = dt.now()
                self.instrument.write_register(WatlowF4Registers.PROFILE_AUTOSTART_DATE_MONTH, now.month)
                self.logger.debug(f"set autostart month to {now}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_AUTOSTART_DATE_DAY, now.day)
                self.logger.debug(f"set autostart day to {now}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_AUTOSTART_DATE_YEAR, now.year)
                self.logger.debug(f"set autostart year to {now}")

                #day of week
                self.instrument.write_register(WatlowF4Registers.PROFILE_AUTOSTART_DAY_OF_WEEK, step.start_day)
                self.logger.debug(f"set start day to to set {step.start_day}")

                #start time
                start_hours, start_minutes, start_seconds = ph.timedelta_to_hours_minutes_seconds(step.start_time)
                self.instrument.write_register(WatlowF4Registers.PROFILE_AUTOSTART_TIME_HOURS, start_hours)
                self.logger.debug(f"Set autostart hours to {start_hours}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_AUTOSTART_TIME_MINUTES, start_minutes)
                self.logger.debug(f"Set autostart minutes to {start_minutes}")

                self.instrument.write_register(WatlowF4Registers.PROFILE_AUTOSTART_TIME_SECONDS, start_seconds)
                self.logger.debug(f"Set autostart seconds to {start_seconds}")

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

    def clear_profile(self, profile_number: int):
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


# Example Usage (ensure this is run only when testing the module directly)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    controller = None
    try:
        print("Attempting to connect to Watlow F4...")
        # To run this example, you might need to specify the COM port if auto-detection fails
        # For example: controller = WatlowF4(slave_address=1, com_port='COM3')
        controller = WatlowF4(slave_address=1) 
        print(f"Connected to Watlow F4 on {controller.com_port}")

        print("\nReading current PID parameters for PID Set 1, Ch1 Heat (Side A)...")
        initial_pids = controller.read_pid_parameters(pid_set_number=1, channel=1, output_side='A')
        print(f"Initial PIDs (Set 1, Ch1 A): {initial_pids}")

        print("\nTesting write_pid_parameters with clamping...")
        # Values designed to test clamping
        pb_test = PB_ENG_PARAM.max + 1000   # Above max
        ir_test_si = INTEGRAL_SI_ENG_PARAM.max - 1.0 # Below min
        dr_test_si = DERIVATIVE_SI_ENG_PARAM.max + 1.0 # Above max
        db_test = DB_ENG_PARAM.max + 500 # Above max
        hyst_test = 0 # Below min for hysteresis

        # Assume SI units for this test write
        if controller.get_pid_units_mode() != "SI":
            print("WARNING: Controller not in SI mode, test values for I/D might not be ideal but clamping will be based on SI limits in this example section if not careful")
        
        controller.write_pid_parameters(
            proportional_band=pb_test, 
            integral_or_reset=ir_test_si,  # Test with SI integral
            derivative_or_rate=dr_test_si, # Test with SI derivative
            dead_band=db_test,
            hysteresis=hyst_test, # Test hysteresis (will only be written if pb_test clamps to 0)
            pid_set_number=1, 
            channel=1, 
            output_side='A'
        )
        
        print("\nReading PID parameters after writing with clamping...")
        clamped_pids = controller.read_pid_parameters(pid_set_number=1, channel=1, output_side='A')
        print(f"Clamped PIDs (Set 1, Ch1 A): {clamped_pids}")

        # Test restoring reasonable values
        print("\nRestoring reasonable PID values...")
        controller.write_pid_parameters(
            proportional_band=25.0, 
            integral_or_reset=0.5, 
            derivative_or_rate=0.1,
            dead_band=0.0,
            hysteresis=5.0, # Will not be written if PB is not 0
            pid_set_number=1, 
            channel=1, 
            output_side='A'
        )
        restored_pids = controller.read_pid_parameters(pid_set_number=1, channel=1, output_side='A')
        print(f"Restored PIDs (Set 1, Ch1 A): {restored_pids}")


    except ConnectionError as ce:
        print(f"Connection Error: {ce}")
    except minimalmodbus.ModbusException as me:
        print(f"Modbus Error: {me}")
    except Exception as e:
        import traceback
        print(f"An unexpected error occurred in __main__: {e}")
        print(traceback.format_exc())
    finally:
        if controller and controller.instrument and controller.instrument.serial and controller.instrument.serial.is_open:
            controller.instrument.serial.close()
            print("Serial port closed.")