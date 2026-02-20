import numpy as np
import pandas
import pandas as pd

class Transformer:
    def __init__(self, name: str, bus1_name: str, bus2_name, r: float, x: float):
        self.name = name
        self.bus1_name = bus1_name
        self.bus2_name = bus2_name
        self.r = r
        self.x = x

        #Storing admittance as an attribute
        self.Yseries = 1 / (self.r + self.x * 1j)
    #Method
    def calc_yprim(self):

        colm_index = [self.bus1_name, self.bus2_name]
        row_index = [self.bus1_name, self.bus2_name]

        Yprim = pandas.DataFrame ([[self.Yseries, -self.Yseries],[-self.Yseries, self.Yseries]],
                                  columns=[colm_index], index= [row_index])
        return Yprim


if __name__ == "__main__":
    t1 = Transformer("t1", "bus1","bus2", 0.01, 0.10)
    print(t1.Yseries)
    print(t1.calc_yprim())
