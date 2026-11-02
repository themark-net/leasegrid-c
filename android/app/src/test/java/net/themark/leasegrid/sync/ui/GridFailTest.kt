package net.themark.leasegrid.sync.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class GridFailTest {
    @Test
    fun unexpectedCardDoesNotNameTheExceptionClass() {
        val card = unexpectedGridCard(IllegalStateException("boom"))
        assertEquals("could not complete that.", card.message)
        assertFalse(card.message.contains("IllegalStateException"))
        assertFalse(card.next.contains("IllegalStateException"))
        assertTrue(card.next.contains("Retry"))
    }

    @Test
    fun oneRetryRerunsTheBlockAndASecondTapDoesNot() {
        val body = runGridBody()
        assertTrue(
            "Retry must run the same block again",
            body.contains("show(unexpectedGridCard(exc)) { runGrid(label, block) }"),
        )
        assertFalse(body.contains("could not complete that. \${"))
        var runs = 0
        val slot = RetryOnce()
        fun attempt() {
            runs += 1
            if (runs == 1) {
                val card = unexpectedGridCard(IllegalStateException("boom"))
                assertFalse(card.message.contains("IllegalStateException"))
                slot.arm { attempt() }
            }
        }
        attempt()
        slot.pull()?.invoke()
        assertEquals(2, runs)
        assertNull("a second tap ran the block again", slot.pull())
    }
}

private fun runGridBody(): String {
    var dir: java.io.File? = java.io.File(System.getProperty("user.dir") ?: ".")
    var text = ""
    repeat(6) {
        val here = dir ?: return@repeat
        val candidate = java.io.File(here, "src/main/java/net/themark/leasegrid/sync/ui/AppModel.kt")
        if (candidate.isFile) {
            text = candidate.readText()
            return@repeat
        }
        dir = here.parentFile
    }
    if (text.isEmpty()) error("AppModel.kt not found from ${System.getProperty("user.dir")}")
    val start = text.indexOf("    private fun runGrid(")
    val end = text.indexOf("    private fun mimeFor(", start)
    return text.substring(start, end)
}
