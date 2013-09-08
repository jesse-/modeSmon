#!/usr/bin/env python3

# This is a Python3 library for parsing ADS-B messages contained within Mode S
# extended squitters. The library is used by instantiating the Message class
# with the ME field of a Mode S squitter. The resulting object can be
# queried for the message type and content.
#
# Details of the ADS-B message format can be found in ICAO document
# 9871 -- 'Technical Provisions for Mode S Services and Extended Squitter'
# -- Appendix C.
#
# Copyright (C) 2013 Jesse Hamer
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


DEBUG = True

# The length of the mode S ME field in bits. This contains the ADS-B message.
ME_LENGTH_BITS = 56
# The length of the type field within the ADS-B message. This corresponds to the top (first) 5 bits of the message.
TYPE_LENGTH_BITS = 5

# ADS-B message type table
TYPE_TABLE = (
#   Type  | Format  | Description
    (0,    'NOPOS',   'No position information available. Barometric altitude may be available.'),
    (1,    'IDENT',   'Aircraft identifiaction and category (set D)'),
    (2,    'IDENT',   'Aircraft identifiaction and category (set C)'),
    (3,    'IDENT',   'Aircraft identifiaction and category (set B)'),
    (4,    'IDENT',   'Aircraft identifiaction and category (set A)'),
    (5,    'SPOS',    'Surface position message'),
    (6,    'SPOS',    'Surface position message'),
    (7,    'SPOS',    'Surface position message'),
    (8,    'SPOS',    'Surface position message'),
    (9,    'APOS',    'Airborne position plus barometric altitude'),
    (10,   'APOS',    'Airborne position plus barometric altitude'),
    (11,   'APOS',    'Airborne position plus barometric altitude'),
    (12,   'APOS',    'Airborne position plus barometric altitude'),
    (13,   'APOS',    'Airborne position plus barometric altitude'),
    (14,   'APOS',    'Airborne position plus barometric altitude'),
    (15,   'APOS',    'Airborne position plus barometric altitude'),
    (16,   'APOS',    'Airborne position plus barometric altitude'),
    (17,   'APOS',    'Airborne position plus barometric altitude'),
    (18,   'APOS',    'Airborne position plus barometric altitude'),
    (19,   'AVEL',    'Airborne velocity plus difference between barometric altitude and GNSS height'),
    (20,   'APOS',    'Airborne position plus GNSS height'),
    (21,   'APOS',    'Airborne position plus GNSS height'),
    (22,   'APOS',    'Airborne position plus GNSS height'),
    (23,   'TEST',    'Test message'),
    (24,   'SSTATUS', 'Surface system status'),
    (25,   'RESVD',   'Reserved'),
    (26,   'RESVD',   'Reserved'),
    (27,   'RESVD',   'Reserved'),
    (28,   'ASTATUS', 'Aircraft status message'),
    (29,   'TSTATUS', 'Target status message'),
    (30,   'RESVD',   'Reserved'),
    (31,   'AOSTATUS', 'Aircraft operational status')
)

# Character set used in identifiaction messages
IDENT_CHARSET = ( '','A','B','C','D','E','F','G','H','I','J','K','L','M','N','O',
                 'P','Q','R','S','T','U','V','W','X','Y','Z', '', '', '', '', '',
                 ' ', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '',
                 '0','1','2','3','4','5','6','7','8','9', '', '', '', '', '', ''
                )

# Emitter category (4 sets are defined)
CATEGORY_TABLE = {
    'A' : (None, 'Light (< 15500 lbs)', 'Small (15500 to 75000 lbs)', 'Large (75000 to 300000 lbs)', 'High Vortex Large (aircraft such as B-757)',
           'Heavy (> 300000 lbs)', 'High Performance (> 5g acceleration and 400 kts)', 'Rotorcraft'),

    'B' : (None, 'Glider / sailplane', 'Lighter-than-air', 'Parachutist / Skydiver', 'Ultralight / hang-glider / paraglider', None,
           'Unmanned Aerial Vehicle', 'Space / Trans-atmospheric vehicle'),

    'C' : (None, 'Surface Vehicle - Emergency Vehicle', 'Surface Vehicle', 'Point Obstacle (includes tethered balloons)',
           'Cluster Obstacle', 'Line Obstacle', None, None),

    'D' : (None, None, None, None, None, None, None, None)
}

# Emergency state table
EMERG_STATES = ('',
                'General emergency',
                'Lifeguard/Medical',
                'Minimum fuel',
                'No communications',
                'Unlawful interference',
                'Downed aircraft',
                ''
               )


def parse_ident(msg_type, message):
    """Parse an IDENT type message to get aircraft identification and class."""
    
    ret = {}
    
    if TYPE_TABLE[msg_type][1] != 'IDENT':
        raise ValueError('Message type {0} is not an IDENT type.'.format(msg_type))
    
    emitter_category = (message >> 48) & 0x07  # Emitter category is sent in the bottom 3 bits of the first byte sent.
    category_set = ('D','C','B','A')[msg_type-1]  # Message type 1 -> category set D, 2->C, 3->B, 4->A
    if emitter_category != 0:
        ret['Category'] = CATEGORY_TABLE[category_set][emitter_category]
    
    # The identifiaction string is encoded at 6 bits per character
    ident = ''
    for i in range(7, -1, -1):
        ident += IDENT_CHARSET[(message >> i*6) & 0x3f]
    ret['Identification'] = ident
    
    return ret


def parse_apos(msg_type, message):
    """Parse an airborne position message to extract position and altitude.
    
    The airborne position consists of CPR encoded (see C.2.6) latitude and
    longitude along with an altitude code. The NIC-B field and the message type
    indicate the positional accuracy. Surveillance status and time sync
    status are also carried in these messages.
    """
    
    ret = {}
    
    # Airborne position messages use register format 05.
    s_status = (message >> 49) & 0x03
    nic_b = (message >> 48) & 0x01
    alt_code = (message >> 36) & 0xfff
    time_sync = (message >> 35) & 0x01
    cpr_format = (message >> 34) & 0x01
    cpr_lat = (message >> 17) & 0x1ffff
    cpr_lon = message & 0x1ffff
    
    if msg_type >= 20 and msg_type <= 22:
        ret['Alt. Type'] = 'GNSS'
    elif msg_type >= 9 and msg_type <= 18:
        ret['Alt. Type'] = 'Barometric'
    else:
        raise ValueError('Message type {0} is not an airborne position type.'.format(msg_type))
    
    if s_status == 1:
        ret['Surveillance Status'] = 'Emergency'
    elif s_status == 2:
        ret['Surveillance Status'] = 'Temporary Alert (Changed Mode A Status)'
    elif s_status == 3:
        ret['Surveillance Status'] = 'Special Position Identification'
    
    if ret['Alt. Type'] == 'GNSS':
        ret['Altitude'] = 'GNSS code 0x{0:X}'.format(alt_code)  # Not sure how this is coded yet. I think it's some sort of BCD affair.
    else:
        ret['Altitude'] = None  # Need Tom's decoding function for this -- it's almost the same as the native Mode S code.
    
    ret['NIC Supplement-B'] = nic_b
    ret['Time Synchronized'] = True if time_sync else False
    ret['CPR Format'] = 'Odd' if cpr_format else 'Even'
    ret['CPR Latitude'] = cpr_lat
    ret['CPR Longitude'] = cpr_lon
    
    return ret


def parse_spos(msg_type, message):
    """Parse a surface position message to extract position and movement (speed & heading).
    
    This is a similar format to the airborne position message but it includes speed and heading
    information instead of altitude.
    """
    
    def dequantize(nlow, nhigh, xlow, xhigh, n):
        """Deal with the silly quantization used for surface movement reporting."""
        nsteps = nhigh - nlow + 1
        delta = (xhigh - xlow) / nsteps
        return xlow + (n - nlow + 1) * delta
    
    ret = {}
    
    if msg_type < 5 or msg_type > 8:
        raise ValueError('Message type {0} is not an airborne position type.'.format(msg_type))
    
    # Surface position messages use register format 06.
    movement = (message >> 44) & 0x7f
    heading_valid = (message >> 43) & 0x01
    heading = (message >> 36) & 0x7f
    # These fields are the same as the airborne message (although the CPR encoding is different)
    time_sync = (message >> 35) & 0x01
    cpr_format = (message >> 34) & 0x01
    cpr_lat = (message >> 17) & 0x1ffff
    cpr_lon = message & 0x1ffff
    
    # This isn't pretty. It implements table C-3.
    if movement == 1:
        ret['Movement'] = 'Stopped'
    elif movement == 2:
        ret['Movement'] = '<= 0.125kt'
    elif movement >= 3 and movement <= 8:
        ret['Movement'] = '{0}kt'.format(dequantize(3, 8, 0.125, 1.0, movement))
    elif movement >= 9 and movement <= 12:
        ret['Movement'] = '{0}kt'.format(dequantize(9, 12, 1.0, 2.0, movement))
    elif movement >= 13 and movement <= 38:
        ret['Movement'] = '{0}kt'.format(dequantize(13, 38, 2.0, 15.0, movement))
    elif movement >= 39 and movement <= 93:
        ret['Movement'] = '{0}kt'.format(dequantize(39, 93, 15.0, 70.0, movement))
    elif movement >= 94 and movement <= 108:
        ret['Movement'] = '{0}kt'.format(dequantize(94, 108, 70.0, 100.0, movement))
    elif movement >= 109 and movement <= 123:
        ret['Movement'] = '{0}kt'.format(dequantize(109, 123, 100.0, 175.0, movement))
    elif movement == 124:
        ret['Movement'] = '> 175kt'
    elif movement == 125:
        ret['Movement'] = 'Decelerating'
    elif movement == 126:
        ret['Movement'] = 'Accelerating'
    elif movement == 127:
        ret['Movement'] = 'Reversing'
    
    if heading_valid:
        ret['Heading'] = 360.0 * (heading / (2 ** 7))
    
    ret['Time Synchronized'] = True if time_sync else False
    ret['CPR Format'] = 'Odd' if cpr_format else 'Even'
    ret['CPR Latitude'] = cpr_lat
    ret['CPR Longitude'] = cpr_lon
    
    return ret


def parse_avel(msg_type, message):
    """Parse an airborne velocity message to extract speed, direction and vertical rate.
    
    Subtypes 1 and 2 contain velocity over ground and vertical rate. Subtypes 3 and 4 contain
    heading and airspeed. All subtypes optinally contain the geometric difference between GNSS
    and barometric altitude.
    """
    
    ret = {}
    
    if msg_type != 19:
        raise ValueError('Message type {0} is not an airborne velocity type.'.format(msg_type))
    
    subtype = (message >> 48) & 0x07
    intent_change = (message >> 47) & 0x01
    nac_v = (message >> 43) & 0x07
    vert_rate_type = (message >> 20) & 0x01
    vert_rate_sign = (message >> 19) & 0x01
    vert_rate = (message >> 10) & 0x1ff
    height_diff_sign = (message >> 7) & 0x01
    height_diff = message & 0x7f
    
    ret['Intent Change'] = True if intent_change else False
    
    if nac_v == 1:
        ret['Horiz. Velocity Error (m/s)'] = 10.0
    elif nac_v == 2:
        ret['Horiz. Velocity Error (m/s)'] = 3.0
    elif nac_v == 3:
        ret['Horiz. Velocity Error (m/s)'] = 1.0
    elif nac_v == 4:
        ret['Horiz. Velocity Error (m/s)'] = 0.3
    
    if vert_rate > 0 and vert_rate < 511:
        vert_rate = (vert_rate - 1) * 64.0
        ret['Vertical Rate (ft/min)'] = -vert_rate if vert_rate_sign else vert_rate
        ret['Vertical Rate Source'] = 'Baro' if vert_rate_type else 'GNSS'
    
    if height_diff > 0 and height_diff < 127:
        height_diff = (height_diff - 1) * 25.0
        ret['GNSS Alt. - Baro Alt. (ft)'] = -height_diff if height_diff_sign else height_diff
    
    # Speed multiplier
    if subtype == 2 or subtype == 4:  # Supersonic
        mult = 4.0
    else:  # Subsonic
        mult = 1.0
    
    if subtype == 1 or subtype == 2:
        # We have N-S and E-W velocity
        ew_sign = (message >> 42) & 0x01
        vel_ew = (message >> 32) & 0x3ff
        ns_sign = (message >> 31) & 0x01
        vel_ns = (message >> 21) & 0x3ff
        if vel_ew > 0 and vel_ew < 1023 and vel_ns > 0 and vel_ns < 1023:
            ret['Velocity East (kt)'] = -(vel_ew - 1) * mult if ew_sign else (vel_ew - 1) * mult
            ret['Velocity North (kt)'] = -(vel_ns - 1) * mult if ns_sign else (vel_ns - 1) * mult
    elif subtype == 3 or subtype == 4:
        # We have airspeed and heading
        heading_valid = (message >> 42) & 0x01
        heading = (message >> 32) & 0x3ff
        airspeed_type = (message >> 31) & 0x01
        airspeed = (message >> 21) & 0x3ff
        if heading_valid:
            ret['Heading'] = heading * 360.0 / 1024.0
        ret['Airspeed Type'] = 'TAS' if airspeed_type else 'IAS'
        if airspeed > 0 and airspeed < 1023:
            ret['Airspeed'] = (airspeed - 1) * mult
    else:
        return {}  # If the subtype is unrecognized then we shouldn't return anything.
    
    return ret


def parse_astatus(msg_type, message):
    """Parse an aircraft status message to get the Mode A code and emergency status."""
    
    ret = {}
    
    if msg_type != 28:
        raise ValueError('Message type {0} is not an aircraft status type.'.format(msg_type))
    
    subtype = (message >> 48) & 0x07
    
    if subtype == 1:
        # Emergency/priority status and Mode A code
        emerg_state = (message >> 45) & 0x07
        mode_a = (message >> 32) & 0x1fff
        if emerg_state:
            ret['Emergency'] = EMERG_STATES[emerg_state]
        ret['Mode A Code'] = mode_a
    elif subtype == 2:
        # 1090ES TCAS RA Broadcast
        # Looks like this is more of a mode S thing. I'll have to speak to Tom before implementing it.
        pass
    else:
        return {}  # If the subtype is unrecognized then we shouldn't return anything.
    
    return ret


def parse_aostatus(msg_type, message):
    """Parse an aircraft operational status message to retrieve a variety of capability codes."""
    
    ret = {}
    
    if msg_type != 31:
        raise ValueError('Message type {0} is not an aircraft operational status type.'.format(msg_type))
    
    subtype = (message >> 48) & 0x07
    version = (message >> 13) & 0x07
    nic_a = (message >> 12) & 0x01
    nac_p = (message >> 8) & 0x0f
    sil = (message >> 4) & 0x03
    hrd = (message >> 2) & 0x01
    sil_sup = (message >> 1) & 0x01
    
    if subtype == 0:
        aircapclass = (message >> 32) & 0xffff
        airopmode = (message >> 16) & 0xffff
        gva = (message >> 6) & 0x03
        nic_baro = (message >> 3) & 0x01
    elif subtype == 1:
        surcapclass = (message >> 36) & 0x0fff
        lenw = (message >> 32) & 0x0f
        suropmode = (message >> 16) & 0xffff
        trkhd = (message >> 3) & 0x01
    else:
        return {}  # If the subtype is unrecognized then we shouldn't return anything.
    
    return ret


class Message:
    """A class to hold the data conveyed by an ADS-B message
    
    The instantiated object contains two data members: type and params. The latter is
    a dictionary of field names and values. The fields present will depend on the value
    of type. type is an integer between 0 and 31 corresponding to the ADS-B type field.
    """
    
    def __init__(self, ME):
        """Initialise the instance from the 56 bit ME field of a mode S extended squitter."""
        self.ME = int(ME)
        if self.ME > ((1 << ME_LENGTH_BITS) - 1):
            raise ValueError('ME field of value {0} exceeds {1} bits.'.format(self.ME, ME_LENGTH_BITS))
        
        self.type = self.ME >> (ME_LENGTH_BITS - TYPE_LENGTH_BITS)  # Extract the type code from the msbs
        
        if TYPE_TABLE[self.type][1] == 'APOS':
            self.params = parse_apos(self.type, self.ME)
        elif TYPE_TABLE[self.type][1] == 'AVEL':
            self.params = parse_avel(self.type, self.ME)
        elif TYPE_TABLE[self.type][1] == 'ASTATUS':
            self.params = parse_astatus(self.type, self.ME)
        elif TYPE_TABLE[self.type][1] == 'IDENT':
            self.params = parse_ident(self.type, self.ME)
        elif TYPE_TABLE[self.type][1] == 'SPOS':
            self.params = parse_spos(self.type, self.ME)
        else:
            self.params = {}
            if DEBUG:
                print('Note: No parser for messsage type {0} ({1}).'.format(self.type, TYPE_TABLE[self.type][2]))
    
    def describe(self):
        return TYPE_TABLE[self.type][2]
    
    def params_dict(self):
        return self.params


if __name__ == '__main__':
    es = int(input('Enter an extended squitter message block in hex (omit the CRC): '), 16)
    m = Message(es & 0xffffffffffffff)
    print(m.describe(), end=':\n')
    params = m.params_dict()
    for key in params.keys():
        print('    {0}: {1}'.format(key, params[key]))
