from settings import SETTINGS

LOAD_TYPES = {"PQ", "Z"}

class Load:
    def __init__(self, name:str, bus1_name:str, mw:float, mvar:float, load_type:str="PQ", min_voltage:float=0.7):
        if load_type not in LOAD_TYPES:
            raise ValueError(f"Invalid load type '{load_type}'. Must be one of {LOAD_TYPES}")

        self.name = name
        self.bus1_name = bus1_name
        self.mw = mw
        self.mvar = mvar
        self.p = self.calc_p()
        self.q = self.calc_q()

        self.load_type = load_type
        self.min_voltage = min_voltage


    def calc_p(self):
        p = self.mw/SETTINGS.sbase
        return p

    def calc_q(self):
        q = self.mvar/SETTINGS.sbase
        return q

    def update_type(self, vpu:float):
        """
        Switch between PQ and Z based on voltage.
        """
        if self.load_type == "PQ":
            if vpu < self.min_voltage:
                self.load_type = "Z"
        elif self.load_type == "Z":
            if vpu > (self.min_voltage+0.05):
                self.load_type = "PQ"

    def get_power(self):
        """
        Return (P,Q) contribution to mismatch.
        Only applies when load is PQ.
        """
        if self.load_type == "PQ":
            return self.p, self.q

        # Z loads are not part of mismatch
        return 0.0, 0.0

    def calc_yprim(self):
        """
        Return equivalent admittance when load is Z.
        """
        if self.load_type != "Z":
            return 0.0 + 0.0*1j

        vth2 = self.min_voltage ** 2
        G = self.p/vth2
        B = -self.q/vth2
        return complex(G,B)


if __name__ == "__main__":
    load1 = Load("Load1", "Bus2", 50.0, 30.0)

    print(f"Load1 Name: {load1.name}")
    print(f"Load1 Bus Name: {load1.bus1_name}")
    print(f"Load1 Real Power: {load1.mw}")
    print(f"Load1 Reactive Power: {load1.mvar}")
    print(f"Load1 Real Power Per-Unit: {load1.p}")
    print(f"Load1 Reactive Power Per-Unit: {load1.q}")
