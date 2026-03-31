import numpy as np
from circuit import Circuit
from jacobian import Jacobian
from settings import Settings


class PowerFlow:
    def __init__(self, circuit: Circuit, jacobian: Jacobian):
        self.circuit = circuit
        self.jacobian = jacobian
        self.tol = 0.001
        self.max_iter = 50


    def solve(self, tol=0.001, max_iter=50, flat_start=True):
        self.circuit.update_generator()
        self.circuit.calc_ybus()
        self.circuit.zero_islanded_buses()
        self.converged = False
        self.iteration = 0

        if flat_start:
            # flat start initialization
            for bus in self.circuit.buses.values():
                if bus.bus_type == "Slack":
                    continue
                elif bus.bus_type == "PV":
                    bus.delta = 0.0
                    for gen in self.circuit.generators.values():
                        if gen.bus1_name == bus.name:
                            bus.vpu = gen.voltage_setpoint
                elif bus.bus_type == "PQ":
                    bus.vpu = 1.0
                    bus.delta = 0.0

        # Newton-Raphson iteration loop
        for self.iteration in range(1, max_iter + 1):
            jacobian_obj = Jacobian(self.circuit)
            mismatch = self.circuit.compute_power_mismatch()
            J = jacobian_obj.calc_jacobian()
            max_mismatch = np.max(abs(mismatch))

            #print(f"Iteration {iteration}: max mismatch = {max_mismatch:.6f}")

            if max_mismatch < tol:
                self.converged = True
                break
            else:
                x_vector = np.linalg.solve(J, mismatch)
                num_angles = len(jacobian_obj.angle_buses)
                delta_angles = x_vector[:num_angles]
                delta_voltages = x_vector[num_angles:]

                # update non-slack bus angles
                for i, bus in enumerate(jacobian_obj.angle_buses):
                    bus.delta += np.rad2deg(delta_angles[i])

                # update PQ bus voltages
                for i, bus in enumerate(jacobian_obj.voltage_buses):
                    bus.vpu += delta_voltages[i]

        if not self.converged:
            raise ValueError("Algorithm did not converge")

        return {
            "converged": self.converged,
            "iterations": self.iteration,
            "bus_data": {
                bus.name: {"vpu": bus.vpu, "delta": bus.delta}
                for bus in self.circuit.buses.values()
            }
        }

    def compute_power_flow_direction(self, settings: Settings):
        global direction
        flow_results_tl_tf = {}
        flow_results_g_l = {}

        # ---------- transmission line flows ----------
        for line_name, line in self.circuit.transmission_lines.items():
            bus1 = self.circuit.buses[line.bus1_name]
            bus2 = self.circuit.buses[line.bus2_name]

            # complex bus voltages
            V1 = bus1.vpu * np.exp(1j * np.deg2rad(bus1.delta))
            V2 = bus2.vpu * np.exp(1j * np.deg2rad(bus2.delta))

            # currents using pi-model
            I12 = (V1 - V2) * line.Yseries + V1 * (line.Yshunt / 2)
            I21 = (V2 - V1) * line.Yseries + V2 * (line.Yshunt / 2)

            # complex powers
            S12 = V1 * np.conj(I12)
            S21 = V2 * np.conj(I21)

            P12 = S12.real
            Q12 = S12.imag
            P21 = S21.real
            Q21 = S21.imag

            Ploss = P12 + P21
            Qloss = Q12 + Q21

            # determine displayed direction from real power
            if P12 >= 0:
                direction = f"{bus1.name} -> {bus2.name}"
                display_mw = P12 * settings.sbase
                display_mvar = Q12 * settings.sbase
            else:
                direction = f"{bus2.name} -> {bus1.name}"
                display_mw = abs(P12) * settings.sbase
                display_mvar = abs(Q12) * settings.sbase

            flow_results_tl_tf[line_name] = {
                "type": "Transmission Line",
                "from_bus": bus1.name,
                "to_bus": bus2.name,
                "P12_MW": P12 * settings.sbase,
                "Q12_MVAR": Q12 * settings.sbase,
                "P21_MW": P21 * settings.sbase,
                "Q21_MVAR": Q21 * settings.sbase,
                "Ploss_MW": Ploss * settings.sbase,
                "Qloss_MVAR": Qloss * settings.sbase,
                "direction": direction,
                "display_MW": display_mw,
                "display_MVAR": display_mvar
            }

        # ---------- transformer flows ----------
        for transformer_name, transformer in self.circuit.transformers.items():
            bus1 = self.circuit.buses[transformer.bus1_name]
            bus2 = self.circuit.buses[transformer.bus2_name]

            V1 = bus1.vpu * np.exp(1j * np.deg2rad(bus1.delta))
            V2 = bus2.vpu * np.exp(1j * np.deg2rad(bus2.delta))

            # transformer current, no shunt branch
            I12 = (V1 - V2) * transformer.Yseries
            I21 = (V2 - V1) * transformer.Yseries

            S12 = V1 * np.conj(I12)
            S21 = V2 * np.conj(I21)

            P12 = S12.real
            Q12 = S12.imag
            P21 = S21.real
            Q21 = S21.imag

            Ploss = P12 + P21
            Qloss = Q12 + Q21

            if P12 >= 0:
                direction = f"{bus1.name} -> {bus2.name}"
                display_mw = P12 * settings.sbase
                display_mvar = Q12 * settings.sbase
            else:
                direction = f"{bus2.name} -> {bus1.name}"
                display_mw = abs(P12) * settings.sbase
                display_mvar = abs(Q12) * settings.sbase

            flow_results_tl_tf[transformer_name] = {
                "type": "Transformer",
                "from_bus": bus1.name,
                "to_bus": bus2.name,
                "P12_MW": P12 * settings.sbase,
                "Q12_MVAR": Q12 * settings.sbase,
                "P21_MW": P21 * settings.sbase,
                "Q21_MVAR": Q21 * settings.sbase,
                "Ploss_MW": Ploss * settings.sbase,
                "Qloss_MVAR": Qloss * settings.sbase,
                "direction": direction,
                "display_MW": display_mw,
                "display_MVAR": display_mvar
            }
        for load_name, load in self.circuit.loads.items():
            bus1 = self.circuit.buses[load.bus1_name]

            P_delivered = 0.0
            Q_delivered = 0.0

            # PQ bus: sum incoming flows from already-calculated results
            for line_name, data in flow_results_tl_tf.items():
                if data["type"] == "Transmission Line":
                    if data["to_bus"] == bus1.name:
                        #abs becuase - would be leaving bus2
                        P_delivered += abs(data["P21_MW"])
                        Q_delivered += abs(data["Q21_MVAR"])
                    elif data["from_bus"] == bus1.name:
                        if data["P12_MW"] < 0:
                            P_delivered += (data["P12_MW"])
                            Q_delivered += (data["Q12_MVAR"])

                elif data["type"] == "Transformer":
                    ##Question on PI
                    Pcalc, Qcalc = self.circuit.compute_power_injection(bus1)
                    if data["from_bus"] == bus1.name:
                        P_delivered += (data["P12_MW"])
                        Q_delivered += (data["Q12_MVAR"])
                    elif data["to_bus"] == bus1.name:
                        if data["P21_MW"] < 0:
                            P_delivered += (data["P21_MW"])
                            Q_delivered += (data["Q21_MVAR"])

            direction_q = None  # default

            if P_delivered >= 0 and Q_delivered >= 0:
                direction = f"{bus1.name} -> load"
                display_mw = P_delivered
                display_mvar = Q_delivered
            elif P_delivered <= 0 and Q_delivered <= 0:
                direction = f"load -> {bus1.name}"
                display_mw = P_delivered
                display_mvar = Q_delivered
            elif P_delivered >= 0 and Q_delivered <= 0:
                direction = f"{bus1.name} -> Load_P"
                direction_q = f"load Q -> {bus1.name}"
                display_mw = P_delivered
                display_mvar = Q_delivered
            else: #P_delivered <= 0 and Q_delivered >= 0
                direction = f"load P -> {bus1.name}"
                direction_q = f"{bus1.name} -> Load_Q"
                display_mw = P_delivered
                display_mvar = Q_delivered

            # outside all branches
            flow_results_g_l[load_name] = {
                "type": "Load",
                "from_bus": bus1.name,
                "to": "load",
                "P_delivered_MW": P_delivered,
                "Q_delivered_MVAR": Q_delivered,
                "P_specified_MW": load.mw,
                "Q_specified_MVAR": load.mvar,
                "direction": direction,
                "direction_q": direction_q,
                "display_MW": display_mw,
                "display_MVAR": display_mvar
            }

        return flow_results_tl_tf, flow_results_g_l

    def print_flow_results(self, flow_results_tl_tf: dict, flow_results_g_l: dict):
        for element_name, data in flow_results_tl_tf.items():
            print(f"{element_name}:")
            print(f"  Type:         {data['type']}")
            print(f"  From Bus:     {data['from_bus']}")
            print(f"  To Bus:       {data['to_bus']}")
            print(f"  P12 (MW):     {data['P12_MW']:.4f}")
            print(f"  Q12 (MVAR):   {data['Q12_MVAR']:.4f}")
            print(f"  Ploss (MW):   {data['Ploss_MW']:.4f}")
            print(f"  Qloss (MVAR): {data['Qloss_MVAR']:.4f}")
            print(f"  Direction:    {data['direction']}")
            print(f"  Display MW:   {data['display_MW']:.4f}")
            print(f"  Display MVAR: {data['display_MVAR']:.4f}\n")

        for element_name, data_s in flow_results_g_l.items():
            print(f"{element_name}:")
            print(f"  Type:              {data_s['type']}")
            print(f"  Bus:               {data_s['from_bus']}")
            print(f"  To:                {data_s['to']}")
            print(f"  P Delivered (MW):  {data_s['P_delivered_MW']:.4f}")
            print(f"  Q Delivered (MVAR):{data_s['Q_delivered_MVAR']:.4f}")
            print(f"  P Specified (MW):  {data_s['P_specified_MW']:.4f}")
            print(f"  Q Specified (MVAR):{data_s['Q_specified_MVAR']:.4f}")
            print(f"  Direction:         {data_s['direction']}")
            print(f"  Display MW:        {data_s['display_MW']:.4f}")
            print(f"  Display MVAR:      {data_s['display_MVAR']:.4f}\n")



if __name__ == '__main__':
    from bus import Bus
    from circuit import Circuit
    from jacobian import Jacobian
    from settings import Settings

    c1 = Circuit("Test Circuit")
    Bus.index_counter = 0

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

    c1.add_generator("G1", "Bus1", 1.00, 0.0)
    c1.add_generator("G2", "Bus3", 1.05, 520.0)

    c1.add_load("L1", "Bus3", 80.0, 40.0)
    c1.add_load("L2", "Bus2", 800.0, 280.0)

    c1.calc_ybus()

    print("Ybus:\n")
    print(c1.ybus)


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

    print("\nJacobian Shape:")
    print(jacobian_matrix.shape)
    sbaseS = Settings()
    pf = PowerFlow(c1, J)

    NR = pf.solve(tol=0.001, max_iter = 50)

    print("\nNewton-Raphson Results:\n")
    print(f"Converged: {NR['converged']}")
    print(f"Iterations: {NR['iterations']}\n")

    for bus_name, data in NR["bus_data"].items():
        print(f"{bus_name}:")
        print(f"   Voltage (pu): {data['vpu']:.6f}")
        print(f"   Angle (deg):  {data['delta']:.6f}\n")

    pfd_tf_l, pfd_g_l = pf.compute_power_flow_direction(sbaseS)
    print("\nPower Flow Results:\n")
    pfr = pf.print_flow_results(pfd_tf_l, pfd_g_l)