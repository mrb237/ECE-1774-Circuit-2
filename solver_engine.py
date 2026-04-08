from bus import Bus
from circuit import Circuit
from jacobian import Jacobian, JacobianFormatter
from power_flow import PowerFlow
from settings import SETTINGS
import numpy as np


class SolverEngine:
    def __init__(self):
        self.circuit = None
        self.jacobian = None
        self.power_flow = None

        # Cache breaker state so we only re-solve when something changes
        self.last_breaker_state = {}

        self.build_default_circuit()
        self.solve_base_case()

    # ---------------------------------------------------------
    # BUILD DEFAULT CIRCUIT
    # ---------------------------------------------------------
    def build_default_circuit(self):
        Bus.index_counter = 0
        c = Circuit("5-Bus Runtime Circuit")

        # Buses
        c.add_bus("Bus1", 15.0, "Slack")
        c.add_bus("Bus2", 345.0, "PQ")
        c.add_bus("Bus3", 15.0, "PV")
        c.add_bus("Bus4", 345.0, "PQ")
        c.add_bus("Bus5", 345.0, "PQ")

        # Transformers
        c.add_transformer("T1", "Bus1", "Bus5", 0.0015, 0.02, 9999.0)
        c.add_transformer("T2", "Bus3", "Bus4", 0.00075, 0.01, 9999.0)

        # Transmission lines
        c.add_transmission_line("TL1", "Bus5", "Bus4", 0.00225, 0.025, 0.0, 0.44, 9999.0)
        c.add_transmission_line("TL2", "Bus5", "Bus2", 0.0045, 0.05, 0.0, 0.88, 9999.0)
        c.add_transmission_line("TL3", "Bus4", "Bus2", 0.009, 0.1, 0.0, 1.72, 9999.0)

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
        self.last_breaker_state = self.get_breaker_state()

    # ---------------------------------------------------------
    # REFRESH OBJECTS
    # ---------------------------------------------------------
    def refresh_objects(self):
        self.circuit.update_load_models()
        self.circuit.update_generator()
        self.circuit.calc_ybus()
        self.jacobian = Jacobian(self.circuit)
        self.power_flow = PowerFlow(self.circuit, self.jacobian)

    # ---------------------------------------------------------
    # BREAKER HELPERS
    # ---------------------------------------------------------
    def get_breaker_state(self):
        return {
            name: breaker.is_closed
            for name, breaker in self.circuit.breakers.items()
        }

    def breakers_changed(self):
        current = self.get_breaker_state()
        changed = current != self.last_breaker_state
        return changed

    def update_breaker_cache(self):
        self.last_breaker_state = self.get_breaker_state()

    def set_breaker(self, breaker_name: str, closed: bool):
        br = self.circuit.breakers[breaker_name]
        if closed:
            br.close()
        else:
            br.open()

    # ---------------------------------------------------------
    # SOLVING
    # ---------------------------------------------------------
    def solve(self, flat_start=False, print_diagnostics=True, title="Solve"):
        self.refresh_objects()
        result = self.power_flow.solve(flat_start=flat_start)

        # Explicitly write solved values back into the circuit
        for bus_name, data in result["bus_data"].items():
            self.circuit.buses[bus_name].vpu = data["vpu"]
            self.circuit.buses[bus_name].delta = data["delta"]

        self.refresh_objects()
        self.update_breaker_cache()

        if print_diagnostics:
            self.print_diagnostics(title)

        return result

    def solve_base_case(self):
        return self.solve(flat_start=True, print_diagnostics=True, title="Base Case")

    def resolve(self):
        if self.breakers_changed():
            print("\nBreaker state change detected. Re-solving...")
            return self.solve(flat_start=False, print_diagnostics=True, title="Recalculated Case")
        return None

    # ---------------------------------------------------------
    # PRINT DIAGNOSTICS
    # ---------------------------------------------------------
    def print_bus_data(self):
        print("\nBus Data:")
        for name, bus in self.circuit.buses.items():
            print(f"{name}: V = {bus.vpu:.6f} pu, delta = {bus.delta:.6f} deg, type = {bus.bus_type}")

    def print_ybus(self, decimals=4):
        print("\nYbus Matrix:")
        print(self.circuit.ybus.round(decimals))

    def print_mismatch(self, decimals=6):
        mismatch = self.circuit.compute_power_mismatch()

        print("\nPower Mismatch Vector:")
        print(np.round(mismatch, decimals))

        active_buses = self.circuit.get_active_bus_names()

        non_slack_buses = [
            bus for bus in self.circuit.buses.values()
            if bus.name in active_buses and bus.bus_type != "Slack"
        ]

        pq_buses = [
            bus for bus in self.circuit.buses.values()
            if bus.name in active_buses and bus.bus_type == "PQ"
        ]

        print("\nStructured Mismatch Output:")
        for i, bus in enumerate(non_slack_buses):
            print(f"ΔP at {bus.name}: {mismatch[i]:.{decimals}f}")

        q_start = len(non_slack_buses)
        for i, bus in enumerate(pq_buses):
            print(f"ΔQ at {bus.name}: {mismatch[q_start + i]:.{decimals}f}")

    def print_jacobian(self, decimals=4):
        self.refresh_objects()
        jacobian_matrix = self.jacobian.calc_jacobian()

        print("\nJacobian Matrix:")
        formatter = JacobianFormatter(self.jacobian)
        print(formatter.to_dataframe().round(decimals))

    def print_breaker_states(self):
        print("\nBreaker States:")
        for name, breaker in self.circuit.breakers.items():
            print(f"{name}: {'Closed' if breaker.is_closed else 'Open'}")

    def print_diagnostics(self, title="Diagnostics"):
        print(f"\n================ {title} ================")
        self.print_breaker_states()
        self.print_bus_data()
        self.print_ybus()
        self.print_mismatch()
        self.print_jacobian()

    # ---------------------------------------------------------
    # FLOW DIRECTION FOR LED MANAGER
    # ---------------------------------------------------------
    def _parse_direction(self, direction_text, from_bus, to_bus, quantity_type):
        if direction_text is None:
            return "forward"

        text = direction_text.replace(" ", "")

        forward_token = f"{from_bus}{quantity_type}->{to_bus}"
        reverse_token = f"{to_bus}{quantity_type}->{from_bus}"

        if forward_token in text:
            return "forward"
        elif reverse_token in text:
            return "reverse"

        return "forward"

    def get_led_flow_data(self):
        self.refresh_objects()
        flow_results_tl_tf, _ = self.power_flow.compute_power_flow_direction(SETTINGS)

        led_flow_data = {}

        for element_name, data in flow_results_tl_tf.items():
            from_bus = data["from_bus"]
            to_bus = data["to_bus"]

            p_direction = self._parse_direction(data.get("direction", ""), from_bus, to_bus, "p")
            q_direction = self._parse_direction(data.get("direction_q", ""), from_bus, to_bus, "q")

            connected = True
            breaker_name = f"BR_{element_name}"
            if breaker_name in self.circuit.breakers:
                connected = self.circuit.breakers[breaker_name].is_closed

            led_flow_data[element_name] = {
                "type": data["type"],
                "from_bus": from_bus,
                "to_bus": to_bus,
                "p_direction": p_direction,
                "q_direction": q_direction,
                "connected": connected
            }

        return led_flow_data

    def print_led_flow_summary(self):
        flow_data = self.get_led_flow_data()

        print("\nLED Flow Summary:")
        for name, data in flow_data.items():
            print(f"{name}:")
            print(f"  Type:       {data['type']}")
            print(f"  From Bus:   {data['from_bus']}")
            print(f"  To Bus:     {data['to_bus']}")
            print(f"  P Dir:      {data['p_direction']}")
            print(f"  Q Dir:      {data['q_direction']}")
            print(f"  Connected:  {data['connected']}")