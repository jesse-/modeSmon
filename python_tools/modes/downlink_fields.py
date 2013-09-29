class AltitudeCode(object):
    """
    3.1.2.6.5.4 AC: Altitude code.


     0   1   2   3   4   5 | 6|  7 | 8|  9  10  11  12
    20  21  22  23  24  25 |26| 27 |28| 29  30  31  32
                           | M|    | Q|
    C1  A1  C2  A2  C4  A4 | 0| B1 | 0| B2  D2  B4  D4  (M = 0, Q = 0)
    D11 D10 D9  D8  D7  D6 | 0| D5 | 1| D4  D3  D2  D1  (M = 0, Q = 1)
    D12 D11 D10 D9  D8  D7 | 1| D6  D5  D4  D3  D2  D1  (M = 1)


    """

    length = 13
    df_validity = (4, 20)
    unit = None

    def __init__(self, data):
        self.data = data
        self.unpack()

    def unpack(self):
        m, q = self.data.unpack('pad:6, bool, pad:1, bool, pad:4')
        self.unit = 'meters' if m else 'feet'

    @property
    def valid(self):
        self.data.all(0)



