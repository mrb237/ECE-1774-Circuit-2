from typing import Dict
from Bus import Bus
from generator import Generator
from load import Load
from transformer import Transformer
from transmission_line import TransmissionLine

class Circuit:
    def __init__(self, name:str):
        self.name = name
        self.buses: Dict[str, Bus] = {}
        self.transformers: Dict[str, Transformer] = {}
        self.transmission_lines: Dict[str, TransmissionLine] = {}
        self.generators: Dict[str, Generator] = {}
        self.loads: Dict[str, Load] = {}



    def duplicate_name(self,d: dict, name:str, equipment_type:str ):
        if name in d:
            raise ValueError(f"Duplicate name {name} from {equipment_type}.")

    def add_bus(self, name:str, nominal_kv:float):
        #Why don't we store the nominal kv here?
        self.duplicate_name(self.buses, name, 'Bus')
        busobj = Bus(name, nominal_kv)
        self.buses[name] = busobj
        return busobj

    def add_transformer(self, name:str, bus1_name: str, bus2_name: str, r: float, x: float):
        self.duplicate_name(self.transformers, name, 'Transformer')
        transformerobj = Transformer(name, bus1_name, bus2_name, r, x)
        self.transformers[name] = transformerobj
        return transformerobj

    def add_transmission_line(self, name:str, bus1_name: str, bus2_name: str, r: float, x: float, g: float, b: float):
        self.duplicate_name(self.transmission_lines, name, 'TransmissionLine')
        transmissionlineobj = TransmissionLine(name, bus1_name, bus2_name, r, x, g, b)
        self.transmission_lines[name] = transmissionlineobj
        return transmissionlineobj

    def add_generator(self, name:str, bus1_name: str, voltage_setpoint: float, mw_setpoint: float):
        self.duplicate_name(self.generators, name, 'Generator')
        generatorobj = Generator(name, bus1_name, voltage_setpoint, mw_setpoint)
        self.generators[name] = generatorobj
        return generatorobj

    def add_load(self, name:str, bus1_name: str, mw: float, mvar: float):
        self.duplicate_name(self.loads, name, 'Load')
        loadobj = Load(name, bus1_name, mw, mvar)
        self.loads[name] = loadobj
        return loadobj

if __name__ == "__main__":
    """"
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