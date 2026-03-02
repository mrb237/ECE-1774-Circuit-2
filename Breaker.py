import pandas as pd

class Breaker:
    def __init__(self, name, node1_name: str, node2_name: str, state: bool, rating: float):
        self.name = name
        self.node1_name = node1_name
        self.node2_name = node2_name
        self.isOpen = state
        self.rating = rating


    def open(self):
        self.isOpen = False
        return self

    def close(self):
        self.isOpen = True
        return self

    def toggle(self):
        self.isOpen = not self.isOpen
        return self

    def isOpen(self):
        return self.isOpen
