import re
import bitstring
import adsblib


class DownlinkFormat(object):

    SHORT_DATA = 27
    LONG_DATA = 83

    parity_fields = ('AP', 'PI', 'P')

    downlink_formats = {
        0: ('DF:5 VS:1 CC:1 _:1 SL:3 _:2 RI:4 _:2 AC:13 AP:24',
            'Short air-air surveillance (ACAS)'),
        1: ('DF:5 _:27|83 P:24', 'Reserved'),
        2: ('DF:5 _:27|83 P:24', 'Reserved'),
        3: ('DF:5 _:27|83 P:24', 'Reserved'),
        4: ('DF:5 FS:3 DR:5 UM:6 AC:13 AP:24', 'Surveillance, altitude reply'),
        5: ('DF:5 FS:3 DR:5 UM:6 ID:13 AP:24', 'Surveillance, identify reply'),
        6: ('DF:5 _:27|83 P:24', 'Reserved'),
        7: ('DF:5 _:27|83 P:24', 'Reserved'),
        8: ('DF:5 _:27|83 P:24', 'Reserved'),
        9: ('DF:5 _:27|83 P:24', 'Reserved'),
        10: ('DF:5 _:27|83 P:24', 'Reserved'),
        11: ('DF:5 CA:3 AA:24 PI:24', 'All-call reply'),
        12: ('DF:5 _:27|83 P:24', 'Reserved'),
        13: ('DF:5 _:27|83 P:24', 'Reserved'),
        14: ('DF:5 _:27|83 P:24', 'Reserved'),
        15: ('DF:5 _:27|83 P:24', 'Reserved'),
        16: ('DF:5 VS:1 _:2 SL:3 _:2 RI:4 _:2 AC:13 MV:56 AP:24',
             'Long air-air surveillance (ACAS)'),
        17: ('DF:5 CA:3 AA:24 ME:56 PI:24', 'Extended squitter'),
        18: ('DF:5 CF:3 AA:24 ME:56 PI:24', 'Extended squitter/non transponder'),
        19: ('DF:5 AF:3 _:104', 'Military extended squitter'),
        20: ('DF:5 FS:3 DR:5 UM:6 AC:13 MB:56 AP:24', 'Comm-B, altitude reply'),
        21: ('DF:5 FS:3 DR:5 UM:6 ID:13 MB:56 AP:24', 'Comm-B, identify reply'),
        22: ('DF:5 _:27|83 P:24', 'Reserved for military use'),
        23: ('DF:5 _:27|83 P:24', 'Reserved'),
        24: ('DF:2 _:1 KE:1 ND:4 MD:80 AP:24', 'Comm-D (ELM)'),
    }

    def tokenize_format(self, format_text):
        return [tuple(o.split(':')) for o in format_text.split(' ')]

    def strip_parity(self, tokens):
        return [o for o in tokens if o[0] not in self.parity_fields]

    def get_format(self, format_id):
        downlink_format = self.downlink_formats[format_id]
        format_text, _ = downlink_format
        tokens = self.tokenize_format(format_text)
        return self.strip_parity(tokens)

    def binary_unpack(self, format_id, short=True):
        tokens = self.get_format(format_id)
        return ', '.join(["bin:" + str(self.field_length(y, short)) for (x, y) in tokens])

    def field_length(self, length, short):
        first, separator, second = length.partition('|')
        if separator:
            if short:
                return first
            else:
                return second
        else:
            return first

    def format_length(self, format_id, short=True):
        tokens = self.get_format(format_id)
        return sum(int(self.field_length(y, short)) for (x, y) in tokens)

    def format_verbose(self, format_id):
        return self.downlink_formats[format_id][1]


class ModeSReply(object):

    timestamp = None
    icao = None
    data = None
    message = None

    def __init__(self, timestamp=None, icao=None, data=None):
        self.timestamp = timestamp
        self.icao = icao
        self.data = data

        dlf = DownlinkFormat()
        link_format = dlf.get_format(self.format)
        if link_format[-1] == ('ME', '56'):
            self.message = adsblib.Message(self.data[-56:].uint)
        else:
            self.message = None

    @classmethod
    def from_message(cls, message):
        timestamp, icao, data = cls.unpack(message)
        timestamp = cls.parse_timestamp(timestamp)
        icao = cls.parse_icao(icao)
        data = cls.parse_data(data)
        return cls(
            timestamp=timestamp,
            icao=icao,
            data=data
        )

    @staticmethod
    def unpack(message):
        msg_format = re.compile('^(.*): (.*), (.*);$')
        match = msg_format.match(message)
        return match.groups() if match else None

    @staticmethod
    def parse_timestamp(text):
        return float(text)

    @staticmethod
    def parse_icao(text):
        icao = bitstring.Bits(hex=text)
        assert icao.len == 24
        return icao

    @staticmethod
    def parse_data(text):
        return bitstring.Bits(hex=text)

    @property
    def length(self):
        return self.data.length

    @property
    def format(self):
        fmt = self.data[0:5]
        return 24 if fmt[0:2].all(1) else fmt.uint

    def decode(self, print_format=False):
        dlf = DownlinkFormat()
        link_format = dlf.get_format(self.format)
        if print_format:
            print(link_format)
        return dlf.format_verbose(self.format)
