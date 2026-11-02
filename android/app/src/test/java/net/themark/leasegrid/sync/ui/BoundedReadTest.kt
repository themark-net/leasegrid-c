package net.themark.leasegrid.sync.ui

import java.io.ByteArrayInputStream
import java.io.InputStream
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BoundedReadTest {
    /** A stream that never ends, like a picked file far bigger than the heap. */
    private class Endless : InputStream() {
        var served = 0L
        override fun read(): Int = 1.also { served++ }
        override fun read(b: ByteArray, off: Int, len: Int): Int {
            b.fill(1, off, off + len)
            served += len
            return len
        }
    }

    @Test
    fun aStreamExactlyAtTheCapIsReadWhole() {
        val bytes = ByteArray(1000) { it.toByte() }
        assertEquals(bytes.toList(), readAtMost(ByteArrayInputStream(bytes), 1000).toList())
    }

    @Test
    fun oneByteOverTheCapIsTooLarge() {
        try {
            readAtMost(ByteArrayInputStream(ByteArray(1001)), 1000)
            error("expected TooLarge")
        } catch (exc: TooLarge) {
            assertEquals(1000, exc.max)
        }
    }

    @Test(timeout = 10_000)
    fun anEndlessStreamStopsSoonAfterTheCap() {
        val endless = Endless()
        try {
            readAtMost(endless, 1 shl 20)
            error("expected TooLarge")
        } catch (_: TooLarge) {
            assertTrue("read ${endless.served} bytes for a 1 MiB cap", endless.served <= (1 shl 20) + 64 * 1024)
        }
    }

}
