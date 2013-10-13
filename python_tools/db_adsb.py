#!/usr/bin/env python
# This is very similar to dump_adsb.py except that it builds a dictionary of aircraft objects to contain the data.
# The parameters collected by each aircraft object are printed out at EOF rather than there being a continuous
# stream of messages.
# The script expects to read a file in the format produced by receiver.c. You can pipe the output of receiver.c
# straight into this script if you give it - as the filename. E.g.
# >>$ receiver/receiver | python_tools/db_adsb.py -

import fileinput
import modes
import aircraft

aircraft_db = {}

def main():
    for line in fileinput.input():
        reply = modes.ModeSReply.from_message(line)
        if reply.icao not in aircraft_db:
            aircraft_db[reply.icao] = aircraft.Aircraft.from_reply(reply)
        else:
            aircraft_db[reply.icao].push_modes_reply(reply)

    for icao in aircraft_db:
        aircraft_db[icao].dump_print(True)


if __name__ == "__main__":
    main()
