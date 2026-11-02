package net.themark.leasegrid.sync.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RetryOnceTest {
    @Test
    fun aSecondTapDoesNotRunTheActionAgain() {
        val slot = RetryOnce()
        var runs = 0
        slot.arm { runs += 1 }
        slot.pull()?.invoke()
        // The card is still on screen. A second tap must not run it again.
        assertNull("a second tap ran the action again", slot.pull())
        assertEquals(1, runs)
    }

    @Test
    fun appModelPullsTheRetryBeforeItRuns() {
        val model = appModelText()
        val start = model.indexOf("    fun retryFail()")
        val end = model.indexOf("    fun join()", start)
        val body = model.substring(start, end)
        assertTrue("retryFail must take the action once", body.contains("retries.pull()"))
        assertTrue(
            "retryFail must clear the action before running it",
            body.indexOf("pull()") < body.indexOf("invoke()"),
        )
        val show = model.substring(model.indexOf("    private fun show("))
        assertTrue(show.contains("retries.arm(again)"))
    }

    @Test
    fun aNewFailureCanBeRetriedAfterTheFirstTap() {
        val slot = RetryOnce()
        var runs = 0
        slot.arm { runs += 1 }
        slot.pull()?.invoke()
        slot.arm { runs += 10 }
        slot.pull()?.invoke()
        assertEquals(11, runs)
        assertNull("the new action stayed armed after it ran", slot.pull())
    }
}

private fun appModelText(): String {
    var dir: java.io.File? = java.io.File(System.getProperty("user.dir") ?: ".")
    repeat(6) {
        val here = dir ?: return@repeat
        val candidate = java.io.File(here, "src/main/java/net/themark/leasegrid/sync/ui/AppModel.kt")
        if (candidate.isFile) return candidate.readText()
        dir = here.parentFile
    }
    error("AppModel.kt not found from ${System.getProperty("user.dir")}")
}
