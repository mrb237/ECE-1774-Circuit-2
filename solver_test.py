from bus import Bus
from circuit import Circuit
from jacobian import Jacobian
from power_flow import PowerFlow
from settings import SETTINGS


class SolverTest:
    def __init__(self):
        self.circuit = None
        self.jacobian = None
        self.power_flow = None

    # ---------------------------------------------------------
    # BUILD DEFAULT 5-BUS SYSTEM
    # ---------------------------------------------------------
    def build_default_circuit(self):
        Bus.index_counter = 0
        c = Circuit("5-Bus Solver Test Circuit")

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
    # REFRESH OBJECTS
    # ---------------------------------------------------------
    def refresh_objects(self):
        self.circuit.update_generator()
        self.circuit.calc_ybus()
        self.jacobian = Jacobian(self.circuit)
        self.power_flow = PowerFlow(self.circuit, self.jacobian)

    # ---------------------------------------------------------
    # LOAD HELPER
    # ---------------------------------------------------------
    def set_load(self, load_name, mw, mvar):
        load = self.circuit.loads[load_name]
        load.mw = mw
        load.mvar = mvar
        load.p = mw / SETTINGS.sbase
        load.q = mvar / SETTINGS.sbase

    # ---------------------------------------------------------
    # RESET DEFAULT MODEL
    # ---------------------------------------------------------
    def reset_default_model(self):
        self.set_load("L1", 80.0, 40.0)
        self.set_load("L2", 800.0, 280.0)

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

    # ---------------------------------------------------------
    # DISPLAY HELPERS
    # ---------------------------------------------------------
    def print_breaker_states(self):
        print("\nBreaker States:")
        for name, br in self.circuit.breakers.items():
            state = "Closed" if br.is_closed else "Open"
            print(f"  {name}: {state}")

    def print_active_and_islanded_buses(self):
        active = sorted(self.circuit.get_active_bus_names())
        islanded = sorted(self.circuit.get_islanded_bus_names())

        print("\nActive Buses:")
        print(active)

        print("\nIslanded Buses:")
        print(islanded)

    def print_current_bus_state(self, title="Current Bus State"):
        print(f"\n{title}")
        for bus_name, bus in self.circuit.buses.items():
            print(f"{bus_name}:")
            print(f"  Voltage (pu): {bus.vpu:.6f}")
            print(f"  Angle (deg):  {bus.delta:.6f}")
            print(f"  Type:         {bus.bus_type}")
            print()

    def print_ybus(self, decimals=2):
        print("\nYbus Matrix:")
        print(self.circuit.ybus.round(decimals))

    # ---------------------------------------------------------
    # STORE / RESTORE SOLVED STATE
    # ---------------------------------------------------------
    def capture_bus_state(self):
        return {
            bus_name: {
                "vpu": bus.vpu,
                "delta": bus.delta
            }
            for bus_name, bus in self.circuit.buses.items()
        }

    def restore_bus_state(self, state_dict):
        for bus_name, values in state_dict.items():
            if bus_name in self.circuit.buses:
                self.circuit.buses[bus_name].vpu = values["vpu"]
                self.circuit.buses[bus_name].delta = values["delta"]

    # ---------------------------------------------------------
    # SAFE SOLVE
    # ---------------------------------------------------------
    def safe_solve(self, title="Solve Results", flat_start=True):
        try:
            result = self.power_flow.solve(tol=0.001, max_iter=50, flat_start=flat_start)
            print(f"\n{title}")
            print(f"Converged: {result['converged']}")
            print(f"Iterations: {result['iterations']}")
            return result
        except ValueError as e:
            print(f"\n{title}")
            print(f"Solve failed: {e}")
            return None

    # ---------------------------------------------------------
    # CONTINUATION SOLVE HELPER
    # ---------------------------------------------------------
    def solve_running_contingency(self, breaker_names, title):
        """
        For running cases:
        1. solve base case
        2. store solved V and delta
        3. open breaker(s)
        4. reapply stored solved V and delta
        5. rebuild system
        6. solve again from previous state
        """
        self.build_default_circuit()
        self.reset_default_model()

        base_result = self.safe_solve(title="Base Solve Before Breaker Opens", flat_start=True)
        if base_result is None:
            return None
        stored_state = self.capture_bus_state()


        self.print_current_bus_state("Stored Base Solved State")

        # Open one or more breakers
        for br in breaker_names:
            self.set_breaker(br, False)

        # Reapply stored solved state to buses
        self.restore_bus_state(stored_state)

        # Rebuild after topology change
        self.refresh_objects()

        self.print_breaker_states()
        self.print_active_and_islanded_buses()
        self.print_ybus()
        self.print_current_bus_state("Bus State Immediately After Breaker Opens")

        # Resolve from previous solved state
        result = self.safe_solve(title=title, flat_start=False)
        self.print_current_bus_state(f"Solved Bus State: {title}")
        return result

    def solve_before_start_contingency(self, breaker_names, title):
        """
        For before-start cases:
        1. build default circuit
        2. open breaker(s)
        3. solve from flat start
        """
        self.build_default_circuit()
        self.reset_default_model()

        for br in breaker_names:
            self.set_breaker(br, False)

        self.print_breaker_states()
        self.print_active_and_islanded_buses()
        self.print_ybus()

        result = self.safe_solve(title=title, flat_start=True)
        self.print_current_bus_state(f"Solved Bus State: {title}")
        return result

    # ---------------------------------------------------------
    # SCENARIOS
    # ---------------------------------------------------------
    def solve_base_case(self):
        print("\n===================================================")
        print("SOLVE CASE 0: BASE CASE")
        print("===================================================")

        self.build_default_circuit()
        self.reset_default_model()

        self.print_breaker_states()
        self.print_active_and_islanded_buses()
        self.print_ybus()

        result = self.safe_solve(title="Base Case", flat_start=True)
        self.print_current_bus_state("Solved Bus State: Base Case")
        return result

    def solve_tl2_open_running(self):
        print("\n===================================================")
        print("SOLVE CASE 1: TL2 OPEN WHILE RUNNING")
        print("===================================================")
        return self.solve_running_contingency(["BR_TL2"], "TL2 Open While Running")

    def solve_tl2_open_before_start(self):
        print("\n===================================================")
        print("SOLVE CASE 2: TL2 OPEN BEFORE START")
        print("===================================================")
        return self.solve_before_start_contingency(["BR_TL2"], "TL2 Open Before Start")

    def solve_tl3_open_running(self):
        print("\n===================================================")
        print("SOLVE CASE 3: TL3 (BUS 2 - BUS 4) OPEN WHILE RUNNING")
        print("===================================================")
        return self.solve_running_contingency(["BR_TL3"], "TL3 Open While Running")

    def solve_tl3_open_before_start(self):
        print("\n===================================================")
        print("SOLVE CASE 4: TL3 (BUS 2 - BUS 4) OPEN BEFORE START")
        print("===================================================")
        return self.solve_before_start_contingency(["BR_TL3"], "TL3 Open Before Start")

    def solve_g1_open_running(self):
        print("\n===================================================")
        print("SOLVE CASE 5: G1 (SLACK) OPEN WHILE RUNNING")
        print("===================================================")
        return self.solve_running_contingency(["BR_G1"], "G1 Open While Running")

    def solve_g1_open_before_start(self):
        print("\n===================================================")
        print("SOLVE CASE 6: G1 (SLACK) OPEN BEFORE START")
        print("===================================================")
        return self.solve_before_start_contingency(["BR_G1"], "G1 Open Before Start")

    def solve_g2_open_running(self):
        print("\n===================================================")
        print("SOLVE CASE 7: G2 (PV) OPEN WHILE RUNNING")
        print("===================================================")
        return self.solve_running_contingency(["BR_G2"], "G2 Open While Running")

    def solve_g2_open_before_start(self):
        print("\n===================================================")
        print("SOLVE CASE 8: G2 (PV) OPEN BEFORE START")
        print("===================================================")
        return self.solve_before_start_contingency(["BR_G2"], "G2 Open Before Start")

    def solve_l2_open_running(self):
        print("\n===================================================")
        print("SOLVE CASE 9: L2 OPEN WHILE RUNNING")
        print("===================================================")
        return self.solve_running_contingency(["BR_L2"], "L2 Open While Running")

    def solve_l2_open_before_start(self):
        print("\n===================================================")
        print("SOLVE CASE 10: L2 OPEN BEFORE START")
        print("===================================================")
        return self.solve_before_start_contingency(["BR_L2"], "L2 Open Before Start")

    def solve_t2_open_running(self):
        print("\n===================================================")
        print("SOLVE CASE 11: T2 OPEN WHILE RUNNING")
        print("===================================================")
        # Match your reference style more closely:
        # open T2, disconnect G2, disconnect L1
        return self.solve_running_contingency(["BR_T2", "BR_G2", "BR_L1"], "T2 Open While Running")

    def solve_t2_open_before_start(self):
        print("\n===================================================")
        print("SOLVE CASE 12: T2 OPEN BEFORE START")
        print("===================================================")
        return self.solve_before_start_contingency(["BR_T2", "BR_G2", "BR_L1"], "T2 Open Before Start")

    # ---------------------------------------------------------
    # RUN ALL
    # ---------------------------------------------------------
    def run_all_solver_tests(self):
        self.solve_base_case()
        self.solve_tl2_open_running()
        self.solve_tl2_open_before_start()
        self.solve_tl3_open_running()
        self.solve_tl3_open_before_start()
        self.solve_g1_open_running()
        self.solve_g1_open_before_start()
        self.solve_g2_open_running()
        self.solve_g2_open_before_start()
        self.solve_l2_open_running()
        self.solve_l2_open_before_start()
        self.solve_t2_open_running()
        self.solve_t2_open_before_start()


if __name__ == "__main__":
    tester = SolverTest()
    tester.run_all_solver_tests()