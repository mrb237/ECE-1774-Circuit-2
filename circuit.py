from typing import Dict
from bus import Bus
from generator import Generator
from load import Load
from transformer import Transformer
from transmission_line import TransmissionLine
from settings import Settings
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

    def add_transformer(self, name: str, bus1_name: str, bus2_name: str, r: float, x: float):
        self.duplicate_name(self.transformers, name, 'Transformer')
        transformerobj = Transformer(name, bus1_name, bus2_name, r, x)
        self.transformers[name] = transformerobj
        return transformerobj

    def add_transmission_line(self, name: str, bus1_name: str, bus2_name: str, r: float, x: float, g: float, b: float):
        self.duplicate_name(self.transmission_lines, name, 'TransmissionLine')
        transmissionlineobj = TransmissionLine(name, bus1_name, bus2_name, r, x, g, b)
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

        ybus_rounded = self.ybus.round(2)
        self.ybus = pd.DataFrame(ybus_rounded, columns=bus_names, index=bus_names)


if __name__ == "__main__":
    # 5 Bus Validation
    c1 = Circuit("Test Circuit")
    c1.add_bus("Bus1", 15.0)
    c1.add_bus("Bus2", 345.0)
    c1.add_bus("Bus3", 15.0)
    c1.add_bus("Bus4", 345.0)
    c1.add_bus("Bus5", 345.0)
    c1.add_transformer("T1", "Bus1", "Bus5", 0.0015, 0.02)
    c1.add_transformer("T2", "Bus3", "Bus4", 0.00075, 0.01)
    c1.add_transmission_line("TL1", "Bus5", "Bus4", 0.002250, 0.025, 0.0, 0.44)
    c1.add_transmission_line("TL2", "Bus5", "Bus2", 0.0045, 0.05, 0.0, 0.88)
    c1.add_transmission_line("TL3", "Bus4", "Bus2", 0.009, 0.1, 0.0, 1.72)
    c1.add_load("L1", "Bus3", 80.0, 40.0)
    c1.add_load("L2", "Bus2", 800.0, 280.0)
    # print(T1.calc_yprim())
    c1.calc_ybus()
    print(c1.ybus)
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
