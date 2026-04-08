from rpi_ws281x import PixelStrip, Color


class LEDManager:
    def __init__(self, led_count=174, pin=18, brightness=15):
        self.strip = PixelStrip(
            led_count,
            pin,
            800000,
            10,
            False,
            brightness,
            0
        )
        self.strip.begin()

        # CHANGE VALUES BASED OFF MAPPING
        self.element_map = {
            "T1": list(range(0, 10)),
            "TL1": list(range(10, 20)),
            "TL2": list(range(20, 30)),
            "TL3": list(range(30, 40)),
            "T2": list(range(40, 50)),
            "G1": list(range(50, 60)),
            "G2": list(range(60, 70)),
            "L1": list(range(70, 80)),
            "L2": list(range(80, 90))
        }

        self.real_color = Color(0, 255, 0)      # green
        self.reactive_color = Color(0, 0, 255)  # blue
        self.off_color = Color(0, 0, 0)

        self.step = 0

    # ---------------------------------------------------------
    # BASIC HELPERS
    # ---------------------------------------------------------
    def clear(self):
        for i in range(self.strip.numPixels()):
            self.strip.setPixelColor(i, self.off_color)

    def show(self):
        self.strip.show()

    def reverse_flow(self, indices, direction):
        if direction == "reverse":
            return list(reversed(indices))
        return indices

    # ---------------------------------------------------------
    # SPARSE TWO-COLOR FLOW ANIMATION
    # ---------------------------------------------------------
    def animate_flow(self, indices, p_direction, q_direction):
        if not indices:
            return

        # Turn this segment off first
        for led in indices:
            self.strip.setPixelColor(led, self.off_color)

        p_indices = self.reverse_flow(indices, p_direction)
        q_indices = self.reverse_flow(indices, q_direction)

        # Real power sparse moving pattern
        for local_idx, led in enumerate(p_indices):
            if (local_idx + self.step) % 4 == 0:
                self.strip.setPixelColor(led, self.real_color)

        # Reactive power sparse moving pattern
        for local_idx, led in enumerate(q_indices):
            if (local_idx + self.step) % 4 == 2:
                self.strip.setPixelColor(led, self.reactive_color)

    # ---------------------------------------------------------
    # MAIN UPDATE
    # ---------------------------------------------------------
    def update_from_flows(self, flow_results_tl_tf):
        self.clear()

        for element_name, data in flow_results_tl_tf.items():
            if element_name not in self.element_map:
                continue

            if not data.get("connected", True):
                continue

            indices = self.element_map[element_name]
            p_direction = data.get("p_direction", "forward")
            q_direction = data.get("q_direction", "forward")

            self.animate_flow(indices, p_direction, q_direction)

        self.show()
        self.step = (self.step + 1) % 4