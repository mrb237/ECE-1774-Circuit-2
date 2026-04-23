from circuit import Circuit
from jacobian import Jacobian, JacobianFormatter
from power_flow import PowerFlow
from dcopf import DCOPF
from settings import Settings
from bus import Bus

def main():
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
    c1.calc_ybus()
    print("Ybus:\n")
    print(c1.ybus)

    mistmatch = c1.compute_power_mismatch()
    c1.power_mismatch_formatter(mistmatch)


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
    print("\nJacobian Matrix Dataframe:\n")
    formatter_j = JacobianFormatter(J)
    formatter_j.print_dataframe(decimals=2)

    pf = PowerFlow(c1, J, mode="power_flow")
    NR = pf.run_type(tol=0.001, max_iter=50)
    print("\nNR:\n")
    pf.print_NF_result(NR)

 # fault study starts here, outside the loop
    print("\n" + "=" * 50)
    print("FAULT STUDY")
    print("=" * 50)

    pf_fault = PowerFlow(c1, J, mode="fault")
    print(c1.calc_zbus())

    for fault_bus in c1.buses.keys():
        fault_result = pf_fault.run_type(fault_bus=fault_bus, vf=1.0)
        pf_fault.print_fault_results(fault_result)

main()


