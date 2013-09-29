
class FieldFormats(object):

    field_formats = {
        # 3.1.2.5.2.2.2, unique
        'AA': (':24', 'address announced', [11, 17, 18]),
        # 3.1.2.6.5.4
        'AC': (':13', 'altitude code', [4, 20]),
        # 3.1.2.8.8.2
        'AF': (':3', 'application field', [19]),
        # 3.1.2.3.2.1.3
        'AP': (':24', 'address/parity', [0, 4, 5, 16, 20, 21, 24]),
        # 3.1.2.8.1.1
        'AQ': (None, 'acquisition'),
        # 3.1.2.5.2.2.1
        'CA': (None, 'capability', [11, 17]),
        # 3.1.2.8.2.3
        'CC': (None, 'cross-link capability', [0]),
        # 3.1.2.8.2.3
        'CC': ({
            0: 'cannot support',
            1: 'supports'}
        , 'cross-link capability'),
        # 3.1.2.8.7.2
        'CF': (None, 'control field', [18]),
        # 3.1.2.5.2.1.3
        'CL': (None, 'code label'),
        # 3.1.2.3.2.1.2
        'DF': (None, 'downlink format'), # valid for all DL formats
        # 3.1.2.6.1.3
        'DI': (None, 'designator identification'),
        # 3.1.2.6.5.2
        'DR': (None, 'downlink request', [4, 5, 20, 21]),
        # 3.1.2.8.1.3
        'DS': (None, 'data selector'),
        # 3.1.2.6.5.1
        'FS': (None, 'flight status', [4, 5, 20, 21]),
        # 3.1.2.5.2.1.2
        'IC': (None, 'interrogator code'),
        # 3.1.2.6.7.1
        'ID': (None, 'identity', [5, 21]),
        # 3.1.2.7.3.1
        'KE': (None, 'control, ELM', [24]),
        # 3.1.2.6.2.1
        'MA': (None, 'message, Comm-A'),
        # 3.1.2.6.6.1
        'MB': (None, 'message, Comm-B', [20, 21]),
        # 3.1.2.7.1.3
        'MC': (None, 'message, Comm-C'),
        # 3.1.2.7.3.3
        'MD': (None, 'message, Comm-D', [24]),
        # 3.1.2.8.6.2
        'ME': (None, 'message, extended squitter', [17, 18]),
        # 4.3.8.4.2.3
        'MU': (None, 'message, ACAS'),
        # 3.1.2.8.3.1, 4.3.8.4.2.4
        'MV': (None, 'message, ACAS', [16]),
        # 3.1.2.7.1.2
        'NC': (None, 'number of C-segment'),
        # 3.1.2.7.3.2
        'ND': (None, 'number of D-segment', [24]),
        # 3.1.2.6.1.1
        'PC': (None, 'protocol'),
        # 3.1.2.3.2.1.4
        'PI': (None, 'parity/interrogator identifier', [11, 17, 18]),
        # 3.1.2.5.2.1.1
        'PR': (None, 'probability of reply'),
        # 3.1.2.7.1.1
        'RC': (None, 'reply control'),
        # 3.1.2.8.2.2
        'RI': (None, 'reply information', [0]),
        # 3.1.2.8.1.2
        'RL': (None, 'reply length'),
        # 3.1.2.6.1.2
        'RR': (None, 'reply request'),
        # 3.1.2.6.1.4
        'SD': (None, 'special designator'),
        # 4.3.8.4.2.5
        'SL': (None, 'sensitivity Level (ACAS)', [0, 16]),
        # 4.3.8.4.2.5
        'SL': ({
              0: 'ACAS inoperative',
              1: 'ACAS is operating at sensitivity level 1',
              2: 'ACAS is operating at sensitivity level 2',
              3: 'ACAS is operating at sensitivity level 3',
              4: 'ACAS is operating at sensitivity level 4',
              5: 'ACAS is operating at sensitivity level 5',
              6: 'ACAS is operating at sensitivity level 6',
              7: 'ACAS is operating at sensitivity level 7'}),
        # 3.1.2.3.2.1.1
        'UF': (None, 'uplink format'),
        # 3.1.2.6.5.3
        'UM': (None, 'utility message', [4, 5, 20, 21]),
        # 3.1.2.8.2.1
        'VS': ({
            0, 'aircraft is airborne',
            1, 'aircraft is on the ground'
            }, 'vertical status'), 
    }
