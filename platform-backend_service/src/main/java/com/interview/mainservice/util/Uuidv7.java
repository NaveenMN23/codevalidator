package com.interview.mainservice.util;

import java.nio.ByteBuffer;
import java.security.SecureRandom;
import java.util.UUID;

/**
 * Generates time-ordered UUIDv7 values (RFC 9562) so primary keys retain
 * B-tree insert locality close to a sequence, without being enumerable.
 */
public final class Uuidv7 {

    private static final SecureRandom RANDOM = new SecureRandom();

    private Uuidv7() {
    }

    public static UUID generate() {
        long timestampMs = System.currentTimeMillis();
        byte[] random = new byte[10];
        RANDOM.nextBytes(random);

        byte[] uuidBytes = new byte[16];
        uuidBytes[0] = (byte) (timestampMs >>> 40);
        uuidBytes[1] = (byte) (timestampMs >>> 32);
        uuidBytes[2] = (byte) (timestampMs >>> 24);
        uuidBytes[3] = (byte) (timestampMs >>> 16);
        uuidBytes[4] = (byte) (timestampMs >>> 8);
        uuidBytes[5] = (byte) timestampMs;

        uuidBytes[6] = (byte) (0x70 | (random[0] & 0x0F)); // version 7
        uuidBytes[7] = random[1];

        uuidBytes[8] = (byte) (0x80 | (random[2] & 0x3F)); // variant 10
        System.arraycopy(random, 3, uuidBytes, 9, 7);

        ByteBuffer buffer = ByteBuffer.wrap(uuidBytes);
        return new UUID(buffer.getLong(), buffer.getLong());
    }
}
