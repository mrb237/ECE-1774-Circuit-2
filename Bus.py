class Bus:
    def __init__(self, name:str, nominal_kn:float):
        self.name = name
        self.nominal_kn = nominal_kn
        self.bus_index = 1 # Change value

if __name__ == "__main__":
    bus1 = Bus("Bus1", 1.0)

    print(f"Bus1 name: {bus1.name}")
    print(f"Bus1 Nominal Voltage: {bus1.nominal_kn} Volts")
    print(f"Bus1 Index: {bus1.bus_index}")

