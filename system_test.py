import numpy as np
import pandas as pd

from bus import Bus
from circuit import Circuit
from jacobian import Jacobian, JacobianFormatter
from power_flow import PowerFlow


class SystemTest:
    """
    Test harness for the 5-bus senior design system.

    Purpose:
    - Build a reusable 5-bus circuit
    - Test Ybus construction
    - Test power mismatch vector
    - Test Jacobian matrix
    - Test full Newton-Raphson power flow
    - Easily toggle breakers for scenario testing
    """

    def __init__(self):
        self.circuit = None
        self.jacobian = None
        self.power_flow = None

    # ---------------------------------------------------------
    # CIRCUIT BUILD
    # ---------------------------------------------------------
    def build_default_circuit(self):
        Bus.index_counter = 0
        c = Circuit("5-Bus Test Circuit")

        # Buses
        c.add_bus("Bus1", 15.0, "Slack")
        c.add_bus("Bus2", 345.0, "PQ")
        c.add_bus("Bus3", 15.0, "PV")
        c.add_bus("Bus4", 345.0, "PQ")
        c.add_bus("Bus5", 345.0, "PQ")

        # Transformers
        c.add_transformer("T1", "Bus1", "Bus5", 0.0015, 0.02)
        c.add_transformer("T2", "Bus3", "Bus4", 0.00075, 0.01)

        # Transmission lines
        c.add_transmission_line("TL1", "Bus5", "Bus4", 0.00225, 0.025, 0.0, 0.44)
        c.add_transmission_line("TL2", "Bus5", "Bus2", 0.0045, 0.05, 0.0, 0.88)
        c.add_transmission_line("TL3", "Bus4", "Bus2", 0.009, 0.1, 0.0, 1.72)

        # Generators
        c.add_generator("G1", "Bus1", 1.00, 0.0)
        c.add_generator("G2", "Bus3", 1.05, 520.0)

        # Loads
        c.add_load("L1", "Bus3", 80.0, 40.0)
        c.add_load("L2", "Bus2", 800.0, 280.0)

        # Breakers
        c.add_breaker("BR_T1", "Bus1", "Bus5", True)
        c.add_breaker("BR_T2", "Bus3", "Bus4", True)
        c.add_breaker("BR_TL1", "Bus5", "Bus4", True)
        c.add_breaker("BR_TL2", "Bus5", "Bus2", True)
        c.add_breaker("BR_TL3", "Bus4", "Bus2", True)

        self.circuit = c
        self.circuit.calc_ybus()
        self.jacobian = Jacobian(self.circuit)
        self.power_flow = PowerFlow(self.circuit, self.jacobian)
        return self.circuit

    # ---------------------------------------------------------
    # BREAKER CONTROL
    # ---------------------------------------------------------
    def set_breaker(self, breaker_name: str, closed: bool):
        if breaker_name not in self.circuit.breakers:
            raise KeyError(f"Breaker '{breaker_name}' not found.")

        if closed:
            self.circuit.breakers[breaker_name].close()
        else:
            self.circuit.breakers[breaker_name].open()

        self.circuit.calc_ybus()
        self.jacobian = Jacobian(self.circuit)
        self.power_flow = PowerFlow(self.circuit, self.jacobian)

    def print_breaker_states(self):
        print("\nBreaker States:")
        for name, br in self.circuit.breakers.items():
            state = "Closed" if br.is_closed else "Open"
            print(f"  {name}: {state}")

    # ---------------------------------------------------------
    # TESTS
    # ---------------------------------------------------------
    def test_ybus(self, decimals: int = 4):
        self.circuit.calc_ybus()
        print("\nYbus Matrix:")
        print(self.circuit.ybus.round(decimals))
        return self.circuit.ybus

    def test_power_mismatch(self, decimals: int = 6):
        mismatch = self.circuit.compute_power_mismatch()

        print("\nPower Mismatch Vector:")
        print(np.round(mismatch, decimals))

        print("\nStructured Mismatch Output:")
        idx = 0
        for bus in self.circuit.buses.values():
            if bus.bus_type == "Slack":
                continue

            print(f"ΔP at {bus.name}: {mismatch[idx]:.{decimals}f}")
            idx += 1

            if bus.bus_type == "PQ":
                print(f"ΔQ at {bus.name}: {mismatch[idx]:.{decimals}f}")
                idx += 1

        return mismatch

    def test_jacobian(self, decimals: int = 4):
        self.circuit.calc_ybus()
        self.jacobian = Jacobian(self.circuit)
        jacobian_matrix = self.jacobian.calc_jacobian()

        print("\nJacobian Matrix:")
        formatter = JacobianFormatter(self.jacobian)
        print(formatter.to_dataframe().round(decimals))

        print("\nJacobian Shape:")
        print(jacobian_matrix.shape)

        return jacobian_matrix

    def test_power_flow(self, tol: float = 0.001, max_iter: int = 50):
        result = self.power_flow.solve(tol=tol, max_iter=max_iter)

        print("\nNewton-Raphson Results:")
        print(f"Converged: {result['converged']}")
        print(f"Iterations: {result['iterations']}\n")

        for bus_name, data in result["bus_data"].items():
            print(f"{bus_name}:")
            print(f"  Voltage (pu): {data['vpu']:.6f}")
            print(f"  Angle (deg):  {data['delta']:.6f}\n")

        return result

    # ---------------------------------------------------------
    # CONVENIENCE METHODS
    # ---------------------------------------------------------
    def run_all_tests(self):
        self.print_breaker_states()
        self.test_ybus()
        self.test_power_mismatch()
        self.test_jacobian()
        self.test_power_flow()

    def run_breaker_scenario(self, breaker_name: str, closed: bool):
        print(f"\n--- Testing Scenario: {breaker_name} -> {'Closed' if closed else 'Open'} ---")
        self.set_breaker(breaker_name, closed)
        self.print_breaker_states()
        self.test_ybus()
        self.test_power_mismatch()
        try:
            self.test_jacobian()
            self.test_power_flow()
        except Exception as e:
            print(f"\nPower flow failed for this scenario: {e}")


if __name__ == "__main__":
    tester = SystemTest()
    tester.build_default_circuit()

    # Base case
    tester.run_all_tests()

    # Example breaker scenario
    tester.run_breaker_scenario("BR_TL2", False)