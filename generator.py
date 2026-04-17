from settings import SETTINGS

class Generator:
    def __init__(self, name:str, bus1_name:str, voltage_setpoint:float, mw_setpoint:float, x_sub_reactance: float, cost_a: float = 0.0,
                 cost_b: float = 0.0, cost_c: float = 0.0, p_min:float = 0.0, p_max:float = 9999.0):
        self.name = name
        self.bus1_name = bus1_name
        self.voltage_setpoint = voltage_setpoint
        self.mw_setpoint = mw_setpoint
        self.p = self.calc_p()
        self.x_sub_reactance = x_sub_reactance
        self.cost_a = cost_a # fixed cost per/h
        self.cost_b = cost_b # linear cost coef per/MWhr
        self.cost_c = cost_c # quadratic coef per/MW^2
        self.p_min = p_min
        self.p_max = p_max


    def calc_p(self):
        p = self.mw_setpoint/SETTINGS.sbase
        return p

    def calc_cost(self):
        #Total cost per hour MW
        return self.cost_a + (self.cost_b * self.mw_setpoint) + (self.cost_c * self.mw_setpoint **2)

    def calc_incremental_cost(self):
        # Incremental cost derivative = dC/dP in per/MW
        return self.cost_b + (2 * self.cost_c * self.mw_setpoint)

if __name__ == "__main__":
    gen1 = Generator("G1", "Bus 1", 1.04, 520.0, 0,350,20,0.005, 0.0,9999.0)

    print(f"Generator1 Name: {gen1.name}")
    print(f"Generator1 Bus Name: {gen1.bus1_name}")
    print(f"Generator1 Voltage Setpoint (V): {gen1.voltage_setpoint}")
    print(f"Load1 Real Power Setpoint (MW): {gen1.mw_setpoint}")
    print(f"Generator1 Per-Unit Real Power: {gen1.p}")
    gen1.calc_incremental_cost()
    print(f"Generator1 Cost: {gen1.calc_cost()}")
    gen1.calc_incremental_cost()
    print(f"Generator1 Incremental Cost: {gen1.calc_incremental_cost()}")