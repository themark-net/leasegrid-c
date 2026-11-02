package net.themark.leasegrid.sync.ui

import java.io.ByteArrayOutputStream
import java.io.IOException
import java.io.InputStream

/** The stream had more than [max] bytes. Nothing past [max] was kept in memory. */
class TooLarge(val max: Int) : IOException("over $max bytes")

/**
 * Read at most [max] bytes. A longer stream throws [TooLarge] instead of growing
 * one array until the phone runs out of memory (OutOfMemoryError is an Error,
 * so a catch of Exception would not stop the crash).
 */
fun readAtMost(input: InputStream, max: Int): ByteArray {
    val out = ByteArrayOutputStream()
    val buf = ByteArray(64 * 1024)
    var total = 0L
    while (true) {
        val n = input.read(buf)
        if (n < 0) break
        total += n
        if (total > max) throw TooLarge(max)
        out.write(buf, 0, n)
    }
    return out.toByteArray()
}
