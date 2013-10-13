/*
 * receiver.c
 * A software-defined receiver for Mode S squitters which are transmitted by suitably equipped aircraft.
 *
 * The Mode S standard is defined in Annex 10, Volume IV to the Convention on International Civil Aviation.
 *
 * This program uses the rtl-sdr library {http://sdr.osmocom.org/trac/wiki/rtl-sdr} in conjunction with a compatible USB dongle to receive
 * the Mode S messages on 1090MHz. The messages are demodulated and CRC checking is performed. The program can correct single bit errors
 * using the CRC. The decoded messages are sent to the standard output, accompanied by a timestamp and the ICAO aircraft address.
 *
 *
 * Copyright (C) 2013 Jesse Hamer
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see {http://www.gnu.org/licenses/}.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <pthread.h>
#include <math.h>
#include <float.h>
#include <inttypes.h>

#include <rtl-sdr.h>


/* Parameters and Constants =========================================================================================================================== */

// Fractional delay filter configuration
#define FILTER_LEN 32  // This is expected to be a power of 2.
#define N_FILTERS 4    // The number of interpolated sample points per sample period (the number of filters)

/*
 * Sample buffer configuration
 * PROCESS_BLOCK_SIZE is the number of samples processed at a time which is equal to the number of samples passed by the rtlsdr library at
 * each callback. Each sample is 2 bytes (1 I, 1 Q). PROCESS_BLOCK_SIZE must be a multiple of 256 so that the rtlsdr library's buffers are
 * a multiple of 512 in length.
 */
#define PROCESS_BLOCK_SIZE (256 * 1024)

// Maximum number of known ICAO numbers to store
#define ICAO_LIST_SIZE 256
#define ICAO_N_BITS 24  // Number of bits in the ICAO address
// The fast list is a big bitfield with 1 bit for each possible address.
#define ICAO_FAST_LIST_SIZE ((1 << ICAO_N_BITS) / 32)  // Array of uint32_t so 32 aircraft per address

// detect_thresh is the correlation peak threshold required for a decoding attempt. A threshold of zero means that the total energy
// in the spaces is equal to the total energy in the marks -- quite a bad SNR.
const float detect_thresh = 0.0;

// Debug enable (currently just on or off)
const int debug = 0;

// Setting fix_xored_crcs will cause the error correction code to attempt to fix single bit errors in messages where the CRC is XORed with
// the ICAO aircraft address. Doing this is computationally more intensive.
const int fix_xored_crcs = 0;
/*
 * Setting fix_2_bit_errors will cause the error correction code to attempt to fix double bit errors but only in messages where the CRC is not
 * XORed with the ICAO aircraft address. Double bit errors where both flipped bits fall within the DF field will not be corrected. Fixing
 * double bit errors is computationally quite intensive.
 */
const int fix_2_bit_errors = 0;

// Mode S receiver parameters
#define MODE_S_FREQ 1090000000
#define MODE_S_RATE 2000000
#define SAMPLES_PER_BIT 2
#define PREAMBLE_SAMPLES 16
#define MESSAGE_BITS_MAX 112
#define MESSAGE_BITS_SHORT 56
#define DF_BITS 5  // The number of bits in the downlink format (message type) field at the start of the message

// CRC lookup table
const uint32_t crc_table[MESSAGE_BITS_MAX] __attribute__ ((aligned (32))) = {
    0x3935ea, 0x1c9af5, 0xf1b77e, 0x78dbbf, 0xc397db, 0x9e31e9, 0xb0e2f0, 0x587178,
    0x2c38bc, 0x161c5e, 0x0b0e2f, 0xfa7d13, 0x82c48d, 0xbe9842, 0x5f4c21, 0xd05c14,
    0x682e0a, 0x341705, 0xe5f186, 0x72f8c3, 0xc68665, 0x9cb936, 0x4e5c9b, 0xd8d449,
    0x939020, 0x49c810, 0x24e408, 0x127204, 0x093902, 0x049c81, 0xfdb444, 0x7eda22,
    0x3f6d11, 0xe04c8c, 0x702646, 0x381323, 0xe3f395, 0x8e03ce, 0x4701e7, 0xdc7af7,
    0x91c77f, 0xb719bb, 0xa476d9, 0xadc168, 0x56e0b4, 0x2b705a, 0x15b82d, 0xf52612,
    0x7a9309, 0xc2b380, 0x6159c0, 0x30ace0, 0x185670, 0x0c2b38, 0x06159c, 0x030ace,
    0x018567, 0xff38b7, 0x80665f, 0xbfc92b, 0xa01e91, 0xaff54c, 0x57faa6, 0x2bfd53,
    0xea04ad, 0x8af852, 0x457c29, 0xdd4410, 0x6ea208, 0x375104, 0x1ba882, 0x0dd441,
    0xf91024, 0x7c8812, 0x3e4409, 0xe0d800, 0x706c00, 0x383600, 0x1c1b00, 0x0e0d80,
    0x0706c0, 0x038360, 0x01c1b0, 0x00e0d8, 0x00706c, 0x003836, 0x001c1b, 0xfff409,
    0x800000, 0x400000, 0x200000, 0x100000, 0x080000, 0x040000, 0x020000, 0x010000,
    0x008000, 0x004000, 0x002000, 0x001000, 0x000800, 0x000400, 0x000200, 0x000100,
    0x000080, 0x000040, 0x000020, 0x000010, 0x000008, 0x000004, 0x000002, 0x000001
};


/* Global Variables and Buffers ======================================================================================================================= */

// Fractional delay filter coefficients
float filter_coeffs[N_FILTERS][FILTER_LEN] __attribute__ ((aligned (32)));

// Sample processing buffers
// The sample buffer is padded by FILTER_LEN to aid vectorization, and the interpolation buffer is similarly padded by PREAMBLE_SAMPLES.
float sbuf_re[PROCESS_BLOCK_SIZE+FILTER_LEN] __attribute__ ((aligned (32)));  // These store PROCESS_BLOCK_SIZE complex floating point samples from hardware or file.
float sbuf_im[PROCESS_BLOCK_SIZE+FILTER_LEN] __attribute__ ((aligned (32)));
float interp_buf[N_FILTERS][PROCESS_BLOCK_SIZE+PREAMBLE_SAMPLES] __attribute__ ((aligned (32)));  // Buffer for holding the square magnitudes of the interpolated samples
float detect_buf[N_FILTERS][PROCESS_BLOCK_SIZE] __attribute__ ((aligned (32)));  // Stores the results of the preamble correlation for each sample in interp_buf
uint64_t block_no = 0;  // Number of the current processing block (for time stamping)
pthread_mutex_t sbuf_mutex;
pthread_cond_t go_process_cond;

// Buffers for holding the hard and soft decisions during demodulation and decoding
float soft_bits[MESSAGE_BITS_MAX] __attribute__ ((aligned (32)));
int hard_bits[MESSAGE_BITS_MAX] __attribute__ ((aligned (32)));

// The list of ICAO numbers of previously seen aircraft
uint32_t icao_list[ICAO_LIST_SIZE];
uint32_t icao_fast_list[ICAO_FAST_LIST_SIZE];
int icao_wrindex = 0;

// RTL-SDR device pointer
rtlsdr_dev_t *dev;

// File pointer for a saved dump file, input/output mode flags and temporary storage
FILE *dumpfile;
unsigned char *filebuf;
int read_file = 0;
int write_file = 0;

// Thread exit flag
int exiting = 0;


/* Initialisation Functions =========================================================================================================================== */

/*
 * Initialise the filter coefficients.
 * These are all shifted sinc functions with a Hann window function applied. They are evenly spaced over the sample period.
 */
static void init_filters(void) {
    int i, j;
    double x_sinc, sinc, window;
    
    if (debug)
        printf("Filter coefficients:\n");
    
    for (i = 0; i < N_FILTERS; ++i) {
        for (j = 0; j < FILTER_LEN; ++j) {
            /* The Hann window function is 0.5 * (1 - cos(2*pi*n/(N-1)))
             * The first and last samples are zero. We want the last sample to be zero because it will shift outside of the
             * filter array as the filter functions are shifted in time (increasing i). The first sample will always fall within
             * the array so we would like to push it back to i = -1. That way we avoid a constant zero at the start of the array.
             * Therefore N (for the purposes of the window function) is actually FILTER_LEN + 1 and n is j + 1. There will be
             * a single maximum sample at j = FILTER_LEN / 2 - 1 corresponding to 'x = 0'. There is also a fractional part of
             * n corresponding to - i / N_FILTERS.
             */
            window = 0.5 * (1.0 - cos(2 * M_PI * ((j+1) - (double) i / N_FILTERS) / FILTER_LEN));
            //                                   |               n              |   |  N - 1  |
            
            /* The sinc function's x = 0 value occurs at j = FILTER_LEN / 2 - 1, (corresponding with the window maximum).
             * There is similarly a fractional part equal to - i / N_FILTERS.
             */
            x_sinc = M_PI * (j - (FILTER_LEN / 2 - 1) - (double) i / N_FILTERS);
            sinc = (x_sinc == 0.0) ? 1.0 : sin(x_sinc) / x_sinc;
            
            filter_coeffs[i][j] = sinc * window;
            
            if (debug)
                printf("%f  ", filter_coeffs[i][j]);
        }
        if (debug)
            printf("\n\n");
    }
}

/*
 * Initialise the RTL-SDR stuff.
 * The device at dev_index is opened and configured.
 */
static void rtl_sdr_init(int dev_index) {
    int device_count;
    int i;
    int numgains;
    int gain;
    int gains[100];
    char vendor[256], product[256], serial[256];
    
    device_count = rtlsdr_get_device_count();
    if (!device_count) {
        fprintf(stderr, "No supported RTL-SDR devices found.\n");
        exit(1);
    }
    
    fprintf(stderr, "Found %u device(s):\n", device_count);
    for (i = 0; i < device_count; i++) {
        rtlsdr_get_device_usb_strings(i, vendor, product, serial);
        fprintf(stderr, "%u: %s, %s, SN: %s %s\n", i, vendor, product, serial, (i == dev_index) ? "(currently selected)" : "");
    }
    
    if (dev_index >= device_count) {
        fprintf(stderr, "No RTL-SDR device at index %u.\n", dev_index);
        exit(1);
    } else if (rtlsdr_open(&dev, dev_index) < 0) {
        fprintf(stderr, "Error opening the RTL-SDR device %u: %s\n", dev_index, strerror(errno));
        exit(1);
    }
    
    // Set tuner gain to manual, baseband gain to automatic
    rtlsdr_set_agc_mode(dev, 1);
    rtlsdr_set_tuner_gain_mode(dev, 1);
    // Apply maximum tuner gain
    numgains = rtlsdr_get_tuner_gains(dev, gains);
    gain = gains[numgains-1];
    fprintf(stderr, "Setting maximum available gain: %.1fdB\n", gain / 10.0);
    rtlsdr_set_tuner_gain(dev, gain);
    
    // Set the frequency and sample rate
    rtlsdr_set_center_freq(dev, MODE_S_FREQ);
    rtlsdr_set_sample_rate(dev, MODE_S_RATE);
    
    // Reset and purge the buffer
    rtlsdr_reset_buffer(dev);
    sleep(1);
	rtlsdr_read_sync(dev, NULL, 4096, NULL);
    
    // Report actual gain, frequency and sample rate
    fprintf(stderr, "Gain reported by device: %.1fdB\n", rtlsdr_get_tuner_gain(dev) / 10.0);
    fprintf(stderr, "Centre frequency reported by device: %uHz\n", rtlsdr_get_center_freq(dev));
    fprintf(stderr, "Sample rate reported by device: %usps\n", rtlsdr_get_sample_rate(dev));
}


/* Demodulation, Error Detection and Error Correction Functions ======================================================================================= */

/*
 * Perform a fast lookup of ICAO number icao.
 * If it is in the list of known aircraft then return 0. If the number is invalid then return -1. If the number
 * is valid but not in the list then return 1;
 */
static inline int icao_fast_lookup(uint32_t icao) {
    if (icao == 0 || icao >= ((1 << ICAO_N_BITS) - 1))
        return -1;

    // The lower 5 bits of the ICAO No. give the bit number (0 to 31) and the upper 19 give the
    // index in the fast list.
    if ((icao_fast_list[icao>>5] >> (icao & 0x1f)) & 1)
        return 0;
    else
        return 1;
}

/*
 * Add a new ICAO number to the lists of known aircraft.
 * Oldest entries are overwritten by newest ones. The function returns 0 if the new ICAO number was
 * successfully added or if it was already there. -1 is returned if the number is invalid.
 */
static inline int icao_add(uint32_t icao) {
    if (icao == 0 || icao >= ((1 << ICAO_N_BITS) - 1))
        return -1;
    else if ((icao_fast_list[icao>>5] >> (icao & 0x1f)) & 1)  // It's already there.
        return 0;
    else {
        uint32_t old;
        // Clear the previous entry from the fast list if it exists.
        if ((old = icao_list[icao_wrindex]) != 0)
            icao_fast_list[old>>5] &= ~(1 << (old & 0x1f));

        // Write the new entry to the slow list.
        icao_list[icao_wrindex++] = icao;
        if (icao_wrindex >= ICAO_LIST_SIZE)  // Wrap the write index.
            icao_wrindex = 0;

        // Write the new entry to the fast list.
        icao_fast_list[icao>>5] |= (1 << (icao & 0x1f));

        if (debug)
            fprintf(stderr, "Added %.6x\n", icao);

        return 0;
    }
}

/*
 * Display the contents of a succesfully decoded message and add the ICAO No. to the list of known aircraft if necessary.
 */
static void message_post_process(int filter_no, int sample_start, uint32_t icao_from_crc, int icao_in_message) {
    uint32_t icao_from_message = 0;
    int i;

    // If this is a DF11, DF17 or DF18 then extract the ICAO number and add it to the list if it isn't already there.
    if (icao_in_message) {
        for (i = 8; i < 32; ++i)  // The aircraft address is stored in bits [8:31] for these message types (big endian).
            icao_from_message = (icao_from_message << 1) | hard_bits[i];

        if (icao_add(icao_from_message)) {
            fprintf(stderr, "Received valid message containing invalid ICAO number: 0x%.6x\n", icao_from_message);
            return;
        }
    }

    // Print the timestamp in samples and the ICAO number.
    printf("%.14llu.%.2d: ", block_no * PROCESS_BLOCK_SIZE + sample_start, 100 * filter_no / N_FILTERS);
    printf("0x%.6x, ", (icao_in_message) ? icao_from_message : icao_from_crc);

    // Print the message content in hex.
    printf("0x");
    for (i = 0; i < ((hard_bits[0]) ? MESSAGE_BITS_MAX : MESSAGE_BITS_SHORT) - 24; i += 4)  // We don't need to print the CRC (hence the - 24).
        printf("%x", hard_bits[i] << 3 | hard_bits[i+1] << 2 | hard_bits[i+2] << 1 | hard_bits[i+3]);

    printf(";\n");
}

/*
 * Check the CRC for a message stored in hard_bits.
 * Returns 0 if the CRC passed and -1 if it failed. The remainder is stored in *crc_remainder. *icao_in_message is set to 1 if the message
 * is a DF11, DF17 or DF18 in which the ICAO aircraft address is stored in the message and the CRC is plain. The meaning of *crc_remainder is
 * as follows:           _______________________________________________
 *                      |               Return value                    |
 *                      |         -1          |           0             |
 *  ____________________|_____________________|_________________________|
 * |*icao_in_message | 0| syndrome ^ ICAO No. | ICAO No.                |
 * |                 | 1| syndrome            | 0                       |
 * |--------------------------------------------------------------------|
 */
static inline int calc_crc(uint32_t *crc_remainder, int *icao_in_message) {
    int i;
    uint32_t crc_val = 0;

    if (hard_bits[0]) {
        // Message is long (112 bits).
        for (i = 0; i < MESSAGE_BITS_MAX; ++i) {
            crc_val ^= (hard_bits[i]) ? crc_table[i] : 0;
        }
    } else {
        // Message is short (56 bits).
        for (i = 0; i < MESSAGE_BITS_SHORT; ++i) {
            crc_val ^= (hard_bits[i]) ? crc_table[i+MESSAGE_BITS_SHORT] : 0;
        }
    }
    *crc_remainder = crc_val;
    
    // DF18, DF17 and DF11 do not have CRCs XORed with the aircraft address so just return 0 if crc_val is zero.
    if ((hard_bits[0] && !hard_bits[1] && !hard_bits[2] && hard_bits[3] && !hard_bits[4]) ||  // DF18 (10010)
        (hard_bits[0] && !hard_bits[1] && !hard_bits[2] && !hard_bits[3] && hard_bits[4]) ||  // DF17 (10001)
        (!hard_bits[0] && hard_bits[1] && !hard_bits[2] && hard_bits[3] && hard_bits[4])) {   // DF11 (01011)

        *icao_in_message = 1;
        return (crc_val) ? -1 : 0;
    } else {
        // All other messages need to have their CRC remainder compared with the known aircraft list.
        *icao_in_message = 0;
        if (icao_fast_lookup(crc_val) == 0)
            return 0;
        else
            return -1;
    }

    return -1;  // Shouldn't get here.
}

/*
 * Fix a single bit error.
 * If the CRC remainder is an entry in the CRC table then the error can be fixed by flipping the
 * corresponding bit. The function does this (to hard_bits) and returns the bit index of the flipped bit.
 * The function returns -1 on failure.
 *
 * If the CRC has been XORed with the ICAO number of the transmitting aircraft then fixing a single bit
 * error is harder. This is because the CRC remainder must be compared with each entry in the known
 * aircraft list XORed with each entry in the CRC table. This will only be attempted if fix_xored_crcs is set.
 *
 * Note that the function does not fix flipped bits in the message type field because this affects how the
 * CRC is calculated.
 */
static inline int fix_1_bit(uint32_t remainder, int icao_in_message) {
    int i;

    if (icao_in_message) {
        if (hard_bits[0]) {
            for (i = DF_BITS; i < MESSAGE_BITS_MAX; ++i)
                if (remainder == crc_table[i]) {
                    hard_bits[i] ^= 1;
                    return i;
                }
        } else {
            for (i = DF_BITS; i < MESSAGE_BITS_SHORT; ++i)
                if (remainder == crc_table[i+MESSAGE_BITS_SHORT]) {
                    hard_bits[i] ^= 1;
                    return i;
                }
        }
    } else if (fix_xored_crcs) {
        if (hard_bits[0]) {
            for (i = DF_BITS; i < MESSAGE_BITS_MAX; ++i)
                if (!icao_fast_lookup(remainder ^ crc_table[i])) {
                    hard_bits[i] ^= 1;
                    return i;
                }
        } else {
            for (i = DF_BITS; i < MESSAGE_BITS_SHORT; ++i)
                if (!icao_fast_lookup(remainder ^ crc_table[i+MESSAGE_BITS_SHORT])) {
                    hard_bits[i] ^= 1;
                    return i;
                }
        }
    }

    return -1;
}

/*
 * Attempt to demodulate a message starting at sample_start using fractional delay filter filter_no.
 * Samples are read from interp_buf which has already been filled in by process_samples().
 * The encoding scheme is PPM and the soft bits are generated by taking the difference in energy between pairs
 * of samples and normalizing by the total energy of the pair. The message length (long or short) is indicated
 * by the first bit of the message.
 *
 * The message CRC is used to verify successful demodulation and to perform some primitive error correction. This
 * is complicated by the fact that the CRC is XORed with the aircraft address (ICAO number) for most message types.
 *
 * If decoding is successful, the function returns the number of samples occupied by the message.
 */
static int demod_decode(int filter_no, int sample_start) {
    int i, j;
    uint32_t icao_from_crc = 0;
    int icao_in_message, icao_in_message_orig;

    // Perform initial soft demodulation.
    sample_start += PREAMBLE_SAMPLES;  // Skip the preamble.
    for (i = 0; i < MESSAGE_BITS_MAX; ++i) {  // This must vectorize.
        soft_bits[i] = 0.5 + 0.5 * (interp_buf[filter_no][sample_start+2*i] - interp_buf[filter_no][sample_start+2*i+1]) /
                                   (interp_buf[filter_no][sample_start+2*i] + interp_buf[filter_no][sample_start+2*i+1]) ;
        hard_bits[i] = (soft_bits[i] > 0.5) ? 1 : 0;
    }

    // Check the CRC.
    if (!calc_crc(&icao_from_crc, &icao_in_message)) {
        if (debug) {
            fprintf(stderr, "CRC OK");
            if (!icao_in_message)
                fprintf(stderr, " (known ICAO No. 0x%.6x)\n", icao_from_crc);
            else
                fprintf(stderr, "\n");
        }
        message_post_process(filter_no, sample_start, icao_from_crc, icao_in_message);
        return (hard_bits[0]) ? (MESSAGE_BITS_MAX * SAMPLES_PER_BIT) : (MESSAGE_BITS_SHORT * SAMPLES_PER_BIT);
    } else {
        // CRC failure -- try to correct the error.
        icao_in_message_orig = icao_in_message;  // Save the original CRC mode for step 3 below.

        // Step 1: sweep for a single bit error.
        if ((i = fix_1_bit(icao_from_crc, icao_in_message)) >= 0) {
            if (debug)
                fprintf(stderr, "CRC CORRECTED [%d]\n", i);
            message_post_process(filter_no, sample_start, icao_from_crc, icao_in_message);
            return (hard_bits[0]) ? (MESSAGE_BITS_MAX * SAMPLES_PER_BIT) : (MESSAGE_BITS_SHORT * SAMPLES_PER_BIT);
        }

        // Step 2: fix_1_bit() doesn't correct the message type field so that has to be tried manually.
        for (i = 0; i < DF_BITS; ++i) {
            hard_bits[i] ^= 1;
            if (!calc_crc(&icao_from_crc, &icao_in_message)) {
                if (debug) {
                    fprintf(stderr, "CRC CORRECTED [%d]", i);
                    if (!icao_in_message)
                        fprintf(stderr, " (known ICAO No. 0x%.6x)\n", icao_from_crc);
                    else
                        fprintf(stderr, "\n");
                }
                message_post_process(filter_no, sample_start, icao_from_crc, icao_in_message);
                return (hard_bits[0]) ? (MESSAGE_BITS_MAX * SAMPLES_PER_BIT) : (MESSAGE_BITS_SHORT * SAMPLES_PER_BIT);
            // Try to fix another bit within the message when in fix_2_bits mode.
            } else if (fix_2_bit_errors && icao_in_message && (j = fix_1_bit(icao_from_crc, icao_in_message)) >= 0) {
                if (debug)
                    fprintf(stderr, "CRC CORRECTED [%d, %d]\n", i, j);
                message_post_process(filter_no, sample_start, icao_from_crc, icao_in_message);
                return (hard_bits[0]) ? (MESSAGE_BITS_MAX * SAMPLES_PER_BIT) : (MESSAGE_BITS_SHORT * SAMPLES_PER_BIT);
            }
            hard_bits[i] ^= 1;
        }

        // Step 3: If requested, try to fix a double bit error within the main body of the message.
        // In this loop, we assume that the DF field has been correctly received (it has already been twiddled in step 2).
        if (fix_2_bit_errors && icao_in_message_orig) {
            int imax = (hard_bits[0]) ? MESSAGE_BITS_MAX : MESSAGE_BITS_SHORT;
            for (i = DF_BITS; i < imax; ++i) {
                hard_bits[i] ^= 1;
                calc_crc(&icao_from_crc, &icao_in_message);  // This is guaranteed to fail.
                if ((j = fix_1_bit(icao_from_crc, icao_in_message)) >= 0) {
                    if (debug)
                        fprintf(stderr, "CRC CORRECTED [%d, %d]\n", i, j);
                    message_post_process(filter_no, sample_start, icao_from_crc, icao_in_message);
                    return (hard_bits[0]) ? (MESSAGE_BITS_MAX * SAMPLES_PER_BIT) : (MESSAGE_BITS_SHORT * SAMPLES_PER_BIT);
                }
                hard_bits[i] ^= 1;
            }
        }
    }

    // If we get to here then the message remains undecoded.
    return 0;
}


/* Sample Handling and Processing Functions =========================================================================================================== */

/*
 * Callback to read samples from the RTL SDR hardware and store in sbuf
 * process_samples() is signaled via go_process_cond. If write_file is set then the samples are written to a file rather than being sent to
 * process_samples().
 */
void read_samples(unsigned char *buf, uint32_t len, void *ctx) {
    int i;
    int err;
    
    if (exiting) {
        // Cancel the hardware reads and signal the sample processing thread so it can see the exiting flag.
        rtlsdr_cancel_async(dev);
        pthread_mutex_lock(&sbuf_mutex);
        pthread_cond_signal(&go_process_cond);
        pthread_mutex_unlock(&sbuf_mutex);
    } else if (write_file) {
        fwrite(buf, sizeof(*buf), len, dumpfile);
    } else {
        if ((err = pthread_mutex_trylock(&sbuf_mutex))) {
            // If the mutex was not immediately lockable then the sample processing thread must still be reading the buffer
            // i.e. it is not keeping up with the hardware.
            if (err == EBUSY) {
                fprintf(stderr, "Overflow!\n");
                pthread_mutex_lock(&sbuf_mutex);
            } else {
                fprintf(stderr, "%s: Mutex lock error: %s\n", __func__, strerror(err));
                exit(1);
            }
        }
        
        // This check makes the following loop safe and vectorizable. This error condition should never occur though.
        if (len != PROCESS_BLOCK_SIZE * 2) {
            fprintf(stderr, "Error: len = %u, PROCESS_BLOCK_SIZE * 2 = %u\n", len, PROCESS_BLOCK_SIZE * 2);
            exit(1);
        }
        // Convert the samples generated by the hardware from offset binary integers into floats.
        for (i = 0; i < PROCESS_BLOCK_SIZE; ++i) {  // This must vectorize.
            sbuf_re[i] = (float) buf[2*i] - 128.0;
            sbuf_im[i] = (float) buf[2*i+1] - 128.0;
        }
        ++block_no;
        
        pthread_cond_signal(&go_process_cond);
        pthread_mutex_unlock(&sbuf_mutex);
    }
}

/*
 * Start the hardware reading thread.
 */
void *start_reader_thread(void *arg) {
    if (!read_file)
        rtlsdr_read_async(dev, read_samples, NULL, 0, PROCESS_BLOCK_SIZE * 2);
    return NULL;
}

/*
 * Utility function for reading samples from a file rather than the hardware dongle.
 */
static void read_samples_file(void) {
    int i, n_read;
    
    n_read = fread(filebuf, sizeof(unsigned char), PROCESS_BLOCK_SIZE * 2, dumpfile);
    // Similar to read_samples() above. This must vectorize.
    for (i = 0; i < n_read / 2; ++i) {
        sbuf_re[i] = (float) filebuf[2*i] - 128.0;
        sbuf_im[i] = (float) filebuf[2*i+1] - 128.0;
    }
    ++block_no;
    
    if (n_read != PROCESS_BLOCK_SIZE * 2)  // Probably an EOF
        exiting = 1;
}

/*
 * Main sample processing function
 * This handles application of the fractional delay filters and preamble searching.
 */
void *process_samples(void *arg) {
    float accum_re, accum_im;
    float max_corr;
    int max_i, max_j;
    int i, j, k;
    
    pthread_mutex_lock(&sbuf_mutex);
    for (;;) {
        // Read from a file or wait for read_samples() to get some samples.
        if (read_file)
            read_samples_file();
        else
            pthread_cond_wait(&go_process_cond, &sbuf_mutex);  // Mutex is unlocked while waiting so read_samples() can lock it.
        
        if (exiting) {
            pthread_mutex_unlock(&sbuf_mutex);
            break;
        }
        
        // If we get here then sbuf should be filled with PROCESS_BLOCK_SIZE fresh samples.
        
        // Run though each fractional delay filter and apply it along the length of the block of samples.
        // Calculate the square magnitude of each interpolated sample and store it in interp_buf.
        for (i = 0; i < N_FILTERS; ++i) {
            for (j = 0; j < PROCESS_BLOCK_SIZE; ++j) {  // This must vectorize.
                for (k = 0, accum_re = 0.0, accum_im = 0.0; k < FILTER_LEN; ++k) {
                    accum_re += sbuf_re[j+k] * filter_coeffs[i][k];
                    accum_im += sbuf_im[j+k] * filter_coeffs[i][k];
                }
                interp_buf[i][j] = accum_re * accum_re + accum_im * accum_im;
            }
        }
        
        /*
         * Search for the mode S preamble amongst the interpolated magnitudes. We are looking for: -_-____-_-______
         * This equivalent to applying a 16 tap filter with positive coefficients at 0, 2, 7 and 9 and negative coefficients at all other taps.
         * This correlation result is normalized by the sum of the 16 samples analyzed so that the final result is independent of signal strength.
         */
        for (i = 0; i < N_FILTERS; ++i) {
            for (j = 0; j < PROCESS_BLOCK_SIZE; ++j) {  // This must vectorize.
                detect_buf[i][j] = (+ interp_buf[i][j+0]  - interp_buf[i][j+1]  + interp_buf[i][j+2]  - interp_buf[i][j+3]
                                    - interp_buf[i][j+4]  - interp_buf[i][j+5]  - interp_buf[i][j+6]  + interp_buf[i][j+7]
                                    - interp_buf[i][j+8]  + interp_buf[i][j+9]  - interp_buf[i][j+10] - interp_buf[i][j+11]
                                    - interp_buf[i][j+12] - interp_buf[i][j+13] - interp_buf[i][j+14] - interp_buf[i][j+15])
                                   /
                                   (+ interp_buf[i][j+0]  + interp_buf[i][j+1]  + interp_buf[i][j+2]  + interp_buf[i][j+3]
                                    + interp_buf[i][j+4]  + interp_buf[i][j+5]  + interp_buf[i][j+6]  + interp_buf[i][j+7]
                                    + interp_buf[i][j+8]  + interp_buf[i][j+9]  + interp_buf[i][j+10] + interp_buf[i][j+11]
                                    + interp_buf[i][j+12] + interp_buf[i][j+13] + interp_buf[i][j+14] + interp_buf[i][j+15]);
            }
        }
        
        // Examine the preamble correlation results and look for possible transmissions. We search detect_buf for values exceeding detect_thresh.
        // Whenever a group of consecutive correlation values exceed the threshold, the algorithm will only attempt to decode the maximum one.
        max_corr = detect_thresh - 1.0;
        max_i = 0;
        max_j = 0;
        for (j = 0; j < PROCESS_BLOCK_SIZE; ++j) {  // These loops search detect_buf in chronological order
            for (i = 0; i < N_FILTERS; ++i) {
                if (detect_buf[i][j] > detect_thresh) {
                    // Correlation value is above the threshold -- update the running maximum.
                    if (detect_buf[i][j] > max_corr) {
                        max_corr = detect_buf[i][j];
                        max_i = i;
                        max_j = j;
                    }
                } else if (max_corr > detect_thresh) {
                    /*
                     * Correlation value has dropped below the threshold but it was above it. We will try to decode a message starting at the
                     * maximum stored correlation value.
                     *
                     * We have to check that there are enough samples in the buffer to decode a message. Messages spanning two process blocks will be
                     * lost. The probability of this happening for any given message is (MESSAGE_BITS_MAX * SAMPLES_PER_BIT) / PROCESS_BLOCK_SIZE. It
                     * is quite easy to keep this number and the associated packet loss rate very small by sizing PROCESS_BLOCK_SIZE appropriately.
                     */
                    if (PROCESS_BLOCK_SIZE - max_j >= MESSAGE_BITS_MAX * SAMPLES_PER_BIT)
                        j += demod_decode(max_i, max_j);  // This will make the loop jump forward by the number of succesfully demodulated samples.
                    max_corr = detect_thresh - 1.0;  // Reset the running maximum
                    break;  // Break out of the inner loop so that i is reset.
                }
            }
        }
    }
    
    return NULL;
}


/* ==================================================================================================================================================== */

int main(int argc, char *argv[]) {
    int i, j;
    pthread_t reader_thread;
    pthread_t sample_process_thread;
    
    init_filters();
    
    // Initialise the buffers with overspill regions to avoid spurious detections
    for (i = 0; i < PROCESS_BLOCK_SIZE+FILTER_LEN; ++i) {
        sbuf_re[i] = 1.0;
        sbuf_im[i] = 1.0;
    }
    for (i = 0; i < N_FILTERS; ++i)
        for (j = 0; j < PROCESS_BLOCK_SIZE+PREAMBLE_SAMPLES; ++j)
            interp_buf[i][j] = 1.0;
    
    // Initialise the aircraft address lists with zeros (zero is defined as an invalid address).
    for (i = 0; i < ICAO_LIST_SIZE; ++i)
        icao_list[i] = 0;
    for (i = 0; i < ICAO_FAST_LIST_SIZE; ++i)
        icao_fast_list[i] = 0;
    
    pthread_mutex_init(&sbuf_mutex, NULL);
    pthread_cond_init(&go_process_cond, NULL);
    
    if (argc == 2) {
        // Read samples from a file
        read_file = 1;
        write_file = 0;
        dumpfile = fopen(argv[1], "rb");
        if (dumpfile == NULL) {
            fprintf(stderr, "Could not open %s: %s\n", argv[1], strerror(errno));
            exit(1);
        }
        if ((filebuf = (unsigned char *) malloc(sizeof(unsigned char) * PROCESS_BLOCK_SIZE * 2)) == NULL) {
            fprintf(stderr, "Could not allocate file buffer\n");
            exit(1);
        }
    } else if (argc == 3 && !strcmp(argv[1], "-w")) {
        // Write samples to a file
        read_file = 0;
        write_file = 1;
        rtl_sdr_init(0);
        dumpfile = fopen(argv[2], "wb");
        if (dumpfile == NULL) {
            fprintf(stderr, "Could not open %s: %s\n", argv[2], strerror(errno));
            exit(1);
        }
    } else {
        // Just process the samples from hardware
        read_file = 0;
        write_file = 0;
        rtl_sdr_init(0);
    }
    
    pthread_create(&sample_process_thread, NULL, process_samples, NULL);
    pthread_create(&reader_thread, NULL, start_reader_thread, NULL);
    pthread_join(sample_process_thread, NULL);
    pthread_join(reader_thread, NULL);
    
    if (read_file || write_file)
        fclose(dumpfile);
    
    if (read_file)
        free(filebuf);
    else
        rtlsdr_close(dev);
    
    pthread_mutex_destroy(&sbuf_mutex);
    pthread_cond_destroy(&go_process_cond);
    
    return 0;
}
