import time
import RPi.GPIO as GPIO

from solver_engine import SolverEngine
from led_manager import LEDManager


# -----------------------------------------
# Breaker GPIO mapping
# These are OUTPUT pins that reflect breaker states
# HIGH = breaker open
# LOW  = breaker closed
# -----------------------------------------
BREAKER_OUTPUT_GPIO_MAP = {
    1: 4,    # G1
    2: 17,   # T1
    3: 27,   # TL1
    4: 22,   # T2
    5: 23,   # G2 + L1
    6: 24,   # TL3
    7: 25,   # L2
    8: 21    # TL2
}

# -----------------------------------------
# Manual switch input
# GPIO 26 controls TL3 only
# -----------------------------------------
TL3_SWITCH_PIN = 26
TL3_BREAKER_NUM = 6


def setup_gpio():
    GPIO.setmode(GPIO.BCM)

    # Breaker state outputs
    for pin in BREAKER_OUTPUT_GPIO_MAP.values():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

    # Manual switch input for TL3
    GPIO.setup(TL3_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)


def cleanup_gpio():
    GPIO.cleanup()


def push_breaker_outputs(solver):
    """
    Reflect software breaker states to GPIO outputs.
    HIGH = breaker open
    LOW  = breaker closed
    """
    breaker_states = solver.get_breaker_number_states()

    for breaker_num, pin in BREAKER_OUTPUT_GPIO_MAP.items():
        is_closed = breaker_states[breaker_num]
        GPIO.output(pin, GPIO.LOW if is_closed else GPIO.HIGH)


def main():
    solver = SolverEngine()
    leds = LEDManager(
        led_count=174,
        pin=18,
        brightness=120
    )

    setup_gpio()

    # -----------------------------------------
    # Solve base case once
    # -----------------------------------------
    solver.solve_base_case()

    # Push initial breaker outputs
    push_breaker_outputs(solver)

    # Initial LED update
    flow_data = solver.get_led_flow_data()
    leds.update_from_flows(flow_data)

    print("Running TL3 switch + breaker output + LED test loop. Ctrl+C to stop.")

    try:
        last_switch_state = GPIO.input(TL3_SWITCH_PIN)

        while True:
            current_switch_state = GPIO.input(TL3_SWITCH_PIN)

            # -----------------------------------------
            # GPIO 26 switch controls TL3
            # HIGH = open TL3
            # LOW  = close TL3
            # -----------------------------------------
            if current_switch_state != last_switch_state:
                desired_closed = not bool(current_switch_state)

                print(
                    f"TL3 switch changed on GPIO {TL3_SWITCH_PIN}: "
                    f"{'closing' if desired_closed else 'opening'} TL3"
                )

                solver.set_breaker_number(TL3_BREAKER_NUM, desired_closed)

                solver.solve(
                    flat_start=False,
                    print_diagnostics=True,
                    title="TL3 Switch Change Solve"
                )

                # Update physical breaker output pins
                push_breaker_outputs(solver)

                # Update LEDs from solved flow data
                flow_data = solver.get_led_flow_data()
                leds.update_from_flows(flow_data)

                last_switch_state = current_switch_state

            # -----------------------------------------
            # Keep LED animation moving continuously
            # -----------------------------------------
            flow_data = solver.get_led_flow_data()
            leds.update_from_flows(flow_data)

            time.sleep(0.15)

    except KeyboardInterrupt:
        print("Stopping...")

    finally:
        leds.clear()
        leds.show()
        cleanup_gpio()


if __name__ == "__main__":
    main()