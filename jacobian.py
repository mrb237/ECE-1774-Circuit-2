import numpy as np
import pandas as pd
from circuit import Circuit


class Jacobian:
    def __init__(self, circuit: Circuit):
        self.circuit = circuit
        self.buses = circuit.buses
        self.ybus = circuit.ybus

        active_bus_names = self.circuit.get_active_bus_names()
        self.ordered_buses = sorted(
            [bus for bus in self.buses.values() if bus.name in active_bus_names],
            key=lambda bus: bus.bus_index)

        self.angle_buses = [bus for bus in self.ordered_buses if bus.bus_type != "Slack"]
        self.voltage_buses = [bus for bus in self.ordered_buses if bus.bus_type == "PQ"]

        self.num_buses = len(self.ordered_buses)
        self.num_pv = sum(1 for bus in self.ordered_buses if bus.bus_type == "PV")

        self.size = (2 * self.num_buses) - 2 - self.num_pv
        self.jacobian = np.zeros((self.size, self.size), dtype=float)

        # Row/column lookup maps
        self.p_row_map = {bus.name: i for i, bus in enumerate(self.angle_buses)}
        self.q_row_map = {
            bus.name: i + len(self.angle_buses)
            for i, bus in enumerate(self.voltage_buses)
        }

        self.delta_col_map = {bus.name: i for i, bus in enumerate(self.angle_buses)}
        self.v_col_map = {
            bus.name: i + len(self.angle_buses)
            for i, bus in enumerate(self.voltage_buses)
        }

    def calc_jacobian(self, buses=None, ybus=None, angles=None, voltages=None):
        if buses is None:
            buses = self.buses
        if ybus is None:
            ybus = self.ybus

        self.jacobian = np.zeros((self.size, self.size), dtype=float)

        for kbus in self.ordered_buses:
            if kbus.bus_type == "Slack":
                continue

            k = kbus.bus_index

            # Use passed dictionaries if provided, otherwise use bus object values
            Vk = voltages[kbus.name] if voltages is not None else kbus.vpu
            delta_k = np.deg2rad(angles[kbus.name]) if angles is not None else np.deg2rad(kbus.delta)

            Pk, Qk = self.circuit.compute_power_injection(kbus)

            Gkk = ybus.iloc[k, k].real
            Bkk = ybus.iloc[k, k].imag

            # ----- ΔP row for this bus -----
            p_row = self.p_row_map[kbus.name]

            for nbus in self.angle_buses:
                n = nbus.bus_index

                Vn = voltages[nbus.name] if voltages is not None else nbus.vpu
                delta_n = np.deg2rad(angles[nbus.name]) if angles is not None else np.deg2rad(nbus.delta)

                Gkn = ybus.iloc[k, n].real
                Bkn = ybus.iloc[k, n].imag
                delta_kn = delta_k - delta_n

                delta_col = self.delta_col_map[nbus.name]

                # J1 = ∂P/∂δ
                if k == n:
                    self.jacobian[p_row, delta_col] = -Qk - (Bkk * Vk * Vk)
                else:
                    self.jacobian[p_row, delta_col] = Vk * Vn * (
                        Gkn * np.sin(delta_kn) - Bkn * np.cos(delta_kn)
                    )

            for nbus in self.voltage_buses:
                n = nbus.bus_index

                Vn = voltages[nbus.name] if voltages is not None else nbus.vpu
                delta_n = np.deg2rad(angles[nbus.name]) if angles is not None else np.deg2rad(nbus.delta)

                Gkn = ybus.iloc[k, n].real
                Bkn = ybus.iloc[k, n].imag
                delta_kn = delta_k - delta_n

                v_col = self.v_col_map[nbus.name]

                # J2 = ∂P/∂V
                if k == n:
                    self.jacobian[p_row, v_col] = (Pk / Vk) + (Gkk * Vk)
                else:
                    self.jacobian[p_row, v_col] = Vk * (
                        Gkn * np.cos(delta_kn) + Bkn * np.sin(delta_kn)
                    )

            # ----- ΔQ row for this bus (PQ only) -----
            if kbus.bus_type == "PQ":
                q_row = self.q_row_map[kbus.name]

                for nbus in self.angle_buses:
                    n = nbus.bus_index

                    Vn = voltages[nbus.name] if voltages is not None else nbus.vpu
                    delta_n = np.deg2rad(angles[nbus.name]) if angles is not None else np.deg2rad(nbus.delta)

                    Gkn = ybus.iloc[k, n].real
                    Bkn = ybus.iloc[k, n].imag
                    delta_kn = delta_k - delta_n

                    delta_col = self.delta_col_map[nbus.name]

                    # J3 = ∂Q/∂δ
                    if k == n:
                        self.jacobian[q_row, delta_col] = Pk - (Gkk * Vk * Vk)
                    else:
                        self.jacobian[q_row, delta_col] = -Vk * Vn * (
                            Gkn * np.cos(delta_kn) + Bkn * np.sin(delta_kn)
                        )

                for nbus in self.voltage_buses:
                    n = nbus.bus_index

                    Vn = voltages[nbus.name] if voltages is not None else nbus.vpu
                    delta_n = np.deg2rad(angles[nbus.name]) if angles is not None else np.deg2rad(nbus.delta)

                    Gkn = ybus.iloc[k, n].real
                    Bkn = ybus.iloc[k, n].imag
                    delta_kn = delta_k - delta_n

                    v_col = self.v_col_map[nbus.name]

                    # J4 = ∂Q/∂V
                    if k == n:
                        self.jacobian[q_row, v_col] = (Qk / Vk) - (Bkk * Vk)
                    else:
                        self.jacobian[q_row, v_col] = Vk * (
                            Gkn * np.sin(delta_kn) - Bkn * np.cos(delta_kn)
                        )

        return self.jacobian


class JacobianFormatter:
    def __init__(self, jacobian_obj: Jacobian):
        self.jacobian_obj = jacobian_obj

    def to_dataframe(self):
        row_labels = []
        for bus in self.jacobian_obj.angle_buses:
            row_labels.append(f"P {bus.name}")
        for bus in self.jacobian_obj.voltage_buses:
            row_labels.append(f"Q {bus.name}")

        col_labels = []
        for bus in self.jacobian_obj.angle_buses:
            col_labels.append(f"δ {bus.name}")
        for bus in self.jacobian_obj.voltage_buses:
            col_labels.append(f"V {bus.name}")

        return pd.DataFrame(
            self.jacobian_obj.jacobian,
            index=row_labels,
            columns=col_labels
        )

    def print_dataframe(self, decimals=2):
        print(self.to_dataframe().round(decimals))


if __name__ == "__main__":
    from bus import Bus
    from circuit import Circuit

    c1 = Circuit("Test Circuit")
    Bus.index_counter = 0

    c1.add_bus("Bus1", 15.0, "Slack")
    c1.add_bus("Bus2", 345.0, "PQ")
    c1.add_bus("Bus3", 15.0, "PV")
    c1.add_bus("Bus4", 345.0, "PQ")
    c1.add_bus("Bus5", 345.0, "PQ")

    c1.add_transformer("T1", "Bus1", "Bus5", 0.0015, 0.02, 600)
    c1.add_transformer("T2", "Bus3", "Bus4", 0.00075, 0.01, 1000)

    c1.add_transmission_line("TL1", "Bus5", "Bus4", 0.00225, 0.025, 0.0, 0.44, 1200)
    c1.add_transmission_line("TL2", "Bus5", "Bus2", 0.0045, 0.05, 0.0, 0.88, 1200)
    c1.add_transmission_line("TL3", "Bus4", "Bus2", 0.009, 0.1, 0.0, 1.72, 1200)

    c1.add_generator("G1", "Bus1", 1.00, 0.0)
    c1.add_generator("G2", "Bus3", 1.05, 520.0)

    c1.add_load("L1", "Bus3", 80.0, 40.0)
    c1.add_load("L2", "Bus2", 800.0, 280.0)

    c1.calc_ybus()

    print("Ybus:\n")
    print(c1.ybus)

    # Converged Case
    c1.buses["Bus1"].vpu = 1.0000000000
    c1.buses["Bus1"].delta = 0.00

    c1.buses["Bus2"].vpu = 0.83377000000000000
    c1.buses["Bus2"].delta = -22.40640311913491800

    c1.buses["Bus3"].vpu = 1.04999998126552560
    c1.buses["Bus3"].delta = -0.59734111596806682

    c1.buses["Bus4"].vpu = 1.01930239875375090
    c1.buses["Bus4"].delta = -2.83397066041765570

    c1.buses["Bus5"].vpu = 0.97428869484455565
    c1.buses["Bus5"].delta = -4.54788331806453890

    mismatch = c1.compute_power_mismatch()

    print("\nStructured Mismatch Output:")
    index = 0
    for bus in c1.buses.values():
        if bus.bus_type == "Slack":
            continue

        print(f"ΔP at {bus.name}: {mismatch[index]:.6f}")
        index += 1

        if bus.bus_type == "PQ":
            print(f"ΔQ at {bus.name}: {mismatch[index]:.6f}")
            index += 1

    angle_dict = {
        "Bus1": c1.buses["Bus1"].delta,
        "Bus2": c1.buses["Bus2"].delta,
        "Bus3": c1.buses["Bus3"].delta,
        "Bus4": c1.buses["Bus4"].delta,
        "Bus5": c1.buses["Bus5"].delta,
    }

    voltage_dict = {
        "Bus1": c1.buses["Bus1"].vpu,
        "Bus2": c1.buses["Bus2"].vpu,
        "Bus3": c1.buses["Bus3"].vpu,
        "Bus4": c1.buses["Bus4"].vpu,
        "Bus5": c1.buses["Bus5"].vpu,
    }

    J = Jacobian(c1)
    jacobian_matrix = J.calc_jacobian(
        buses=c1.buses,
        ybus=c1.ybus,
        angles=angle_dict,
        voltages=voltage_dict
    )

    print("\nJacobian Matrix:\n")
    print(jacobian_matrix)

    print("\nJacobian Shape:")
    print(jacobian_matrix.shape)

    formatter = JacobianFormatter(J)
    print("\nJacobian DataFrame:\n")
    formatter.print_dataframe(decimals=2)
