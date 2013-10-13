#!/usr/bin/env python

import time

class Aircraft:
    """A class to hold data about a single aircraft including a log of past position/velocity/altitude data."""

    _icao = None
    _parameters = None
    _lastupdate = None

    def __init__(self, icao):
        self._icao = icao
        self._parameters = {}
        self._lastupdate = 0

    @classmethod
    def from_reply(cls, reply):
        inst = cls(icao=reply.icao)
        inst.push_modes_reply(reply)
        return inst

    def push_modes_reply(self, modes_reply):
        if modes_reply.icao != self._icao:
            raise ValueError('Message with ICAO No. 0x{0:x} is not from this aircraft (0x{1:x}).'.format(modes_reply.icao, self._icao))
        if modes_reply.message:
            for key in modes_reply.message.params:
                self._parameters[key] = modes_reply.message.params[key]    
        self._lastupdate = time.time()

    @property
    def icao(self):
        return self._icao

    @property
    def parameters(self):
        return self._parameters

    def dump_print(self, print_if_no_params=False):
        if print_if_no_params or len(self._parameters):
            print('ICAO: 0x{0:06X}'.format(self._icao))
            for key in self._parameters:
                print('\t{0}: {1}'.format(key, self._parameters[key]))
            print('')
