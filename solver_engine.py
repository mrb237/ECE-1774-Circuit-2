from bus import Bus
from circuit import Circuit
from jacobian import Jacobian, JacobianFormatter
from power_flow import PowerFlow
from settings import SETTINGS
import numpy as np
import time


class SolverEngine:
    def __init__(self):
        self.circuit = None
        self.jacobian = None
        self.power_flow = None

        # Cache breaker state so we only re-solve when something changes
        self.last_breaker_state = {}

        self.build_default_circuit()
        self.solve_base_case()

        self.protection_timers = {}
        self.last_solve_converged = True

        self.breaker_number_map = {
            1: ["BR_G1"],
            2: ["BR_T1"],
            3: ["BR_TL1"],
            4: ["BR_T2"],
            5: ["BR_G2", "BR_L1"],
            6: ["BR_TL3"],
            7: ["BR_L2"],
            8: ["BR_TL2"],
        }

        self.breaker_gpio_map = {
            1: 4,
            2: 17,
            3: 27,
            4: 22,
            5: 23,
            6: 24,
            7: 25,
            8: 5  # Change
        }

    # ---------------------------------------------------------
    # BUILD DEFAULT CIRCUIT
    # ---------------------------------------------------------
    def build_default_circuit(self):
        Bus.index_counter = 0
        c = Circuit("5-Bus Runtime Circuit")

        # Buses
        c.add_bus("Bus1", 15.0, "Slack")
        c.add_bus("Bus2", 345.0, "PQ")
        c.add_bus("Bus3", 15.0, "PV")
        c.add_bus("Bus4", 345.0, "PQ")
        c.add_bus("Bus5", 345.0, "PQ")

        # Transformers
        c.add_transformer("T1", "Bus1", "Bus5", 0.0015, 0.02, 9999.0)
        c.add_transformer("T2", "Bus3", "Bus4", 0.00075, 0.01, 9999.0)

        # Transmission lines
        c.add_transmission_line("TL1", "Bus5", "Bus4", 0.00225, 0.025, 0.0, 0.44, 9999.0)
        c.add_transmission_line("TL2", "Bus5", "Bus2", 0.0045, 0.05, 0.0, 0.88, 9999.0)
        c.add_transmission_line("TL3", "Bus4", "Bus2", 0.009, 0.1, 0.0, 1.72, 9999.0)

        # Generators
        c.add_generator("G1", "Bus1", 1.00, 0.0)
        c.add_generator("G2", "Bus3", 1.05, 520.0)

        # Loads
        c.add_load("L1", "Bus3", 80.0, 40.0)
        c.add_load("L2", "Bus2", 800.0, 280.0)

        # Breakers
        c.add_breaker("BR_G1", "G1", "Bus1", True)
        c.add_breaker("BR_G2", "G2", "Bus3", True)

        c.add_breaker("BR_T1", "Bus1", "Bus5", True)
        c.add_breaker("BR_T2", "Bus3", "Bus4", True)

        c.add_breaker("BR_TL1", "Bus5", "Bus4", True)
        c.add_breaker("BR_TL2", "Bus5", "Bus2", True)
        c.add_breaker("BR_TL3", "Bus4", "Bus2", True)

        c.add_breaker("BR_L1", "L1", "Bus3", True)
        c.add_breaker("BR_L2", "L2", "Bus2", True)

        self.circuit = c
        self.refresh_objects()
        self.last_breaker_state = self.get_breaker_state()

    # ---------------------------------------------------------
    # REFRESH OBJECTS
    # ---------------------------------------------------------
    def refresh_objects(self):
        self.circuit.update_load_models()
        self.circuit.update_generator()
        self.circuit.calc_ybus()
        self.jacobian = Jacobian(self.circuit)
        self.power_flow = PowerFlow(self.circuit, self.jacobian)

    # ---------------------------------------------------------
    # BREAKER HELPERS
    # ---------------------------------------------------------
    def get_breaker_state(self):
        return {
            name: breaker.is_closed
            for name, breaker in self.circuit.breakers.items()
        }

    def breakers_changed(self):
        current = self.get_breaker_state()
        changed = current != self.last_breaker_state
        return changed

    def update_breaker_cache(self):
        self.last_breaker_state = self.get_breaker_state()

    def set_breaker(self, breaker_name: str, closed: bool):
        br = self.circuit.breakers[breaker_name]
        if closed:
            br.close()
        else:
            br.open()

    def set_breaker_number(self, breaker_num: int, closed: bool):
        if breaker_num not in self.breaker_number_map:
            raise KeyError(f"Breaker number {breaker_num} is not mapped.")

        for br_name in self.breaker_number_map[breaker_num]:
            if br_name not in self.circuit.breakers:
                raise KeyError(f"Software breaker '{br_name}' not found in circuit.")

            if closed:
                self.circuit.breakers[br_name].close()
            else:
                self.circuit.breakers[br_name].open()

        self.refresh_objects()

    def get_breaker_number_states(self):
        states = {}

        for breaker_num, br_list in self.breaker_number_map.items():
            all_closed = True
            for br_name in br_list:
                if br_name not in self.circuit.breakers:
                    all_closed = False
                    break
                if not self.circuit.breakers[br_name].is_closed:
                    all_closed = False
                    break

            states[breaker_num] = all_closed

        return states
    # ---------------------------------------------------------
    # SOLVING
    # ---------------------------------------------------------
    def solve(self, flat_start=False, print_diagnostics=True, title="Solve"):
        self.refresh_objects()
        result = self.power_flow.solve(flat_start=flat_start)

        # Explicitly write solved values back into the circuit
        for bus_name, data in result["bus_data"].items():
            self.circuit.buses[bus_name].vpu = data["vpu"]
            self.circuit.buses[bus_name].delta = data["delta"]

        self.refresh_objects()
        self.update_breaker_cache()

        if print_diagnostics:
            self.print_diagnostics(title)

        return result

    def solve_base_case(self):
        return self.solve(flat_start=True, print_diagnostics=True, title="Base Case")

    def resolve(self):
        if self.breakers_changed():
            print("\nBreaker state change detected. Re-solving...")
            return self.solve(flat_start=False, print_diagnostics=True, title="Recalculated Case")
        return None

    def startup(self):
        self.build_default_circuit()
        self.solve(flat_start=True, print_diagnostics=True, title="Base Case")

    def set_breaker_number(self, breaker_num: int, closed: bool):
        for br_name in self.breaker_number_map[breaker_num]:
            if closed:
                self.circuit.breakers[br_name].close()
            else:
                self.circuit.breakers[br_name].open()
        self.refresh_objects()

    def apply_gui_edits(self, g2_mw=None, l2_mw=None, l2_mvar=None):
        if g2_mw is not None and "G2" in self.circuit.generators:
            self.circuit.generators["G2"].mw_setpoint = g2_mw
        if l2_mw is not None and "L2" in self.circuit.loads:
            self.circuit.loads["L2"].mw = l2_mw
            self.circuit.loads["L2"].p = self.circuit.loads["L2"].calc_p()
        if l2_mvar is not None and "L2" in self.circuit.loads:
            self.circuit.loads["L2"].mvar = l2_mvar
            self.circuit.loads["L2"].q = self.circuit.loads["L2"].calc_q()
        self.refresh_objects()

    def solve_and_check_trips(self):
        self.solve(flat_start=False, print_diagnostics=True, title="System Solve")
        self.auto_trip_overloaded_breakers()
        self.solve(flat_start=False, print_diagnostics=True, title="Post-Trip Solve")

    def auto_trip_overloaded_breakers(self):
        flow_results_tl_tf, _ = self.power_flow.compute_power_flow_direction(SETTINGS)

        for element_name, data in flow_results_tl_tf.items():
            if element_name in self.circuit.transmission_lines:
                rating = self.circuit.transmission_lines[element_name].mva_limit
            elif element_name in self.circuit.transformers:
                rating = self.circuit.transformers[element_name].mva_limit
            else:
                continue

            if rating <= 0:
                continue

            p = data.get("P12_MW", 0.0)
            q = data.get("Q12_MVAR", 0.0)
            s = (p ** 2 + q ** 2) ** 0.5
            pct = 100.0 * s / rating

            if pct > 200.0:
                br_name = f"BR_{element_name}"
                if br_name in self.circuit.breakers and self.circuit.breakers[br_name].is_closed:
                    self.circuit.breakers[br_name].open()
                    print(f"Auto-tripped {br_name}: {pct:.1f}% of rating")

    def _get_overload_band(self, pct_loading: float):
        if 150.0 <= pct_loading < 200.0:
            return "band_150_200"
        elif 105.0 <= pct_loading < 150.0:
            return "band_105_150"
        elif 50.0 <= pct_loading < 95.0:
            return "band_50_95"
        return None

    def _get_band_delay_seconds(self, band: str):
        if band == "band_150_200":
            return 30.0
        elif band == "band_105_150":
            return 60.0
        elif band == "band_50_95":
            return 60.0
        return None

    def _trip_element_breaker(self, element_name: str):
        br_name = f"BR_{element_name}"
        if br_name in self.circuit.breakers and self.circuit.breakers[br_name].is_closed:
            self.circuit.breakers[br_name].open()
            print(f"Protection tripped {br_name}")
            self.refresh_objects()

    def _reset_protection_timer(self, element_name: str):
        if element_name in self.protection_timers:
            del self.protection_timers[element_name]

    def update_time_delayed_protection(self, converged: bool):
        now = time.time()

        flow_results_tl_tf, _ = self.power_flow.compute_power_flow_direction(SETTINGS)

        for element_name, data in flow_results_tl_tf.items():
            # Only protect lines and transformers
            if element_name in self.circuit.transmission_lines:
                rating = self.circuit.transmission_lines[element_name].mva_limit
            elif element_name in self.circuit.transformers:
                rating = self.circuit.transformers[element_name].mva_limit
            else:
                continue

            if rating is None or rating <= 0:
                self._reset_protection_timer(element_name)
                continue

            p = data.get("P12_MW", 0.0)
            q = data.get("Q12_MVAR", 0.0)
            s = (p ** 2 + q ** 2) ** 0.5
            pct_loading = 100.0 * s / rating

            band = self._get_overload_band(pct_loading)

            # Outside all bands -> reset
            if band is None:
                self._reset_protection_timer(element_name)
                continue

            # 50-95 band only matters when the solve diverges
            if band == "band_50_95" and converged:
                self._reset_protection_timer(element_name)
                continue

            # Start or continue timer
            if element_name not in self.protection_timers:
                self.protection_timers[element_name] = {
                    "band": band,
                    "start": now
                }
            else:
                # If the band changed, restart timer
                if self.protection_timers[element_name]["band"] != band:
                    self.protection_timers[element_name] = {
                        "band": band,
                        "start": now
                    }

            delay = self._get_band_delay_seconds(band)
            elapsed = now - self.protection_timers[element_name]["start"]

            if delay is not None and elapsed >= delay:
                print(
                    f"{element_name} exceeded protection band {band} "
                    f"for {elapsed:.1f}s at {pct_loading:.1f}% loading"
                )
                self._trip_element_breaker(element_name)
                self._reset_protection_timer(element_name)

    # ---------------------------------------------------------
    # PRINT DIAGNOSTICS
    # ---------------------------------------------------------
    def print_bus_data(self):
        print("\nBus Data:")
        for name, bus in self.circuit.buses.items():
            print(f"{name}: V = {bus.vpu:.6f} pu, delta = {bus.delta:.6f} deg, type = {bus.bus_type}")

    def print_ybus(self, decimals=4):
        print("\nYbus Matrix:")
        print(self.circuit.ybus.round(decimals))

    def print_mismatch(self, decimals=6):
        mismatch = self.circuit.compute_power_mismatch()

        print("\nPower Mismatch Vector:")
        print(np.round(mismatch, decimals))

        active_buses = self.circuit.get_active_bus_names()

        non_slack_buses = [
            bus for bus in self.circuit.buses.values()
            if bus.name in active_buses and bus.bus_type != "Slack"
        ]

        pq_buses = [
            bus for bus in self.circuit.buses.values()
            if bus.name in active_buses and bus.bus_type == "PQ"
        ]

        print("\nStructured Mismatch Output:")
        for i, bus in enumerate(non_slack_buses):
            print(f"ΔP at {bus.name}: {mismatch[i]:.{decimals}f}")

        q_start = len(non_slack_buses)
        for i, bus in enumerate(pq_buses):
            print(f"ΔQ at {bus.name}: {mismatch[q_start + i]:.{decimals}f}")

    def print_jacobian(self, decimals=4):
        self.refresh_objects()
        jacobian_matrix = self.jacobian.calc_jacobian()

        print("\nJacobian Matrix:")
        formatter = JacobianFormatter(self.jacobian)
        print(formatter.to_dataframe().round(decimals))

    def print_breaker_states(self):
        print("\nBreaker States:")
        for name, breaker in self.circuit.breakers.items():
            print(f"{name}: {'Closed' if breaker.is_closed else 'Open'}")

    def print_diagnostics(self, title="Diagnostics"):
        print(f"\n================ {title} ================")
        self.print_breaker_states()
        self.print_bus_data()
        self.print_ybus()
        self.print_mismatch()
        self.print_jacobian()

    # ---------------------------------------------------------
    # FLOW DIRECTION FOR LED MANAGER
    # ---------------------------------------------------------
    def _parse_direction(self, direction_str, from_bus, to_bus):
        if f"{from_bus} -> {to_bus}" in direction_str:
            return "forward"
        elif f"{to_bus} -> {from_bus}" in direction_str:
            return "reverse"
        return "forward"

    def get_led_flow_data(self):
        self.refresh_objects()

        flow_results_tl_tf, flow_results_g_l = self.power_flow.compute_power_flow_direction(SETTINGS)
        active_buses = self.circuit.get_active_bus_names()

        led_flow_data = {}

        # ---------------------------------------------------------
        # Transformers + transmission lines
        # ---------------------------------------------------------
        for element_name, data in flow_results_tl_tf.items():
            from_bus = data["from_bus"]
            to_bus = data["to_bus"]

            p_direction = self._parse_direction(data.get("direction", ""), from_bus, to_bus)
            q_direction = self._parse_direction(data.get("direction_q", ""), from_bus, to_bus)

            # Use actual computed MW / MVAR values
            p_magnitude = abs(data.get("P12_MW", 0.0))
            q_magnitude = abs(data.get("Q12_MVAR", 0.0))

            breaker_name = f"BR_{element_name}"
            connected = True
            if breaker_name in self.circuit.breakers:
                connected = self.circuit.breakers[breaker_name].is_closed

            energized = (from_bus in active_buses) and (to_bus in active_buses)

            rating = 1.0
            if element_name in self.circuit.transmission_lines:
                rating = self.circuit.transmission_lines[element_name].mva_limit
            elif element_name in self.circuit.transformers:
                rating = self.circuit.transformers[element_name].mva_limit

            led_flow_data[element_name] = {
                "type": data["type"],
                "from_bus": from_bus,
                "to_bus": to_bus,
                "p_direction": p_direction,
                "q_direction": q_direction,
                "p_magnitude": p_magnitude,
                "q_magnitude": q_magnitude,
                "rating": rating if rating > 0 else 1.0,
                "connected": connected,
                "energized": energized,
            }

        # ---------------------------------------------------------
        # Loads
        # ---------------------------------------------------------
        for load_name, load in self.circuit.loads.items():
            breaker_name = f"BR_{load_name}"
            connected = True
            if breaker_name in self.circuit.breakers:
                connected = self.circuit.breakers[breaker_name].is_closed

            bus_name = load.bus1_name
            energized = bus_name in active_buses

            load_data = flow_results_g_l.get(load_name, {})

            direction_str = load_data.get("direction", f"{bus_name} -> load")
            direction_q_str = load_data.get("direction_q", f"{bus_name} -> load")

            # Real power direction
            if "load ->" in direction_str or "load P ->" in direction_str:
                p_direction = "reverse"
            else:
                p_direction = "forward"

            # Reactive power direction
            if direction_q_str is None:
                q_direction = p_direction
            elif "load Q ->" in direction_q_str or "load ->" in direction_q_str:
                q_direction = "reverse"
            else:
                q_direction = "forward"

            p_magnitude = abs(load_data.get("P_delivered_MW", load.mw))
            q_magnitude = abs(load_data.get("Q_delivered_MVAR", load.mvar))
            rating = max(abs(load.mw), abs(load.mvar), 1.0)

            led_flow_data[load_name] = {
                "type": "Load",
                "from_bus": bus_name,
                "to_bus": "load",
                "p_direction": p_direction,
                "q_direction": q_direction,
                "p_magnitude": p_magnitude,
                "q_magnitude": q_magnitude,
                "rating": rating,
                "connected": connected,
                "energized": energized,
            }

        # ---------------------------------------------------------
        # Generators
        # ---------------------------------------------------------
        for gen_name, gen in self.circuit.generators.items():
            breaker_name = f"BR_{gen_name}"
            connected = True
            if breaker_name in self.circuit.breakers:
                connected = self.circuit.breakers[breaker_name].is_closed

            bus_name = gen.bus1_name
            energized = bus_name in active_buses

            # Generator assumed to inject toward the bus
            p_direction = "forward"
            q_direction = "forward"

            p_magnitude = abs(gen.mw_setpoint)
            # No explicit Q setpoint stored the same way, so use 0 unless you later calculate it
            q_magnitude = 0.0
            rating = max(abs(gen.mw_setpoint), 1.0)

            led_flow_data[gen_name] = {
                "type": "Generator",
                "from_bus": gen.name,
                "to_bus": bus_name,
                "p_direction": p_direction,
                "q_direction": q_direction,
                "p_magnitude": p_magnitude,
                "q_magnitude": q_magnitude,
                "rating": rating,
                "connected": connected,
                "energized": energized,
            }

        return led_flow_data

    def print_led_flow_summary(self):
        flow_data = self.get_led_flow_data()

        print("\nLED Flow Summary:")
        for name, data in flow_data.items():
            print(f"{name}:")
            print(f"  Type:       {data['type']}")
            print(f"  From Bus:   {data['from_bus']}")
            print(f"  To Bus:     {data['to_bus']}")
            print(f"  P Dir:      {data['p_direction']}")
            print(f"  Q Dir:      {data['q_direction']}")
            print(f"  Connected:  {data['connected']}")