package net.themark.leasegrid.sync.invite

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import net.themark.leasegrid.sync.ui.failNextLine

// #50 option 1: the phone asks for the desktop's full join link. Pure JVM.
class InviteCopyTest {
    private fun failFor(raw: String): InviteFail =
        Invite.attempt(raw, fail = { it }) { error("expected fail for $raw") }

    private val samples = listOf(
        "",
        "   ",
        "7-guitarist-revenge",
        "https://example.test/tahoe",
        "not-a-code",
        "leasegrid:join",
        "#v=1&n=2",
        "#v=1&i=not-a-link",
        "pb://short",
    )

    @Test
    fun userVisibleInviteStringsPassTheBannedWordGuard() {
        val fails = samples.flatMap { failFor(it).let { exc -> listOf(exc.banner, exc.next) } }
        val screen = listOf(
            Invite.TITLE, Invite.BODY, Invite.INPUT_HINT, Invite.ACK_MSG, Invite.ACK_NEXT,
            Invite.JOIN_FAILED, Invite.JOIN_FAILED_NEXT,
        )
        for (line in screen + fails) {
            assertEquals("banned word in: $line", emptyList<String>(), bannedWords(line))
        }
    }

    @Test
    fun bannedWordGuardCatchesEachWord() {
        for (bad in listOf(
            "the furl", "a pb://x value", "Introducer down", "wormhole code",
            "this friendnet", "could not join this", "Could Not Join",
        )) {
            assertTrue(bad, bannedWords(bad).isNotEmpty())
        }
    }

    @Test
    fun screenCopyMatchesDesign() {
        assertEquals("Share invite", Invite.SHARE_INVITE)
        assertEquals("Show full join link (advanced)", Invite.SHOW_FULL_JOIN_LINK)
        assertEquals("Join a shared folder", Invite.TITLE)
        assertEquals(
            "On your computer, click Share invite in Leasegrid Sync and tick Show full join link (advanced). " +
                "Copy that link and paste it below.",
            Invite.BODY,
        )
        assertEquals("Paste the full join link", Invite.INPUT_HINT)
    }

    @Test
    fun failCopyMatchesDesign() {
        assertEquals("Paste the join link first.", failFor("").banner)
        assertEquals("Paste the join link first.", failFor("   ").banner)
        assertEquals(
            "That isn't a join link. On your computer, tick Show full join link (advanced), " +
                "then copy and paste the whole link.",
            failFor("not-a-code").banner,
        )
        assertEquals(
            "That's the Sync web page address, not a join link. On your computer, " +
                "tick Show full join link (advanced) and paste that link here.",
            failFor("https://example.test/tahoe").banner,
        )
        val noAddress = "That link is missing your computer's address. On your computer, " +
            "tick Show full join link (advanced), then copy and paste the whole link."
        assertEquals(noAddress, failFor("leasegrid:join").banner)
        assertEquals(noAddress, failFor("#v=1&n=2").banner)
        assertEquals(
            "That join link is incomplete. On your computer, tick Show full join link (advanced), " +
                "then copy and paste the whole link.",
            failFor("pb://short").banner,
        )
        // An i= value that is not an address is garbage too.
        assertEquals(Invite.GARBAGE_MSG, failFor("#v=1&i=not-a-link").banner)
        assertEquals("Couldn't reach your computer.", Invite.JOIN_FAILED)
        assertEquals(
            "Check that Leasegrid Sync is open on your computer and this phone is online, then tap Retry. " +
                "If it still fails, copy the join link again from your computer and paste it here.",
            Invite.JOIN_FAILED_NEXT,
        )
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
                "tick Show full join link (advanced), then paste that link here.",
            exc.banner,
        )
        assertNotEquals(Invite.GARBAGE_MSG, exc.banner)
    }

    @Test
    fun shortCodePasteRendersNoNextLineAndNeverJoins() {
        var joinCalls = 0
        val exc = Invite.attempt("7-guitarist-revenge", fail = { it }) {
            joinCalls++
            null
        }!!
        assertEquals(0, joinCalls)
        assertNull("short code must render no Next line", failNextLine(exc.next))
    }

    @Test
    fun everyParseFailRendersNoNextLine() {
        for (raw in samples) {
            assertNull(raw, failNextLine(failFor(raw).next))
        }
        // JOIN_FAILED_NEXT is for a real join attempt that failed; it does render.
        assertEquals("Next: ${Invite.JOIN_FAILED_NEXT}", failNextLine(Invite.JOIN_FAILED_NEXT))
    }

    @Test
    fun joinStaysDisabledForABlankField() {
        assertFalse(Invite.joinEnabled(true, ""))
        assertFalse(Invite.joinEnabled(true, "  \t "))
        assertTrue(Invite.joinEnabled(true, "x"))
    }

    @Test
    fun aJoinLinkStillReachesJoin() {
        val link = "leasegrid:join#v=1&i=pb://hashhashhash@127.0.0.1:45001/swissnumswiss&n=2&h=3&t=3"
        var joined: ParsedInvite? = null
        Invite.attempt(link, fail = { error("unexpected fail: ${it.banner}") }) { joined = it }
        assertEquals(listOf(2, 3, 3), joined!!.shares)
    }

    @Test
    fun linkFailBannersNameTheDesktopLabel() {
        for (raw in listOf("7-guitarist-revenge", "not-a-code", "https://example.test/tahoe", "leasegrid:join", "pb://short")) {
            val exc = failFor(raw)
            assertTrue(exc.banner, exc.banner.contains(Invite.SHOW_FULL_JOIN_LINK))
        }
        assertTrue(Invite.BODY.contains(Invite.SHOW_FULL_JOIN_LINK))
        assertTrue(Invite.BODY.contains(Invite.SHARE_INVITE))
    }
}

/** Words a phone user must never see (#50): internals, "friendnet", "could not join". */
fun bannedWords(line: String): List<String> {
    val low = line.lowercase()
    return listOf("furl", "pb://", "introducer", "wormhole", "friendnet", "could not join").filter { low.contains(it) }
}
