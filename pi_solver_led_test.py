import time
import RPi.GPIO as GPIO

from solver_engine import SolverEngine
from led_manager import LEDManager


BREAKER_GPIO_MAP = {
    1: 4,
    2: 17,
    3: 27,
    4: 22,
    5: 23,
    6: 24,
    7: 25,
    8: 21 # Change
}


def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    for pin in BREAKER_GPIO_MAP.values():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)


def cleanup_gpio():
    GPIO.cleanup()


def main():
    solver = SolverEngine()
    leds = LEDManager()

    setup_gpio()

    # Solve base case once
    solver.solve_base_case()
    leds.update_from_flows(solver.get_led_flow_data())

    print("Running continuous breaker + LED loop. Ctrl+C to stop.")

    try:
        while True:
            topology_changed = False

            current_states = solver.get_breaker_number_states()

            for breaker_num, pin in BREAKER_GPIO_MAP.items():
                pin_high = GPIO.input(pin)

                # HIGH = open, LOW = closed
                desired_closed = not bool(pin_high)
                current_closed = current_states[breaker_num]

                if current_closed != desired_closed:
                    print(
                        f"Breaker {breaker_num}: "
                        f"{'closing' if desired_closed else 'opening'}"
                    )
                    solver.set_breaker_number(breaker_num, desired_closed)
                    topology_changed = True

            if topology_changed:
                solver.solve(
                    flat_start=False,
                    print_diagnostics=True,
                    title="Breaker Change Solve"
                )

            leds.update_from_flows(solver.get_led_flow_data())

            time.sleep(0.15)

    except KeyboardInterrupt:
        print("Stopping...")

    finally:
        leds.clear()
        leds.show()
        cleanup_gpio()


if __name__ == "__main__":
    main()