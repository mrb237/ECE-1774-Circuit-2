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
            key=lambda bus: bus.bus_index
        )

        self.angle_buses = [
            bus for bus in self.ordered_buses
            if bus.bus_type != "Slack"
        ]

        self.voltage_buses = [
            bus for bus in self.ordered_buses
            if bus.bus_type == "PQ"
        ]

        self.num_buses = len(self.ordered_buses)
        self.num_pv = sum(1 for bus in self.ordered_buses if bus.bus_type == "PV")

        self.size = (2 * self.num_buses) - 2 - self.num_pv

        if self.size < 0:
            self.size = 0

        self.jacobian = np.zeros((self.size, self.size), dtype=float)

        self.p_row_map = {
            bus.name: i for i, bus in enumerate(self.angle_buses)
        }

        self.q_row_map = {
            bus.name: i + len(self.angle_buses)
            for i, bus in enumerate(self.voltage_buses)
        }

        self.delta_col_map = {
            bus.name: i for i, bus in enumerate(self.angle_buses)
        }

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

        if self.size == 0:
            return self.jacobian

        for kbus in self.ordered_buses:
            if kbus.bus_type == "Slack":
                continue

            k = kbus.bus_index

            Vk = voltages[kbus.name] if voltages is not None else kbus.vpu
            delta_k = np.deg2rad(angles[kbus.name]) if angles is not None else np.deg2rad(kbus.delta)

            Pk, Qk = self.circuit.compute_power_injection(kbus)

            Gkk = ybus.iloc[k, k].real
            Bkk = ybus.iloc[k, k].imag

            p_row = self.p_row_map[kbus.name]

            for nbus in self.angle_buses:
                n = nbus.bus_index

                Vn = voltages[nbus.name] if voltages is not None else nbus.vpu
                delta_n = np.deg2rad(angles[nbus.name]) if angles is not None else np.deg2rad(nbus.delta)

                Gkn = ybus.iloc[k, n].real
                Bkn = ybus.iloc[k, n].imag

                delta_kn = delta_k - delta_n
                delta_col = self.delta_col_map[nbus.name]

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

                if k == n:
                    self.jacobian[p_row, v_col] = (Pk / Vk) + (Gkk * Vk)
                else:
                    self.jacobian[p_row, v_col] = Vk * (
                        Gkn * np.cos(delta_kn) + Bkn * np.sin(delta_kn)
                    )

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