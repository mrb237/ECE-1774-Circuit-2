import numpy as np
from scipy.optimize import minimize
from circuit import Circuit
from settings import SETTINGS


class DCOPF:
    def __init__(self, circuit: Circuit):
        self.circuit = circuit
        self.result = None

    def solve(self):
        # Setup

        self.circuit.calc_ybus()
        self.circuit.calc_B()

        buses = list(self.circuit.buses.values())
        generators = list(self.circuit.generators.values())
        bus_names = [bus.name for bus in buses]

        slack_idx = next(
            i for i, bus in enumerate(buses) if bus.bus_type == "Slack"
        )

        N = len(buses)
        G = len(generators)
        num_vars = G + N

        bus_index = {bus.name: i for i, bus in enumerate(buses)}
        gen_bus_idx = [bus_index[gen.bus1_name] for gen in generators]

        # Total load at each bus in MW
        load_per_bus = np.zeros(N)
        for load in self.circuit.loads.values():
            idx = bus_index[load.bus1_name]
            load_per_bus[idx] += load.mw

        # B matrix is in per-unit so convert load to per-unit too
        load_per_bus_pu = load_per_bus / SETTINGS.sbase

        B = self.circuit.bbus.values

        # Objective Function: generator outputs in per-unit
        def objective(x):
            Pg_pu = x[:G]
            total_cost = 0.0
            for i, gen in enumerate(generators):
                Pg_mw = Pg_pu[i] * SETTINGS.sbase  # convert to MW for cost
                total_cost += gen.cost_a + gen.cost_b * Pg_mw + gen.cost_c * Pg_mw ** 2
            return total_cost

        # Constraints
        constraints = []



        # 2. Total generation must equal total load (scalar)
        def total_power_balance(x):
            Pg_pu = x[:G]
            total_gen = sum(Pg_pu)
            total_load = load_per_bus_pu.sum()
            return total_gen - total_load

        constraints.append({"type": "eq", "fun": total_power_balance})

        # Slack bus angle = 0
        def slack_angle(x):
            return x[G + slack_idx]

        constraints.append({"type": "eq", "fun": slack_angle})

        # Bounds — generators in per-unit, angles in radians
        bounds = []

        for gen in generators:
            bounds.append((gen.p_min / SETTINGS.sbase, gen.p_max / SETTINGS.sbase))

        for _ in range(N):
            bounds.append((-np.pi / 2, np.pi / 2))

        # Intial Guess
        total_load_pu = load_per_bus_pu.sum()
        x0 = np.zeros(num_vars)

        for i, gen in enumerate(generators):
            x0[i] = max(gen.p_min / SETTINGS.sbase,
                        min(gen.p_max / SETTINGS.sbase,
                            gen.mw_setpoint / SETTINGS.sbase if gen.mw_setpoint > 0
                            else total_load_pu / G))

        # Solve
        result = minimize(
            objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"ftol": 1e-9, "maxiter": 2000, "disp": True}
        )

        if not result.success:
            raise ValueError(f"DC OPF did not converge: {result.message}")

        # Extract results — convert back to MW
        Pg_opt_pu = result.x[:G]
        Pg_opt_mw = Pg_opt_pu * SETTINGS.sbase
        delta_opt = result.x[G:]

        dispatch = {gen.name: Pg_opt_mw[i] for i, gen in enumerate(generators)}
        angles = {bus.name: np.rad2deg(delta_opt[i]) for i, bus in enumerate(buses)}

        # Line flows in MW
        line_flows = {}
        for line_name, line in self.circuit.transmission_lines.items():
            i = bus_index[line.bus1_name]
            j = bus_index[line.bus2_name]
            P_flow_pu = (delta_opt[i] - delta_opt[j]) / line.x
            line_flows[line_name] = P_flow_pu * SETTINGS.sbase

        for tf_name, tf in self.circuit.transformers.items():
            i = bus_index[tf.bus1_name]
            j = bus_index[tf.bus2_name]
            P_flow_pu = (delta_opt[i] - delta_opt[j]) / tf.x
            line_flows[tf_name] = P_flow_pu * SETTINGS.sbase

        # Total cost
        total_cost = 0.0
        gen_costs = {}
        for i, gen in enumerate(generators):
            cost = gen.cost_a + gen.cost_b * Pg_opt_mw[i] + gen.cost_c * Pg_opt_mw[i] ** 2
            gen_costs[gen.name] = cost
            total_cost += cost

        self.result = {
            "success": result.success,
            "dispatch": dispatch,
            "angles_deg": angles,
            "line_flows_MW": line_flows,
            "gen_costs": gen_costs,
            "total_cost": total_cost
        }

        return self.result

    def print_results(self):
        if self.result is None:
            raise ValueError("No results available. Call solve() first.")

        print("\n" + "=" * 50)
        print("DC OPF RESULTS")
        print("=" * 50)

        print("\nOptimal Generator Dispatch:")
        for gen_name, mw in self.result["dispatch"].items():
            cost = self.result["gen_costs"][gen_name]
            print(f"  {gen_name}: {mw:.2f} MW   Cost: ${cost:.2f}/hr")

        print(f"\n  Total System Cost: ${self.result['total_cost']:.2f}/hr")

        print("\nDC Bus Angles:")
        for bus_name, angle in self.result["angles_deg"].items():
            print(f"  {bus_name}: {angle:.4f} deg")

        print("\nDC Line Flows:")
        for element_name, flow in self.result["line_flows_MW"].items():
            print(f"  {element_name}: {flow:.2f} MW")

if __name__ == "__main__":
    from bus import Bus
    from circuit import Circuit

    # ------------------------------------------------
    # Build 5-Bus System
    # ------------------------------------------------
    Bus.index_counter = 0
    c1 = Circuit("5-Bus DC OPF Test")

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

    # ------------------------------------------------
    # Print Ybus and B matrix
    # ------------------------------------------------
    c1.calc_ybus()
    print("Ybus:\n")
    print(c1.ybus)

    c1.calc_B()
    print("\nB Matrix:\n")
    print(c1.bbus)

    # ------------------------------------------------
    # Pre-dispatch cost (current hardcoded values)
    # ------------------------------------------------
    print("\n" + "=" * 50)
    print("PRE-DISPATCH (hardcoded)")
    print("=" * 50)

    G1 = c1.generators["G1"]
    G2 = c1.generators["G2"]

    # G1 slack picks up ~395 MW based on NR results
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
    # Run DC OPF
    # ------------------------------------------------
    print("\n" + "=" * 50)
    print("RUNNING DC OPF")
    print("=" * 50)

    opf = DCOPF(c1)
    result = opf.solve()
    opf.print_results()

    # ------------------------------------------------
    # Verify equal incremental cost after dispatch
    # ------------------------------------------------
    print("\n" + "=" * 50)
    print("INCREMENTAL COST VERIFICATION")
    print("=" * 50)

    G1.mw_setpoint = result["dispatch"]["G1"]
    G2.mw_setpoint = result["dispatch"]["G2"]

    print(f"\n  G1 Incremental Cost: ${G1.calc_incremental_cost():.4f}/MWhr")
    print(f"  G2 Incremental Cost: ${G2.calc_incremental_cost():.4f}/MWhr")
    print(f"  (Should be equal -> optimal dispatch confirmed)")

    # ------------------------------------------------
    # Cost savings summary
    # ------------------------------------------------
    print("\n" + "=" * 50)
    print("COST SAVINGS SUMMARY")
    print("=" * 50)
    savings = pre_total - result["total_cost"]
    print(f"\n  Pre-dispatch cost:  ${pre_total:.2f}/hr")
    print(f"  Optimal cost:       ${result['total_cost']:.2f}/hr")
    print(f"  Savings:            ${savings:.2f}/hr")