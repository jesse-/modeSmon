# Note: This is a copy of Tom's Gillham code decoder. The original repo (plus tests) is here:
# https://github.com/tomad/gillham
#
# Copyright (C) 2013 Thomas Daley
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see {http://www.gnu.org/licenses/}.

import warnings


def gillham(code):
    """
        Covert Gillham code to altitude

        Input is a integer representing the following binary code G:

            0  2  3  4  5  6  7  8  9  10 11 12
            D1 D2 D4 A1 A2 A4 B1 B2 B4 C1 C2 C4

        For valid input codes the output value is the altitude at the center
        point of the 100 ft interval defined by the input code (with the
        exception of -975 ft level where the interval is 50 ft).

        Invalid input codes raise a warning and return None.
    """

    bits = '{0:012b}'.format(code)

    if len(bits) != 12:
        raise TypeError('Expected 12 bit input word')

    d1 = bool(int(bits[0]))

    g_500 = gray2bin(bits[0:9])
    g_100 = gray2bin(bits[9:])

    valid_g_100 = (7, 4, 3, 2, 1) if g_500 > 0 else (3, 4, 7)

    if d1 or g_100 not in valid_g_100:
        warnings.warn(
            'Gillham code {0} is not valid {1} {2}'.format(
                bits,
                g_500,
                g_100
            )
        )
        return None

    g_100 = 5 if g_100 == 7 else g_100

    if g_500 % 2:
        g_100 = 6 - g_100

    g_100 = g_100 - 1
    g_100_scale = 100

    if g_500 == 0 and g_100 == 2:
            g_100 = 3
            g_100_scale = 75

    return ((g_500 * 500) + (g_100 * g_100_scale)) - 1200


def gray2bin(bitstring):
    gray = [int(i) for i in bitstring]

    bits = gray[0:1]

    for bit in gray[1:]:
        bits.append(bits[-1] ^ bit)

    return int('0b' + ''.join(map(str, bits)), base=2)


def dump_code():
    """
        Return an ordered list of all valid codes.

        In each element the first two values define the lower and upper bounds
        of the altitude interval represented by the binary code.
    """

    code = []

    for i in range(2 ** 12):
        bit_pattern = '{0:012b}'.format(i)

        with warnings.catch_warnings(record=True) as warns:
            g = int(bit_pattern, base=2)
            converted_alt = gillham(g)

        if warns:
            continue

        if g == 2:
            error = 25
        else:
            error = 50

        lower = converted_alt - error
        upper = converted_alt + error

        code.append((lower, upper, '0b{0}'.format(bit_pattern)))

    return sorted(code, key=lambda x: x[0])


def main():
    for lower, upper, converted_alt, bit_pattern in dump_code():
        print('{0:>10} to {1:>10} ({2}): {3}'.format(
            lower,
            upper,
            converted_alt,
            bit_pattern,
            width=40))


if __name__ == '__main__':
    main()
