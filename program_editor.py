import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import csv
from enum import Enum
from typing import Union

import program_handler as ph

# Constants
FILE_DIRECTORY = os.path.join(os.getcwd(), 'watlow_programs')
FILE_EXTENSION = '.csv'
HEADER = ['step_type', 'key_value']
DEFAULT_COLOR = 'white'
ERROR_COLOR = 'red'

# Create directory if it doesn't exist
if not os.path.exists(FILE_DIRECTORY):
    os.makedirs(FILE_DIRECTORY)

class EntryTypes(Enum):
    TEXT = 0
    BOOLEAN = 1
    EVENT_OUTPUT = 2
    TIME = 3

class ProgramEditor:
    frame_step_type_row = 0
    frame_event_outputs_row = 1
    frame_duration_row=2
    frame_ch1_pid_row=3
    frame_ch2_pid_row=4
    frame_ch1_pid_selection_row=5
    frame_ch2_pid_selection_row=6
    frame_guaranteed_soak_1_row=7
    frame_guaranteed_soak_2_row=8
    def __init__(self, root):
        self.root = root
        self.root.title("Watlow F4 Program Editor")
        self.root.geometry("520x600")  # Adjusted size for the combined view
        self.root.resizable(False, False)

        self.create_widgets()

        self.current_file = None
        self.current_step_id = None
        self.event_output_checkboxes = []

    def create_widgets(self):
        # Create a frame for the Treeview
        tree_frame = tk.Frame(self.root)
        tree_frame.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

        # Configure tree_frame to expand
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Setup Treeview
        self.tree = ttk.Treeview(tree_frame, columns=('step', 'step_type', 'key_value'), show='headings')
        self.tree.heading('step', text='Step')
        self.tree.heading('step_type', text='Step Type')
        self.tree.heading('key_value', text='Key Value')

        # Set column widths
        self.tree.column('step', width=5 * 10, anchor='center') 
        self.tree.column('step_type', width=12 * 10, anchor='center')  
        self.tree.column('key_value', width=12 * 10, anchor='center')  

        # Expand Treeview in the available space
        self.tree.grid(row=0, column=0, sticky='nsew')

        # Setup Vertical Scrollbar
        self.scrollbar = tk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview, width=20)
        self.scrollbar.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscrollcommand=self.scrollbar.set)

        # Create a frame for the detail section
        detail_frame = tk.Frame(self.root)
        detail_frame.grid(row=0, column=2, sticky='nsew', padx=5, pady=5)

        # Configure detail_frame to expand
        detail_frame.grid_rowconfigure(0, weight=0)
        detail_frame.grid_rowconfigure(1, weight=0)
        detail_frame.grid_rowconfigure(2, weight=0)
        detail_frame.grid_columnconfigure(0, weight=1)
        detail_frame.grid_columnconfigure(1, weight=0)

        self.detail_label = tk.Label(detail_frame, text="Step Details")
        self.detail_label.grid(row=0, column=0, pady=0, columnspan=2)

        #setup step type frame
        step_type_dropdown_frame = tk.Frame(detail_frame)
        step_type_dropdown_frame.grid(row=1, column=0, columnspan=2, pady=5, sticky='ew')
        step_type_dropdown_frame.grid_columnconfigure(0, weight=1)
        
        step_type_label = tk.Label(step_type_dropdown_frame, text="Step Type:", anchor='center')
        step_type_label.grid(row=0, column=0, padx=5, pady=5, sticky='ew')
        
        self.step_type_dropdown = ttk.Combobox(step_type_dropdown_frame, values=[step_type.value for step_type in ph.StepTypeName if step_type != ph.StepTypeName.END], state="readonly")
        self.step_type_dropdown.grid(row=1, column=0, padx=20, pady=5, sticky='ew')
        self.step_type_dropdown.bind("<<ComboboxSelected>>", self.on_step_type_selected)
        self.step_type_dropdown.current(0)

        # Setup detail section
        self.details_frame = tk.Frame(detail_frame)
        self.details_frame.grid(row=2, column=0, columnspan=2, sticky='nsew', padx=5, pady=5)

        # Configure details_frame to expand
        self.details_frame.grid_rowconfigure(0, weight=0)
        self.details_frame.grid_rowconfigure(1, weight=0)
        self.details_frame.grid_rowconfigure(2, weight=1)
        self.details_frame.grid_columnconfigure(0, weight=1)
        self.details_frame.grid_columnconfigure(1, weight=1)

        #bottom buttons
        self.add_button = tk.Button(detail_frame, text="Add Step", command=self.add_step)
        self.add_button.grid(row=3, column=0, pady=5, sticky='ews')

        self.update_button = tk.Button(detail_frame, text="Update Step", command=self.update_step)
        self.update_button.grid(row=3, column=1, pady=5, sticky='ews')

        self.remove_button = tk.Button(detail_frame, text="Remove Step", command=self.remove_step)
        self.remove_button.grid(row=4, column=0, columnspan=2, pady=5, sticky='ews')

        # Setup Menu
        self.menu = tk.Menu(self.root)
        self.root.config(menu=self.menu)

        self.file_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="New", command=self.new_file)
        self.file_menu.add_command(label="Open", command=self.open_file)
        self.file_menu.add_command(label="Save", command=self.save_file)

        self.menu.add_separator()  # Add a separator before Help
        self.menu.add_command(label="Help", command=self.show_help)  # Direct command to show help

        # Configure root grid
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=0)
        self.root.grid_columnconfigure(2, weight=1)

        # Bind treeview events
        self.tree.bind('<<TreeviewSelect>>', self.on_treeview_select)
        self.step_type_dropdown.event_generate("<<ComboboxSelected>>")

    def create_boolean_widget(self, parent_frame:tk.Frame, text:str, var:tk.BooleanVar) -> tuple[tk.Frame, tk.Checkbutton]:
        frame = tk.Frame(parent_frame)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)

        label = tk.Label(frame, text=text, anchor='center')
        label.grid(row=0, column=0, padx=5, pady=0, sticky='ew')

        entry = tk.Checkbutton(frame, variable=var)
        entry.grid(row=0, column=1, padx=5, pady=0, sticky='ew')

        return frame, entry

    def create_label_entry_widget(self, parent_frame:tk.Frame, text:str, var:tk.StringVar) -> tuple[tk.Frame, tk.Entry]:
        frame = tk.Frame(parent_frame)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=0)

        label = tk.Label(frame, text=text, anchor='center')
        label.grid(row=0, column=0, padx=5, pady=5, sticky='w')

        entry = tk.Entry(frame, textvariable=var, width=5)
        entry.grid(row=0, column=1, padx=5, pady=5, sticky='e')

        return frame, entry
    
    def create_combobox_widget(self, parent_frame:tk.Frame, values:list, label_name:str) -> tuple[tk.Frame, ttk.Combobox]:
        frame = tk.Frame(parent_frame)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)

        label = tk.Label(frame, text=label_name, anchor='center')
        label.grid(row=0, column=0, padx=5, pady=5, sticky='w')

        combobox = ttk.Combobox(frame, values=list(values), state="readonly", width=2)
        combobox.grid(row=0, column=1, padx=5, pady=5, sticky='e')
        combobox.current(0)

        return frame, combobox

    def create_event_output_widget(self, parent_frame:tk.Frame) -> tk.Frame:
        frame = tk.Frame(parent_frame)
        for i in range(4):
            frame.grid_columnconfigure(i, weight=1)

        tk.Label(frame, text="Wait for Event Output(s)", anchor='center').grid(row=0, columnspan=4)

        self.event_output_checkboxes = []  # Clear the list before creating new checkboxes
        for i in range(8):
            chk = tk.Checkbutton(frame, text=str(i+1), variable=tk.BooleanVar(value=False))
            chk.grid(row=i//4+1, column=i%4, padx=5, pady=2)
            self.event_output_checkboxes.append(chk)
        
        return frame

    def create_duration_widgets(self, parent_frame:tk.Frame) -> tk.Frame:
        frame = tk.Frame(parent_frame)
        frame.grid(row=self.frame_duration_row, column=self.frame_duration_row, columnspan=2, pady=5, sticky='we')

        tk.Label(frame, text="Hours").grid(row=0, column=0, padx=5, pady=5, sticky='ew')
        self.hours_entry = tk.Entry(frame, width=5)
        self.hours_entry.insert(0, "0")
        self.hours_entry.grid(row=1, column=0, padx=5, pady=5, sticky='ew')

        tk.Label(frame, text="Minutes").grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        self.minutes_entry = tk.Entry(frame, width=5)
        self.minutes_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        self.minutes_entry.insert(0, "0")

        tk.Label(frame, text="Seconds").grid(row=0, column=2, padx=5, pady=5, sticky='ew')
        self.seconds_entry = tk.Entry(frame, width=5)
        self.seconds_entry.grid(row=1, column=2, padx=5, pady=5, sticky='ew')
        self.seconds_entry.insert(0, "1")

        self.hours_entry.bind('<KeyRelease>', self.update_button_state_duration)
        self.minutes_entry.bind('<KeyRelease>', self.update_button_state_duration)
        self.seconds_entry.bind('<KeyRelease>', self.update_button_state_duration)

        return frame

    def validate_duration_entry(self, value):
        valid = True
        if not value:
            return True

        try:
            int_value = int(value)
            if int_value < 0 or int_value > 99:
                valid = False
            if self.seconds_entry is self.root.focus_get() and int_value < 1:
                valid = False
        except ValueError:
            valid = False

        if not valid:
            self.hours_entry.config(bg=ERROR_COLOR)
            self.minutes_entry.config(bg=ERROR_COLOR)
            self.seconds_entry.config(bg=ERROR_COLOR)
        else:
            self.hours_entry.config(bg=DEFAULT_COLOR)
            self.minutes_entry.config(bg=DEFAULT_COLOR)
            self.seconds_entry.config(bg=DEFAULT_COLOR)
            
        return valid

    def validate_jump_to_profile(self, value):
        valid = True
        if not value:
            return True

        try:
            int_value = int(value)
            if not (1 <= int_value <= 40):
                valid = False
        except ValueError:
            valid = False

        if not valid:
            self.frame_jump_to_profile_entry.config(bg=ERROR_COLOR)
        else:
            self.frame_jump_to_profile_entry.config(bg=DEFAULT_COLOR)
            
        return valid

    def validate_jump_to_step(self, value):
        valid = True
        if not value:
            return True

        try:
            int_value = int(value)
            if not (1 <= int_value <= 256):
                valid = False
        except ValueError:
            valid = False

        if not valid:
            self.frame_jump_to_step_entry.config(bg=ERROR_COLOR)
        else:
            self.frame_jump_to_step_entry.config(bg=DEFAULT_COLOR)
            
        return valid

    def validate_number_of_repeats(self, value):
        valid = True
        if not value:
            return True

        try:
            int_value = int(value)
            if not (1 <= int_value <= 999):
                valid = False
        except ValueError:
            valid = False

        if not valid:
            self.number_of_repeats_entry.config(bg=ERROR_COLOR)
        else:
            self.number_of_repeats_entry.config(bg=DEFAULT_COLOR)
            
        return valid

    def update_button_state_duration(self, event=None):
        if (self.validate_duration_entry(self.hours_entry.get()) and
                self.validate_duration_entry(self.minutes_entry.get()) and
                self.validate_duration_entry(self.seconds_entry.get())):
            self.add_button.config(state='normal')
            self.update_button.config(state='normal')
        else:
            self.add_button.config(state='disabled')
            self.update_button.config(state='disabled')

    def update_button_state_jump(self, event=None):
        if (self.validate_jump_to_profile(self.frame_jump_to_profile_entry.get()) and
                self.validate_jump_to_step(self.frame_jump_to_step_entry.get()) and
                self.validate_number_of_repeats(self.number_of_repeats_entry.get())):
            self.add_button.config(state='normal')
            self.update_button.config(state='normal')
        else:
            self.add_button.config(state='disabled')
            self.update_button.config(state='disabled')

    def on_step_type_selected(self, event):
        step_type = self.step_type_dropdown.get()
        self.create_detail_widgets(step_type)

    def create_detail_widgets(self, step_type):
        for widget in self.details_frame.winfo_children():
            widget.grid_forget()

        self.details_frame.grid_rowconfigure(0, weight=1)
        self.details_frame.grid_rowconfigure(1, weight=1)
        self.details_frame.grid_rowconfigure(2, weight=1)
        self.details_frame.grid_rowconfigure(3, weight=1)

        if step_type == ph.StepTypeName.RAMP_BY_TIME.value:
            self.create_ramp_by_time_widgets()
        elif step_type == ph.StepTypeName.RAMP_BY_RATE.value:
            self.create_ramp_by_rate_widgets()
        elif step_type == ph.StepTypeName.SOAK.value:
            self.create_soak_widgets()
        elif step_type == ph.StepTypeName.JUMP.value:
            self.create_jump_widgets()
        elif step_type == ph.StepTypeName.END.value:
            self.create_end_widgets()
        else:
            raise ValueError(f"Unknown step type: {step_type}")

    def create_ramp_by_time_widgets(self):
        self.event_outputs_frame = self.create_event_output_widget(self.details_frame)
        self.event_outputs_frame.grid(row=self.frame_event_outputs_row, column=0, columnspan=2, pady=5, sticky='ew')

        self.duration_frame = self.create_duration_widgets(self.details_frame)
        self.duration_frame.grid(row=self.frame_duration_row, column=0, columnspan=2, pady=5, sticky='ew')

        self.ch1_temp_setpoint_frame, self.ch1_temp_setpoint_entry  = self.create_label_entry_widget(self.details_frame, "Ch 1 Setpoint (C):", tk.StringVar(value='25'))
        self.ch1_temp_setpoint_frame.grid(row=self.frame_ch1_pid_row, column=0, padx=7, pady=5, sticky='ew', columnspan=2)
        
        self.ch2_temp_setpoint_frame, self.ch2_temp_setpoint_entry = self.create_label_entry_widget(self.details_frame, "Ch 2 Setpoint (C):", tk.StringVar(value='25'))
        self.ch2_temp_setpoint_frame.grid(row=self.frame_ch2_pid_row, column=0, padx=7, pady=5, sticky='ew', columnspan=2)
        
        self.frame_ch1_selection_dropdown, self.ch1_setpoint_dropdown = self.create_combobox_widget(self.details_frame, range(1, 6), 'Ch 1 PID Selection:')
        self.frame_ch1_selection_dropdown.grid(row=self.frame_ch1_pid_selection_row, column=0, padx=5, pady=5, sticky='ew', columnspan=2)
        
        self.frame_ch2_selection_dropdown, self.ch2_setpoint_dropdown = self.create_combobox_widget(self.details_frame, range(6, 11), 'Ch 2 PID Selection:')
        self.frame_ch2_selection_dropdown.grid(row=self.frame_ch2_pid_selection_row, column=0, padx=5, pady=5, sticky='ew', columnspan=2)

        self.frame_guaranteed_soak_1, self.guaranteed_soak_1_checkbutton = self.create_boolean_widget(self.details_frame, "Guarantee Soak 1:", tk.BooleanVar(value=False))
        self.frame_guaranteed_soak_1.grid(row=self.frame_guaranteed_soak_1_row, column=0, columnspan=2, padx=0, pady=5, sticky='ew')

        self.frame_guaranteed_soak_2, self.guaranteed_soak_2_checkbutton = self.create_boolean_widget(self.details_frame, "Guarantee Soak 2:", tk.BooleanVar(value=False))
        self.frame_guaranteed_soak_2.grid(row=self.frame_guaranteed_soak_2_row, column=0, columnspan=2, padx=0, pady=5, sticky='ew')

    def create_ramp_by_rate_widgets(self):
        self.event_outputs_frame = self.create_event_output_widget(self.details_frame)
        self.event_outputs_frame.grid(row=self.frame_event_outputs_row, column=0, columnspan=2, pady=5, sticky='ew')

        self.create_label_entry_widget(self.details_frame, "Rate (C) per Minute:", tk.StringVar(value='2'))

        self.ch1_temp_setpoint_frame, self.ch1_temp_setpoint_entry  = self.create_label_entry_widget(self.details_frame, "Ch 1 Setpoint (C):", tk.StringVar(value='25'))
        self.ch1_temp_setpoint_frame.grid(row=self.frame_ch1_pid_row, column=0, padx=7, pady=5, sticky='ew', columnspan=2)

        self.frame_ch1_selection_dropdown, self.ch1_setpoint_dropdown = self.create_combobox_widget(self.details_frame, range(1, 6), 'Ch 1 PID Selection:')
        self.frame_ch1_selection_dropdown.grid(row=self.frame_ch1_pid_selection_row, column=0, padx=5, pady=5, sticky='ew', columnspan=2)
        
        self.frame_guaranteed_soak_1, self.guaranteed_soak_1_checkbutton = self.create_boolean_widget(self.details_frame, "Guarantee Soak 1:", tk.BooleanVar(value=False))
        self.frame_guaranteed_soak_1.grid(row=self.frame_guaranteed_soak_1_row, column=0, columnspan=2, padx=0, pady=5, sticky='ew')

    def create_soak_widgets(self):
        self.event_outputs_frame = self.create_event_output_widget(self.details_frame)
        self.event_outputs_frame.grid(row=self.frame_event_outputs_row, column=0, columnspan=2, pady=5, sticky='ew')

        self.duration_frame = self.create_duration_widgets(self.details_frame)
        self.duration_frame.grid(row=self.frame_duration_row, column=0, columnspan=2, pady=5, sticky='ew')

        self.ch1_temp_setpoint_frame, self.ch1_temp_setpoint_entry  = self.create_label_entry_widget(self.details_frame, "Ch 1 Setpoint (C):", tk.StringVar(value='25'))
        self.ch1_temp_setpoint_frame.grid(row=self.frame_ch1_pid_row, column=0, padx=7, pady=5, sticky='ew', columnspan=2)

        self.ch2_temp_setpoint_frame, self.ch2_temp_setpoint_entry  = self.create_label_entry_widget(self.details_frame, "Ch 2 Setpoint (C):", tk.StringVar(value='25'))
        self.ch2_temp_setpoint_frame.grid(row=self.frame_ch2_pid_row, column=0, padx=7, pady=5, sticky='ew', columnspan=2)

        self.frame_ch1_selection_dropdown, self.ch1_setpoint_dropdown = self.create_combobox_widget(self.details_frame, range(1, 6), 'Ch 1 PID Selection:')
        self.frame_ch1_selection_dropdown.grid(row=self.frame_ch1_pid_selection_row, column=0, padx=5, pady=5, sticky='ew', columnspan=2)
        
        self.frame_ch2_selection_dropdown, self.ch2_setpoint_dropdown = self.create_combobox_widget(self.details_frame, range(6, 11), 'Ch 2 PID Selection:')
        self.frame_ch2_selection_dropdown.grid(row=self.frame_ch2_pid_selection_row, column=0, padx=5, pady=5, sticky='ew', columnspan=2)

        self.frame_guaranteed_soak_1, self.guaranteed_soak_1_checkbutton = self.create_boolean_widget(self.details_frame, "Guarantee Soak 1:", tk.BooleanVar(value=False))
        self.frame_guaranteed_soak_1.grid(row=self.frame_guaranteed_soak_1_row, column=0, columnspan=2, padx=0, pady=5, sticky='ew')

        self.frame_guaranteed_soak_2, self.guaranteed_soak_2_checkbutton = self.create_boolean_widget(self.details_frame, "Guarantee Soak 2:", tk.BooleanVar(value=False))
        self.frame_guaranteed_soak_2.grid(row=self.frame_guaranteed_soak_2_row, column=0, columnspan=2, padx=0, pady=5, sticky='ew')

    def create_jump_widgets(self):
        self.jump_frame = tk.Frame(self.details_frame)
        self.jump_frame.grid(row=self.frame_guaranteed_soak_2_row+1, column=0, columnspan=2, pady=5, sticky='we')

        self.jump_frame.grid_columnconfigure(0, weight=1)
        self.jump_frame.grid_columnconfigure(1, weight=1)

        self.frame_jump_to_profile, self.frame_jump_to_profile_entry = self.create_label_entry_widget(
            self.jump_frame, "Jump To Profile:", tk.StringVar(value='1')
        )
        self.frame_jump_to_profile.grid(row=0, column=0, columnspan=2, pady=5, sticky='we')

        self.frame_jump_to_step, self.frame_jump_to_step_entry = self.create_label_entry_widget(
            self.jump_frame, "Jump To Step:", tk.StringVar(value='1')
        )
        self.frame_jump_to_step.grid(row=1, column=0, columnspan=2, pady=5, sticky='we')

        self.frame_number_of_repeats, self.number_of_repeats_entry = self.create_label_entry_widget(
            self.jump_frame, "Number of Repeats:", tk.StringVar(value='1')
        )
        self.frame_number_of_repeats.grid(row=2, column=0, columnspan=2, pady=5, sticky='we')

        self.frame_jump_to_profile_entry.bind('<KeyRelease>', self.update_button_state_jump)
        self.frame_jump_to_step_entry.bind('<KeyRelease>', self.update_button_state_jump)
        self.number_of_repeats_entry.bind('<KeyRelease>', self.update_button_state_jump)



    def create_end_widgets(self):
        self.frame_end_action_combobox, self.end_action_combobox = self.create_combobox_widget(self.details_frame, [step_type.value for step_type in ph.EndActions], 'End Action:')
        self.frame_end_action_combobox.grid(row=self.frame_guaranteed_soak_2_row+1, column=0, columnspan=2, padx=0, pady=5, sticky='ew')
        self.end_action_combobox.config(width=12)
        self.end_action_combobox.grid(padx=0)

        self.frame_ch1_idle_setpoint_dropdown, self.ch1idle_setpoint_dropdown = self.create_combobox_widget(self.details_frame, range(1, 6), 'Ch 1 Idle Setpoint')
        self.frame_ch1_idle_setpoint_dropdown.grid(row=self.frame_guaranteed_soak_2_row+2, column=0, padx=0, pady=5, sticky='ew')
        
        self.frame_ch2_idle_setpoint_dropdown, self.ch2idle_setpoint_dropdown = self.create_combobox_widget(self.details_frame, range(6, 11), 'Ch 2 Idle Setpoint')
        self.frame_ch2_idle_setpoint_dropdown.grid(row=self.frame_guaranteed_soak_2_row+3, column=0, padx=0, pady=5, sticky='ew')

    def add_step(self):
        # Add step logic
        pass

    def update_step(self):
        # Update step logic
        pass

    def remove_step(self):
        # Remove step logic
        pass

    def on_treeview_select(self, event):
        selected_item = self.tree.selection()
        if selected_item:
            self.current_step_id = self.tree.item(selected_item)['text']
            self.load_step_details(self.current_step_id)

    def load_step_details(self, step_id):
        # Load step details logic
        pass

    def new_file(self):
        self.current_file = None
        self.tree.delete(*self.tree.get_children())

    def open_file(self):
        file_path = filedialog.askopenfilename(defaultextension=FILE_EXTENSION, filetypes=[("CSV Files", FILE_EXTENSION)])
        if file_path:
            self.current_file = file_path
            self.load_file(file_path)

    def load_file(self, file_path):
        self.tree.delete(*self.tree.get_children())
        with open(file_path, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                self.tree.insert('', 'end', text=row['step_type'], values=(row['step_type'], row['key_value']))

    def save_file(self):
        if self.current_file:
            with open(self.current_file, 'w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=HEADER)
                writer.writeheader()
                for item in self.tree.get_children():
                    values = self.tree.item(item, 'values')
                    writer.writerow({'step_type': values[0], 'key_value': values[1]})
        else:
            file_path = filedialog.asksaveasfilename(defaultextension=FILE_EXTENSION, filetypes=[("CSV Files", FILE_EXTENSION)])
            if file_path:
                self.current_file = file_path
                self.save_file()

    def show_help(self):
        messagebox.showinfo("Help", "Help information goes here.")
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        print(f"Width: {width}, Height: {height}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ProgramEditor(root)
    root.mainloop()
