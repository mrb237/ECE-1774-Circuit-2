from typing import Dict

import numpy as np
import pandas as pd

from bus import Bus
from generator import Generator
from load import Load
from transformer import Transformer
from transmission_line import TransmissionLine
from breaker import Breaker


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

    def add_bus(self, name: str, nominal_kv: float, bus_type: str = "PQ"):
        Circuit.duplicate_name(self.buses, name, "Bus")
        busobj = Bus(name, nominal_kv, bus_type)
        self.buses[name] = busobj
        return busobj

    def add_transformer(
        self,
        name: str,
        bus1_name: str,
        bus2_name: str,
        r: float,
        x: float,
        mva_limit: float = 1000.0
    ):
        self.duplicate_name(self.transformers, name, "Transformer")
        transformerobj = Transformer(name, bus1_name, bus2_name, r, x, mva_limit)
        self.transformers[name] = transformerobj
        return transformerobj

    def add_transmission_line(
        self,
        name: str,
        bus1_name: str,
        bus2_name: str,
        r: float,
        x: float,
        g: float,
        b: float,
        mva_limit: float = 1200.0
    ):
        self.duplicate_name(self.transmission_lines, name, "TransmissionLine")
        transmissionlineobj = TransmissionLine(name, bus1_name, bus2_name, r, x, g, b, mva_limit)
        self.transmission_lines[name] = transmissionlineobj
        return transmissionlineobj

    def add_generator(self, name: str, bus1_name: str, voltage_setpoint: float, mw_setpoint: float):
        self.duplicate_name(self.generators, name, "Generator")
        generatorobj = Generator(name, bus1_name, voltage_setpoint, mw_setpoint)
        self.generators[name] = generatorobj
        return generatorobj

    def add_load(self, name: str, bus1_name: str, mw: float, mvar: float):
        self.duplicate_name(self.loads, name, "Load")
        loadobj = Load(name, bus1_name, mw, mvar)
        self.loads[name] = loadobj
        return loadobj

    def add_breaker(
        self,
        name: str,
        node1_name: str = None,
        node2_name: str = None,
        is_closed: bool = True,
        rating: float = 0.0,
        element_type: str = None,
        element_name: str = None
    ):
        """
        Dynamic breaker method.

        Supports senior-design style:
            add_breaker("BR_TL2", "Bus5", "Bus2", True)
            add_breaker("BR_G1", "G1", "Bus1", True)
            add_breaker("BR_L1", "L1", "Bus3", True)

        Also supports element-based style:
            add_breaker("BR_TL2", element_type="line", element_name="TL2")
            add_breaker("BR_T1", element_type="transformer", element_name="T1")
        """
        self.duplicate_name(self.breakers, name, "Breaker")

        breakerobj = Breaker(
            name=name,
            node1_name=node1_name,
            node2_name=node2_name,
            is_closed=is_closed,
            rating=rating,
            element_type=element_type,
            element_name=element_name
        )

        self.breakers[name] = breakerobj
        return breakerobj

    def is_connection_closed(self, node1_name: str, node2_name: str):
        """
        Returns False if there is an open breaker between node1 and node2.
        If no breaker exists for that connection, the connection is assumed closed.
        """
        for breaker in self.breakers.values():
            if breaker.controls_connection(node1_name, node2_name):
                return breaker.is_closed

        return True

    def is_element_closed(self, element_type: str, element_name: str, bus1_name: str = None, bus2_name: str = None):
        """
        Checks whether a line, transformer, generator, or load is enabled.

        It supports:
        - element-based breakers
        - connection-based breakers
        """
        for breaker in self.breakers.values():
            if breaker.controls_element(element_type, element_name):
                return breaker.is_closed

        if bus1_name is not None and bus2_name is not None:
            return self.is_connection_closed(bus1_name, bus2_name)

        return True

    def is_generator_connected(self, gen: Generator):
        return self.is_element_closed(
            element_type="generator",
            element_name=gen.name,
            bus1_name=gen.name,
            bus2_name=gen.bus1_name
        )

    def is_load_connected(self, load: Load):
        return self.is_element_closed(
            element_type="load",
            element_name=load.name,
            bus1_name=load.name,
            bus2_name=load.bus1_name
        )

    def is_transformer_connected(self, transformer: Transformer):
        return self.is_element_closed(
            element_type="transformer",
            element_name=transformer.name,
            bus1_name=transformer.bus1_name,
            bus2_name=transformer.bus2_name
        )

    def is_transmission_line_connected(self, line: TransmissionLine):
        return self.is_element_closed(
            element_type="line",
            element_name=line.name,
            bus1_name=line.bus1_name,
            bus2_name=line.bus2_name
        )

    def build_adjacency_list(self):
        """
        Builds bus-to-bus adjacency using only closed transmission lines and transformers.
        This is dynamic and works for any number of buses.
        """
        adjacency = {bus_name: [] for bus_name in self.buses.keys()}

        for tf in self.transformers.values():
            if self.is_transformer_connected(tf):
                adjacency[tf.bus1_name].append(tf.bus2_name)
                adjacency[tf.bus2_name].append(tf.bus1_name)

        for tl in self.transmission_lines.values():
            if self.is_transmission_line_connected(tl):
                adjacency[tl.bus1_name].append(tl.bus2_name)
                adjacency[tl.bus2_name].append(tl.bus1_name)

        return adjacency

    def adjacency_list(self):
        return self.build_adjacency_list()

    def get_slack_bus_name(self):
        for bus in self.buses.values():
            if bus.bus_type == "Slack":
                return bus.name
        return None

    def get_active_generator_names(self):
        active = []

        for gen in self.generators.values():
            if self.is_generator_connected(gen):
                active.append(gen.name)

        return active

    def get_active_generators(self):
        return [
            gen for gen in self.generators.values()
            if self.is_generator_connected(gen)
        ]

    def update_generator(self):
        """
        Dynamic generator-role logic.

        Rules:
        - Any connected generator can support an energized island.
        - If the current Slack generator is still connected, keep it Slack.
        - If the current Slack generator is disconnected, promote another connected generator to Slack.
        - All other connected generator buses become PV.
        - Buses without connected generators become PQ unless manually set otherwise later.
        - No hardcoded Bus1/G1 or Bus3/G2 logic.
        """
        active_generators = self.get_active_generators()

        if len(active_generators) == 0:
            raise ValueError("No active generators are connected. No Slack bus available.")

        previous_slack_bus = self.get_slack_bus_name()

        # Reset every bus to PQ first
        for bus in self.buses.values():
            bus.bus_type = "PQ"

        # Determine slack generator dynamically
        slack_gen = None

        if previous_slack_bus is not None:
            for gen in active_generators:
                if gen.bus1_name == previous_slack_bus:
                    slack_gen = gen
                    break

        if slack_gen is None:
            slack_gen = active_generators[0]

        # Set selected slack
        self.buses[slack_gen.bus1_name].bus_type = "Slack"
        self.buses[slack_gen.bus1_name].vpu = slack_gen.voltage_setpoint

        # Set other active generator buses to PV
        for gen in active_generators:
            if gen.bus1_name == slack_gen.bus1_name:
                continue

            self.buses[gen.bus1_name].bus_type = "PV"
            self.buses[gen.bus1_name].vpu = gen.voltage_setpoint

        # If slack is disconnected from some generators by topology,
        # keep only generators connected to the active slack island as PV.
        active_buses = self.get_active_bus_names()

        for gen in active_generators:
            if gen.bus1_name not in active_buses:
                self.buses[gen.bus1_name].bus_type = "PQ"

        # If the selected slack is not connected to anything, still allow it
        # as the energized reference island, but downstream logic will identify islanded buses.

    def is_generator_active(self, gen_name: str, bus_name: str):
        if gen_name not in self.generators:
            return False

        gen = self.generators[gen_name]

        return (
            gen.bus1_name == bus_name
            and self.is_generator_connected(gen)
            and bus_name in self.get_active_bus_names()
        )

    def get_active_bus_names(self):
        """
        Returns buses reachable from the current Slack bus.
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
        active_buses = self.get_active_bus_names()
        return set(self.buses.keys()) - active_buses

    def zero_islanded_buses(self):
        islanded_buses = self.get_islanded_bus_names()

        for bus_name in islanded_buses:
            self.buses[bus_name].vpu = 0.0
            self.buses[bus_name].delta = 0.0

    def update_load_models(self):
        active_buses = self.get_active_bus_names()

        for load in self.loads.values():
            if load.bus1_name not in self.buses:
                continue

            if load.bus1_name not in active_buses:
                continue

            if not self.is_load_connected(load):
                continue

            bus = self.buses[load.bus1_name]
            load.update_type(bus.vpu)

    def calc_ybus(self):
        """
        Calculates Ybus using only closed breakers.
        Dynamic for any network.
        """
        self.update_generator()

        N = len(self.buses)
        self.ybus = np.zeros((N, N), dtype=complex)

        bus_mapping = {name: bus.bus_index for name, bus in self.buses.items()}
        bus_names = list(bus_mapping.keys())

        for name, tf_v in self.transformers.items():
            if not self.is_transformer_connected(tf_v):
                continue

            Yprim_tf = tf_v.calc_yprim()

            b1 = tf_v.bus1_name
            b2 = tf_v.bus2_name

            i = bus_mapping[b1]
            j = bus_mapping[b2]

            self.ybus[i, i] += Yprim_tf.iloc[0, 0]
            self.ybus[i, j] += Yprim_tf.iloc[0, 1]
            self.ybus[j, i] += Yprim_tf.iloc[1, 0]
            self.ybus[j, j] += Yprim_tf.iloc[1, 1]

        for name, tl_v in self.transmission_lines.items():
            if not self.is_transmission_line_connected(tl_v):
                continue

            Yprim_tl = tl_v.calc_yprim()

            b1 = tl_v.bus1_name
            b2 = tl_v.bus2_name

            i = bus_mapping[b1]
            j = bus_mapping[b2]

            self.ybus[i, i] += Yprim_tl.iloc[0, 0]
            self.ybus[i, j] += Yprim_tl.iloc[0, 1]
            self.ybus[j, i] += Yprim_tl.iloc[1, 0]
            self.ybus[j, j] += Yprim_tl.iloc[1, 1]

        active_buses = self.get_active_bus_names()

        for load in self.loads.values():
            if not self.is_load_connected(load):
                continue

            if load.bus1_name not in active_buses:
                continue

            if load.load_type == "Z":
                i = bus_mapping[load.bus1_name]
                Yload = load.calc_yprim()
                self.ybus[i, i] += Yload

        self.ybus = pd.DataFrame(self.ybus, columns=bus_names, index=bus_names)

    def compute_power_injection(self, bus):
        i = bus.bus_index

        Vi = bus.vpu
        delta_i = np.deg2rad(bus.delta)

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
        self.update_generator()

        ordered_buses = sorted(self.buses.values(), key=lambda bus: bus.bus_index)

        power_mismatches = []
        reactive_mismatches = []

        active_buses = self.get_active_bus_names()

        for bus in ordered_buses:
            if bus.name not in active_buses:
                continue

            if bus.bus_type == "Slack":
                continue

            Pcalc, Qcalc = self.compute_power_injection(bus)

            Pspec = 0.0
            Qspec = 0.0

            for gen in self.generators.values():
                if gen.bus1_name == bus.name and self.is_generator_active(gen.name, bus.name):
                    Pspec += gen.p

            for load in self.loads.values():
                if load.bus1_name == bus.name:
                    if self.is_load_connected(load) and bus.name in active_buses:
                        p_load, q_load = load.get_power()
                        Pspec -= p_load
                        Qspec -= q_load

            if bus.bus_type in {"PQ", "PV"}:
                delta_P = Pspec - Pcalc
                power_mismatches.append(delta_P)

            if bus.bus_type == "PQ":
                delta_Q = Qspec - Qcalc
                reactive_mismatches.append(delta_Q)

        return np.array(power_mismatches + reactive_mismatches)