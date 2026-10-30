package net.themark.leasegrid.sync.invite

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

// #50 option 1: the phone asks for the desktop's full join link. Pure JVM.
class InviteCopyTest {
    private val forbidden = listOf("furl", "pb://", "introducer", "wormhole")

    private fun failFor(raw: String): InviteFail =
        Invite.attempt(raw, fail = { it }) { error("expected fail for $raw") }

    // Every InviteFail path plus the screen copy.
    private fun userVisible(): List<String> {
        val samples = listOf(
            "",
            "7-guitarist-revenge",
            "https://example.test/tahoe",
            "not-a-code",
            "leasegrid:join",
            "#v=1&n=2",
            "#v=1&i=not-a-link",
            "pb://short",
        )
        val fails = samples.flatMap { failFor(it).let { exc -> listOf(exc.banner, exc.next) } }
        return listOf(Invite.TITLE, Invite.BODY, Invite.INPUT_HINT, Invite.ACK_MSG, Invite.ACK_NEXT) + fails
    }

    @Test
    fun userVisibleInviteStringsNameNoFurl() {
        for (line in userVisible()) {
            for (word in forbidden) {
                assertFalse("'$word' in: $line", line.lowercase().contains(word))
            }
        }
    }

    @Test
    fun screenCopyMatchesDesign() {
        assertEquals("Join a shared folder", Invite.TITLE)
        assertEquals(
            "On your computer, open the share card in Leasegrid Sync and choose Show full join link. " +
                "Copy that link and paste it below.",
            Invite.BODY,
        )
        assertEquals("Paste the full join link", Invite.INPUT_HINT)
    }

    @Test
    fun failCopyMatchesDesign() {
        val next = "Couldn't join with that link. On your computer, choose Show full join link again, " +
            "paste the new link here, and tap Retry."
        assertEquals(next, Invite.WORMHOLE_NEXT)
        val garbage = failFor("not-a-code")
        assertEquals(
            "That isn't a join link. On your computer, choose Show full join link, then copy and paste the whole link.",
            garbage.banner,
        )
        assertEquals(next, garbage.next)
        val web = failFor("https://example.test/tahoe")
        assertEquals(
            "That's the Sync web page address, not a join link. On your computer, choose Show full join link " +
                "and paste that link here.",
            web.banner,
        )
        // An i= value that is not an address is garbage too.
        assertEquals(Invite.GARBAGE_MSG, failFor("#v=1&i=not-a-link").banner)
    }

    @Test
    fun shortCodeShowsShortCodeMessageAndNeverJoins() {
        var joined = false
        val exc = Invite.attempt("7-guitarist-revenge", fail = { it }) {
            joined = true
            null
        }
        assertFalse("a short code must not reach join", joined)
        exc!!
        assertEquals(
            "That's a short code. This phone can't use short codes yet. On your computer, " +
                "choose Show full join link, then paste that link here.",
            exc.banner,
        )
        assertNotEquals(Invite.GARBAGE_MSG, exc.banner)
        assertEquals(Invite.WORMHOLE_NEXT, exc.next)
    }

    @Test
    fun aJoinLinkStillReachesJoin() {
        val link = "leasegrid:join#v=1&i=pb://hashhashhash@127.0.0.1:45001/swissnumswiss&n=2&h=3&t=3"
        var joined: ParsedInvite? = null
        Invite.attempt(link, fail = { error("unexpected fail: ${it.banner}") }) { joined = it }
        assertEquals(listOf(2, 3, 3), joined!!.shares)
    }

    @Test
    fun everyFailLineNamesTheDesktopLabel() {
        for (raw in listOf("7-guitarist-revenge", "not-a-code", "https://example.test/tahoe")) {
            val exc = failFor(raw)
            assertTrue(exc.banner, exc.banner.contains(Invite.SHOW_FULL_JOIN_LINK))
            assertTrue(exc.next, exc.next.contains(Invite.SHOW_FULL_JOIN_LINK))
        }
    }
}
