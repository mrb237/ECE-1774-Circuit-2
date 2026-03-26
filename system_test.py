import numpy as np
import pandas as pd

from bus import Bus
from circuit import Circuit
from jacobian import Jacobian, JacobianFormatter
from power_flow import PowerFlow


class SystemTest:
    """
    Reusable test harness for the senior design 5-bus system.

    Supports:
    - building the default circuit
    - printing Ybus
    - printing mismatch vector
    - printing Jacobian
    - running Newton-Raphson
    - testing breaker open/close scenarios
    """

    def __init__(self):
        self.circuit = None
        self.jacobian = None
        self.power_flow = None

    # ---------------------------------------------------------
    # BUILD DEFAULT 5-BUS SYSTEM
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

        # Branch breakers
        c.add_breaker("BR_T1", "Bus1", "Bus5", True)
        c.add_breaker("BR_T2", "Bus3", "Bus4", True)
        c.add_breaker("BR_TL1", "Bus5", "Bus4", True)
        c.add_breaker("BR_TL2", "Bus5", "Bus2", True)
        c.add_breaker("BR_TL3", "Bus4", "Bus2", True)

        # Optional generator/load breakers (not yet active in mismatch unless you add logic)
        c.add_breaker("BR_G1", "G1", "Bus1", True)
        c.add_breaker("BR_G2", "G2", "Bus3", True)
        c.add_breaker("BR_L1", "L1", "Bus3", True)
        c.add_breaker("BR_L2", "L2", "Bus2", True)

        self.circuit = c
        self.refresh_objects()
        return self.circuit

    # ---------------------------------------------------------
    # REFRESH SOLVER OBJECTS
    # ---------------------------------------------------------
    def refresh_objects(self):
        self.circuit.calc_ybus()
        self.jacobian = Jacobian(self.circuit)
        self.power_flow = PowerFlow(self.circuit, self.jacobian)

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

        self.refresh_objects()

    def print_breaker_states(self):
        print("\nBreaker States:")
        for name, br in self.circuit.breakers.items():
            state = "Closed" if br.is_closed else "Open"
            print(f"  {name}: {state}")

    # ---------------------------------------------------------
    # OPTIONAL: APPLY A KNOWN CONVERGED STATE
    # ---------------------------------------------------------
    def apply_known_converged_state(self):
        self.circuit.buses["Bus1"].vpu = 1.0000000000
        self.circuit.buses["Bus1"].delta = 0.00

        self.circuit.buses["Bus2"].vpu = 0.8337700000000000
        self.circuit.buses["Bus2"].delta = -22.4064031191349180

        self.circuit.buses["Bus3"].vpu = 1.0499999812655256
        self.circuit.buses["Bus3"].delta = -0.5973411159680668

        self.circuit.buses["Bus4"].vpu = 1.0193023987537509
        self.circuit.buses["Bus4"].delta = -2.8339706604176557

        self.circuit.buses["Bus5"].vpu = 0.9742886948445556
        self.circuit.buses["Bus5"].delta = -4.5478833180645389

    # ---------------------------------------------------------
    # TEST METHODS
    # ---------------------------------------------------------
    def test_ybus(self, decimals=4):
        self.circuit.calc_ybus()
        print("\nYbus Matrix:")
        print(self.circuit.ybus.round(decimals))
        return self.circuit.ybus

    def test_power_mismatch(self, decimals=6):
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

    def test_jacobian(self, decimals=4):
        self.refresh_objects()
        jacobian_matrix = self.jacobian.calc_jacobian()

        print("\nJacobian Matrix:")
        formatter = JacobianFormatter(self.jacobian)
        print(formatter.to_dataframe().round(decimals))

        print("\nJacobian Shape:")
        print(jacobian_matrix.shape)

        return jacobian_matrix

    def test_power_flow(self, tol=0.001, max_iter=50):
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
    # CONVENIENCE RUNNERS
    # ---------------------------------------------------------
    def run_base_case(self):
        print("\n=== BASE CASE ===")
        self.print_breaker_states()
        self.test_ybus()
        self.test_power_mismatch()
        self.test_jacobian()
        self.test_power_flow()

    def run_converged_state_check(self):
        print("\n=== KNOWN CONVERGED STATE CHECK ===")
        self.apply_known_converged_state()
        self.test_power_mismatch()
        self.test_jacobian()

    def run_breaker_scenario(self, breaker_name, closed):
        print(f"\n=== BREAKER SCENARIO: {breaker_name} -> {'Closed' if closed else 'Open'} ===")
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

    tester.run_base_case()
    tester.run_converged_state_check()
    tester.run_breaker_scenario("BR_TL2", False)