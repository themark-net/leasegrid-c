package net.themark.leasegrid.sync.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Copy of the two fallback lines. AppModelRetryTest drives them through AppModel. */
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
    fun downloadFailureDoesNotNameTheExceptionClass() {
        val next = downloadFailNext(IllegalStateException("boom"))
        assertEquals("check network / free space; Retry.", next)
        assertFalse(next.contains("IllegalStateException"))
    }
}
