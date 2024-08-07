import os
from datetime import timedelta as td
from datetime import datetime as dt
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import winsound
import serial.tools.list_ports
import webbrowser

import program_handler as ph
import watlow_f4

# Constants
FILE_DIRECTORY = os.path.join(os.getcwd(), 'watlow_programs')
FILE_EXTENSION = '.csv'
HEADER = ['step_type']
DEFAULT_COLOR = 'white'
ERROR_COLOR = 'red'

BASE_TITLE = "Watlow F4 Program Editor"

if not os.path.exists(FILE_DIRECTORY):
    os.makedirs(FILE_DIRECTORY)

class ProgramEditor:
    program = ph.Program(name="New Program", steps=[])
    step_detail_frames:list[tk.Frame] = []
    event_output_vars:list[tk.BooleanVar] = []
    guaranteed_soak_vars:list[tk.BooleanVar] = []
    channel_temp_setpoint_vars:list[tk.IntVar] = []
    ch_pid_selection_comboboxes:list[ttk.Combobox] = []
    ramp_rate_var:tk.StringVar = None
    time_vars:list[tk.IntVar] = []
    jump_vars:list[tk.IntVar] = []
    end_action_vars:list[tk.IntVar] = []
    date_vars :list[tk.IntVar] = []
    autostart_date_or_day_combobox :ttk.Combobox = None
    autostart_start_day_combobox :ttk.Combobox = None
    current_selected_item = None #current selected item in tree
    do_not_update:bool = False #prevents loading step after deletions and when first file open

    def __init__(self, root):
        self.root = root
        self.root.title(BASE_TITLE)
        self.root.geometry("520x600")  # Adjusted size for the combined view
        self.root.resizable(False, False)

        self.create_app_widgets()
        self.new_file()

    def create_app_widgets(self):
        tree_frame = tk.Frame(self.root)
        tree_frame.pack(side='left', fill='both', expand=True)

        # Treeview
        self.tree = ttk.Treeview(tree_frame, columns=('step', 'step_type'), show='headings')
        self.tree.heading('step', text='Step')
        self.tree.heading('step_type', text='Step Type')

        self.tree.column('step', width=5 * 10, anchor='center') 
        self.tree.column('step_type', width=12 * 10, anchor='center')  

        self.tree.pack(side='left', fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', self.on_treeview_select)

        # Setup Vertical Scrollbar
        self.scrollbar = tk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview, width=20)
        self.scrollbar.pack(side='right', fill='y', expand=False)
        self.tree.configure(yscrollcommand=self.scrollbar.set)

        # Setup detail section
        detail_frame = tk.Frame(self.root)
        detail_frame.pack(side='right', fill='both', expand=False, padx=0, pady=5)

        detail_frame.grid_rowconfigure(0, weight=0)
        detail_frame.grid_rowconfigure(1, weight=0)
        detail_frame.grid_rowconfigure(2, weight=0)
        detail_frame.grid_rowconfigure(3, weight=1) #causes the buttons to go to the bottom
        detail_frame.grid_rowconfigure(4, weight=0)
        detail_frame.grid_columnconfigure(0, weight=1)
        detail_frame.grid_columnconfigure(1, weight=1)

        self.detail_label = tk.Label(detail_frame, text="Step Details")
        self.detail_label.grid(row=0, column=0, pady=0, columnspan=2)

        #setup step type dropdown
        step_type_dropdown_frame = tk.Frame(detail_frame)
        step_type_dropdown_frame.grid(row=1, column=0, columnspan=2, pady=5, sticky='ew')
        step_type_dropdown_frame.grid_columnconfigure(0, weight=1)
        
        step_type_label = tk.Label(step_type_dropdown_frame, text="Step Type:", anchor='center')
        step_type_label.grid(row=0, column=0, padx=5, pady=5, sticky='ew')
        
        self.step_type_dropdown = ttk.Combobox(step_type_dropdown_frame,
                                                values=[step_type.value for step_type in ph.StepTypeName if 
                                                        step_type not in [ph.StepTypeName.END]], 
                                                state="readonly")
        self.step_type_dropdown.grid(row=1, column=0, padx=20, pady=5, sticky='ew')
        self.step_type_dropdown.bind("<<ComboboxSelected>>", self.on_step_type_selected)
        self.step_type_dropdown.set(ph.StepTypeName.END.value)

        # Setup step_options section
        self.step_options_frame = tk.Frame(detail_frame)
        self.step_options_frame.grid(row=2, column=0, columnspan=2, sticky='nsew', padx=0, pady=0)

        self.step_options_frame.grid_rowconfigure(0, weight=0)
        self.step_options_frame.grid_rowconfigure(1, weight=0)
        self.step_options_frame.grid_rowconfigure(2, weight=1)
        self.step_options_frame.grid_columnconfigure(0, weight=1)
        self.step_options_frame.grid_columnconfigure(1, weight=1)

        #bottom buttons
        self.add_button = tk.Button(detail_frame, text="Add Step", command=self.add_step)
        self.add_button.grid(row=3, column=0, pady=0, sticky='ews')

        self.update_button = tk.Button(detail_frame, text="Update Step", command=self.update_step)
        self.update_button.grid(row=3, column=1, pady=0, sticky='ews')

        self.remove_button = tk.Button(detail_frame, text="Remove Step", command=self.remove_step)
        self.remove_button.grid(row=4, column=0, columnspan=2, pady=0, sticky='ews')

        # Setup Menu
        self.menu = tk.Menu(self.root)
        self.root.config(menu=self.menu)

        self.file_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="New", command=self.new_file)
        self.file_menu.add_command(label="Open", command=self.open_file)
        self.file_menu.add_command(label="Save", command=self.save_file)

        self.menu.add_separator() 
        self.menu.add_command(label="Load Program", command=self.open_load_to_watlow_dialog)
        self.menu.add_separator() 
        self.menu.add_command(label="Help", command=self.show_help)  # Direct command to show help

        self.step_type_dropdown.event_generate("<<ComboboxSelected>>") # Build first step in step options

    def create_entry_widget(self, parent_frame:tk.Frame, label_text:str, initial_value=0, validation_limits:tuple = None, horizontal:bool=True) -> tuple[tk.Frame, tk.IntVar]:
        frame = tk.Frame(parent_frame)

        label = tk.Label(frame, text=label_text, anchor='center')

        var = tk.IntVar(value=initial_value)
        entry = tk.Entry(frame, textvariable=var, width=5)

        if horizontal:
            label.grid(row=0, column=0, padx=10, pady=5, sticky='e')
            entry.grid(row=0, column=1, padx=5, pady=5, sticky='e')
            frame.grid_columnconfigure(0, weight=1)
            frame.grid_columnconfigure(1, weight=0)
        else:
            label = tk.Label(frame, text=label_text, anchor='center')

            var = tk.IntVar(value=initial_value)
            entry = tk.Entry(frame, textvariable=var, width=5)
            
            label.grid(row=0, column=0, padx=0, pady=5, sticky='w')
            entry.grid(row=1, column=0, padx=0, pady=5, sticky='e')
            frame.grid_rowconfigure(0, weight=0)
            frame.grid_rowconfigure(1, weight=0)

        if validation_limits:
            limit_lo, limit_hi = validation_limits[0], validation_limits[1]
        entry.bind('<KeyRelease>', lambda event: self.update_buttons_state(entry, limit_lo, limit_hi, event))

        return frame, var 

    def validate_entry(self, entry:tk.Entry, value:int, limit_lo:int, limit_hi:int):
        valid = True

        try:
            if not (limit_lo <= float(value) <= limit_hi):
                valid = False
        except (ValueError, TypeError):
            valid = False

        if not valid:
            entry.config(bg=ERROR_COLOR)
        else:
            entry.config(bg=DEFAULT_COLOR)
            
        return valid

    def create_ramp_rate_entry_widget(self, parent_frame:tk.Frame) -> tk.Frame:
        frame = tk.Frame(parent_frame)
        frame.grid(row=len(self.step_detail_frames)+1, column=0, columnspan=2, padx=0, pady=5, sticky='e')   
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=0)
        
        self.step_detail_frames.append(frame)

        frame_entry, self.ramp_rate_var = self.create_entry_widget(frame, "Deg C per Minute: ", 2, validation_limits=(0.1, 3000))
        frame_entry.grid(row=0, column=0, columnspan=2, pady=5, padx=6, sticky='we')

        return frame
 
    def create_combobox_widget(self, parent_frame:tk.Frame, values:list, label_name:str) -> tuple[tk.Frame, ttk.Combobox]:
        frame = tk.Frame(parent_frame)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)

        label = tk.Label(frame, text=label_name, anchor='center')
        label.grid(row=0, column=0, padx=5, pady=5, sticky='e')

        combobox = ttk.Combobox(frame, values=list(values), state="readonly", width=2)
        combobox.grid(row=0, column=1, padx=5, pady=5, sticky='e')
        combobox.current(0)

        return frame, combobox

    def create_event_output_widgets(self, parent_frame:tk.Frame):
        frame = tk.Frame(parent_frame)
        frame.grid(row=len(self.step_detail_frames)+1, column=0, columnspan=2, padx=15, pady=5, sticky='e')
        
        self.step_detail_frames.append(frame)

        for i in range(4):
            frame.grid_columnconfigure(i, weight=0)

        tk.Label(frame, text="Wait for Event Output(s)", anchor='center').grid(row=0, columnspan=4)

        self.event_output_vars = []  # Clear the list before creating new checkboxes
        for i in range(8):
            var = tk.BooleanVar(value=False)
            self.event_output_vars.append(var)

            check_button = tk.Checkbutton(frame, text=str(i+1), variable=var)
            check_button.grid(row=i//4+1, column=i%4, padx=1, pady=2)

    def get_event_output_states(self) -> tuple[bool, list[bool]]:
        event_output_states = [checkbox_var.get() for checkbox_var in self.event_output_vars]
        return any(event_output_states), event_output_states

    def create_grouped_entry_widgets(self, parent_frame:tk.Frame, label_name:str, vars_list:list, entry_params:list[tuple[str, tuple[int, int]]]):
        frame = tk.Frame(parent_frame)
        frame.grid(row=len(self.step_detail_frames)+1, column=0, columnspan=2, padx=20, pady=2, sticky='e')
        for i in range(3):
            frame.grid_columnconfigure(i, weight=0)
        
        self.step_detail_frames.append(frame)

        if label_name:
            tk.Label(frame, text=label_name, anchor='center').grid(row=0, columnspan=3, pady=0)

        for idx, param in enumerate(entry_params):
            frame_entry, var = self.create_entry_widget(frame, param[0], param[1][0], 
                                                validation_limits=param[1], horizontal=False)
            frame_entry.grid(row=1, column=idx, pady=0, sticky='ew', padx=0)
            vars_list.append(var)

    def get_time_entries_timedelta(self) -> td:
        hours = int(self.time_vars[0].get())
        minutes = int(self.time_vars[1].get())
        seconds = int(self.time_vars[2].get())

        if seconds >= 60:
            minutes += seconds // 60
            seconds = seconds % 60

        if minutes >= 60:
            hours += minutes // 60
            hours = hours if hours <= 99 else 99 #limit hours to 99

            minutes = minutes % 60

        return td(hours=hours, 
                minutes=minutes, 
                seconds=seconds)

    def create_channel_temp_setpoint_widgets(self, parent_frame:tk.Frame, widget_count:int) -> tk.Frame:
        frame = tk.Frame(parent_frame)
        frame.grid(row=len(self.step_detail_frames)+1, column=0, padx=7, pady=5, sticky='ew', columnspan=2)
        for i in range(2):
            frame.grid_columnconfigure(i, weight=1)
        
        self.step_detail_frames.append(frame)

        self.channel_temp_setpoint_vars = []  # Clear the list before creating new entries
        for i in range(1, widget_count+1):
            frame, var = self.create_entry_widget(frame, f"Ch {i} Setpoint (C):", 25, validation_limits=(1, 200))
            frame.grid(row=i, column=0, columnspan=2, pady=5, sticky='we')
            self.channel_temp_setpoint_vars.append(var)

        return frame
    
    def create_channel_pid_selection_widgets(self, parent_frame:tk.Frame, widget_count:int) -> tk.Frame:
        frame = tk.Frame(parent_frame)
        frame.grid(row=len(self.step_detail_frames)+1, column=0, padx=5, pady=5, sticky='ew', columnspan=2)
        for i in range(2):
            frame.grid_columnconfigure(i, weight=1)
        
        self.step_detail_frames.append(frame)

        self.ch_pid_selection_comboboxes = []  # Clear the list before creating new comboboxes
        for i in range(1, widget_count+1):
            label = tk.Label(frame, text=f"Ch {i} PID Selection:", anchor='center')
            label.grid(row=i, column=0, padx=5, pady=5, sticky='e')

            start_value = 5 * (i - 1) + 1

            combobox = ttk.Combobox(frame, values=[x for x in range(start_value, start_value + 5)], state="readonly", width=2)
            combobox.grid(row=i, column=1, padx=5, pady=5, sticky='e')
            combobox.current(0)
            self.ch_pid_selection_comboboxes.append(combobox)

        return frame

    def create_guaranteed_soak_widgets(self, parent_frame:tk.Frame, widget_count:int) -> tk.Frame:
        frame = tk.Frame(parent_frame)
        frame.grid(row=len(self.step_detail_frames)+1, column=0, columnspan=2, padx=0, pady=5, sticky='ew')
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=0)

        self.step_detail_frames.append(frame)

        self.guaranteed_soak_vars = []  # Clear the list before creating new checkboxes
        for i in range(1, widget_count+1):
            label = tk.Label(frame, text=f"Guarantee Soak {i}:", anchor='center')
            label.grid(row=i, column=0, padx=13, pady=0, sticky='e')

            var = tk.BooleanVar(value=False)
            self.guaranteed_soak_vars.append(var)

            check_button = tk.Checkbutton(frame, variable=var)
            check_button.grid(row=i, column=1, padx=10, pady=0, sticky='we')

        return frame

    def on_step_type_selected(self, event):
        step_type_name = self.step_type_dropdown.get()
        self.create_detail_widgets(step_type_name)

        if self.current_selected_item:
            if self.tree.item(self.current_selected_item, 'values')[-1] != ph.StepTypeName.END.value: #prevent from updating END step
                self.update_button.config(state='disabled')

    def create_detail_widgets(self, step_type_name:ph.StepTypeName):
        for widget in self.step_options_frame.winfo_children():
            widget.destroy()

        for i in range(4):
            self.step_options_frame.grid_rowconfigure(i, weight=1)

        self.add_button.config(state='normal')
        self.remove_button.config(state='normal')
        self.update_button.config(state='normal')
        
        if step_type_name == ph.StepTypeName.RAMP_BY_TIME.value:
            self.create_ramp_by_time_widgets()
        elif step_type_name == ph.StepTypeName.RAMP_BY_RATE.value:
            self.create_ramp_by_rate_widgets()
        elif step_type_name == ph.StepTypeName.SOAK.value:
            self.create_soak_widgets()
        elif step_type_name == ph.StepTypeName.JUMP.value:
            self.create_jump_widgets()
        elif step_type_name == ph.StepTypeName.END.value:
            self.create_end_widgets()
            self.remove_button.config(state='disabled')
            self.add_button.config(state='disabled')
        elif step_type_name == ph.StepTypeName.AUTOSTART.value:
            self.create_autostart_widgets()

    def create_ramp_by_time_widgets(self):
        self.create_event_output_widgets(self.step_options_frame)
        self.create_grouped_entry_widgets(self.step_options_frame, 'Duration', self.time_vars, [('Hours',(0,99)), ('Minutes',(0,99)), ('Seconds',(1,99))])
        self.create_channel_temp_setpoint_widgets(self.step_options_frame, 2)
        self.create_channel_pid_selection_widgets(self.step_options_frame, 2)
        self.create_guaranteed_soak_widgets(self.step_options_frame, 2)

    def create_ramp_by_rate_widgets(self):
        self.create_event_output_widgets(self.step_options_frame)
        self.create_ramp_rate_entry_widget(self.step_options_frame)
        self.create_channel_temp_setpoint_widgets(self.step_options_frame, 1)
        self.create_channel_pid_selection_widgets(self.step_options_frame, 1)
        self.create_guaranteed_soak_widgets(self.step_options_frame, 1)

    def create_soak_widgets(self):
        self.create_event_output_widgets(self.step_options_frame)
        self.create_grouped_entry_widgets(self.step_options_frame, 'Duration', self.time_vars, [('Hours',(0,99)), ('Minutes',(0,99)), ('Seconds',(1,99))])
        self.create_channel_pid_selection_widgets(self.step_options_frame, 2)
        self.create_guaranteed_soak_widgets(self.step_options_frame, 2)

    def create_jump_widgets(self):
        frame = tk.Frame(self.step_options_frame)
        frame.grid(row=len(self.step_detail_frames)+1, column=0, columnspan=2, padx=5, pady=5, sticky='ew')
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=0)

        self.step_detail_frames.append(frame)

        self.jump_vars = [] #clear the list before making new vars

        frame, var = self.create_entry_widget(frame, "Jump To Profile:", 1, validation_limits=(1, 40))
        frame.grid(row=0, column=0, columnspan=2, pady=5, sticky='we')
        self.jump_vars.append(var)

        frame, var = self.create_entry_widget(frame, "Jump To Step:", 1, validation_limits=(1, 256))
        frame.grid(row=1, column=0, columnspan=2, pady=5, sticky='we')
        self.jump_vars.append(var)

        frame, var = self.create_entry_widget(frame, "Repeats:", 1, validation_limits=(1, 999))
        frame.grid(row=2, column=0, columnspan=2, pady=5, sticky='we')
        self.jump_vars.append(var)

    def create_autostart_widgets(self):
        autostart_frame = tk.Frame(self.step_options_frame)
        autostart_frame.grid(row=len(self.step_detail_frames)+1, column=0, columnspan=2, padx=5, pady=5, sticky='ew')
        for i in range(2):
            autostart_frame.grid_columnconfigure(i, weight=1)

        self.step_detail_frames.append(autostart_frame)

        selection_frame = tk.Frame(autostart_frame)
        selection_frame.grid(row=1, column=0, padx=5, pady=5, sticky='ew', columnspan=2)
        for i in range(2):
            selection_frame.grid_columnconfigure(i, weight=1)

        def on_autostart_day_date_selected(event, selection):
            for widget in selection_frame.winfo_children():
                widget.destroy()

            if selection == 'Date':                                                         #got tired of messing with the grid...
                self.create_grouped_entry_widgets(selection_frame, '', self.date_vars, [('Day',(1,31)), ('  Month',(1,12)), ('    Year  ',(1998,2035))])
            elif selection == 'Day':
                frame, self.autostart_start_day_combobox = self.create_combobox_widget(selection_frame, ("Every Day", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"), "Day:")
                frame.grid(row=0, column=0, padx=5, pady=5, sticky='ew')
                self.autostart_start_day_combobox.config(width=10)
                self.autostart_start_day_combobox.grid(padx=0)

            self.create_grouped_entry_widgets(selection_frame, 'Time', self.time_vars, [('Hours',(0,23)), ('Minutes',(0,59)), ('Seconds',(0,59))])
        
        frame, self.autostart_date_or_day_combobox = self.create_combobox_widget(autostart_frame, ['Date', 'Day'], 'Select:')
        frame.grid(row=0, column=0, padx=5, pady=5, sticky='ew')
        self.autostart_date_or_day_combobox.config(width=10)
        self.autostart_date_or_day_combobox.grid(padx=0)
        self.autostart_date_or_day_combobox.bind("<<ComboboxSelected>>", lambda event: on_autostart_day_date_selected(event, self.autostart_date_or_day_combobox.get()))
        self.autostart_date_or_day_combobox.event_generate("<<ComboboxSelected>>")

    def update_buttons_state(self, entry:tk.Entry, limit_lo:int, limit_hi:int, event=None):
        if (self.validate_entry(entry, entry.get(), limit_lo, limit_hi)):
            self.add_button.config(state='normal')
            self.update_button.config(state='normal')
        else:
            self.add_button.config(state='disabled')
            self.update_button.config(state='disabled')

    def create_end_widgets(self):
        end_frame = tk.Frame(self.step_options_frame)
        end_frame.grid(row=len(self.step_detail_frames)+1, column=0, columnspan=2, padx=0, pady=5, sticky='ew')
        for i in range(2):
            end_frame.grid_columnconfigure(i, weight=1)
        for i in range(3):
            end_frame.grid_rowconfigure(i, weight=1)

        self.step_detail_frames.append(end_frame)

        self.end_action_vars = [] #clear the list before making new comboboxes
        
        frame, combobox = self.create_combobox_widget(end_frame, [step_type.value for step_type in ph.EndActions], 'End Action:')
        frame.grid(row=0, column=0, padx=5, pady=5, sticky='ew')
        combobox.config(width=10)
        combobox.grid(padx=0)
        self.end_action_vars.append(combobox)

        frame, var = self.create_entry_widget(end_frame, 'Ch 1 Idle Setpoint', 25)
        frame.grid(row=1, column=0, padx=0, pady=5, sticky='ew')
        self.end_action_vars.append(var)
        
        frame, var = self.create_entry_widget(end_frame, 'Ch 2 Idle Setpoint', 25)
        frame.grid(row=2, column=0, padx=0, pady=5, sticky='ew')
        self.end_action_vars.append(var)

    def get_step_from_current_selection(self) -> ph.Step:
        step_type_name = self.step_type_dropdown.get()

        if step_type_name == ph.StepTypeName.RAMP_BY_TIME.value:
            wait_for_state, event_output_states = self.get_event_output_states()
            step = ph.Step(
                type_name=ph.StepTypeName.RAMP_BY_TIME,
                details = ph.RampTime(
                    wait_for=wait_for_state,
                    event_output_states=event_output_states,
                    duration=self.get_time_entries_timedelta(),
                    ch1_temp_setpoint=self.channel_temp_setpoint_vars[0].get(),
                    ch2_temp_setpoint=self.channel_temp_setpoint_vars[1].get(),
                    ch1_pid_selection=self.ch_pid_selection_comboboxes[0].current(),
                    ch2_pid_selection=self.ch_pid_selection_comboboxes[1].current(),
                    guaranteed_soak_1=self.guaranteed_soak_vars[0].get(),
                    guaranteed_soak_2=self.guaranteed_soak_vars[1].get()
                )
            )
        elif step_type_name == ph.StepTypeName.RAMP_BY_RATE.value:
            wait_for_state, event_output_states = self.get_event_output_states()
            step = ph.Step(
                type_name=ph.StepTypeName.RAMP_BY_RATE,
                details = ph.RampRate(
                    wait_for=wait_for_state,
                    event_output_states=event_output_states,
                    rate=self.ramp_rate_var.get(),
                    ch1_temp_setpoint=self.channel_temp_setpoint_vars[0].get(),
                    ch1_pid_selection=self.ch_pid_selection_comboboxes[0].current(),
                    guaranteed_soak_1=self.guaranteed_soak_vars[0].get()
                )
            )
        elif step_type_name == ph.StepTypeName.SOAK.value:
            wait_for_state, event_output_states = self.get_event_output_states()
            step = ph.Step(
                type_name=ph.StepTypeName.SOAK,
                details = ph.Soak(
                    wait_for=wait_for_state,
                    event_output_states=event_output_states,
                    duration=self.get_time_entries_timedelta(),
                    ch1_pid_selection=self.ch_pid_selection_comboboxes[0].current(),
                    ch2_pid_selection=self.ch_pid_selection_comboboxes[1].current(),
                    guaranteed_soak_1=self.guaranteed_soak_vars[0].get(),
                    guaranteed_soak_2=self.guaranteed_soak_vars[1].get()
                )
            )
        elif step_type_name == ph.StepTypeName.JUMP.value:
            step = ph.Step(
                type_name=ph.StepTypeName.JUMP, 
                details = ph.Jump(
                    jump_to_profile=self.jump_vars[0].get(),
                    jump_to_step=self.jump_vars[1].get(),
                    number_of_repeats=self.jump_vars[2].get()
                )
            )
        elif step_type_name == ph.StepTypeName.END.value:
            step = ph.Step(
                type_name=ph.StepTypeName.END, 
                details = ph.End(
                    end_action=self.end_action_vars[0].get(),
                    ch1_idle_setpoint=self.end_action_vars[1].get(),
                    ch2_idle_setpoint=self.end_action_vars[2].get()
                )
            )

        elif step_type_name == ph.StepTypeName.AUTOSTART.value:
            date_or_day = self.autostart_date_or_day_combobox.current()
            step = ph.Step(
                type_name=ph.StepTypeName.AUTOSTART, 
                details = ph.Autostart(
                    date_or_day= date_or_day,
                    start_time = self.get_time_entries_timedelta(),
                    start_day = self.autostart_start_day_combobox.current() if date_or_day == 1 else None,
                    start_date = dt(day=self.date_vars[0].get(), month=self.date_vars[1].get(), year=self.date_vars[2].get()) if date_or_day == 0 else None,
                )
            )

        return step
    
    def add_step(self):
        step = self.get_step_from_current_selection()

        if self.current_selected_item:
            tree_item_index = self.tree.index(self.current_selected_item)
            self.program.steps.insert(tree_item_index, step)

            tree_index = self.tree.index(self.tree.get_children()[tree_item_index])

        else: #if nothing is selected, add before the end step
            self.program.steps.insert(-1, step)
    
            tree_index = self.tree.index(self.tree.get_children()[-1])
        
        new_values = (f"{tree_index}", f"{self.program.steps[tree_index].type_name}")
        self.tree.insert("", tree_index, values=new_values)

        self.current_selected_item = self.tree.get_children()[tree_index]
        self.tree.selection_set(self.tree.get_children()[tree_index+1])

        self.reindex_tree_view()

    def update_step(self):
        #prevent updating end step to other than an end step type
        if self.current_selected_item[0] == self.tree.get_children()[-1]:
            if self.step_type_dropdown.get() != ph.StepTypeName.END.value:
                return
            
        self.program.steps[self.tree.index(self.current_selected_item)] = self.get_step_from_current_selection()

        item_id = self.current_selected_item
        new_values = (f"{self.tree.index(self.current_selected_item)}", f"{self.program.steps[self.tree.index(self.current_selected_item)].type_name}")
        self.tree.item(item_id, values=new_values)

        self.reindex_tree_view()
        
    def remove_step(self):
        self.current_selected_item = self.tree.selection()
        if self.current_selected_item:
            current_item_index = self.tree.index(self.current_selected_item)

            self.program.steps.pop(current_item_index)
            self.tree.delete(self.current_selected_item)

            self.do_not_update = True

            self.reindex_tree_view()

            self.current_selected_item = self.tree.get_children()[current_item_index] #set to item newly at this index
            self.step_type_dropdown.set(self.program.steps[current_item_index].type_name) #so that update step has right type
            self.tree.selection_set(self.current_selected_item)

    def on_treeview_select(self, event):
        if self.do_not_update: 
            self.do_not_update = False
        else: #dont update step if it was just deleted
            self.update_step()
            
        self.current_selected_item = self.tree.selection()

        if self.current_selected_item: # load into step details frame
            step = self.program.steps[self.tree.index(self.current_selected_item)]
            self.step_type_dropdown.set(step.type_name)
            self.create_detail_widgets(step.type_name)

            if step.type_name == ph.StepTypeName.RAMP_BY_TIME:
                for idx, var in enumerate(self.event_output_vars):
                    var.set(step.details.event_output_states[idx])

                hours, minutes, seconds = ph.timedelta_to_hours_minutes_seconds(step.details.duration)
                self.time_vars[0].set(hours)
                self.time_vars[1].set(minutes)
                self.time_vars[2].set(seconds)

                self.channel_temp_setpoint_vars[0].set(step.details.ch1_temp_setpoint)
                self.channel_temp_setpoint_vars[1].set(step.details.ch2_temp_setpoint)
                self.ch_pid_selection_comboboxes[0].current(step.details.ch1_pid_selection)
                self.ch_pid_selection_comboboxes[1].current(step.details.ch2_pid_selection)
                self.guaranteed_soak_vars[0].set(step.details.guaranteed_soak_1)
                self.guaranteed_soak_vars[1].set(step.details.guaranteed_soak_2)

            elif step.type_name == ph.StepTypeName.RAMP_BY_RATE:
                for idx, var in enumerate(self.event_output_vars):
                    var.set(step.details.event_output_states[idx])
                
                self.ramp_rate_var.set(step.details.rate)
                self.channel_temp_setpoint_vars[0].set(step.details.ch1_temp_setpoint)
                self.ch_pid_selection_comboboxes[0].current(step.details.ch1_pid_selection)
                self.guaranteed_soak_vars[0].set(step.details.guaranteed_soak_1)

            elif step.type_name == ph.StepTypeName.SOAK:
                for idx, var in enumerate(self.event_output_vars):
                    var.set(step.details.event_output_states[idx])

                hours, minutes, seconds = ph.timedelta_to_hours_minutes_seconds(step.details.duration)
                self.time_vars[0].set(hours)
                self.time_vars[1].set(minutes)
                self.time_vars[2].set(seconds)

                self.ch_pid_selection_comboboxes[0].current(step.details.ch1_pid_selection)
                self.ch_pid_selection_comboboxes[1].current(step.details.ch2_pid_selection)
                self.guaranteed_soak_vars[0].set(step.details.guaranteed_soak_1)
                self.guaranteed_soak_vars[1].set(step.details.guaranteed_soak_2)

            elif step.type_name == ph.StepTypeName.JUMP:
                self.jump_vars[0].set(step.details.jump_to_profile)
                self.jump_vars[1].set(step.details.jump_to_step)
                self.jump_vars[2].set(step.details.number_of_repeats)

            elif step.type_name == ph.StepTypeName.END:
                self.end_action_vars[0].set(step.details.end_action)
                self.end_action_vars[1].set(step.details.ch1_idle_setpoint)
                self.end_action_vars[2].set(step.details.ch2_idle_setpoint)

            elif step.type_name == ph.StepTypeName.AUTOSTART:
                self.autostart_date_or_day_combobox.current(step.details.date_or_day)
                self.autostart_date_or_day_combobox.event_generate("<<ComboboxSelected>>") #so that date_or_day conditional widgets are made

                if step.details.date_or_day == 0:
                    day, month, year = step.details.start_date.day, step.details.start_date.month, step.details.start_date.year
                    self.date_vars[0].set(day)
                    self.date_vars[1].set(month)
                    self.date_vars[2].set(year)
                else:
                    self.autostart_start_day_combobox.set(step.details.start_day)

                hours, minutes, seconds = ph.timedelta_to_hours_minutes_seconds(step.details.start_time)
                self.time_vars[0].set(hours)
                self.time_vars[1].set(minutes)
                self.time_vars[2].set(seconds)

    def reindex_tree_view(self):
        children = self.tree.get_children()

        for new_index, item_id in enumerate(children, start=0):
            self.tree.item(item_id, values=(new_index, self.tree.item(item_id, 'values')[1]))

    def build_tree_view(self):
        self.tree.delete(*self.tree.get_children())
        
        for idx, step in enumerate(self.program.steps):
            self.tree.insert("", "end", text=step.type_name, values=(idx, step.type_name))

        self.do_not_update = True #we cleared everything so dont update not existing steps

    def new_file(self):
        self.tree.delete(*self.tree.get_children())

        self.program.name = "New Program"
        self.program.steps = []

        self.program.steps.append(
            ph.Step(
                type_name=ph.StepTypeName.END,
                details=ph.End(
                    end_action=[step_type.value for step_type in ph.EndActions][0],
                    ch1_idle_setpoint=0,
                    ch2_idle_setpoint=0
                )
            )
        )

        self.tree.insert("", "end", values=(f"0", f"{ph.StepTypeName.END}"))

        self.current_selected_item = self.tree.get_children()

        self.root.title(f"{BASE_TITLE} | {self.program.name}")

    def open_file(self):
        filepath = Path(filedialog.askopenfilename(defaultextension=FILE_EXTENSION, filetypes=[("CSV Files", FILE_EXTENSION)], title="Open file"))
        if filepath:
            self.program = ph.read_program_from_file(filepath)
            self.build_tree_view()

            #set up first step in step details
            self.step_type_dropdown.set(self.program.steps[0].type_name)
            self.current_selected_item = self.tree.get_children()[0]
            self.tree.selection_set(self.current_selected_item)

            self.root.title(f"{BASE_TITLE} | {self.program.name}")

    def save_file(self):
        filepath = Path(filedialog.asksaveasfilename(defaultextension=FILE_EXTENSION, filetypes=[("CSV Files", FILE_EXTENSION)], title="Save file"))
        if filepath:
            self.program.name = filepath.stem
            ph.write_program_to_file(self.program, filepath)
            messagebox.showinfo("File save successful", f"File successfully saved to: {filepath}")

            self.root.title(f"{BASE_TITLE} | {self.program.name}")

    def show_help(self):
        help_text = (
            "Watlow Controller Program Editor Help:\n\n"
            "1. Adding Steps:\n"
            "   - Select the step type from the dropdown menu on the right.\n"
            "   - Fill in the details for the selected step type.\n"
            "   - Click the 'Add Step' button to insert the step into the program.\n\n"
            "2. Updating Steps:\n"
            "   - Select a step from the TreeView.\n"
            "   - Modify the details in the step details section on the right.\n"
            "   - Click the 'Update Step' button to save changes.\n\n"
            "3. Removing Steps:\n"
            "   - Select a step from the TreeView.\n"
            "   - Click the 'Remove Step' button to delete the step.\n\n"
            "4. Saving and Loading Programs:\n"
            "   - Use the 'File' menu to create a new program, open an existing program, or save the current program.\n"
            "   - Programs are saved as CSV files.\n\n"
            "5. Loading to Watlow:\n"
            "   - Use the 'Load to Watlow' option in the 'File' menu to upload the program to the Watlow controller.\n"
            "   - Select the COM port, profile number, and slave address in the dialog that appears.\n\n"
            "6. Additional Information:\n"
            "   - Visit the GitHub repository for source code and further documentation:\n\n"
            "       https://github.com/shanedertrain/watlow_controller\n\n"
            "       License: GNU GENERAL PUBLIC LICENSE Version 3"
        )

        def open_github():
            webbrowser.open("https://github.com/shanedertrain/watlow_controller")

        # Create a custom Toplevel window
        help_window = tk.Toplevel(self.root)
        help_window.title("Help")
        help_window.geometry("900x400")  # Adjust width and height as needed

        # Add a Text widget to display the help text
        text_widget = tk.Text(help_window, wrap="word", height=20, width=100)
        text_widget.insert(tk.END, help_text)
        text_widget.config(state=tk.DISABLED)  # Make the text widget read-only
        text_widget.pack(pady=10, padx=10, expand=True, fill=tk.BOTH)

        # Add a clickable link to GitHub
        link_label = tk.Label(help_window, text="Visit GitHub Repository", fg="blue", cursor="hand2")
        link_label.pack(pady=5)
        link_label.bind("<Button-1>", lambda e: open_github())

        # Add a close button
        close_button = ttk.Button(help_window, text="Close", command=help_window.destroy)
        close_button.pack(pady=10)

        # Make the window modal
        help_window.transient(self.root)
        help_window.grab_set()
        self.root.wait_window(help_window)

    def open_load_to_watlow_dialog(self):
        modal = tk.Toplevel()
        modal.title("Load to Watlow")
        modal.geometry("300x250")
        modal.transient(self.root)  # Make it modal
        modal.grab_set()

        def list_com_ports():
            ports = serial.tools.list_ports.comports()
            return [port.device for port in ports]

        # COM port combobox
        com_label = tk.Label(modal, text="COM Port:")
        com_label.pack(pady=5)
        com_ports = list_com_ports()
        com_combobox = ttk.Combobox(modal, values=com_ports, state="readonly")
        com_combobox.pack(pady=5)
        if com_ports:
            com_combobox.current(0)  # Set to first element

        # Profile number combobox
        profile_label = tk.Label(modal, text="Profile Number:")
        profile_label.pack(pady=5)
        profile_combobox = ttk.Combobox(modal, values=list(range(1, 41)), state="readonly")
        profile_combobox.pack(pady=5)
        profile_combobox.current(0)  # Set to first element

        # Slave address combobox
        slave_address_label = tk.Label(modal, text="Slave Address:")
        slave_address_label.pack(pady=5)
        slave_address_combobox = ttk.Combobox(modal, values=list(range(1, 256)), state="readonly")
        slave_address_combobox.pack(pady=5)
        slave_address_combobox.current(0)  # Set to first element

        # Load Program button
        load_button = tk.Button(modal, text="Load Program")
        load_button.pack(pady=20)

        def load_program():
            load_button.config(state=tk.DISABLED)
            load_button.config(text="Loading...")
            modal.update_idletasks()

            try:
                watlow = watlow_f4.WatlowF4(slave_address=int(slave_address_combobox.get()), com_port=com_combobox.get())
                watlow.configure_profile(self.program, int(profile_combobox.get()))
                on_load_done(True)
            except Exception as e:
                on_load_done(False, e)

        def on_load_done(success, failure_message=None):
            if success:
                load_button.config(text="Success! Click to close")
                load_button.config(command=modal.destroy)
            else:
                load_button.config(text="Load Program")
                messagebox.showerror("Failure", f"The program failed to load: {failure_message}")
            
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            load_button.config(state=tk.NORMAL)

        load_button.config(command=load_program)
        
if __name__ == "__main__":
    root = tk.Tk()
    app = ProgramEditor(root)
    root.mainloop()
