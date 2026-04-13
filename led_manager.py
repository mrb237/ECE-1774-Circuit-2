from rpi_ws281x import PixelStrip, Color


class LEDManager:
    def __init__(self, led_count=174, pin=18, brightness=120):
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

        self.element_map = {
            "G1": list(range(0, 6)),
            "T1": list(range(6, 12)),
            "TL1": list(range(12, 18)),
            "T2": list(range(18, 24)),
            "G2": list(range(24, 30)),
            "L1": list(range(30, 36)),
            "TL3": list(range(36, 42)),
            "L2": list(range(42, 48)),
            "TL2": list(range(48, 54)),
        }

        self.off_color = (0, 0, 0)
        self.real_base = (0, 255, 0)
        self.reactive_base = (0, 0, 255)
        self.step = 0

    def rgb_to_color(self, rgb):
        r, g, b = rgb
        return Color(int(r), int(g), int(b))

    def clear(self):
        for i in range(self.strip.numPixels()):
            self.strip.setPixelColor(i, self.rgb_to_color(self.off_color))

    def show(self):
        self.strip.show()

    def segment_off(self, indices):
        for led in indices:
            self.strip.setPixelColor(led, self.rgb_to_color(self.off_color))

    def reverse_if_needed(self, indices, direction):
        if direction == "reverse":
            return list(reversed(indices))
        return indices

    def scale_color(self, base_rgb, magnitude, rating):
        if rating is None or rating <= 0:
            frac = 0.0
        else:
            frac = min(max(abs(magnitude) / rating, 0.0), 1.0)

        if abs(magnitude) > 1e-6 and frac < 0.15:
            frac = 0.15

        r, g, b = base_rgb
        return (r * frac, g * frac, b * frac)

    def animate_sparse_dual_flow(
        self,
        indices,
        p_direction,
        q_direction,
        p_magnitude,
        q_magnitude,
        rating
    ):
        if not indices:
            return

        self.segment_off(indices)

        p_indices = self.reverse_if_needed(indices, p_direction)
        q_indices = self.reverse_if_needed(indices, q_direction)

        p_color = self.scale_color(self.real_base, p_magnitude, rating)
        q_color = self.scale_color(self.reactive_base, q_magnitude, rating)

        # real power
        for i, led in enumerate(p_indices):
            if abs(p_magnitude) > 1e-6 and (i + self.step) % 4 == 0:
                self.strip.setPixelColor(led, self.rgb_to_color(p_color))

        # reactive power
        for i, led in enumerate(q_indices):
            if abs(q_magnitude) > 1e-6 and (i + self.step) % 4 == 2:
                self.strip.setPixelColor(led, self.rgb_to_color(q_color))

    def update_from_flows(self, flow_data):
        self.clear()

        for element_name, data in flow_data.items():
            if element_name not in self.element_map:
                continue

            indices = self.element_map[element_name]

            connected = data.get("connected", True)
            energized = data.get("energized", True)

            # If breaker open or blacked out, whole connection stays off
            if not connected or not energized:
                self.segment_off(indices)
                continue

            self.animate_sparse_dual_flow(
                indices=indices,
                p_direction=data.get("p_direction", "forward"),
                q_direction=data.get("q_direction", "forward"),
                p_magnitude=data.get("p_magnitude", 0.0),
                q_magnitude=data.get("q_magnitude", 0.0),
                rating=data.get("rating", 1.0),
            )

        self.show()
        self.step = (self.step + 1) % 4