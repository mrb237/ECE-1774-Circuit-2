from bus import Bus
from circuit import Circuit
from jacobian import Jacobian, JacobianFormatter
from power_flow import PowerFlow
from settings import SETTINGS
import numpy as np


class SystemTest:
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

        # Breakers
        c.add_breaker("BR_G1", "G1", "Bus1", True)
        c.add_breaker("BR_G2", "G2", "Bus3", True)

        c.add_breaker("BR_T1", "Bus1", "Bus5", True)
        c.add_breaker("BR_T2", "Bus3", "Bus4", True)

        c.add_breaker("BR_TL1", "Bus5", "Bus4", True)
        c.add_breaker("BR_TL2", "Bus5", "Bus2", True)
        c.add_breaker("BR_TL3", "Bus4", "Bus2", True)

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
    # RESET MODEL TO DEFAULT POWER VALUES / BUS TYPES
    # ---------------------------------------------------------
    def reset_default_model(self):
        # Default loads
        self.circuit.loads["L1"].p = 80.0/SETTINGS.sbase
        self.circuit.loads["L1"].q = 40.0/SETTINGS.sbase
        self.circuit.loads["L2"].p = 800.0/SETTINGS.sbase
        self.circuit.loads["L2"].q = 280.0/SETTINGS.sbase

        # Default bus roles
        self.circuit.buses["Bus1"].bus_type = "Slack"
        self.circuit.buses["Bus3"].bus_type = "PV"

    # ---------------------------------------------------------
    # BREAKER CONTROL
    # ---------------------------------------------------------
    def set_breaker(self, breaker_name, closed):
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
    # DISPLAY HELPERS
    # ---------------------------------------------------------
    def print_ybus(self, decimals=2):
        print("\nYbus Matrix:")
        print(self.circuit.ybus.round(decimals))

    def print_mismatch(self, decimals=2):
        mismatch = self.circuit.compute_power_mismatch()

        print("\nPower Mismatch Vector:")
        print(np.round(mismatch, decimals))

        print("\nStructured Mismatch Output:")

        non_slack_buses = [bus for bus in self.circuit.buses.values() if bus.bus_type != "Slack"]
        pq_buses = [bus for bus in self.circuit.buses.values() if bus.bus_type == "PQ"]

        # First all ΔP terms
        for i, bus in enumerate(non_slack_buses):
            print(f"ΔP at {bus.name}: {mismatch[i]:.{decimals}f}")

        # Then all ΔQ terms for PQ buses only
        q_start = len(non_slack_buses)
        for i, bus in enumerate(pq_buses):
            print(f"ΔQ at {bus.name}: {mismatch[q_start + i]:.{decimals}f}")

        return mismatch

    def print_jacobian(self, decimals=4):
        self.refresh_objects()
        jacobian_matrix = self.jacobian.calc_jacobian()

        print("\nJacobian Matrix:")
        formatter = JacobianFormatter(self.jacobian)
        print(formatter.to_dataframe().round(decimals))

        return jacobian_matrix

    def print_bus_results(self, result, title="Bus Results"):
        print(f"\n{title}")
        print(f"Converged: {result['converged']}")
        print(f"Iterations: {result['iterations']}")

        if "error" in result:
            print(f"Error: {result['error']}")

        print()
        for bus_name, data in result.get("bus_data", {}).items():
            print(f"{bus_name}:")
            print(f"  Voltage (pu): {data['vpu']:.6f}")
            print(f"  Angle (deg):  {data['delta']:.6f}")
            print()

    # ---------------------------------------------------------
    # APPLY REFERENCE STATES
    # ---------------------------------------------------------
    def apply_base_case_state(self):
        self.reset_default_model()

        self.circuit.buses["Bus1"].vpu = 1.00000
        self.circuit.buses["Bus1"].delta = 0.00

        self.circuit.buses["Bus2"].vpu = 0.83377
        self.circuit.buses["Bus2"].delta = -22.4063

        self.circuit.buses["Bus3"].vpu = 1.05000
        self.circuit.buses["Bus3"].delta = -0.5973

        self.circuit.buses["Bus4"].vpu = 1.01930
        self.circuit.buses["Bus4"].delta = -2.8340

        self.circuit.buses["Bus5"].vpu = 0.97429
        self.circuit.buses["Bus5"].delta = -4.5479

    def apply_tl2_open_running_state(self):
        self.reset_default_model()

        # Match PowerWorld bus values
        self.circuit.buses["Bus1"].vpu = 1.00000
        self.circuit.buses["Bus1"].delta = 0.00

        self.circuit.buses["Bus2"].vpu = 0.19606
        self.circuit.buses["Bus2"].delta = -47.33

        self.circuit.buses["Bus3"].vpu = 0.91960
        self.circuit.buses["Bus3"].delta = 10.50

        self.circuit.buses["Bus4"].vpu = 0.87801
        self.circuit.buses["Bus4"].delta = 7.57

        self.circuit.buses["Bus5"].vpu = 0.94568
        self.circuit.buses["Bus5"].delta = 3.08

        # Match PowerWorld Bus 2 load
        self.circuit.loads["L2"].p = 145.12/SETTINGS.sbase
        self.circuit.loads["L2"].q = 50.79/SETTINGS.sbase

    def apply_tl2_open_before_start_state(self):
        self.reset_default_model()

        self.circuit.buses["Bus1"].vpu = 1.00000
        self.circuit.buses["Bus1"].delta = 0.00

        self.circuit.buses["Bus2"].vpu = 1.03630
        self.circuit.buses["Bus2"].delta = -62.23

        self.circuit.buses["Bus3"].vpu = 1.05729
        self.circuit.buses["Bus3"].delta = -7.22

        self.circuit.buses["Bus4"].vpu = 1.02216
        self.circuit.buses["Bus4"].delta = -9.65

        self.circuit.buses["Bus5"].vpu = 1.00943
        self.circuit.buses["Bus5"].delta = -4.33

        self.circuit.loads["L2"].p = 800.0/SETTINGS.sbase
        self.circuit.loads["L2"].q = 280.0/SETTINGS.sbase

    # ---------------------------------------------------------
    # G1 OPEN (Slack generator removed)
    # Bus3 becomes Slack, Bus1 becomes PQ
    # ---------------------------------------------------------
    def set_roles_for_g1_open(self):
        self.circuit.buses["Bus1"].bus_type = "PQ"
        self.circuit.buses["Bus3"].bus_type = "Slack"

    def apply_g1_open_before_start_state(self):
        self.reset_default_model()
        self.set_roles_for_g1_open()

        self.circuit.buses["Bus1"].vpu = 0.82030
        self.circuit.buses["Bus1"].delta = -12.22

        self.circuit.buses["Bus2"].vpu = 0.59905
        self.circuit.buses["Bus2"].delta = -37.81

        self.circuit.buses["Bus3"].vpu = 1.05000
        self.circuit.buses["Bus3"].delta = 0.00

        self.circuit.buses["Bus4"].vpu = 0.95573
        self.circuit.buses["Bus4"].delta = -4.37

        self.circuit.buses["Bus5"].vpu = 0.82030
        self.circuit.buses["Bus5"].delta = -12.22

        self.circuit.loads["L2"].p = 759.64/SETTINGS.sbase
        self.circuit.loads["L2"].q = 265.87/SETTINGS.sbase

    def apply_g1_open_running_state(self):
        self.reset_default_model()
        self.set_roles_for_g1_open()

        self.circuit.buses["Bus1"].vpu = 0.82034
        self.circuit.buses["Bus1"].delta = -12.82

        self.circuit.buses["Bus2"].vpu = 0.59912
        self.circuit.buses["Bus2"].delta = -38.40

        self.circuit.buses["Bus3"].vpu = 1.05000
        self.circuit.buses["Bus3"].delta = -0.60

        self.circuit.buses["Bus4"].vpu = 0.95575
        self.circuit.buses["Bus4"].delta = -4.97

        self.circuit.buses["Bus5"].vpu = 0.82034
        self.circuit.buses["Bus5"].delta = -12.82

        self.circuit.loads["L2"].p = 759.70/SETTINGS.sbase
        self.circuit.loads["L2"].q = 265.90/SETTINGS.sbase

    # ---------------------------------------------------------
    # G2 OPEN (PV generator removed)
    # Bus1 remains Slack, Bus3 becomes PQ
    # ---------------------------------------------------------
    def set_roles_for_g2_open(self):
        self.circuit.buses["Bus1"].bus_type = "Slack"
        self.circuit.buses["Bus3"].bus_type = "PQ"

    def apply_g2_open_before_start_state(self):
        self.reset_default_model()
        self.set_roles_for_g2_open()

        self.circuit.buses["Bus1"].vpu = 1.00000
        self.circuit.buses["Bus1"].delta = 0.00

        self.circuit.buses["Bus2"].vpu = 0.45017
        self.circuit.buses["Bus2"].delta = -45.52

        self.circuit.buses["Bus3"].vpu = 0.68492
        self.circuit.buses["Bus3"].delta = -17.01

        self.circuit.buses["Bus4"].vpu = 0.69172
        self.circuit.buses["Bus4"].delta = -16.08

        self.circuit.buses["Bus5"].vpu = 0.77027
        self.circuit.buses["Bus5"].delta = -9.78

        self.circuit.loads["L2"].p = 573.83/SETTINGS.sbase
        self.circuit.loads["L2"].q = 200.84/SETTINGS.sbase

    def apply_g2_open_running_state(self):
        self.reset_default_model()
        self.set_roles_for_g2_open()

        self.circuit.buses["Bus1"].vpu = 1.00000
        self.circuit.buses["Bus1"].delta = 0.00

        self.circuit.buses["Bus2"].vpu = 0.45015
        self.circuit.buses["Bus2"].delta = -45.52

        self.circuit.buses["Bus3"].vpu = 0.68490
        self.circuit.buses["Bus3"].delta = -17.01

        self.circuit.buses["Bus4"].vpu = 0.69170
        self.circuit.buses["Bus4"].delta = -16.08

        self.circuit.buses["Bus5"].vpu = 0.77026
        self.circuit.buses["Bus5"].delta = -9.78

        self.circuit.loads["L2"].p = 573.79/SETTINGS.sbase
        self.circuit.loads["L2"].q = 200.83/SETTINGS.sbase

    # ---------------------------------------------------------
    # L2 OPEN (load removed)
    # ---------------------------------------------------------
    def apply_l2_open_state(self):
        self.reset_default_model()

        self.circuit.buses["Bus1"].vpu = 1.00000
        self.circuit.buses["Bus1"].delta = 0.00

        self.circuit.buses["Bus2"].vpu = 1.09201
        self.circuit.buses["Bus2"].delta = 6.02

        self.circuit.buses["Bus3"].vpu = 1.05000
        self.circuit.buses["Bus3"].delta = 11.76

        self.circuit.buses["Bus4"].vpu = 1.05649
        self.circuit.buses["Bus4"].delta = 9.45

        self.circuit.buses["Bus5"].vpu = 1.04004
        self.circuit.buses["Bus5"].delta = 4.64

        self.circuit.loads["L2"].p = 0.0/SETTINGS.sbase
        self.circuit.loads["L2"].q = 0.0/SETTINGS.sbase

    # ---------------------------------------------------------
    # T2 OPEN REFERENCE ONLY
    # This creates an islanded / removed Bus 3 in PowerWorld.
    # Your current solver likely does not fully support removing
    # that bus from the active NR system, so this is best handled
    # as a reference / reporting case for now.
    # ---------------------------------------------------------
    def apply_t2_open_state(self):
        self.reset_default_model()

        # Bus 3 removed / isolated in PowerWorld
        # We mimic that by opening the transformer, generator, and load
        # connected to Bus 3.
        self.set_breaker("BR_T2", False)
        self.set_breaker("BR_G2", False)
        self.set_breaker("BR_L1", False)

        self.circuit.buses["Bus1"].vpu = 1.00000
        self.circuit.buses["Bus1"].delta = 0.00

        self.circuit.buses["Bus2"].vpu = 0.47739
        self.circuit.buses["Bus2"].delta = -43.36

        self.circuit.buses["Bus3"].vpu = 0.00000
        self.circuit.buses["Bus3"].delta = 0.00

        self.circuit.buses["Bus4"].vpu = 0.72936
        self.circuit.buses["Bus4"].delta = -13.46

        self.circuit.buses["Bus5"].vpu = 0.79093
        self.circuit.buses["Bus5"].delta = -9.01

        # Bus 3 load and generation removed
        self.circuit.loads["L1"].p = 0.0/SETTINGS.sbase
        self.circuit.loads["L1"].q = 0.0/SETTINGS.sbase

        self.circuit.loads["L2"].p = 616.44/SETTINGS.sbase
        self.circuit.loads["L2"].q = 215.75/SETTINGS.sbase

    # ---------------------------------------------------------
    # TEST CASES
    # ---------------------------------------------------------
    def test_base_case(self):
        print("\n===================================================")
        print("CASE 0: BASE CASE")
        print("===================================================")

        self.build_default_circuit()
        self.reset_default_model()
        self.print_breaker_states()
        self.print_ybus()
        self.print_mismatch()
        self.print_jacobian()

        result = self.power_flow.solve(tol=0.001, max_iter=50, flat_start=True)
        self.print_bus_results(result, title="Base Case Results")

    def test_base_case_validation(self):
        print("\n===================================================")
        print("CASE 0A: BASE CASE VALIDATION")
        print("===================================================")

        self.build_default_circuit()
        self.apply_base_case_state()
        self.print_breaker_states()
        self.print_ybus()
        self.print_mismatch()
        self.print_jacobian()

    def test_tl2_open_running(self):
        print("\n===================================================")
        print("CASE 1: TL2 OPEN WHILE RUNNING")
        print("===================================================")

        self.build_default_circuit()
        self.power_flow.solve(tol=0.001, max_iter=50, flat_start=True)

        self.set_breaker("BR_TL2", False)
        self.apply_tl2_open_running_state()

        self.print_breaker_states()
        self.print_ybus()
        self.print_mismatch()
        self.print_jacobian()

    def test_tl2_open_before_start(self):
        print("\n===================================================")
        print("CASE 2: TL2 OPEN BEFORE START")
        print("===================================================")

        self.build_default_circuit()
        self.set_breaker("BR_TL2", False)

        self.print_breaker_states()
        self.print_ybus()
        self.print_mismatch()
        self.print_jacobian()

        result = self.power_flow.solve(tol=0.001, max_iter=50, flat_start=True)
        self.print_bus_results(result, title="TL2 Open Before Start Results")

    def test_g1_open_running(self):
        print("\n===================================================")
        print("CASE 3: G1 (SLACK) OPEN WHILE RUNNING")
        print("===================================================")

        self.build_default_circuit()
        self.power_flow.solve(tol=0.001, max_iter=50, flat_start=True)

        self.set_breaker("BR_G1", False)
        self.apply_g1_open_running_state()

        self.print_breaker_states()
        self.print_ybus()
        self.print_mismatch()
        self.print_jacobian()

    def test_g1_open_before_start(self):
        print("\n===================================================")
        print("CASE 4: G1 (SLACK) OPEN BEFORE START")
        print("===================================================")

        self.build_default_circuit()
        self.set_breaker("BR_G1", False)
        self.apply_g1_open_before_start_state()

        self.print_breaker_states()
        self.print_ybus()
        self.print_mismatch()
        self.print_jacobian()

    def test_g2_open_running(self):
        print("\n===================================================")
        print("CASE 5: G2 (PV) OPEN WHILE RUNNING")
        print("===================================================")

        self.build_default_circuit()
        self.power_flow.solve(tol=0.001, max_iter=50, flat_start=True)

        self.set_breaker("BR_G2", False)
        self.apply_g2_open_running_state()

        self.print_breaker_states()
        self.print_ybus()
        self.print_mismatch()
        self.print_jacobian()

    def test_g2_open_before_start(self):
        print("\n===================================================")
        print("CASE 6: G2 (PV) OPEN BEFORE START")
        print("===================================================")

        self.build_default_circuit()
        self.set_breaker("BR_G2", False)
        self.apply_g2_open_before_start_state()

        self.print_breaker_states()
        self.print_ybus()
        self.print_mismatch()
        self.print_jacobian()

    def test_l2_open_running(self):
        print("\n===================================================")
        print("CASE 7: L2 OPEN WHILE RUNNING")
        print("===================================================")

        self.build_default_circuit()
        self.power_flow.solve(tol=0.001, max_iter=50, flat_start=True)

        self.set_breaker("BR_L2", False)
        self.apply_l2_open_state()

        self.print_breaker_states()
        self.print_ybus()
        self.print_mismatch()
        self.print_jacobian()

    def test_l2_open_before_start(self):
        print("\n===================================================")
        print("CASE 8: L2 OPEN BEFORE START")
        print("===================================================")

        self.build_default_circuit()
        self.set_breaker("BR_L2", False)
        self.apply_l2_open_state()

        self.print_breaker_states()
        self.print_ybus()
        self.print_mismatch()
        self.print_jacobian()

    def test_t2_open_reference(self):
        print("\n===================================================")
        print("CASE 9: T2 OPEN REFERENCE CASE")
        print("===================================================")
        print("NOTE: Bus 3 is islanded / removed in this PowerWorld case.")
        print("This is currently treated as a reference state only.")

        self.build_default_circuit()
        self.apply_t2_open_state()

        self.print_breaker_states()
        self.print_ybus()

        print("\nReference bus values for T2-open case applied.")
        print("Mismatch / Jacobian comparison may not be meaningful until")
        print("the solver supports removing islanded buses from the active system.")

    # ---------------------------------------------------------
    # RUN ALL
    # ---------------------------------------------------------
    def run_all_reference_tests(self):
        self.test_base_case()
        self.test_base_case_validation()

        self.test_tl2_open_running()
        self.test_tl2_open_before_start()

        self.test_g1_open_running()
        self.test_g1_open_before_start()

        self.test_g2_open_running()
        self.test_g2_open_before_start()

        self.test_l2_open_running()
        self.test_l2_open_before_start()

        self.test_t2_open_reference()


if __name__ == "__main__":
    tester = SystemTest()
    tester.run_all_reference_tests()