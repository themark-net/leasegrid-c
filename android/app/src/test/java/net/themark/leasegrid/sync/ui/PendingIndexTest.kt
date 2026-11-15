package net.themark.leasegrid.sync.ui

import java.io.File
import java.io.IOException
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.fail
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

/** A pending-adds index is replaced as a whole. A stopped write keeps the previous rows. */
class PendingIndexTest {
    @get:Rule
    val tmp = TemporaryFolder()

    @Test
    fun aStoppedRewriteKeepsThePreviousRows() {
        val dest = File(tmp.newFolder("leasegrid"), "pending-adds.json")
        val first = """{"rows":[{"name":"notes.txt"}]}"""
        val second = """{"rows":[{"name":"notes.txt"},{"name":"other.txt"}]}"""
        writePendingIndex(dest, first)
        try {
            writePendingIndex(dest, second, stopAfter = 4)
            fail("the stopped write should not finish")
        } catch (exc: IOException) {
            assertEquals("pending index write stopped", exc.message)
        }
        assertEquals(first, dest.readText())
        assertFalse(File(dest.parentFile, dest.name + ".tmp").exists())
        writePendingIndex(dest, second)
        assertEquals(second, dest.readText())
        assertFalse(File(dest.parentFile, dest.name + ".tmp").exists())
    }
}
