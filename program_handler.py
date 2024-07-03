#program_handler.py
import json
from typing import List, Union
from datetime import datetime as dt, timedelta as td
import dataclasses
from dataclasses import dataclass, asdict
from enum import StrEnum

def get_hms(td: td):
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    remaining_seconds = total_seconds % 3600
    minutes = remaining_seconds // 60
    seconds = remaining_seconds % 60
    return hours, minutes, seconds

class StepTypeName(StrEnum):
    RAMP_BY_TIME = 'Ramp by Time'
    RAMP_BY_RATE = 'Ramp by Rate'
    SOAK = 'Soak'
    JUMP = 'Jump'
    END = 'End'

class EndActions(StrEnum):
    HOLD = 'Hold'
    CONTROL_OFF = 'Control Off'
    ALL_OFF = 'All Off'
    IDLE = 'Idle'

@dataclass
class RampTime:
    wait_for: bool
    event_output_states: List[bool]  # Event Output (1 to 8)
    duration: td
    ch1_temp_setpoint: int
    ch2_temp_setpoint: int
    ch1_pid_selection: int  # 1 to 5
    ch2_pid_selection: int  # 6 to 10
    guaranteed_soak_1: bool
    guaranteed_soak_2: bool
    type_enum = 1

@dataclass
class RampRate:
    wait_for: bool
    event_output_states: List[bool]  # Event Output (1 to 8)
    rate: float
    ch1_temp_setpoint: int
    ch1_pid_selection: int  # 1 to 5
    guaranteed_soak_1: bool
    type_enum = 2

@dataclass
class Soak:
    wait_for: bool
    event_output_states: List[bool]  # Event Output (1 to 8)
    duration: td
    ch1_pid_selection: int  # 1 to 5
    ch2_pid_selection: int  # 6 to 10
    guaranteed_soak_1: int
    guaranteed_soak_2: int
    type_enum = 3

@dataclass
class Jump:
    jump_to_profile: int  # 1 to 40
    jump_to_step: int
    number_of_repeats: int
    type_enum = 4

@dataclass
class End:
    end_action: int  # 0 to 3
    ch1_idle_setpoint: int
    ch2_idle_setpoint: int
    type_enum = 5

StepDetail = Union[RampTime, RampRate, Soak, Jump, End]

@dataclass
class Step:
    type_name: StepTypeName
    details: StepDetail

@dataclass
class Program:
    name: str
    steps: List[Step]

def timedelta_to_hours_minutes_seconds(timedelta: td):
    total_seconds = timedelta.total_seconds()
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    hours_combined = (days * 24) + hours
    return (int(hours_combined), int(minutes), int(seconds))

def total_seconds_to_timedelta(total_seconds:int) -> td:
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    return td(days=days, hours=hours, minutes=minutes, seconds=seconds)

def custom_encoder(obj):
    if dataclasses.is_dataclass(obj):
        return asdict(obj)
    elif isinstance(obj, dt):
        return obj.strftime('%H:%M:%S')
    elif isinstance(obj, td):
        return f'{obj.total_seconds():.0f}'
    elif isinstance(obj, StepTypeName):
        return obj.value
    raise TypeError(f"Type {type(obj).__name__} not serializable")

def dict_to_step_details(d, type_name: StepTypeName):
    if type_name == StepTypeName.RAMP_BY_TIME:
        return RampTime(
            wait_for=d.get('wait_for', False),
            event_output_states=d.get('event_output', [False] * 8),
            duration=total_seconds_to_timedelta(int(d.get('duration', 0))),
            ch1_temp_setpoint=d.get('ch1_temp_setpoint', 25),
            ch2_temp_setpoint=d.get('ch2_temp_setpoint', 25),
            ch1_pid_selection=d.get('ch1_pid_selection', 0),
            ch2_pid_selection=d.get('ch2_pid_selection', 0),
            guaranteed_soak_1=d.get('guaranteed_soak_1', False),
            guaranteed_soak_2=d.get('guaranteed_soak_2', False)
        )
    elif type_name == StepTypeName.RAMP_BY_RATE:
        return RampRate(
            wait_for=d.get('wait_for', False),
            event_output_states=d.get('event_output', [False] * 8),
            rate=d.get('rate', 0.0),
            ch1_temp_setpoint=d.get('ch1_temp_setpoint', 25),
            ch1_pid_selection=d.get('ch1_pid_selection', 0),
            guaranteed_soak_1=d.get('guaranteed_soak_1', False)
        )
    elif type_name == StepTypeName.SOAK:
        days, hours, minutes, seconds = map(int, d.get('time', '0:0:0:0').split(':'))
        total_seconds = days * 86400 + hours * 3600 + minutes * 60 + seconds
        return Soak(
            wait_for=d.get('wait_for', False),
            event_output_states=d.get('event_output', [False] * 8),
            duration=td(seconds=total_seconds),
            ch1_pid_selection=d.get('ch1_pid_selection', 0),
            ch2_pid_selection=d.get('ch2_pid_selection', 0),
            guaranteed_soak_1=d.get('guaranteed_soak_1', False),
            guaranteed_soak_2=d.get('guaranteed_soak_2', False)
        )
    elif type_name == StepTypeName.JUMP:
        return Jump(
            jump_to_profile=d.get('jump_to_profile', 1),
            jump_to_step=d.get('jump_to_step', 1),
            number_of_repeats=d.get('number_of_repeats', 1)
        )
    elif type_name == StepTypeName.END:
        return End(
            end_action=d.get('end_action', 0),
            ch1_idle_setpoint=d.get('ch1_idle_set_point', 0),
            ch2_idle_setpoint=d.get('ch2_idle_set_point', 0)
        )
    else:
        raise ValueError(f"Unknown step type: {type_name}")

def program_to_json(program: Program) -> str:
    return json.dumps(asdict(program), default=custom_encoder, indent=4)

def json_to_program(json_str: str) -> Program:
    data = json.loads(json_str)
    steps = [
        Step(
            type_name=StepTypeName(d['type_name']),
            details=dict_to_step_details(d['details'], StepTypeName(d['type_name']))
        )
        for d in data['steps']
    ]
    return Program(name=data['name'], steps=steps)

def write_program_to_file(program: Program, filename: str) -> None:
    with open(filename, 'w') as file:
        json_str = program_to_json(program)
        file.write(json_str)

def read_program_from_file(filename: str) -> Program:
    with open(filename, 'r') as file:
        json_str = file.read()
        return json_to_program(json_str)

if __name__ == "__main__":
    program = Program(
        name='Sample Program',
        steps=[
            Step(
                type_name=StepTypeName.RAMP_BY_TIME,
                details=RampTime(
                    wait_for=True,
                    event_output_states=[False] * 8,
                    duration=td(minutes=60),
                    ch1_temp_setpoint=100.0,
                    ch2_temp_setpoint=200.0,
                    ch1_pid_selection=1,
                    ch2_pid_selection=6,
                    guaranteed_soak_1=True,
                    guaranteed_soak_2=True
                )
            ),
            Step(
                type_name=StepTypeName.RAMP_BY_RATE,
                details=RampRate(
                    wait_for=True,
                    event_output_states=[False] * 8,
                    rate=5.0,
                    ch1_temp_setpoint=150.0,
                    ch1_pid_selection=2,
                    guaranteed_soak_1=True
                )
            ),
            Step(
                type_name=StepTypeName.SOAK,
                details=Soak(
                    wait_for=True,
                    event_output_states=[False] * 8,
                    duration=td(days=1, hours=5, minutes=30, seconds=15),
                    ch1_pid_selection=3,
                    ch2_pid_selection=7,
                    guaranteed_soak_1=4,
                    guaranteed_soak_2=5
                )
            ),
            Step(
                type_name=StepTypeName.JUMP,
                details=Jump(
                    jump_to_profile=10,
                    jump_to_step=5,
                    number_of_repeats=3
                )
            ),
            Step(
                type_name=StepTypeName.END,
                details=End(
                    end_action=1,
                    ch1_idle_setpoint=20.0,
                    ch2_idle_setpoint=25.0
                )
            )
        ]
    )

    write_program_to_file(program, 'program.json')

    new_program = read_program_from_file('program.json')
    print(new_program)
