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
            Invite.JOIN_FAILED, Invite.JOIN_FAILED_NEXT, Invite.REFRESH_FAILED_NEXT, Invite.IMPORT_SAVED_MSG,
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
        assertEquals("Saved on this phone. Couldn't reach your computer to finish.", Invite.IMPORT_SAVED_MSG)
        assertEquals(
            "Check that Leasegrid Sync is open on your computer and this phone is online, then tap Retry.",
            Invite.REFRESH_FAILED_NEXT,
        )
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
    fun aLinkCutInsideAnEscapeIsIncomplete() {
        val exc = failFor("leasegrid:join#v=1&i=pb%3A%2")
        assertEquals(Invite.MALFORMED_MSG, exc.banner)
        assertEquals(Invite.NO_NEXT, exc.next)
    }

    @Test
    fun everyPrefixOfAJoinLinkFailsWithDesignCopyOrParses() {
        // Fake fixture shaped like desktop format_join_url (percent-encoded i=).
        val link = "leasegrid:join#v=1&i=pb%3A%2F%2Fhashhashhash%40127.0.0.1%3A45001%2Fswissnumswiss&n=2&h=3&t=3"
        val design = setOf(
            Invite.EMPTY_MSG, Invite.WORMHOLE_MSG, Invite.GARBAGE_MSG, Invite.WEB_URL_MSG,
            Invite.NO_ADDRESS_MSG, Invite.MALFORMED_MSG,
        )
        var parsed = 0
        for (end in 0..link.length) {
            val prefix = link.substring(0, end)
            val result: Any = try {
                Invite.attempt(prefix, fail = { it }) { it }
            } catch (exc: Exception) {
                throw AssertionError("prefix $end threw ${exc.javaClass.simpleName}")
            }!!
            if (result is InviteFail) {
                assertTrue("prefix $end: ${result.banner}", result.banner in design)
                assertEquals("prefix $end", Invite.NO_NEXT, result.next)
                assertFalse(result.banner, result.banner.contains("Exception"))
            } else {
                parsed++
            }
        }
        assertTrue("the whole link parses", Invite.attempt(link, fail = { null }) { it } != null)
        assertTrue(parsed > 0)
    }

    @Test(timeout = 5000)
    fun aHundredKilobytePasteDoesNotOverflowAndStaysAPlainError() {
        // Near-miss for ^[0-9]{1,3}(-[a-z0-9]+){2,}$: many "-a" groups, then a char
        // that cannot finish the match. The old regex overflows the stack on this.
        val target = 100 * 1024
        val blow = buildString(target) {
            append('1')
            while (length + 2 < target) append("-a")
            append('!')
        }
        assertTrue(blow.length > 90 * 1024)
        val result = try {
            Invite.attempt(blow, fail = { it }) { error("a huge paste must not join") }
        } catch (err: Throwable) {
            throw AssertionError("paste threw ${err.javaClass.simpleName}", err)
        }
        assertEquals(Invite.GARBAGE_MSG, result.banner)
        assertEquals(Invite.NO_NEXT, result.next)
        assertFalse(result.banner, result.banner.contains("Exception"))
        assertTrue(result.banner, bannedWords(result.banner).isEmpty())
        // Recover: the parser still accepts a real short code and a real join link.
        assertEquals(Invite.WORMHOLE_MSG, failFor("7-guitarist-revenge-alpha").banner)
        val link = "leasegrid:join#v=1&i=pb://hashhashhash@127.0.0.1:45001/swissnumswiss&n=2&h=3&t=3"
        var joined: ParsedInvite? = null
        Invite.attempt(link, fail = { error(it.banner) }) { joined = it }
        assertEquals(listOf(2, 3, 3), joined!!.shares)
    }

    @Test(timeout = 5000)
    fun aHundredKilobyteJoinLinkStillParses() {
        val base = "leasegrid:join#v=1&i=pb://hashhashhash@127.0.0.1:45001/swissnumswiss&n=2&h=3&t=3&note="
        val link = base + "a".repeat(100 * 1024)
        var joined: ParsedInvite? = null
        Invite.attempt(link, fail = { error(it.banner) }) { joined = it }
        assertEquals("pb://hashhashhash@127.0.0.1:45001/swissnumswiss", joined!!.furl)
        assertEquals(listOf(2, 3, 3), joined!!.shares)
    }

    @Test
    fun dirtyFurlsAreIncompleteAndACleanLinkStillJoins() {
        val good = "pb://hashhashhash@127.0.0.1:45001/swissnumswiss"
        val cases = listOf(
            "pb://hash%00hash@127.0.0.1:45001/swissnumswiss",
            good.replace("hashhash", "hash\uFFFDhash"),
            "leasegrid:join#v=1&i=pb://hashhashhash@127.0.0.1:45001/swiss+numswiss",
            "pb://hashhashhash@127.0.0.1:45001/swiss\nnumswiss",
            "pb://hashhashhash@127.0.0.1:45001/",
            "pb://hashhashhash@127.0.0.1:45001/ab",
            "leasegrid:join#v=1&i=pb%3A%2F%2Fhash%00hash%40127.0.0.1%3A45001%2Fswissnumswiss",
            "leasegrid:join#v=1&i=pb%3A%2F%2Fhash%FFhash%40127.0.0.1%3A45001%2Fswissnumswiss",
        )
        for (raw in cases) {
            val exc = failFor(raw)
            assertEquals(raw.take(48), Invite.MALFORMED_MSG, exc.banner)
            assertEquals(Invite.NO_NEXT, exc.next)
            assertFalse(exc.banner, exc.banner.contains("Exception"))
            assertTrue(exc.banner, bannedWords(exc.banner).isEmpty())
        }
        val parsed = Invite.attempt(good, fail = { error(it.banner) }) { it }
        assertEquals(good, parsed.furl)
    }

    @Test
    fun invisiblePasteMarksStillParseAndAMarksOnlyPasteAsksForTheLink() {
        val link = "leasegrid:join#v=1&i=pb://hashhashhash@127.0.0.1:45001/swissnumswiss&n=2&h=3&t=3"
        val furl = "pb://hashhashhash@127.0.0.1:45001/swissnumswiss"
        val marked = listOf(
            "\u200B$link",
            "\uFEFF$link",
            "\uFEFF\u200B $link",
            "$link\u200B",
            "$link\uFEFF",
            "\u200B$furl",
            "leasegrid:join#v=1&i=%E2%80%8Bpb://hashhashhash@127.0.0.1:45001/swissnumswiss&n=2&h=3&t=3",
            "leasegrid:join#v=1&i=pb://hashhashhash@127.0.0.1:45001/swissnumswiss%E2%80%8B&n=2&h=3&t=3",
        )
        for (raw in marked) {
            var joined: ParsedInvite? = null
            Invite.attempt(raw, fail = { error("${raw.codePointAt(0)}: ${it.banner}") }) { joined = it }
            assertEquals(furl, joined!!.furl)
            if (raw.contains("n=2")) {
                assertEquals(listOf(2, 3, 3), joined!!.shares)
            } else {
                assertNull(joined!!.shares)
            }
        }
        val empty = failFor("\u200B\uFEFF")
        assertEquals(Invite.EMPTY_MSG, empty.banner)
        assertEquals(Invite.NO_NEXT, empty.next)
        assertFalse(empty.banner, empty.banner.contains("Exception"))
        assertTrue(empty.banner, bannedWords(empty.banner).isEmpty())
        val worm = failFor("\u200B7-guitarist-revenge")
        assertEquals(Invite.WORMHOLE_MSG, worm.banner)
        assertEquals(Invite.NO_NEXT, worm.next)
        var joined: ParsedInvite? = null
        Invite.attempt(link, fail = { error(it.banner) }) { joined = it }
        assertEquals(listOf(2, 3, 3), joined!!.shares)
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
