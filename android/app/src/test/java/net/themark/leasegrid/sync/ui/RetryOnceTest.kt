package net.themark.leasegrid.sync.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
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
