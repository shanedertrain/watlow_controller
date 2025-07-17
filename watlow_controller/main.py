import time
from program_handler import Program, read_program_from_csv
from watlow_f4 import WatlowF4
from watlow_program_thread import WatlowProgramThread

def main():
    # Define the path to your CSV file
    csv_file_path = 'programs\oven_test.csv'

    # Read the program from the CSV file
    program = read_program_from_csv(csv_file_path)

    # Create an instance of the WatlowF4 class
    watlow = WatlowF4('/dev/ttyUSB0', 1)

    # Set initial temperature setpoint
    initial_temp = 25.0
    watlow.set_temperature_setpoint(initial_temp)

    # Create and start the program thread
    program_thread = WatlowProgramThread(watlow, program)
    program_thread.start()

    # Optionally, stop the thread after some time or based on some condition
    # For demonstration, we'll wait for 5 minutes before stopping the program
    time.sleep(300)  # Wait for 5 minutes (300 seconds)
    program_thread.stop()
    program_thread.join()  # Wait for the thread to finish

if __name__ == "__main__":
    main()
