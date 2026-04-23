import numpy as np
from circuit import Circuit
from jacobian import Jacobian
from dcopf import DCOPF

class PowerFlow:

    MODE_TYPES = {"power_flow", "fault", "economic_dispatch"}

    def __init__(self, circuit: Circuit, jacobian: Jacobian, mode: str = "power_flow"):
        self.circuit = circuit
        self.jacobian = jacobian
        self.tol = 0.001
        self.max_iter = 50

        if mode not in self.MODE_TYPES:
            raise ValueError(
                f"Invalid mode '{mode}'. "
                f"Valid modes are: {self.MODE_TYPES}"
            )
        self.mode = mode

    def run_type(self, **kwargs):
        if self.mode == "power_flow":
            return self.solve(**kwargs)
        elif self.mode == "fault":
            return self.solve_fault(**kwargs)
        elif self.mode == "economic_dispatch":
            return self.solve_economic_dispatch(**kwargs)


    def solve(self, tol = 0.001, max_iter = 50):
        self.circuit.calc_ybus()
        jacobian_obj = Jacobian(self.circuit)
        self.converged = False
        self.iteration = 0

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
    def print_NF_result(self, NR: dict):
        print("\nNewton-Raphson Results:\n")
        print(f"Converged: {NR['converged']}")
        print(f"Iterations: {NR['iterations']}\n")

        for bus_name, data in NR["bus_data"].items():
            print(f"{bus_name}:")
            print(f"   Voltage (pu): {data['vpu']:.6f}")
            print(f"   Angle (deg):  {data['delta']:.6f}\n")


    def solve_fault(self, fault_bus: str, vf: float = 1.0):
        # Step 1: build faulted Ybus and Zbus
        self.circuit.calc_ybus_fault()
        self.circuit.calc_zbus()

        # Step 2: validate fault bus
        if fault_bus not in self.circuit.buses:
            raise ValueError(f"Bus '{fault_bus}' not found in circuit.")

        # Step 3: extract Znn
        Znn = self.circuit.zbus.loc[fault_bus, fault_bus]

        # Step 4: calculate fault current
        I_fault = vf / Znn

        # Step 5: calculate post-fault voltage at every bus
        bus_voltages = {}
        for bus_name in self.circuit.buses.keys():
            Zkn = self.circuit.zbus.loc[bus_name, fault_bus]
            Ek = 1 - (Zkn / Znn) * vf
            bus_voltages[bus_name] = Ek

        return {
            "fault_bus": fault_bus,
            "vf": vf,
            "Znn": Znn,
            "I_fault": I_fault,
            "bus_voltages": bus_voltages
        }

    def print_fault_results(self, fault_results: dict):
        print(f"\nFault Study Results:")
        print(f"  Faulted Bus:    {fault_results['fault_bus']}")
        print(f"  Pre-fault V:    {fault_results['vf']} pu")
        print(f"  Znn:            {fault_results['Znn']:.5f}")
        print(f"  Fault Current:  {fault_results['I_fault']:.5f} pu\n")
        print(f"  Post-Fault Bus Voltages:")
        for bus_name, voltage in fault_results["bus_voltages"].items():
            print(f"    {bus_name}: {abs(voltage):.5f} pu")

        # --------------------------------------------------
        # ECONOMIC DISPATCH (DC OPF)
        # --------------------------------------------------

    def solve_economic_dispatch(self, tol=0.001, max_iter=50):
        # Step 1: run DC OPF to find optimal dispatch
        opf = DCOPF(self.circuit)
        opf_result = opf.solve()

        # Step 2: update generator MW setpoints with optimal dispatch
        self.circuit.update_dispatch(opf_result["dispatch"])

        # Step 3: run Newton-Raphson with new dispatch
        pf_result = self.solve(tol=tol, max_iter=max_iter)

        # Step 4: return combined results
        return {
            "dispatch": opf_result["dispatch"],
            "gen_costs": opf_result["gen_costs"],
            "total_cost": opf_result["total_cost"],
            "dc_angles": opf_result["angles_deg"],
            "dc_line_flows": opf_result["line_flows_MW"],
            "power_flow": pf_result
        }

    def print_economic_dispatch_results(self, result: dict):
        print("\n" + "=" * 50)
        print("ECONOMIC DISPATCH RESULTS")
        print("=" * 50)

        print("\nOptimal Generator Dispatch:")
        for gen_name, mw in result["dispatch"].items():
            cost = result["gen_costs"][gen_name]
            print(f"  {gen_name}: {mw:.2f} MW   Cost: ${cost:.2f}/hr")

        print(f"\n  Total System Cost: ${result['total_cost']:.2f}/hr")

        print("\nDC Bus Angles:")
        for bus_name, angle in result["dc_angles"].items():
            print(f"  {bus_name}: {angle:.4f} deg")

        print("\nDC Line Flows:")
        for element_name, flow in result["dc_line_flows"].items():
            print(f"  {element_name}: {flow:.2f} MW")

        print("\nAC Power Flow Results (post-dispatch):")
        print(f"  Converged: {result['power_flow']['converged']}")
        print(f"  Iterations: {result['power_flow']['iterations']}\n")

        for bus_name, data in result["power_flow"]["bus_data"].items():
            print(f"  {bus_name}:")
            print(f"    Voltage (pu): {data['vpu']:.6f}")
            print(f"    Angle (deg):  {data['delta']:.6f}\n")

if __name__ == "__main__":
    from bus import Bus
    from circuit import Circuit
    from jacobian import Jacobian

    # ------------------------------------------------
    # Build 5-Bus System
    # ------------------------------------------------
    Bus.index_counter = 0
    c1 = Circuit("5-Bus System")

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

    c1.add_generator("G1", "Bus1", 1.00, 0.0,
                     x_sub_reactance=0.15,
                     cost_a=200.0, cost_b=12.0, cost_c=0.004,
                     p_min=50.0, p_max=600.0)

    c1.add_generator("G2", "Bus3", 1.05, 520.0,
                     x_sub_reactance=0.20,
                     cost_a=350.0, cost_b=20.0, cost_c=0.005,
                     p_min=100.0, p_max=700.0)

    c1.add_load("L1", "Bus3", 80.0, 40.0)
    c1.add_load("L2", "Bus2", 800.0, 280.0)

    J = Jacobian(c1)

    # ------------------------------------------------
    # STEP 1: BASE POWER FLOW (no economic dispatch)
    # ------------------------------------------------
    print("=" * 50)
    print("STEP 1: BASE POWER FLOW")
    print("=" * 50)

    pf_base = PowerFlow(c1, J, mode="power_flow")
    base_result = pf_base.run_type(tol=0.001, max_iter=50)

    print(f"\nConverged: {base_result['converged']}")
    print(f"Iterations: {base_result['iterations']}\n")

    for bus_name, data in base_result["bus_data"].items():
        print(f"{bus_name}:")
        print(f"   Voltage (pu): {data['vpu']:.6f}")
        print(f"   Angle (deg):  {data['delta']:.6f}\n")

    # ------------------------------------------------
    # STEP 2: PRE-DISPATCH COST
    # ------------------------------------------------
    print("=" * 50)
    print("STEP 2: PRE-DISPATCH COST (hardcoded)")
    print("=" * 50)

    G1 = c1.generators["G1"]
    G2 = c1.generators["G2"]

    # G1 slack picks up ~395 MW based on base power flow
    G1.mw_setpoint = 395.0
    G2.mw_setpoint = 520.0

    pre_cost_g1 = G1.calc_cost()
    pre_cost_g2 = G2.calc_cost()
    pre_total   = pre_cost_g1 + pre_cost_g2

    print(f"\n  G1: {G1.mw_setpoint:.2f} MW   Cost: ${pre_cost_g1:.2f}/hr")
    print(f"  G2: {G2.mw_setpoint:.2f} MW   Cost: ${pre_cost_g2:.2f}/hr")
    print(f"  Total: ${pre_total:.2f}/hr")
    print(f"\n  G1 Incremental Cost: ${G1.calc_incremental_cost():.4f}/MWhr")
    print(f"  G2 Incremental Cost: ${G2.calc_incremental_cost():.4f}/MWhr")
    print(f"  (Not equal -> not optimal)")

    # ------------------------------------------------
    # STEP 3: ECONOMIC DISPATCH (DC OPF + AC Power Flow)
    # ------------------------------------------------
    print("\n" + "=" * 50)
    print("STEP 3: ECONOMIC DISPATCH (DC OPF)")
    print("=" * 50)

    Bus.index_counter = 0
    c2 = Circuit("5-Bus System - Economic Dispatch")

    c2.add_bus("Bus1", 15.0, "Slack")
    c2.add_bus("Bus2", 345.0, "PQ")
    c2.add_bus("Bus3", 15.0, "PV")
    c2.add_bus("Bus4", 345.0, "PQ")
    c2.add_bus("Bus5", 345.0, "PQ")

    c2.add_transformer("T1", "Bus1", "Bus5", 0.0015, 0.02)
    c2.add_transformer("T2", "Bus3", "Bus4", 0.00075, 0.01)

    c2.add_transmission_line("TL1", "Bus5", "Bus4", 0.00225, 0.025, 0.0, 0.44)
    c2.add_transmission_line("TL2", "Bus5", "Bus2", 0.0045, 0.05, 0.0, 0.88)
    c2.add_transmission_line("TL3", "Bus4", "Bus2", 0.009, 0.1, 0.0, 1.72)

    c2.add_generator("G1", "Bus1", 1.00, 0.0,
                     x_sub_reactance=0.15,
                     cost_a=200.0, cost_b=12.0, cost_c=0.004,
                     p_min=50.0, p_max=600.0)

    c2.add_generator("G2", "Bus3", 1.05, 520.0,
                     x_sub_reactance=0.20,
                     cost_a=350.0, cost_b=20.0, cost_c=0.005,
                     p_min=100.0, p_max=700.0)

    c2.add_load("L1", "Bus3", 80.0, 40.0)
    c2.add_load("L2", "Bus2", 800.0, 280.0)

    J2 = Jacobian(c2)
    pf_ed = PowerFlow(c2, J2, mode="economic_dispatch")
    ed_result = pf_ed.run_type(tol=0.001, max_iter=50)
    pf_ed.print_economic_dispatch_results(ed_result)

    # ------------------------------------------------
    # STEP 4: INCREMENTAL COST VERIFICATION
    # ------------------------------------------------
    print("=" * 50)
    print("STEP 4: INCREMENTAL COST VERIFICATION")
    print("=" * 50)

    G1_opt = c2.generators["G1"]
    G2_opt = c2.generators["G2"]

    # mw_setpoint is already updated by update_dispatch() inside solve_economic_dispatch()
    # no need to set it again - just read what the optimizer set

    print(f"\n  G1 dispatch:        {G1_opt.mw_setpoint:.4f} MW")
    print(f"  G2 dispatch:        {G2_opt.mw_setpoint:.4f} MW")
    print(f"  Total generation:   {G1_opt.mw_setpoint + G2_opt.mw_setpoint:.4f} MW")
    print(f"  Total load:         880.0 MW")

    print(f"\n  G1 Incremental Cost: ${G1_opt.calc_incremental_cost():.4f}/MWhr")
    print(f"  G2 Incremental Cost: ${G2_opt.calc_incremental_cost():.4f}/MWhr")

    # ------------------------------------------------
    # STEP 5: COST SAVINGS SUMMARY
    # ------------------------------------------------
    print("\n" + "=" * 50)
    print("STEP 5: COST SAVINGS SUMMARY")
    print("=" * 50)

    savings = pre_total - ed_result["total_cost"]
    print(f"\n  Pre-dispatch cost:  ${pre_total:.2f}/hr")
    print(f"  Optimal cost:       ${ed_result['total_cost']:.2f}/hr")
    print(f"  Savings:            ${savings:.2f}/hr")
    print(f"  Annual savings:     ${savings * 8760:.2f}/yr  (assuming continuous operation)")

"""
    from bus import Bus
    from circuit import Circuit
    from jacobian import Jacobian

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

    c1.add_generator("G1", "Bus1", 1.00, 0.0, 0.0)
    c1.add_generator("G2", "Bus3", 1.05, 520.0, 0.0)

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

    pf = PowerFlow(c1, J)

    NR = pf.solve(tol=0.001, max_iter = 50)

    print("\nNewton-Raphson Results:\n")
    print(f"Converged: {NR['converged']}")
    print(f"Iterations: {NR['iterations']}\n")

    for bus_name, data in NR["bus_data"].items():
        print(f"{bus_name}:")
        print(f"   Voltage (pu): {data['vpu']:.6f}")
        print(f"   Angle (deg):  {data['delta']:.6f}\n")
   """