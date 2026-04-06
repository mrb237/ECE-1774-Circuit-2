from typing import Dict

from bus import Bus
from generator import Generator
from load import Load
from transformer import Transformer
from transmission_line import TransmissionLine
from Breaker import Breaker
import numpy as np
import pandas as pd

class Circuit:
    def __init__(self, name: str):
        self.name = name
        self.buses: Dict[str, Bus] = {}
        self.transformers: Dict[str, Transformer] = {}
        self.transmission_lines: Dict[str, TransmissionLine] = {}
        self.generators: Dict[str, Generator] = {}
        self.loads: Dict[str, Load] = {}
        self.breakers: Dict[str, Breaker] = {}
        self.ybus = None

    @staticmethod
    def duplicate_name(d: dict, name: str, equipment_type: str):
        if name in d:
            raise ValueError(f"Duplicate name {name} from {equipment_type}.")

    def add_bus(self, name: str, nominal_kv: float, bus_type: str):
        Circuit.duplicate_name(d=self.buses, name=name, equipment_type='Bus')
        busobj = Bus(name, nominal_kv, bus_type)
        self.buses[name] = busobj
        return busobj

    def add_transformer(self, name: str, bus1_name: str, bus2_name: str, r: float, x: float, mva_limit: float):
        self.duplicate_name(self.transformers, name, 'Transformer')
        transformerobj = Transformer(name, bus1_name, bus2_name, r, x, mva_limit)
        self.transformers[name] = transformerobj
        return transformerobj

    def add_transmission_line(self, name: str, bus1_name: str, bus2_name: str, r: float, x: float, g: float, b: float, mva_limit: float):
        self.duplicate_name(self.transmission_lines, name, 'TransmissionLine')
        transmissionlineobj = TransmissionLine(name, bus1_name, bus2_name, r, x, g, b, mva_limit)
        self.transmission_lines[name] = transmissionlineobj
        return transmissionlineobj

    def add_generator(self, name: str, bus1_name: str, voltage_setpoint: float, mw_setpoint: float):
        self.duplicate_name(self.generators, name, 'Generator')
        generatorobj = Generator(name, bus1_name, voltage_setpoint, mw_setpoint)
        self.generators[name] = generatorobj
        return generatorobj

    def add_load(self, name: str, bus1_name: str, mw: float, mvar: float):
        self.duplicate_name(self.loads, name, 'Load')
        loadobj = Load(name, bus1_name, mw, mvar)
        self.loads[name] = loadobj
        return loadobj

    def add_breaker(self, name: str, node1_name: str, node2_name: str, is_closed: bool = True, rating: float = 0.0):
        self.duplicate_name(self.breakers, name, 'Breaker')
        breakerobj = Breaker(name, node1_name, node2_name, is_closed, rating)
        self.breakers[name] = breakerobj
        return breakerobj

    def is_connection_closed(self, node1_name: str, node2_name: str):
        for breaker in self.breakers.values():
            a = breaker.node1_name
            b = breaker.node2_name
            if (a == node1_name and b == node2_name) or (a == node2_name and b == node1_name):
                return breaker.is_closed
        return True

    def update_generator(self):
        """
        Hardcoded generator-role logic for the 5-bus system.

        Rules:
        - If G1 is connected, Bus1 is Slack
        - If G2 is also connected, Bus3 is PV
        - If G1 is disconnected and G2 is connected, Bus3 becomes Slack
        - If G2 is disconnected but G1 is connected, Bus3 becomes PQ
        - If both generators are disconnected, raise blackout condition
        """

        # Reset generator buses first
        self.buses["Bus1"].bus_type = "PQ"
        self.buses["Bus3"].bus_type = "PQ"

        g1_closed = self.is_connection_closed("G1", "Bus1")
        g2_closed = self.is_connection_closed("G2", "Bus3")

        if g1_closed:
            self.buses["Bus1"].bus_type = "Slack"
            if g2_closed:
                self.buses["Bus3"].bus_type = "PV"
            else:
                self.buses["Bus3"].bus_type = "PQ"
        elif g2_closed:
            self.buses["Bus3"].bus_type = "Slack"
            self.buses["Bus1"].bus_type = "PQ"
        else:
            raise ValueError("Both generators are disconnected. No Slack bus available.")

        active_buses = self.get_active_bus_names()

        bus1_active = "Bus1" in active_buses and g1_closed
        bus3_active = "Bus3" in active_buses and g2_closed

        self.buses["Bus1"].bus_type = "PQ"
        self.buses["Bus3"].bus_type = "PQ"

        if bus1_active:
            self.buses["Bus1"].bus_type = "Slack"
            if bus3_active:
                self.buses["Bus3"].bus_type = "PV"
            else:
                self.buses["Bus3"].bus_type = "PQ"
        elif bus3_active:
            self.buses["Bus3"].bus_type = "Slack"
            self.buses["Bus1"].bus_type = "PQ"
        else:
            raise ValueError("No energized generator bus available to act as Slack")

    def is_generator_active(self, gen_name:str, bus_name:str):
        return self.is_connection_closed(gen_name, bus_name) and bus_name in self.get_active_bus_names()

    def build_adjacency_list(self):
        """
        Build an adjacency list of bus-to-bus connectivity using only
        CLOSED transformers and transmission lines.
        """
        adjacency = {bus_name: [] for bus_name in self.buses.keys()}

        # Transformers
        for tf in self.transformers.values():
            if self.is_connection_closed(tf.bus1_name, tf.bus2_name):
                adjacency[tf.bus1_name].append(tf.bus2_name)
                adjacency[tf.bus2_name].append(tf.bus1_name)

        # Transmission lines
        for tl in self.transmission_lines.values():
            if self.is_connection_closed(tl.bus1_name, tl.bus2_name):
                adjacency[tl.bus1_name].append(tl.bus2_name)
                adjacency[tl.bus2_name].append(tl.bus1_name)

        return adjacency

    def get_slack_bus_name(self):
        """
        Return the current slack bus name.
        """
        for bus in self.buses.values():
            if bus.bus_type == "Slack":
                return bus.name
        return None

    def get_active_bus_names(self):
        """
        Return the set of buses reachable from the current Slack bus
        using DFS on the adjacency list.
        """
        slack_bus = self.get_slack_bus_name()
        if slack_bus is None:
            return set()

        adjacency = self.build_adjacency_list()

        visited = set()
        stack = [slack_bus]

        while stack:
            current = stack.pop()
            if current in visited:
                continue

            visited.add(current)

            for neighbor in adjacency[current]:
                if neighbor not in visited:
                    stack.append(neighbor)

        return visited

    def get_islanded_bus_names(self):
        """
        Return the set of buses that are NOT connected to the slack bus.
        """
        active_buses = self.get_active_bus_names()
        return set(self.buses.keys()) - active_buses

    def zero_islanded_buses(self):
        """
        Set islanded buses to zero voltage and zero angle for reporting / display.
        """
        islanded_buses = self.get_islanded_bus_names()

        for bus_name in islanded_buses:
            self.buses[bus_name].vpu = 0.0
            self.buses[bus_name].delta = 0.0

    def update_load_models(self):
        """
        Update load types based on bus voltages.
        """
        active_buses = self.get_active_bus_names()

        for load in self.loads.values():
            if load.bus1_name not in self.buses:
                continue

            if load.bus1_name not in active_buses:
                continue

            if not self.is_connection_closed(load.name, load.bus1_name):
                continue

            bus = self.buses[load.bus1_name]
            load.update_type(bus.vpu)

    # Adding Methods
    def calc_ybus(self):
        # Stores amount of buses are in the dictionary
        N = len(self.buses)
        # Initialize matrix
        self.ybus = np.zeros((N, N), dtype=complex)
        # Creates a new dictionary for every name it establishes an index value
        bus_mapping = {name: bus.bus_index for name, bus in self.buses.items()}
        # Extracting bus names
        bus_names = list(bus_mapping.keys())

        # Transformer
        for name, tf_v in self.transformers.items():
            if not self.is_connection_closed(tf_v.bus1_name, tf_v.bus2_name):
                continue

            Yprim_tf = tf_v.calc_yprim()
            # print(Yprim_tf)

            b1 = tf_v.bus1_name
            b2 = tf_v.bus2_name

            i = bus_mapping[b1]
            j = bus_mapping[b2]
            self.ybus[i, i] += (Yprim_tf.iloc[0, 0])
            self.ybus[i, j] += (Yprim_tf.iloc[0, 1])
            self.ybus[j, i] += (Yprim_tf.iloc[1, 0])
            self.ybus[j, j] += (Yprim_tf.iloc[1, 1])

        # Transmission_line
        for name, tl_v in self.transmission_lines.items():
            if not self.is_connection_closed(tl_v.bus1_name, tl_v.bus2_name):
                continue

            Yprim_tl = tl_v.calc_yprim()

            b1 = tl_v.bus1_name
            b2 = tl_v.bus2_name

            i = bus_mapping[b1]
            j = bus_mapping[b2]

            # Stamping Transformer Pmatrix into Ybus
            self.ybus[i, i] += (Yprim_tl.iloc[0, 0])
            self.ybus[i, j] += (Yprim_tl.iloc[0, 1])
            self.ybus[j, i] += (Yprim_tl.iloc[1, 0])
            self.ybus[j, j] += (Yprim_tl.iloc[1, 1])
        # Converting an array to a Dataframe matrix

        # Add Z-load admittances to diagonal
        active_buses = self.get_active_bus_names()

        for load in self.loads.values():
            if not self.is_connection_closed(load.name, load.bus1_name):
                continue

            if load.bus1_name not in active_buses:
                continue

            if load.load_type == "Z":
                i = bus_mapping[load.bus1_name]
                Yload = load.calc_yprim()
                self.ybus[i, i] += Yload

        # ybus_rounded = self.ybus.round(2)
        # self.ybus = pd.DataFrame(ybus_rounded, columns=bus_names, index=bus_names)

        self.ybus = pd.DataFrame(self.ybus, columns=bus_names, index=bus_names)

    def compute_power_injection(self, bus):
        # Bus indecies
        i = bus.bus_index
        # Bus voltage mag and delta from setpoint
        Vi = bus.vpu
        bus_delta = bus.delta
        delta_i = np.deg2rad(bus.delta)

        # Start values from 0
        P_i = 0.0
        Q_i = 0.0

        for bus_j in self.buses.values():
            j = bus_j.bus_index
            Vj = bus_j.vpu
            delta_j = np.deg2rad(bus_j.delta)

            Yij = self.ybus.iloc[i, j]

            Gij = Yij.real
            Bij = Yij.imag
            delta_ij = delta_i - delta_j

            P_i += Vi * Vj * (Gij * np.cos(delta_ij) + Bij * np.sin(delta_ij))
            Q_i += Vi * Vj * (Gij * np.sin(delta_ij) - Bij * np.cos(delta_ij))

        return P_i, Q_i

    def compute_power_mismatch(self):
        self.ordered_buses = sorted(self.buses.values(), key=lambda bus: bus.bus_index)

        power_mismatches = []
        reactive_mismatches = []

        active_buses = self.get_active_bus_names()

        for bus in self.ordered_buses:
            if bus.name not in active_buses:
                continue

            if bus.bus_type == "Slack":
                continue

            Pcalc, Qcalc = self.compute_power_injection(bus)

            Pspec = 0.0
            Qspec = 0.0

            for gen in self.generators.values():
                if gen.bus1_name == bus.name:
                    if self.is_generator_active(gen.name, bus.name):
                        Pspec += gen.p

            for load in self.loads.values():
                if load.bus1_name == bus.name:
                    if self.is_connection_closed(load.name, bus.name) and bus.name in active_buses:
                        load.update_type(bus.vpu)
                        p_load, q_load = load.get_power()
                        Pspec -= p_load
                        Qspec -= q_load

            if bus.bus_type == "PQ" or bus.bus_type == "PV":
                delta_P = Pspec - Pcalc
                power_mismatches.append(delta_P)

            if bus.bus_type == "PQ":
                delta_Q = Qspec - Qcalc
                reactive_mismatches.append(delta_Q)
            #test = np.array(power_mismatches + reactive_mismatches)
        return np.array(power_mismatches + reactive_mismatches)


if __name__ == "__main__":
    # 5 Bus Validation
    c1 = Circuit("Test Circuit")
    Bus.index_counter = 0

    c1.add_bus("Bus1", 15.0, "Slack")
    c1.add_bus("Bus2", 345.0, "PQ")
    c1.add_bus("Bus3", 15.0, "PV")
    c1.add_bus("Bus4", 345.0, "PQ")
    c1.add_bus("Bus5", 345.0, "PQ")

    c1.add_transformer("T1", "Bus1", "Bus5", 0.0015, 0.02)
    c1.add_transformer("T2", "Bus3", "Bus4", 0.00075, 0.01)

    c1.add_transmission_line("TL1", "Bus5", "Bus4", 0.00225, 0.025, 0.0, 0.44)
    c1.add_transmission_line("TL2", "Bus5", "Bus2", 0.0045, 0.05, 0.0, 0.88)
    c1.add_transmission_line("TL3", "Bus4", "Bus2", 0.009, 0.1, 0.0, 1.72)

    c1.add_generator("G1", "Bus1", 1.00, 0.0)
    c1.add_generator("G2", "Bus3", 1.05, 520.0)

    c1.add_load("L1", "Bus3", 80.0, 40.0)
    c1.add_load("L2", "Bus2", 800.0, 280.0)

    c1.add_breaker("BR_G1", "G1", "Bus1", True)
    c1.add_breaker("BR_G2", "G2", "Bus3", True)

    c1.add_breaker("BR_T1", "Bus1", "Bus5", True)
    c1.add_breaker("BR_T2", "Bus3", "Bus4", True)

    c1.add_breaker("BR_TL1", "Bus5", "Bus4", True)
    c1.add_breaker("BR_TL2", "Bus5", "Bus2", True)
    c1.add_breaker("BR_TL3", "Bus4", "Bus2", True)

    c1.add_breaker("BR_L1", "L1", "Bus3", True)
    c1.add_breaker("BR_L2", "L2", "Bus2", True)

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

    # Compute mismatch vector
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

    c1.breakers["BR_T2"].open()
    c1.calc_ybus()

    print("Ybus:\n")
    print(c1.ybus)

    c1.breakers["BR_T2"].close()
    c1.calc_ybus()

    print("Ybus:\n")
    print(c1.ybus)

    """
    # After one iteration
    c1.buses["Bus1"].vpu = 1.0000000000
    c1.buses["Bus1"].delta = 0.00

    c1.buses["Bus2"].vpu = 0.9879657065
    c1.buses["Bus2"].delta = -14.657785055656685


    c1.buses["Bus3"].vpu = 1.0500038185
    c1.buses["Bus3"].delta = 0.155483410181187


    c1.buses["Bus4"].vpu = 1.0331396265
    c1.buses["Bus4"].delta = -1.633263694297374


    c1.buses["Bus5"].vpu = 1.0105737711
    c1.buses["Bus5"].delta = -3.205023385079998


    # Compute mismatch vector
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

    print("Ko")
    """

    """
    #Checking Circuit Class Functionality
    circuit1 = Circuit("Test Circuit")

    print(circuit1.name)
    print(type(circuit1.name))
    #Check Attribute Initialization
    print(circuit1.buses)
    print(type(circuit1.buses))
    print(circuit1.transmission_lines)
    print(circuit1.transmission_lines)
    print(circuit1.generators)
    print(circuit1.loads)

    circuit1.add_bus("Bus1", 20.0)
    circuit1.add_bus("Bus2", 230.0)
    print(list(circuit1.buses.keys()))
    print(circuit1.buses["Bus1"].name, circuit1.buses["Bus1"].nominal_kv)
    print(circuit1.buses["Bus1"])

    #Verifying Transformer
    circuit1.add_transformer("T1", "Bus1", "Bus2", 0.01, 0.10)
    print(list(circuit1.transformers.keys()))
    print(circuit1.transformers["T1"].name, circuit1.transformers["T1"].bus1_name, circuit1.transformers["T1"].bus2_name, circuit1.transformers["T1"].r, circuit1.transformers["T1"].x)

    circuit1.add_transmission_line("Line 1", "Bus1", "Bus2", 0.02, 0.25, 0.0, 0.04)
    print(list(circuit1.transmission_lines.keys()))
    print(circuit1.transmission_lines["Line 1"].name, circuit1.transmission_lines["Line 1"].bus1_name, circuit1.transmission_lines["Line 1"].bus1_name, circuit1.transmission_lines["Line 1"].bus2_name,
    circuit1.transmission_lines["Line 1"].r, circuit1.transmission_lines["Line 1"].x, circuit1.transmission_lines["Line 1"].g, circuit1.transmission_lines["Line 1"].b)

    circuit1.add_load("Load 1", "Bus2", 50.0, 30.0)
    print(list(circuit1.loads.keys()))
    print(circuit1.loads["Load 1"].name, circuit1.loads["Load 1"].bus1_name, circuit1.loads["Load 1"].mw, circuit1.loads["Load 1"].mvar)

    circuit1.add_generator("G1", "Bus 1", 1.04, 100)
    print(list(circuit1.generators.keys()))
    print(circuit1.generators["G1"].name, circuit1.generators["G1"].bus1_name, circuit1.generators["G1"].voltage_setpoint, circuit1.generators["G1"].mw_setpoint)
    """
