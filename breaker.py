class Breaker:
    def __init__(self, name: str, node1_name: str = None, node2_name: str = None, is_closed: bool = True, rating: float = 0.0, element_type: str = None, element_name: str = None):
        self.name = name
        self.node1_name = node1_name
        self.node2_name = node2_name
        self.is_closed = is_closed
        self.rating = rating

        # Optional element-based support:
        # element_type can be "line", "transformer", "generator", or "load"
        self.element_type = element_type
        self.element_name = element_name

    def open(self):
        self.is_closed = False
        return self

    def close(self):
        self.is_closed = True
        return self

    def toggle(self):
        self.is_closed = not self.is_closed
        return self

    def controls_connection(self, node1_name: str, node2_name: str):
        if self.node1_name is None or self.node2_name is None:
            return False

        return (
            (self.node1_name == node1_name and self.node2_name == node2_name)
            or
            (self.node1_name == node2_name and self.node2_name == node1_name)
        )

    def controls_element(self, element_type: str, element_name: str):
        return self.element_type == element_type and self.element_name == element_name

    def __repr__(self):
        state = "Closed" if self.is_closed else "Open"

        if self.element_type is not None:
            return f"{self.name}: {self.element_type} {self.element_name} -> {state}"

        return f"{self.name}: {self.node1_name} - {self.node2_name} -> {state}"