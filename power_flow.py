import numpy as np
from circuit import Circuit
from jacobian import Jacobian

class PowerFlow:
    def __init__(self, circuit: Circuit, jacobian: Jacobian):
        self.circuit = circuit
        self.jacobian = jacobian
        self.tol = 0.001
        self.max_iter = 10


    def solve(self, tol, max_iter):
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


if __name__ == '__main__':
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

    pf = PowerFlow(c1, J)

    NR = pf.solve(tol=0.001, max_iter = 50)

    print("\nNewton-Raphson Results:\n")
    print(f"Converged: {NR['converged']}")
    print(f"Iterations: {NR['iterations']}\n")

    for bus_name, data in NR["bus_data"].items():
        print(f"{bus_name}:")
        print(f"   Voltage (pu): {data['vpu']:.6f}")
        print(f"   Angle (deg):  {data['delta']:.6f}\n")
