from typing import Dict

from bus import Bus
from generator import Generator
from load import Load
from settings import SETTINGS
from transformer import Transformer
from transmission_line import TransmissionLine
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
        self.bbus = None

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

    def add_generator(self, name: str, bus1_name: str, voltage_setpoint: float, mw_setpoint: float, x_sub_reactance: float,
                      cost_a: float, cost_b: float, cost_c: float, p_min: float, p_max: float):
        self.duplicate_name(self.generators, name, 'Generator')
        generatorobj = Generator(name, bus1_name, voltage_setpoint, mw_setpoint, x_sub_reactance, cost_a, cost_b, cost_c, p_min, p_max )
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
        # self.ybus = pd.DataFrame(ybus_rounded, columns=bus_names, index=bus_names)

        self.ybus = pd.DataFrame(ybus_rounded, columns=bus_names, index=bus_names)

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
        power_mismatches = []
        reactive_mismatches = []

        for bus in self.buses.values():
            if bus.bus_type == "Slack":
                continue

            Pcalc, Qcalc = self.compute_power_injection(bus)

            Pspec = 0.0
            Qspec = 0.0

            for gen in self.generators.values():
                if gen.bus1_name == bus.name:
                    Pspec += gen.p

            for load in self.loads.values():
                if load.bus1_name == bus.name:
                    Pspec -= load.p
                    Qspec -= load.q
            if bus.bus_type == "PQ" or bus.bus_type == "PV":
                delta_P = Pspec - Pcalc
                power_mismatches.append(delta_P)

            if bus.bus_type == "PQ":
                delta_Q = Qspec - Qcalc
                reactive_mismatches.append(delta_Q)
            #test = np.array(power_mismatches + reactive_mismatches)
        return np.array(power_mismatches + reactive_mismatches)

    def power_mismatch_formatter(self, mismatch: float):
        print("\nStructured Mismatch Output:")
        index = 0
        for bus in self.buses.values():
            if bus.bus_type == "Slack":
                continue

            print(f"ΔP at {bus.name}: {mismatch[index]:.6f}")
            index += 1

            if bus.bus_type == "PQ":
                print(f"ΔQ at {bus.name}: {mismatch[index]:.6f}")
                index += 1


    def calc_ybus_fault(self):
        self.calc_ybus()
        bus_mapping = {name: bus.bus_index for name, bus in self.buses.items()}

        bus_names = list(bus_mapping.keys())
        ybus_array = self.ybus.values.copy()

        for gen in self.generators.values():
            if gen.x_sub_reactance == 0.0:
                continue

            i = bus_mapping[gen.bus1_name]
            y_gen = 1/ (1j * gen.x_sub_reactance)
            ybus_array[i, i] += y_gen

        self.ybus = pd.DataFrame(ybus_array, columns=bus_names, index=bus_names)

    def calc_zbus(self):
        if self.ybus is None:
            raise ValueError("ybus not calculated")

        bus_names = list(self.buses.keys())

        ybus_array = self.ybus.values
        zbus_array = np.linalg.inv(ybus_array)

        self.zbus = pd.DataFrame(zbus_array, columns=bus_names, index=bus_names)

        return self.zbus

    def update_dispatch(self, dispatch: dict):
        for gen_name, mw in dispatch.items():
            gen = self.generators[gen_name]
            gen.mw_setpoint = mw
            gen.p = mw / SETTINGS.sbase

    def calc_B(self):
        if self.ybus is None:
            raise ValueError("ybus not calculated")
        bus_names = list(self.buses.keys())
        B = self.ybus.values.imag
        self.bbus = pd.DataFrame(B, columns=bus_names, index=bus_names)
        return self.bbus


if __name__ == "__main__":
    """
    # 5 Bus Validation
    from jacobian import Jacobian
    from power_flow import PowerFlow

    c1 = Circuit("Test Circuit")
    Bus.index_counter = 0
    c_val = Circuit("2-Bus Validation")

    # Buses
    c_val.add_bus("Bus1", 138.0, "Slack")
    c_val.add_bus("Bus2", 138.0, "PQ")

    # Single series path: T1 + Line + T2 combined = j0.10 + j0.105 + j0.10 = j0.305
    # Modeled as one transmission line with r=0, x=0.305, g=0, b=0
    c_val.add_transmission_line("T1_Line_T2", "Bus1", "Bus2", 0.0, 0.305, 0.0, 0.0)

    # Generators with subtransient reactance
    c_val.add_generator("G1", "Bus1", 1.0, 0.0, x_sub_reactance=0.15)
    c_val.add_generator("M", "Bus2", 1.0, 0.0, x_sub_reactance=0.20)
    # ------------------------------------------------
    # Print faulted Ybus
    # ------------------------------------------------
    c_val.calc_ybus_fault()
    print("Faulted Ybus:")
    print(c_val.ybus)
    print()

    # Expected:
    # | -j9.9454   j3.2787 |
    # |  j3.2787  -j8.2787 |

    # ------------------------------------------------
    # Print Zbus
    # ------------------------------------------------
    c_val.calc_zbus()
    print("Zbus:")
    print(c_val.zbus)
    print()

    # Expected:
    # | j0.11565   j0.04580 |
    # | j0.04580   j0.13893 |

    # ------------------------------------------------
    # Fault Study
    # ------------------------------------------------
    J_val = Jacobian(c_val)
    pf_val = PowerFlow(c_val, J_val, mode="fault")

    print("=" * 50)
    print("FAULT AT BUS1")
    print("=" * 50)
    # Expected: I_fault = -j8.6468, E1 = 0.0, E2 = 0.60398
    result_bus1 = pf_val.run_type(fault_bus="Bus1", vf=1.0)
    pf_val.print_fault_results(result_bus1)

    print("=" * 50)
    print("FAULT AT BUS2")
    print("=" * 50)
    # Expected: I_fault = -j7.1974, E1 = 0.67015, E2 = 0.0
    result_bus2 = pf_val.run_type(fault_bus="Bus2", vf=1.0)
    pf_val.print_fault_results(result_bus2)
"""
    from jacobian import Jacobian
    from power_flow import PowerFlow

    c1 = Circuit("Test Circuit")

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

    c1.add_generator("G1", "Bus1", 1.00, 0.0, 0.15, 0.0, 0.0, 0.0, 0.0, 0.0)
    c1.add_generator("G2", "Bus3", 1.05, 520.0, 0.20, 0.0, 0.0, 0.0, 0.0, 0.0)
    # Old:
    # c1.add_generator("G1", "Bus1", 1.04, 0.0)     # Slack bus, MW not used directly in mismatch
    # c1.add_generator("G2", "Bus4", 1.01, 400.0)   # Example PV generator
    # c1.add_generator("G3", "Bus5", 1.01, 600.0)   # Example PV generator

    c1.add_load("L1", "Bus3", 80.0, 40.0)
    c1.add_load("L2", "Bus2", 800.0, 280.0)

    c1.calc_ybus()
    print("Ybus:\n")
    print(c1.ybus)

    # Compute mismatch vector
    mismatch = c1.compute_power_mismatch()

    print("\n Array Mistmatch")
    print(mismatch)

    angle_dict = {
        "Bus1": c1.buses["Bus1"].delta,
        "Bus2": c1.buses["Bus2"].delta,
        "Bus3": c1.buses["Bus3"].delta,
        "Bus4": c1.buses["Bus4"].delta,
        "Bus5": c1.buses["Bus5"].delta,
    }

    voltage_dict = {
        "Bus1": c1.buses["Bus1"].vpu,
        "Bus2": c1.buses["Bus2"].vpu,
        "Bus3": c1.buses["Bus3"].vpu,
        "Bus4": c1.buses["Bus4"].vpu,
        "Bus5": c1.buses["Bus5"].vpu,
    }

    J = Jacobian(c1)
    jacobian_matrix = J.calc_jacobian(
        buses=c1.buses,
        ybus=c1.ybus,
        angles=angle_dict,
        voltages=voltage_dict
    )
    print("\nJacobian Matrix:\n")
    print(jacobian_matrix)

    pf = PowerFlow(c1, J, mode="power_flow")
    NR = pf.run_type(tol = 0.001, max_iter = 50)

    print("\nNewton-Raphson Results:\n")
    print(f"Converged: {NR['converged']}")
    print(f"Iterations: {NR['iterations']}\n")

    for bus_name, data in NR["bus_data"].items():
        print(f"{bus_name}:")
        print(f"   Voltage (pu): {data['vpu']:.6f}")
        print(f"   Angle (deg):  {data['delta']:.6f}\n")
"""
    # fault study starts here, outside the loop
    print("\n" + "=" * 50)
    print("FAULT STUDY")
    print("=" * 50)

    pf_fault = PowerFlow(c1, J, mode="fault")
    print(c1.calc_zbus())

    for fault_bus in c1.buses.keys():
        fault_result = pf_fault.run_type(fault_bus=fault_bus, vf=1.0)
        pf_fault.print_fault_results(fault_result)
"""


"""
     # Converged Case
    c1.buses["Bus1"].vpu = 1.00000
    c1.buses["Bus1"].delta = 0.0000010000

    c1.buses["Bus2"].vpu = 0.9879657065
    c1.buses["Bus2"].delta = -14.6577850557

    c1.buses["Bus3"].vpu = 1.0500038185
    c1.buses["Bus3"].delta = 0.1554834102

    c1.buses["Bus4"].vpu = 1.0331396265
    c1.buses["Bus4"].delta = -1.6332636943

    c1.buses["Bus5"].vpu = 1.0105737711
    c1.buses["Bus5"].delta = -3.2050233851
    
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