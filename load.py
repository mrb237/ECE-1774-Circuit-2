from settings import SETTINGS

LOAD_TYPES = {"PQ", "Z"}

class Load:
    # Class-level hard collapse threshold
    collapse_voltage = 0.25

    def __init__(self, name: str, bus1_name: str, mw: float, mvar: float, rating: float = 1000.0, load_type: str = "PQ", min_voltage: float = 0.7):
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
        self.rating = rating

    def calc_p(self):
        return self.mw / SETTINGS.sbase

    def calc_q(self):
        return self.mvar / SETTINGS.sbase

    def update_type(self, vpu: float):
        # Switch between PQ and Z based on voltage.

        if vpu < self.min_voltage:
            self.load_type = "Z"
        else:
            self.load_type = "PQ"

    @classmethod
    def set_collapse_voltage(cls, value: float):
        cls.collapse_voltage = float(value)

    def is_collapsed(self, vpu: float):
        return vpu < Load.collapse_voltage

    def get_power(self):

        if self.load_type == "PQ":
            return self.p, self.q

        return 0.0, 0.0

    def calc_yprim(self):
        if self.load_type != "Z":
            return 0.0 + 0.0j

        vth2 = self.min_voltage ** 2
        G = self.p / vth2
        B = -self.q / vth2
        return complex(G, B)