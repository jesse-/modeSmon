#!/usr/bin/env python
# This is a really simple script to dump out decoded Mode S data and any associated ADS-B data.
# It expects to read a file in the format produced by receiver.c. You can pipe the output of receiver.c
# straight into this script if you give it - as the filename. E.g.
# >>$ receiver/receiver | python_tools/dump_adsb.py -

import fileinput
import modes


def main():
    for line in fileinput.input():
        reply = modes.ModeSReply.from_message(line)
        print("Timestamp (samples): {0}; ICAO No: {1}; Data: {2}; Type: {3}".format(reply.timestamp, reply.icao, reply.data, reply.decode()))
        if reply.message:
            print('\t', reply.message.describe())
            for key in reply.message.params:
                print('\t\t{0}: {1}'.format(key, reply.message.params[key]))
            

if __name__ == "__main__":
    main()
