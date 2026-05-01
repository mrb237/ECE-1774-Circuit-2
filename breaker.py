class Breaker:
    def __init__(self, name: str, element_type: str = None, element_name: str = None, bus1: str = None, bus2: str = None, status: bool = True):
        self.name = name
        self.element_type = element_type
        self.element_name = element_name
        self.bus1 = bus1
        self.bus2 = bus2
        self.status = status

    def is_closed(self):
        return self.status

    def open(self):
        self.status = False

    def close(self):
        self.status = True

    def __repr__(self):
        state = "Closed" if self.status else "Open"
        return f"{self.name} -> {state}"