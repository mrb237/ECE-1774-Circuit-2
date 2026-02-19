import pandas as pd

class TransmissionLine:
    def __init__(self, name, bus1_name: str, bus2_name: str, r: float, x: float, g: float, b: float):
        self.name = name
        self.bus1_name = bus1_name
        self.bus2_name = bus2_name
        self.r = r
        self.x = x
        self.g = g
        self.b = b

    def calc_yprim(self):
        Yseries = 1/(self.r+(1j*self.x))
        Yshunt = self.g + (1j*self.b)

        print(f"Yseries: {Yseries}") # Comment out later, print for testing
        print(f"Yshunt: {Yshunt}") # Comment out later, print for testing

        y_prim = [ [(Yseries + (Yshunt/2)), (-Yseries)], [(-Yseries), (Yseries + (Yshunt/2))]]

        row_labels = [self.bus1_name, self.bus2_name]
        col_labels = [self.bus1_name, self.bus1_name]

        y_prim_df = pd.DataFrame(y_prim, index=row_labels, columns=col_labels)

        return y_prim_df


if __name__ == "__main__":
    # line1 = TransmissionLine("line1", "bus1", "bus2", 0.02, 0.25, 0.0, 0.04)
    # print(line1.name, line1.bus1_name, line1.bus2_name, line1.r, line1.x, line1.g)

    line1 = TransmissionLine("Line 1", "Bus 1", "Bus 2",0.02, 0.25, 0.0, 0.04)
    # print(line1.Yseries, line1.Yshunt) # Done directly in calc_yprim()
    print(line1.calc_yprim())