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
        for kbus in self.buses.values():
            for nbus in self.buses.values():
                if kbus.bus_type == "Slack":
                    continue

                if kbus.bus_type == "PQ":
                    # P & Q, J1 - J4
                    if kbus==nbus:
                        # Slide 7 Calculations
                    # Else Slide 6 Calculations

                if kbus.bus_type == "PV":
                    # P, J1 and J2 only
                    if kbus==nbus:
                        # Slide 7 Calculations
                    # Else Slide 6 Calculations
