class Bus:
    index_counter = 0
    VALID_TYPES = {"PQ", "PV", "Slack"}

    def __init__(self, name:str, nominal_kv:float):
        self.name = name
        self.nominal_kv = nominal_kv
        self.bus_index = Bus.index_counter
        Bus.index_counter += 1
        self.vpu = 1.0
        self.delta = 0.0
        self._bus_type = "PQ"

    def __repr__(self):
        return f"Bus Nominal Voltage: {self.nominal_kv} Volts"

    @property
    def bus_type(self):
        return self._bus_type

    @bus_type.setter
    def bus_type(self, new_type: str):
        if new_type not in Bus.VALID_TYPES:
            raise ValueError(
                f"Invalid bus type '{new_type}'. "
                f"Valid types are: {Bus.VALID_TYPES}"
            )
        self._bus_type = new_type

if __name__ == "__main__":
    bus1 = Bus("Bus1", 20.0)

    print(f"Bus1 name: {bus1.name}")
    print(f"Bus1 Nominal Voltage: {bus1.nominal_kv} Volts")
    print(f"Bus1 Index: {bus1.bus_index}")
    print(f"Bus1 Type: {bus1.bus_type}")

    bus2 = Bus("Bus2", 230.0)

    print(f"Bus2 name: {bus2.name}")
    print(f"Bus2 Nominal Voltage: {bus2.nominal_kv} Volts")
    print(f"Bus2 Index: {bus2.bus_index}")
    print(f"Bus2 Type: {bus2.bus_type}")

    print(bus1)
