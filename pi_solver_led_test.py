import time
import RPi.GPIO as GPIO

from solver_engine import SolverEngine
from led_manager import LEDManager


# -----------------------------
# GPIO pins
# -----------------------------
TL3_SWITCH_PIN = 26   # input switch
TL3_OUTPUT_PIN = 24   # output signal
TL3_BREAKER_NAME = "BR_TL3"


def setup_gpio():
    GPIO.setmode(GPIO.BCM)

    # Input switch for TL3
    GPIO.setup(TL3_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    # Output pin for TL3 breaker state
    GPIO.setup(TL3_OUTPUT_PIN, GPIO.OUT)
    GPIO.output(TL3_OUTPUT_PIN, GPIO.LOW)


def cleanup_gpio():
    GPIO.cleanup()


def set_tl3_breaker_from_switch(circuit):
    """
    GPIO 26 HIGH  -> open TL3
    GPIO 26 LOW   -> close TL3

    Returns True if breaker state changed, else False.
    """
    desired_closed = not bool(GPIO.input(TL3_SWITCH_PIN))
    breaker = circuit.breakers[TL3_BREAKER_NAME]
    current_closed = breaker.is_closed

    if desired_closed != current_closed:
        if desired_closed:
            breaker.close()
            print("TL3 closed from GPIO 26")
        else:
            breaker.open()
            print("TL3 opened from GPIO 26")
        return True

    return False


def update_tl3_output_pin(circuit):
    """
    GPIO 24 HIGH when TL3 breaker is open
    GPIO 24 LOW when TL3 breaker is closed
    """
    breaker = circuit.breakers[TL3_BREAKER_NAME]

    if breaker.is_closed:
        GPIO.output(TL3_OUTPUT_PIN, GPIO.LOW)
    else:
        GPIO.output(TL3_OUTPUT_PIN, GPIO.HIGH)


def main():
    solver = SolverEngine()
    leds = LEDManager(
        led_count=174,
        pin=18,
        brightness=120
    )

    setup_gpio()

    try:
        # ---------------------------------
        # Build and solve base case once
        # ---------------------------------
        solver.build_default_circuit()
        solver.solve(
            flat_start=True,
            print_diagnostics=True,
            title="Base Case"
        )

        # Set GPIO 24 from initial TL3 state
        update_tl3_output_pin(solver.circuit)

        # Initial LED update
        flow_data = solver.get_led_flow_data()
        leds.update_from_flows(flow_data)

        print("Running TL3 switch / GPIO / LED test. Press Ctrl+C to stop.")

        while True:
            topology_changed = False

            # ---------------------------------
            # Check GPIO 26 and update TL3
            # ---------------------------------
            if set_tl3_breaker_from_switch(solver.circuit):
                topology_changed = True
                solver.refresh_objects()

            # ---------------------------------
            # Re-solve if TL3 changed
            # ---------------------------------
            if topology_changed:
                solver.solve(
                    flat_start=False,
                    print_diagnostics=True,
                    title="TL3 Change Solve"
                )

            # ---------------------------------
            # Update GPIO 24 from TL3 state
            # ---------------------------------
            update_tl3_output_pin(solver.circuit)

            # ---------------------------------
            # Update addressable LEDs
            # ---------------------------------
            flow_data = solver.get_led_flow_data()
            leds.update_from_flows(flow_data)

            time.sleep(0.15)

    except KeyboardInterrupt:
        print("Stopping test...")

    finally:
        leds.clear()
        leds.show()
        cleanup_gpio()


if __name__ == "__main__":
    main()