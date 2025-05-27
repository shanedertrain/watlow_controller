import time
import logging
from typing import Callable, List, Tuple, Optional, Dict 
from dataclasses import dataclass

from watlow_f4 import WatlowF4, PIDParameters
from watlow_f4 import (
    PB_ENG_PARAM, INTEGRAL_SI_ENG_PARAM, DERIVATIVE_SI_ENG_PARAM, 
    RESET_US_ENG_PARAM, RATE_US_ENG_PARAM, DB_ENG_PARAM, HYST_ENG_PARAM
)

@dataclass
class StepResponseData:
    time_points: List[float]          # Relative time from the start of data collection for the step
    temp_points: List[float]          # Corresponding temperature readings
    initial_setpoint: float           # The setpoint before the step change
    final_setpoint: float             # The setpoint after the step change
    step_command_execution_time: float # Actual duration the step setpoint was active and data collected

# Clamp helper function
def clamp(val: float, min_val: float, max_val: float) -> float:
    return max(min(val, max_val), min_val)

def perform_step_test(
    controller: WatlowF4,
    read_temperature_func: Callable[[], float],
    initial_sp: float,
    final_sp: float,
    duration_seconds: int,
    sample_interval_seconds: float = 1.0,
    settle_time_seconds: int = 60 # Increased default settle time
) -> StepResponseData:
    """
    Performs a step test on the Watlow F4 and collects temperature response data.
    """
    controller.logger.info(f"Preparing for step test: SP {initial_sp} -> {final_sp}. Duration: {duration_seconds}s, Settle: {settle_time_seconds}s.")
    
    controller.set_temperature_setpoint(initial_sp)
    controller.logger.info(f"Allowing system to settle at initial_sp {initial_sp}°C for {settle_time_seconds}s...")
    time.sleep(settle_time_seconds) 

    time_points: List[float] = []
    temp_points: List[float] = []
    
    # Record one point at initial_sp right before the step command
    pv_at_initial_sp = read_temperature_func()
    time_points.append(0.0) # Relative time 0 for the point just before step
    temp_points.append(pv_at_initial_sp)
    controller.logger.info(f"Pre-step temperature at SP {initial_sp}°C is {pv_at_initial_sp:.2f}°C")

    step_command_issue_time = time.time()
    controller.set_temperature_setpoint(final_sp)
    controller.logger.info(f"Setpoint stepped from {initial_sp}°C to {final_sp}°C at system time {step_command_issue_time:.2f}")

    num_samples = int(duration_seconds / sample_interval_seconds)

    for i in range(1, num_samples + 1): # Start collecting data after the step
        # Calculate the target absolute time for this sample
        target_sample_abs_time = step_command_issue_time + (i * sample_interval_seconds)
        
        # Sleep until it's time for the next sample
        sleep_duration = target_sample_abs_time - time.time()
        if sleep_duration > 0:
            time.sleep(sleep_duration)
        
        actual_sample_time_offset = time.time() - step_command_issue_time
        external_temp = read_temperature_func()
        
        time_points.append(actual_sample_time_offset)
        temp_points.append(external_temp)
        controller.logger.debug(f"Step Test Data: RelTime={actual_sample_time_offset:.2f}s, Temp={external_temp:.2f}°C")
        
    actual_step_test_duration = time.time() - step_command_issue_time
    controller.logger.info(f"Step test data collection finished. Collected {len(temp_points)} points over ~{actual_step_test_duration:.2f}s.")
    return StepResponseData(time_points, temp_points, initial_sp, final_sp, actual_step_test_duration)


def find_reaction_curve_params(
    response_data: StepResponseData, 
    sample_interval: float # Used as a fallback or for context
) -> Tuple[float, float, float]:
    """
    Estimates Kp (Process Gain), L (Dead Time), T (Time Constant) from step response.
    This is a simplified graphical interpretation and needs robust implementation for real systems.
    Assumes a positive PV change (heating step). Modify for cooling steps if needed.
    """
    time_pts = response_data.time_points
    temp_pts = response_data.temp_points
    logger = logging.getLogger("ReactionCurveAnalyzer") # Use a specific logger

    if len(time_pts) < 3: 
        logger.warning("Not enough data points (<3) to estimate reaction curve parameters reliably.")
        return 0.1, sample_interval * 2, sample_interval * 5 

    # First data point is pre-step
    initial_pv = temp_pts[0] 
    # Analyze data from the actual step onwards
    step_time_pts = [t for t in time_pts if t >= 0] # Should be all except potentially the first t=0 if it was pre-step start
    step_temp_pts = temp_pts[len(time_pts) - len(step_time_pts):]

    if not step_temp_pts:
        logger.warning("No data points after step command for analysis.")
        return 0.1, sample_interval * 2, sample_interval * 5

    final_pv_steady_state = step_temp_pts[-1] 
    delta_pv_total = final_pv_steady_state - initial_pv
    
    # Process Gain: Assumes the step was induced by a 100% change in controller output.
    # This is a rough approximation for a closed-loop setpoint change.
    delta_co_assumed_percent = 100.0 
    Kp_process = delta_pv_total / delta_co_assumed_percent if abs(delta_co_assumed_percent) > 1e-6 else 0.1
    if abs(Kp_process) < 1e-9:  # Avoid extremely small or zero gain
        logger.warning(f"Calculated Kp_process is very small ({Kp_process:.2e}). Using fallback 0.1.")
        Kp_process = 0.1 * (1 if delta_pv_total >= 0 else -1)


    # Find point of maximum slope on the data *after* the step was initiated
    max_slope = 0.0
    slope_time_start = 0.0 # Time relative to step_command_issue_time
    slope_pv_start = initial_pv

    if len(step_time_pts) > 1:
        for i in range(len(step_temp_pts) - 1):
            dt = step_time_pts[i+1] - step_time_pts[i]
            if dt < 1e-6: continue # Avoid division by zero, skip if time hasn't changed
            
            current_slope = (step_temp_pts[i+1] - step_temp_pts[i]) / dt
            if abs(current_slope) > abs(max_slope): # Consider magnitude for heating/cooling
                max_slope = current_slope
                slope_time_start = step_time_pts[i]
                slope_pv_start = step_temp_pts[i]
    
    if abs(max_slope) < 1e-6:
        logger.warning("Max slope is near zero. Cannot determine L and T reliably. Using fallbacks.")
        return Kp_process, sample_interval * 2, sample_interval * 5 

    # Estimate L (Dead time): Time from step command until the line of max slope intersects initial_pv
    # L = t_at_slope_start - (pv_at_slope_start - initial_pv) / max_slope
    L = slope_time_start - (slope_pv_start - initial_pv) / max_slope
    L = max(0, L) # Dead time cannot be negative

    # Estimate T (Time constant): Time for PV to reach 63.2% of total change *after* dead time L.
    pv_at_L = initial_pv + L * max_slope # Temperature at the end of dead time, along the max slope line
    target_temp_for_T_calc = pv_at_L + 0.632 * (final_pv_steady_state - pv_at_L)
    
    time_at_63_percent_after_L = L 
    found_T_point = False
    for i in range(len(step_temp_pts)):
        if step_time_pts[i] >= L and step_temp_pts[i] >= target_temp_for_T_calc:
            time_at_63_percent_after_L = step_time_pts[i]
            found_T_point = True
            break
    
    if not found_T_point and len(step_time_pts) > 0 : # If 63.2% not reached, extrapolate or use total time
         T = (final_pv_steady_state - pv_at_L) / max_slope if abs(max_slope)> 1e-6 else sample_interval * 3
    else:
        T = time_at_63_percent_after_L - L
    
    T = max(T, sample_interval) # Ensure T is positive and at least one sample interval

    logger.info(f"Reaction Curve Params: Kp_process={Kp_process:.4f}, L={L:.2f}s, T={T:.2f}s (MaxSlope={max_slope:.3f})")
    return Kp_process, L, T


def calculate_new_watlow_pids_from_step_response(
    response_data: StepResponseData,
    pid_units_mode: str,
    sample_interval: float, 
    pid_type: str = "PID" 
) -> PIDParameters:
    # (Implementation using Z-N from previous response, ensure EngParamRange objects are used for clamping)
    # ... (ensure this function is complete and robust as discussed before) ...
    logging.info(f"Analyzing step response for {pid_type} tuning. Mode: {pid_units_mode}")
    Kp_proc, L, T = find_reaction_curve_params(response_data, sample_interval)

    # Fallback if L or T are problematic
    if L < sample_interval / 10.0 : L = sample_interval / 10.0 # Ensure L is small but non-zero if too small
    if T < sample_interval : T = sample_interval # Ensure T is at least one sample interval

    Kc, Ti_s, Td_s = 0.0, float('inf'), 0.0 # Controller Gain, Integral Time (s), Derivative Time (s)

    if abs(Kp_proc * L) < 1e-9:
        logging.warning("Kp_proc * L is near zero for Z-N. Resulting PB might be max (min gain).")
        pb_new = PB_ENG_PARAM.max
        # Set I and D to minimal action if P gain is effectively zero
        Ti_s = INTEGRAL_SI_ENG_PARAM.max * 60.0 if pid_units_mode == "SI" else (1.0 / RESET_US_ENG_PARAM.min if RESET_US_ENG_PARAM.min > 0 else float('inf'))
        Td_s = 0.0
    else:
        if pid_type.upper() == "P":
            Kc = T / (Kp_proc * L)
        elif pid_type.upper() == "PI":
            Kc = 0.9 * T / (Kp_proc * L)
            Ti_s = L / 0.3
        elif pid_type.upper() == "PID": # Ziegler-Nichols Classic PID
            Kc = 1.2 * T / (Kp_proc * L)
            Ti_s = 2.0 * L
            Td_s = 0.5 * L
        else:
            raise ValueError(f"Unknown PID type for tuning: {pid_type}. Choose 'P', 'PI', or 'PID'.")
        
        # Convert Controller Gain (Kc) to Proportional Band (PB in PV units)
        # PB (units of PV) = Full Control Output Range (%) / Kc (%CO / unit PV_error)
        # Assuming full control output range is 100%
        pb_new = 100.0 / Kc if Kc != 0 else PB_ENG_PARAM.max


    integral_val_si, reset_val_us, derivative_val_si, rate_val_us = None, None, None, None

    if pid_units_mode == "SI":
        integral_val_si = Ti_s / 60.0 if Ti_s != float('inf') and Ti_s > 0 else INTEGRAL_SI_ENG_PARAM.max
        derivative_val_si = Td_s / 60.0 if Td_s > 0 else DERIVATIVE_SI_ENG_PARAM.min
    else: # US
        reset_val_us = 60.0 / Ti_s if Ti_s > 0 and Ti_s != float('inf') else RESET_US_ENG_PARAM.min
        rate_val_us = Td_s / 60.0 if Td_s > 0 else RATE_US_ENG_PARAM.min # Rate is also in minutes

    new_pids = PIDParameters(
        proportional_band=pb_new,
        integral=integral_val_si, reset=reset_val_us,
        derivative=derivative_val_si, rate=rate_val_us,
        dead_band=DB_ENG_PARAM.min, # Start with default/minimal dead_band
        hysteresis=HYST_ENG_PARAM.min    # Start with default/minimal hysteresis
    )
    
    # Clamp to Watlow F4 engineering limits
    new_pids.proportional_band = clamp(new_pids.proportional_band, PB_ENG_PARAM.min, PB_ENG_PARAM.max)
    if pid_units_mode == "SI":
        if new_pids.integral is not None: new_pids.integral = clamp(new_pids.integral, INTEGRAL_SI_ENG_PARAM.min, INTEGRAL_SI_ENG_PARAM.max)
        if new_pids.derivative is not None: new_pids.derivative = clamp(new_pids.derivative, DERIVATIVE_SI_ENG_PARAM.min, DERIVATIVE_SI_ENG_PARAM.max)
    else: # US
        if new_pids.reset is not None: new_pids.reset = clamp(new_pids.reset, RESET_US_ENG_PARAM.min, RESET_US_ENG_PARAM.max)
        if new_pids.rate is not None: new_pids.rate = clamp(new_pids.rate, RATE_US_ENG_PARAM.min, RATE_US_ENG_PARAM.max)
    
    # Deadband and Hysteresis are typically tuned separately or kept at defaults unless specific issues arise.
    if new_pids.dead_band is not None: new_pids.dead_band = clamp(new_pids.dead_band, DB_ENG_PARAM.min, DB_ENG_PARAM.max)
    if new_pids.hysteresis is not None and abs(new_pids.proportional_band) < 1e-6 : # Only meaningful if PB is zero (on/off)
        new_pids.hysteresis = clamp(new_pids.hysteresis, HYST_ENG_PARAM.min, HYST_ENG_PARAM.max)

    logging.info(f"Calculated PIDs (Z-N {pid_type}): {new_pids}")
    return new_pids


def your_pid_tuning_function(
    read_temperature_func: Callable[[], float],
    tuning_targets: List[Tuple[float, int, int, str]], # List of tuples: (target_setpoint_for_tuning, watlow_pid_set_to_apply_results_to, channel_to_tune, output_side_to_tune)
    initial_pid_guess: Optional[PIDParameters] = None,
    step_down_for_test_sp: float = 20.0, # How much to step down from target_sp to get the initial_sp for the test
    step_test_duration_s: int = 300,    # Duration to collect data after step
    step_test_sample_interval_s: float = 1.0,
    step_settle_time_s: int = 60,        # Time to settle at initial_sp before step
    verification_duration_s: int = 120,  # How long to observe after applying new PIDs
    zn_pid_type: str = "PID" # Type of Z-N tuning: "P", "PI", or "PID"
):
    """
    Tunes PID parameters for a list of target setpoints, applying results 
    to specified Watlow PID sets, channels, and output sides.
    """
    try:
        controller = WatlowF4(slave_address=1) # Ensure connection
        controller.logger.info("Successfully connected to Watlow F4 for tuning session.")
    except ConnectionError as e:
        logging.error(f"Failed to connect to Watlow F4: {e}", exc_info=True)
        return

    pid_units_mode = controller.get_pid_units_mode()
    tuned_pids_results: Dict[Tuple[int, int, str], PIDParameters] = {} # (target_sp, pid_set, ch, side) -> PIDs

    # Default initial PIDs if none provided (conservative)
    if initial_pid_guess is None:
        safe_pb = PB_ENG_PARAM.max * 0.8 
        initial_pid_guess = PIDParameters(
            proportional_band=safe_pb,
            integral=INTEGRAL_SI_ENG_PARAM.max if pid_units_mode == "SI" else None,
            reset=RESET_US_ENG_PARAM.min if pid_units_mode == "US" else None,
            derivative=DERIVATIVE_SI_ENG_PARAM.min if pid_units_mode == "SI" else None,
            rate=RATE_US_ENG_PARAM.min if pid_units_mode == "US" else None,
            dead_band=DB_ENG_PARAM.min, 
            hysteresis=HYST_ENG_PARAM.min
        )
        controller.logger.info(f"No initial PID guess provided, using safe defaults: {initial_pid_guess}")

    for target_sp, pid_set_to_tune, channel_to_tune, side_to_tune in tuning_targets:
        controller.logger.info(f"\n--- Starting tuning for Target SP: {target_sp}°C, Watlow PID Set: {pid_set_to_tune}, Ch: {channel_to_tune}, Side: {side_to_tune} ---")

        # 1. Set Initial/Safe PIDs for the current PID set being tuned
        controller.logger.info(f"Setting initial PIDs for Set {pid_set_to_tune} to: {initial_pid_guess}")
        try:
            controller.write_pid_parameters(
                initial_pid_guess, # Use the initial guess or last good tune for this set
                pid_set_number=pid_set_to_tune,
                channel=channel_to_tune,
                output_side=side_to_tune
            )
        except Exception as e:
            controller.logger.error(f"Failed to write initial PIDs for Set {pid_set_to_tune}: {e}", exc_info=True)
            continue # Skip to next target

        # 2. Perform Step Test
        initial_sp_for_test = target_sp - step_down_for_test_sp
        if initial_sp_for_test < 0 and target_sp > 0 : # Basic sanity for step down
            initial_sp_for_test = max(0, target_sp / 2.0)
        controller.logger.info(f"Step test will go from {initial_sp_for_test}°C to {target_sp}°C.")

        response_data = perform_step_test(
            controller, read_temperature_func,
            initial_sp=initial_sp_for_test,
            final_sp=target_sp,
            duration_seconds=step_test_duration_s,
            sample_interval_seconds=step_test_sample_interval_s,
            settle_time_seconds=step_settle_time_s
        )

        # 3. Analyze Response and Calculate New PIDs
        controller.logger.info(f"Step test completed for target {target_sp}°C. Calculating new PIDs using {zn_pid_type} rules.")
        try:
            new_calculated_pids = calculate_new_watlow_pids_from_step_response(
                response_data,
                pid_units_mode,
                step_test_sample_interval_s, # Pass sample interval
                pid_type=zn_pid_type
            )
        except Exception as e:
            controller.logger.error(f"Error calculating PIDs for target {target_sp}°C: {e}", exc_info=True)
            continue

        # 4. Apply New PIDs to the specific Watlow PID Set
        controller.logger.info(f"Applying newly calculated PIDs to Set {pid_set_to_tune}, Ch{channel_to_tune}{side_to_tune}: {new_calculated_pids}")
        try:
            controller.write_pid_parameters(
                new_calculated_pids,
                pid_set_number=pid_set_to_tune,
                channel=channel_to_tune,
                output_side=side_to_tune
            )
            tuned_pids_results[(target_sp, pid_set_to_tune, channel_to_tune, side_to_tune)] = new_calculated_pids
            controller.logger.info(f"New PIDs successfully applied for target {target_sp}°C.")
            
            # Update initial_pid_guess for the next iteration to start from the last successful tune (optional)
            # initial_pid_guess = new_calculated_pids 

        except Exception as e:
            controller.logger.error(f"Error writing new PIDs for target {target_sp}°C to Set {pid_set_to_tune}: {e}", exc_info=True)
            continue

        # 5. Optional Verification at the current target_sp with new PIDs
        if verification_duration_s > 0:
            controller.logger.info(f"Verifying system response at {target_sp}°C with new PIDs for {verification_duration_s}s...")
            # Setpoint is already at target_sp from the end of the step test or re-apply if needed
            controller.set_temperature_setpoint(target_sp) 
            
            verification_loop_start_time = time.time()
            for k in range(int(verification_duration_s / step_test_sample_interval_s)):
                loop_iter_start = time.time()
                ext_temp = read_temperature_func()
                err = target_sp - ext_temp
                controller.logger.info(f"Verification (SP:{target_sp:.1f}, Set:{pid_set_to_tune}): Time={(k+1)*step_test_sample_interval_s:.0f}s, Temp={ext_temp:.2f}, Error={err:.2f}")
                
                sleep_for = step_test_sample_interval_s - (time.time() - loop_iter_start)
                if sleep_for > 0 : time.sleep(sleep_for)
                if (time.time() - verification_loop_start_time) >= verification_duration_s: break
        
        controller.logger.info(f"--- Tuning for Target SP: {target_sp}°C, Watlow PID Set: {pid_set_to_tune} COMPLETE ---")

    controller.logger.info("\n===== PID Tuning Session Complete =====")
    if tuned_pids_results:
        controller.logger.info("Summary of tuned PID parameters:")
        for (tsp, p_set, ch, side), pids in tuned_pids_results.items():
            controller.logger.info(f"  Target SP: {tsp}°C (Watlow Set: {p_set}, Ch{ch}{side}) -> PIDs: {pids}")
    else:
        controller.logger.info("No PID parameters were successfully tuned.")
    
    return tuned_pids_results


if __name__ == "__main__":
    # Configure basic logging for the script
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Define the list of target setpoints and which Watlow PID Set to tune for each
    # Format: (target_setpoint_for_tuning, watlow_pid_set_number, channel, output_side)
    # Example: Tune PID Set 1 (Ch1, Side A) for 50C, and PID Set 2 (Ch1, Side A) for 100C
    targets_to_tune = [
        (50.0, 1, 1, 'A'),  # Target 50C, tune Watlow PID Set 1, Channel 1, Side A
        (100.0, 2, 1, 'A')  # Target 100C, tune Watlow PID Set 2, Channel 1, Side A
        # Add more targets: e.g. (150.0, 3, 1, 'A')
        # Or for a different channel/side: (75.0, 6, 2, 'A') for Channel 2, PID Set 6
    ]

    # Optional: Provide an initial guess for PID parameters for the very first tuning run
    # If None, very conservative defaults will be used.
    # This initial guess is used for the *first* step test's initial PID controller settings.
    # Subsequent step tests in the loop will also start with this unless you modify the logic.
    # initial_guess = PIDParameters(proportional_band=40.0, integral=5.0, derivative=0.5) # Example
    initial_guess = None

    print("Starting PID tuning function...")
    try:
        tuned_results = your_pid_tuning_function(
            get_temperature_func_mock_interactive, # REPLACE THIS with actual get_temperature_func
            targets_to_tune,
            initial_pid_guess=initial_guess,
            step_down_for_test_sp=15.0, # e.g. if target is 50, initial for step is 35
            step_test_duration_s=180,
            step_settle_time_s=20
        )
        if tuned_results:
            print("\nFinal Tuned PID sets map:")
            for key, pids in tuned_results.items():
                print(f"  TargetSP {key[0]}, WatlowSet {key[1]} Ch{key[2]}{key[3]}: {pids}")

    except ConnectionError as e:
        logging.error(f"Could not connect to Watlow controller: {e}")
    except Exception as e:
        logging.error(f"An error occurred during the tuning process: {e}", exc_info=True)
    
    print("PID tuning function script finished.")