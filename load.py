from settings import SETTINGS

class Load:
    def __init__(self, name:str, bus1_name:str, mw:float, mvar:float):
        self.name = name
        self.bus1_name = bus1_name
        self.mw = mw
        self.mvar = mvar
        self.p = self.calc_p()
        self.q = self.calc_q()


    def calc_p(self):
        p = self.mw/SETTINGS.sbase
        return p

    def calc_q(self):
        q = self.mvar/SETTINGS.sbase
        return q

if __name__ == "__main__":
    load1 = Load("Load1", "Bus2", 50.0, 30.0)

    print(f"Load1 Name: {load1.name}")
    print(f"Load1 Bus Name: {load1.bus1_name}")
    print(f"Load1 Real Power: {load1.mw}")
    print(f"Load1 Reactive Power: {load1.mvar}")
    print(f"Load1 Real Power Per-Unit: {load1.p}")
    print(f"Load1 Reactive Power Per-Unit: {load1.q}")
