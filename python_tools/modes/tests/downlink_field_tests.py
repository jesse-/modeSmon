import unittest
import bitstring
from modes.downlink_fields import AltitudeCode


class TestAltitudeCode(unittest.TestCase):

    def test_altitude_reported_in_meters_when_m_bit_1(self):
        ac_data = bitstring.Bits('0b0000001000000')
        ac_field = AltitudeCode(ac_data)
        self.assertEqual(ac_field.unit, 'meters')

    def test_altitude_reported_in_feet_when_m_bit_0(self):
        ac_data = bitstring.Bits('0b1111110111111')
        ac_field = AltitudeCode(ac_data)
        self.assertEqual(ac_field.unit, 'feet')

    def test_altitude_invalid_not_known(self):
        ac_data = bitstring.Bits('0b0000000000000')
        ac_field = AltitudeCode(ac_data)
        self.assertFalse(ac_field.valid)

    def test_altitude_in_100_foot_increments(self):
        ac_data = bitstring.Bits('0b0000000000000')
        ac_field = AltitudeCode(ac_data)
        self.assertFalse(ac_field.valid)
