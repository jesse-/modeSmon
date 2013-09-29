import unittest
from bitstring import Bits
from modes import ModeSReply, DownlinkFormat


class TestModeSReply(unittest.TestCase):

    def test_unpack_message_format(self):
        message = "00000000000001.00: 0xffffff, 0xffffffff;"
        expected = ("00000000000001.00", "0xffffff", "0xffffffff")
        self.assertTupleEqual(expected, ModeSReply().unpack(message))

    def test_parse_timestamp(self):
        stamp_text = "00000000506733.25"
        timestamp = ModeSReply.parse_timestamp(stamp_text)
        self.assertEqual(506733.25, timestamp)

    def test_parse_icao_number(self):
        icao_text = '0x111111'
        icao = ModeSReply.parse_icao(icao_text)
        self.assertEqual(Bits('0x111111'), icao)

    def test_parse_data(self):
        data_text = '0x00000000'
        data = ModeSReply.parse_data(data_text)
        self.assertEqual(Bits('0x00000000'), data)

    def test_instance_from_message(self):
        message = "00000000000001.00: 0xffffff, 0xffffffff;"
        reply = ModeSReply.from_message(message)
        self.assertEqual(1.00, reply.timestamp)
        self.assertEqual(Bits('0xffffff'), reply.icao)
        self.assertEqual(Bits('0xffffffff'), reply.data)

    def test_5bit_downlink_format(self):
        # formats 0 to 23
        data = Bits('0b00001') + Bits(length=(83 - 5))
        reply = ModeSReply(data=data)
        self.assertEqual(1, reply.format)

    def test_2bit_downlink_format(self):
        # format 24 when when the first two bits are '11'
        data = Bits('0b11') + Bits(length=(83 - 2))
        reply = ModeSReply(data=data)
        self.assertEqual(24, reply.format)

    def test_data_length(self):
        data = Bits(length=83)
        reply = ModeSReply(data=data)
        self.assertEqual(83, reply.length)


class TestDownlinkFormat(unittest.TestCase):

    def test_tokenise_downlink_format_string(self):
        link_format = 'CA:3 AA:24 ME:56 PI:24'
        expected_tokens = [
            ('CA', '3'),
            ('AA', '24'),
            ('ME', '56'),
            ('PI', '24')
        ]

        foo = DownlinkFormat()
        tokens = foo.tokenize_format(link_format)
        self.assertSequenceEqual(expected_tokens, tokens)

    def test_get_alternate_lengths(self):
        field_length = '27|83'

    def test_get_format(self):
        dlf = DownlinkFormat()
        link_format = dlf.get_format(5)
        import pdb; pdb.set_trace()

