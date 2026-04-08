import time
import RPi.GPIO as GPIO

from solver_engine import SolverEngine
from led_manager import LEDManager


# ---------------------------------------------------------
# GPIO CONFIG
# ---------------------------------------------------------
TL3_INPUT_PIN = 26   # <-- CHANGED TO GPIO 26


def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(TL3_INPUT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)


def cleanup_gpio():
    GPIO.cleanup()


def main():
    solver = SolverEngine()
    leds = LEDManager()

    setup_gpio()

    # Base case already solved
    leds.update_from_flows(solver.get_led_flow_data())
    solver.print_led_flow_summary()

    print("\nRunning Pi solver + LED loop. Press Ctrl+C to stop.")
    print(f"Monitoring GPIO {TL3_INPUT_PIN} for TL3 breaker control.")

    try:
        while True:
            # -------------------------------------------------
            # GPIO -> BREAKER LOGIC
            # -------------------------------------------------
            tl3_high = GPIO.input(TL3_INPUT_PIN)

            # HIGH = open breaker
            # LOW  = closed breaker
            desired_closed = not bool(tl3_high)

            current_closed = solver.circuit.breakers["BR_TL3"].is_closed

            if current_closed != desired_closed:
                if desired_closed:
                    print(f"\nGPIO {TL3_INPUT_PIN} LOW -> closing BR_TL3")
                else:
                    print(f"\nGPIO {TL3_INPUT_PIN} HIGH -> opening BR_TL3")

                solver.set_breaker("BR_TL3", desired_closed)

            # -------------------------------------------------
            # RESOLVE IF NEEDED
            # -------------------------------------------------
            result = solver.resolve_if_needed()

            # -------------------------------------------------
            # UPDATE LEDS EVERY LOOP
            # -------------------------------------------------
            leds.update_from_flows(solver.get_led_flow_data())

            if result is not None:
                solver.print_led_flow_summary()

            time.sleep(0.15)

    except KeyboardInterrupt:
        print("\nStopping...")

    finally:
        leds.clear()
        leds.show()
        cleanup_gpio()


if __name__ == "__main__":
    main()