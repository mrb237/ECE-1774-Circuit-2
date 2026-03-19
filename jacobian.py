import numpy as np
from bus import Bus
from circuit import Circuit


class Jacobian:
    def __init__(self):
        self.num_buses = len(self.buses)

        # Count PV buses
        self.num_pv = 0
        for bus in self.buses.values():
            if bus.bus_type == "PV":
                self.num_pv += 1

        self.size = (2 * self.num_buses) - 2 - self.num_pv

        self.jacobian = np.zeros((self.size, self.size), dtype=float)

    def calc_jacobian(self, buses, ybus, angles, voltages):
        for bus in self.buses.values():
            if bus.bus_type == "PQ":
                # P & Q

            if bus.bus_type == "PV":
                # P

            if bus.bus_type == "Slack":
                continue