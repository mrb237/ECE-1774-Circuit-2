from bus import Bus
from circuit import Circuit
from jacobian import Jacobian
from power_flow import PowerFlow
from settings import SETTINGS


class SolverEngine:
    def __init__(self):
        self.circuit = None
        self.jacobian = None
        self.power_flow = None
        self.build_default_circuit()

    def build_default_circuit(self):
        Bus.index_counter = 0
        c = Circuit("5-Bus Runtime Circuit")

        c.add_bus("Bus1", 15.0, "Slack")
        c.add_bus("Bus2", 345.0, "PQ")
        c.add_bus("Bus3", 15.0, "PV")
        c.add_bus("Bus4", 345.0, "PQ")
        c.add_bus("Bus5", 345.0, "PQ")

        c.add_transformer("T1", "Bus1", "Bus5", 0.0015, 0.02, 9999.0)
        c.add_transformer("T2", "Bus3", "Bus4", 0.00075, 0.01, 9999.0)

        c.add_transmission_line("TL1", "Bus5", "Bus4", 0.00225, 0.025, 0.0, 0.44, 9999.0)
        c.add_transmission_line("TL2", "Bus5", "Bus2", 0.0045, 0.05, 0.0, 0.88, 9999.0)
        c.add_transmission_line("TL3", "Bus4", "Bus2", 0.009, 0.1, 0.0, 1.72, 9999.0)

        c.add_generator("G1", "Bus1", 1.00, 0.0)
        c.add_generator("G2", "Bus3", 1.05, 520.0)

        c.add_load("L1", "Bus3", 80.0, 40.0)
        c.add_load("L2", "Bus2", 800.0, 280.0)

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

    def refresh_objects(self):
        self.circuit.update_generator()
        self.circuit.calc_ybus()
        self.jacobian = Jacobian(self.circuit)
        self.power_flow = PowerFlow(self.circuit, self.jacobian)

    def solve(self, flat_start=False):
        self.refresh_objects()
        return self.power_flow.solve(flat_start=flat_start)

    def solve_base_case(self):
        return self.solve(flat_start=True)

    def set_breaker(self, breaker_name: str, closed: bool):
        br = self.circuit.breakers[breaker_name]
        if closed:
            br.close()
        else:
            br.open()
        self.refresh_objects()

    def get_bus_data(self):
        return {
            name: {
                "vpu": bus.vpu,
                "delta": bus.delta,
                "type": bus.bus_type,
            }
            for name, bus in self.circuit.buses.items()
        }

    def get_flow_directions(self):
        self.refresh_objects()
        tl_tf, gen_load = self.power_flow.compute_power_flow_direction(SETTINGS)
        return tl_tf, gen_load