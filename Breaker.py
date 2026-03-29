import pandas as pd

class Breaker:
    def __init__(self, name: str, node1_name: str, node2_name: str, is_closed: bool = True, rating: float = 0.0):
        self.name = name
        self.node1_name = node1_name
        self.node2_name = node2_name
        self.is_closed = is_closed
        self.rating = rating

    def open(self):
        self.is_closed = False
        return self

    def close(self):
        self.is_closed = True
        return self

    def toggle(self):
        self.is_closed = not self.is_closed
        return self