import pandas as pd


class Transformer:
    def __init__(self, name: str, bus1_name: str, bus2_name: str, r: float, x: float, mva_limit: float = 1000.0):
        self.name = name
        self.bus1_name = bus1_name
        self.bus2_name = bus2_name
        self.r = r
        self.x = x
        self.tf_mva_limit = mva_limit

        self.Yseries = 1 / (self.r + self.x * 1j)

    def calc_yprim(self):
        col_index = [self.bus1_name, self.bus2_name]
        row_index = [self.bus1_name, self.bus2_name]

        Yprim = pd.DataFrame(
            [
                [self.Yseries, -self.Yseries],
                [-self.Yseries, self.Yseries]
            ],
            columns=col_index,
            index=row_index
        )

        return Yprim


if __name__ == "__main__":
    t1 = Transformer("T1", "Bus1", "Bus2", 0.01, 0.10)
    print(t1.Yseries)
    print(t1.calc_yprim())