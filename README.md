modeSmon
========

Tools for decoding Mode S transmissions from aircraft. Very much a work in progress!

The idea is that one or more SDR receivers will decode and timestamp Mode S squitters and pass the data back to a central server. Some Python code on the server will decode the ADS-B messages within the extended squitters and keep track of all the aircraft that it hears from. It is hoped that we will additionally be able to use the timestamps to perform multilateration where there is more than one receiver. This would allow tracking of any transmitting aircraft even when they are not transmitting their position.


Software-Defined Receiver (receiver/receiver.c)
-----------------------------------------------

This is a software-defined receiver for Mode S squitters. It uses the rtl-sdr library in conjunction with a suitable USB dongle. It outputs timestamps, aircraft IDs and message content (raw hex) to the standard output. There is no higher-level decoding of the messages beyond error detection and correction. Such parsing is better done in a high level language such as Python.

### Building the receiver program on a MacBook Pro ###

I suppose a makefile would be nice, but here is the current procedure:

    gcc -I/opt/local/include -L/opt/local/lib -Wall -O3 receiver.c -lrtlsdr -pthread -march=corei7-avx \
        -S -funsafe-math-optimizations -ftree-vectorizer-verbose=0
    clang -L/opt/local/lib -Wall receiver.s -o receiver -lrtlsdr -pthread

The intermediate assembly step is needed because the assembler in Macports doesn't understand the Intel AVX instructions. It can be skipped if you are not using Mac OS.

### Compiling natively on a BeagleBone Black ###

    gcc -Wall -O3 -mfloat-abi=softfp -mfpu=neon -funsafe-math-optimizations -ftree-vectorizer-verbose=0 \
    receiver.c -lrtlsdr -pthread -lm


Python Libraries (under python_tools)
-------------------------------------

These are still under construction. There will be libraries for parsing Mode S squitters and ADS-B messages contained within them. There will also be a tracking library defining aircraft objects and interpolation functions.
