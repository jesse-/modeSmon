modeSmon
========

Tools for decoding Mode S transmissions from aircraft. Very much a work in progress!

receiver (receiver.c)
---------------------

This is a software-defined receiver for the Mode S messages. It uses the rtl-sdr library in conjunction with a suitable USB dongle. It outputs timestamps, aircraft IDs and message content (raw hex) to the standard output. There is no higher-level decoding of the messages beyond error detection and correction. Such parsing is better done in a high level language; I will probably use Python.

### Building the receiver program on a MacBook Pro ###

I suppose a makefile would be nice, but here is the current procedure:

    gcc -I/opt/local/include -L/opt/local/lib -Wall -O3 receiver.c -lrtlsdr -pthread -march=corei7-avx \
        -S -funsafe-math-optimizations -ftree-vectorizer-verbose=0
    clang -L/opt/local/lib -Wall receiver.s -o receiver -lrtlsdr -pthread

The intermediate assembly step is needed because the assembler in Macports doesn't understand the Intel AVX instructions.

### Compiling natively on a BeagleBone Black ###

    gcc -Wall -O3 -mfloat-abi=softfp -mfpu=neon -funsafe-math-optimizations -ftree-vectorizer-verbose=0 \
    receiver.c -lrtlsdr -pthread -lm

