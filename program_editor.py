import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import csv
from typing import Union
from datetime import timedelta as td

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

class ProgramEditor:
    steps:list[ph.StepDetails] = []
    event_output_vars:list[tk.BooleanVar] = []
    guaranteed_soak_vars:list[tk.BooleanVar] = []
    channel_temp_setpoint_vars:list[tk.IntVar] = []
    ch_pid_selection_vars:list[tk.IntVar] = []
    ramp_rate_var:tk.StringVar = None
    duration_vars:list[tk.IntVar] = []
    jump_vars:list[tk.IntVar] = []
    current_file = None
    current_step_id = None
    step_detail_frames:list[tk.Frame] = []
    frame_jump_row = 8

    def __init__(self, root):
        self.root = root
        self.root.title("Watlow F4 Program Editor")
        self.root.geometry("520x600")  # Adjusted size for the combined view
        self.root.resizable(False, False)

        self.create_app_widgets()

    def create_app_widgets(self):
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

    def create_ramp_rate_entry_widget(self, parent_frame:tk.Frame) -> tk.Frame:
        frame = tk.Frame(parent_frame)
        frame.grid(row=len(self.step_detail_frames)+1, column=0, columnspan=2, padx=5, pady=5, sticky='ew')   
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=0)
        
        self.step_detail_frames.append(frame)

        frame_entry, self.ramp_rate_var = self.create_entry_widget(frame, "Rate per Minute (C):", 2, validation_limits=(0.1, 3000))
        frame_entry.grid(row=0, column=0, columnspan=2, pady=5, sticky='we')

        return frame
    
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

    def create_event_output_widgets(self, parent_frame:tk.Frame):
        frame = tk.Frame(parent_frame)
        frame.grid(row=len(self.step_detail_frames)+1, column=0, columnspan=2, pady=5, sticky='ew')
        
        self.step_detail_frames.append(frame)

        for i in range(4):
            frame.grid_columnconfigure(i, weight=1)

        tk.Label(frame, text="Wait for Event Output(s)", anchor='center').grid(row=0, columnspan=4)

        self.event_output_vars = []  # Clear the list before creating new checkboxes
        for i in range(8):
            var = tk.BooleanVar(value=False)
            self.event_output_vars.append(var)

            check_button = tk.Checkbutton(frame, text=str(i+1), variable=var)
            check_button.grid(row=i//4+1, column=i%4, padx=5, pady=2)

    def get_event_output_states(self) -> tuple[bool, list[bool]]:
        event_output_states = [checkbox_var.get() for checkbox_var in self.event_output_vars]
        return any(event_output_states), event_output_states

    def create_duration_widgets(self, parent_frame:tk.Frame):
        frame = tk.Frame(parent_frame)
        frame.grid(row=len(self.step_detail_frames)+1, column=0, columnspan=2, pady=5, sticky='ew')
        for i in range(3):
            frame.grid_columnconfigure(i, weight=1)
        
        self.step_detail_frames.append(frame)

        self.duration_vars = []

        frame_entry, var = self.create_entry_widget(frame, "Hours", 0, validation_limits=(0, 99), horizontal=False)
        frame_entry.grid(row=0, column=0, pady=5, sticky='ew')
        self.duration_vars.append(var)
        
        frame, var = self.create_entry_widget(frame, "Minutes", 0, validation_limits=(0, 99), horizontal=False)
        frame.grid(row=0, column=1, pady=5, sticky='ew')
        self.duration_vars.append(var) 

        frame, var = self.create_entry_widget(frame, "Seconds", 1, validation_limits=(1, 99), horizontal=False)
        frame.grid(row=0, column=2, pady=5, sticky='ew')
        self.duration_vars.append(var)
   
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

        self.ch_pid_selection_vars = []  # Clear the list before creating new comboboxes
        for i in range(1, widget_count+1):
            label = tk.Label(frame, text=f"Ch {i} PID Selection:", anchor='center')
            label.grid(row=i, column=0, padx=5, pady=5, sticky='w')

            start_value = 5 * (i - 1) + 1

            var = tk.IntVar(value=start_value)
            self.ch_pid_selection_vars.append(var)
            combobox = ttk.Combobox(frame, textvariable=var, values=[x for x in range(start_value, start_value + i)], state="readonly", width=2)
            combobox.grid(row=i, column=1, padx=5, pady=5, sticky='e')
            combobox.current(0)

        return frame

    def create_guaranteed_soak_widgets(self, parent_frame:tk.Frame, widget_count:int) -> tk.Frame:
        frame = tk.Frame(parent_frame)
        frame.grid(row=len(self.step_detail_frames)+1, column=0, columnspan=2, padx=0, pady=5, sticky='ew')
        for i in range(2):
            frame.grid_columnconfigure(i, weight=1)

        self.step_detail_frames.append(frame)

        self.guaranteed_soak_vars = []  # Clear the list before creating new checkboxes
        for i in range(1, widget_count+1):
            label = tk.Label(frame, text=f"Guarantee Soak {i}:", anchor='center')
            label.grid(row=i, column=0, padx=5, pady=0, sticky='ew')

            var = tk.BooleanVar(value=False)
            self.guaranteed_soak_vars.append(var)

            check_button = tk.Checkbutton(frame, variable=var)
            check_button.grid(row=i, column=1, padx=5, pady=0, sticky='ew')

        return frame

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

    def create_ramp_by_time_widgets(self):
        self.create_event_output_widgets(self.details_frame)
        self.create_duration_widgets(self.details_frame)
        self.create_channel_temp_setpoint_widgets(self.details_frame, 2)
        self.create_channel_pid_selection_widgets(self.details_frame, 2)
        self.create_guaranteed_soak_widgets(self.details_frame, 2)

    def create_ramp_by_rate_widgets(self):
        self.create_event_output_widgets(self.details_frame)
        self.create_ramp_rate_entry_widget(self.details_frame)
        self.create_channel_temp_setpoint_widgets(self.details_frame, 1)
        self.create_channel_pid_selection_widgets(self.details_frame, 1)
        self.create_guaranteed_soak_widgets(self.details_frame, 1)

    def create_soak_widgets(self):
        self.create_event_output_widgets(self.details_frame)
        self.create_duration_widgets(self.details_frame)
        self.create_channel_temp_setpoint_widgets(self.details_frame, 2)
        self.create_channel_pid_selection_widgets(self.details_frame, 2)
        self.create_guaranteed_soak_widgets(self.details_frame, 2)

    def create_entry_widget(self, parent_frame:tk.Frame, label_text:str, initial_value=0, validation_limits:tuple = None, horizontal:bool=True) -> tuple[tk.Frame, tk.IntVar]:
        frame = tk.Frame(parent_frame)

        label = tk.Label(frame, text=label_text, anchor='center')

        var = tk.IntVar(value=initial_value)
        entry = tk.Entry(frame, textvariable=var, width=5)

        if horizontal:
            label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
            entry.grid(row=0, column=1, padx=5, pady=5, sticky='e')
            frame.grid_columnconfigure(0, weight=1)
            frame.grid_columnconfigure(1, weight=1)
        else:
            label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
            entry.grid(row=1, column=0, padx=5, pady=5, sticky='e')
            frame.grid_rowconfigure(0, weight=1)
            frame.grid_rowconfigure(1, weight=1)

        if validation_limits:
            limit_lo, limit_hi = validation_limits[0], validation_limits[1]
        entry.bind('<KeyRelease>', lambda event: self.update_buttons_state(entry, limit_lo, limit_hi, event))

        return frame, var 

    def create_jump_widgets(self):
        frame = tk.Frame(self.details_frame)
        frame.grid(row=len(self.step_detail_frames)+1, column=0, columnspan=2, padx=0, pady=5, sticky='ew')
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)

        self.step_detail_frames.append(frame)

        self.jump_vars = [] #clear the list before making new vars

        frame, var = self.create_entry_widget(frame, "Jump To Profile:", 1, validation_limits=(1, 40))
        frame.grid(row=0, column=0, columnspan=2, pady=5, sticky='we')
        self.jump_vars.append(var)

        frame, var = self.create_entry_widget(frame, "Jump To Step:", 1, validation_limits=(1, 256))
        frame.grid(row=1, column=0, columnspan=2, pady=5, sticky='we')
        self.jump_vars.append(var)

        frame, var = self.create_entry_widget(frame, "Number of Repeats:", 1, validation_limits=(1, 999))
        frame.grid(row=2, column=0, columnspan=2, pady=5, sticky='we')
        self.jump_vars.append(var)

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

    def update_buttons_state(self, entry:tk.Entry, limit_lo:int, limit_hi:int, event=None):
        if (self.validate_entry(entry, entry.get(), limit_lo, limit_hi)):
            self.add_button.config(state='normal')
            self.update_button.config(state='normal')
        else:
            self.add_button.config(state='disabled')
            self.update_button.config(state='disabled')

    def create_end_widgets(self):
        frame = tk.Frame(self.details_frame)
        frame.grid(row=len(self.step_detail_frames)+1, column=0, columnspan=2, padx=0, pady=5, sticky='ew')

        for i in range(2):
            frame.grid_columnconfigure(i, weight=1)

        for i in range(3):
            frame.grid_rowconfigure(i, weight=1)

        self.step_detail_frames.append(frame)

        self.end_vars = [] #clear the list before making new vars

        self.frame_end_action_combobox, self.end_action_combobox = self.create_combobox_widget(frame, [step_type.value for step_type in ph.EndActions], 'End Action:')
        self.frame_end_action_combobox.grid(row=0, column=0, columnspan=2, padx=0, pady=5, sticky='ew')
        self.end_action_combobox.config(width=12)
        self.end_action_combobox.grid(padx=0)

        self.frame_ch1_idle_setpoint_dropdown, self.ch1idle_setpoint_dropdown = self.create_combobox_widget(frame, range(1, 6), 'Ch 1 Idle Setpoint')
        self.frame_ch1_idle_setpoint_dropdown.grid(row=1, column=0, padx=0, pady=5, sticky='ew')
        
        self.frame_ch2_idle_setpoint_dropdown, self.ch2idle_setpoint_dropdown = self.create_combobox_widget(frame, range(6, 11), 'Ch 2 Idle Setpoint')
        self.frame_ch2_idle_setpoint_dropdown.grid(row=2, column=0, padx=0, pady=5, sticky='ew')

    def get_duration_timedelta(self) -> td:
        return td(hours=int(self.hours_entry.get), 
                minutes=int(self.minutes_entry.get), 
                seconds=int(self.seconds_entry.get))

    def add_step(self):
        step_type = self.step_type_dropdown.get()

        if step_type == ph.StepTypeName.RAMP_BY_TIME.value:
            wait_for_state, event_output_states = self.get_event_output_states()
            self.get_duration_timedelta()
            self.channel_temp_setpoint_vars[0].get()
            self.channel_temp_setpoint_vars[1].get()
            self.ch_pid_selection_vars[0].get() - 1
            self.ch_pid_selection_vars[1].get() - 1
            self.guaranteed_soak_vars[0].get()
            self.guaranteed_soak_vars[1].get()
        elif step_type == ph.StepTypeName.RAMP_BY_RATE.value:
            wait_for_state, event_output_states = self.get_event_output_states()
            float(self.ramp_rate_var.get())
            self.channel_temp_setpoint_vars[0].get()
            self.ch_pid_selection_vars[0].get() - 1
            self.guaranteed_soak_vars[0].get()
        elif step_type == ph.StepTypeName.SOAK.value:
            wait_for_state, event_output_states = self.get_event_output_states()
            self.get_duration_timedelta()
            self.ch_pid_selection_vars[0].get() - 1
            self.ch_pid_selection_vars[1].get() - 1
            self.guaranteed_soak_vars[0].get()
            self.guaranteed_soak_vars[1].get()
        elif step_type == ph.StepTypeName.JUMP.value:
            self.jump_vars[0].get()
            self.jump_vars[1].get()
            self.jump_vars[2].get()
        elif step_type == ph.StepTypeName.END.value:
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
