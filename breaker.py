class Breaker:
    def __init__(self, name: str, element_type: str, element_name: str, status: bool = True):
        """
        element_type: 'line', 'transformer', 'generator', 'load'
        element_name: name of the element this breaker controls
        status: True = closed, False = open
        """
        self.name = name
        self.element_type = element_type
        self.element_name = element_name
        self.status = status

    def open(self):
        self.status = False

    def close(self):
        self.status = True

    def is_closed(self):
        return self.status

    def __repr__(self):
        state = "Closed" if self.status else "Open"
        return f"{self.name} ({self.element_type}:{self.element_name}) -> {state}"