package net.themark.leasegrid.sync.invite

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
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
            Invite.CODE_EXPIRED, Invite.CODE_EXPIRED_NEXT, Invite.CODE_RELAY, Invite.CODE_RELAY_NEXT,
            Invite.CODE_REJECTED, Invite.CODE_REJECTED_NEXT, Invite.CODE_TIMEOUT, Invite.CODE_TIMEOUT_NEXT,
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
            "On your computer, click Share invite in Leasegrid Sync. Type the short code below, " +
                "or tick Show full join link (advanced) and paste that link.",
            Invite.BODY,
        )
        assertEquals("Short code or join link", Invite.INPUT_HINT)
        assertFalse(Invite.BODY.lowercase().contains("can't use short codes"))
    }

    @Test
    fun failCopyMatchesDesign() {
        assertEquals("Enter a short code or paste the join link first.", failFor("").banner)
        assertEquals("Enter a short code or paste the join link first.", failFor("   ").banner)
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
            "Check that Leasegrid Sync is open on your computer and this phone is online, then tap Retry.",
            Invite.JOIN_FAILED_NEXT,
        )
        assertEquals("This code expired.", Invite.CODE_EXPIRED)
        assertEquals(
            "On your computer, click Share invite again. Keep Leasegrid Sync open, type the new short code here, then tap Retry.",
            Invite.CODE_EXPIRED_NEXT,
        )
        assertEquals("Couldn't reach the invite relay.", Invite.CODE_RELAY)
        assertEquals(
            "Check that this phone is online and Leasegrid Sync is still open on your computer, then tap Retry. " +
                "If it still fails, tick Show full join link (advanced) and paste that link here.",
            Invite.CODE_RELAY_NEXT,
        )
        assertEquals("This code was not accepted.", Invite.CODE_REJECTED)
        assertEquals(
            "On your computer, click Share invite again and use the new short code. Keep Leasegrid Sync open, then tap Retry.",
            Invite.CODE_REJECTED_NEXT,
        )
        assertEquals("Nobody answered this code yet.", Invite.CODE_TIMEOUT)
        assertEquals(
            "Keep Leasegrid Sync open on your computer until this phone joins, then tap Retry. " +
                "If the code is old, click Share invite again and type the new short code.",
            Invite.CODE_TIMEOUT_NEXT,
        )
        for (copy in listOf(
            Invite.redeemCopy("expired"),
            Invite.redeemCopy("rejected"),
            Invite.redeemCopy("relay"),
            Invite.redeemCopy("timeout"),
            Invite.redeemCopy("mystery"),
        )) {
            assertEquals(copy.banner, emptyList<String>(), bannedWords(copy.banner))
            assertEquals(copy.next, emptyList<String>(), bannedWords(copy.next))
            assertEquals("Next: ${copy.next}", failNextLine(copy.next))
        }
        assertEquals(Invite.CODE_REJECTED, Invite.redeemCopy("mystery").banner)
    }

    @Test
    fun shortCodeParsesAsACodeInsteadOfTheOldRefusal() {
        // #77: the phone can use the desktop short code. Parse still happens
        // before any redeem, and the old cannot-use-short-code banner is gone.
        var parsed: ParsedInvite? = null
        val failed = Invite.attempt("7-guitarist-revenge", fail = { it }) {
            parsed = it
            null
        }
        assertTrue("a short code must not be a parse failure", failed !is InviteFail)
        assertEquals("code", parsed!!.kind)
        assertEquals("7-guitarist-revenge", parsed!!.code)
        assertEquals("", parsed!!.furl)
        assertNull(parsed!!.shares)
        val mixed = Invite.parse("\u200B7-Guitarist-Revenge")
        assertEquals("7-guitarist-revenge", mixed.code)
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
            Invite.EMPTY_MSG, Invite.GARBAGE_MSG, Invite.WEB_URL_MSG,
            Invite.NO_ADDRESS_MSG, Invite.MALFORMED_MSG,
        )
        var parsed = 0
        for (end in 0..link.length) {
            val prefix = link.substring(0, end)
            val result: Any = try {
                Invite.attempt(prefix, fail = { it }) { it }
            } catch (exc: Exception) {
                throw AssertionError("prefix $end threw ${exc.javaClass.simpleName}")
            }
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
        assertEquals("code", Invite.parse("7-guitarist-revenge-alpha").kind)
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
        val markedCode = Invite.parse("\u200B7-guitarist-revenge")
        assertEquals("7-guitarist-revenge", markedCode.code)
        assertEquals("code", markedCode.kind)
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
    fun aQueryFormLeasegridLinkJoinsTheSameFurlAsTheHashForm() {
        val furl = "pb://hashhashhash@127.0.0.1:45001/swissnumswiss"
        val hash = "leasegrid:join#v=1&i=$furl&n=2&h=3&t=3"
        val query = "leasegrid:join?v=1&i=$furl&n=2&h=3&t=3"
        assertEquals(furlOf(hash), furlOf(query))
        assertEquals(listOf(2, 3, 3), sharesOf(query))
        val encoded = "leasegrid://join?v=1&i=" +
            java.net.URLEncoder.encode(furl, "UTF-8") +
            "&n=2&h=3&t=3#"
        assertEquals(furl, furlOf(encoded))
        assertEquals(listOf(2, 3, 3), sharesOf(encoded))
        val winner = "leasegrid:join?i=pb://notthisnot@127.0.0.1:1/notswissxx#v=1&i=$furl"
        assertEquals(furl, furlOf(winner))
        assertEquals(
            Invite.WEB_URL_MSG,
            failFor("https://example.test/join?v=1&i=$furl").banner,
        )
    }

    private fun furlOf(raw: String): String =
        Invite.attempt(raw, fail = { error("${raw.take(40)}: ${it.banner}") }) { it.furl }

    private fun sharesOf(raw: String): List<Int>? =
        Invite.attempt(raw, fail = { error("${raw.take(48)}: ${it.banner}") }) { it.shares }

    @Test
    fun invisibleMarksInsideTheLinkAreDroppedAndItJoins() {
        val furl = "pb://hashhashhash@127.0.0.1:45001/swissnumswiss"
        for (mark in listOf('\u200B', '\u200C', '\u200D', '\u2060', '\uFEFF')) {
            val inSwiss = furl.replace("swissnum", "swiss${mark}num")
            val inTub = furl.replace("hashhash", "hash${mark}hash")
            val inLink = "leasegrid:join#v=1&i=${furl.replace("127.0", "127$mark.0")}&n=2&h=3&t=3"
            for (raw in listOf(inSwiss, inTub, inLink, "$mark$furl$mark")) {
                assertEquals(mark.code.toString(16), furl, furlOf(raw))
            }
        }
        val marksOnly = failFor("\u200C\u200D\u2060")
        assertEquals(Invite.EMPTY_MSG, marksOnly.banner)
    }

    @Test
    fun aFurlWithNoTubIdIsIncompleteAndNoLocationAsksForTheAddress() {
        val cut = listOf(
            "pb://@127.0.0.1:45001/swissnumswiss",
            "leasegrid:join#v=1&i=pb://@127.0.0.1:45001/swissnumswiss",
        )
        for (raw in cut) {
            assertEquals(raw, Invite.MALFORMED_MSG, failFor(raw).banner)
        }
        val noPlace = listOf(
            "pb://hashhashhash/swissnumswiss",
            "pb://hashhashhash@/swissnumswiss",
            "leasegrid:join#v=1&i=pb://hashhashhash@/swissnumswiss&n=2&h=3&t=3",
        )
        for (raw in noPlace) {
            val exc = failFor(raw)
            assertEquals(raw, Invite.NO_ADDRESS_MSG, exc.banner)
            assertEquals(Invite.NO_NEXT, exc.next)
        }
        assertEquals("pb://h@127.0.0.1:1/swissnumswiss", furlOf("pb://h@127.0.0.1:1/swissnumswiss"))
    }

    @Test
    fun aShortCodeAtTheLengthCapIsAShortCodeAndOneOverIsNot() {
        val atCap = "7-" + "a".repeat(126) + "-" + "b".repeat(127)
        assertEquals(256, atCap.length)
        assertEquals("code", Invite.parse(atCap).kind)
        assertEquals(atCap, Invite.parse(atCap).code)
        val over = atCap + "b"
        assertEquals(Invite.GARBAGE_MSG, failFor(over).banner)
        assertEquals(Invite.GARBAGE_MSG, failFor(over + "b".repeat(100_000)).banner)
    }

    @Test
    fun c1ControlCharactersMakeTheLinkIncomplete() {
        val good = "pb://hashhashhash@127.0.0.1:45001/swissnumswiss"
        for (ch in listOf('\u0080', '\u0090', '\u009C', '\u009F')) {
            val raw = good.replace("swissnum", "swiss${ch}num")
            assertEquals(ch.code.toString(16), Invite.MALFORMED_MSG, failFor(raw).banner)
        }
        assertEquals(good, furlOf(good))
    }

    @Test
    fun aSoftHyphenInTheLinkIsDroppedAndTheLinkJoins() {
        val furl = "pb://hashhashhash@127.0.0.1:45001/swissnumswiss"
        val raw = furl.replace("swissnum", "swiss\u00ADnum")
        assertEquals(furl, furlOf(raw))
        val wrapped = "leasegrid:join#v=1&i=" +
            java.net.URLEncoder.encode(raw, "UTF-8") +
            "&n=2&h=3&t=3"
        assertEquals(furl, furlOf(wrapped))
        assertEquals(Invite.EMPTY_MSG, failFor("\u00AD").banner)
        assertEquals(furl, furlOf(furl))
    }

    @Test
    fun aRightToLeftOverrideAPlusOrASecondAtIsIncomplete() {
        val furl = "pb://hashhashhash@127.0.0.1:45001/swissnumswiss"
        val override = furl.replace("127.0", "127\u202E.0")
        assertEquals(Invite.MALFORMED_MSG, failFor(override).banner)
        assertEquals(Invite.NO_NEXT, failFor(override).next)
        val plus = "pb://hashhashhash@127.0.0.1:45001/swiss+numswiss"
        assertEquals(Invite.MALFORMED_MSG, failFor(plus).banner)
        val twoAt = "pb://hashhashhash@extra@127.0.0.1:45001/swissnumswiss"
        assertEquals(Invite.MALFORMED_MSG, failFor(twoAt).banner)
        val twoAtLink = "leasegrid:join#v=1&i=pb://hashhashhash@extra@127.0.0.1:45001/swissnumswiss"
        assertEquals(Invite.MALFORMED_MSG, failFor(twoAtLink).banner)
        assertEquals(furl, furlOf(furl))
    }

    @Test
    fun aShortSwissNumHiddenBehindAFragmentIsIncomplete() {
        val raw = "pb://hashhashhash@127.0.0.1:45001/ab#swissnumswissnum"
        assertEquals(Invite.MALFORMED_MSG, failFor(raw).banner)
        val link = "leasegrid:join#v=1&i=pb://hashhashhash@127.0.0.1:45001/ab%23swissnumswissnum"
        assertEquals(Invite.MALFORMED_MSG, failFor(link).banner)
        val ok = "pb://hashhashhash@127.0.0.1:45001/swissnum#tail"
        assertEquals(ok, furlOf(ok))
    }

    @Test
    fun linkFailBannersNameTheDesktopLabel() {
        for (raw in listOf("not-a-code", "https://example.test/tahoe", "leasegrid:join", "pb://short")) {
            val exc = failFor(raw)
            assertTrue(exc.banner, exc.banner.contains(Invite.SHOW_FULL_JOIN_LINK))
        }
        assertTrue(Invite.BODY.contains(Invite.SHOW_FULL_JOIN_LINK))
        assertTrue(Invite.BODY.contains(Invite.SHARE_INVITE))
    }

    @Test
    fun scanCopyPassesTheBannedWordGuard() {
        for (line in listOf(Invite.SCAN_QR, Invite.SCAN_PROMPT, Invite.SCAN_DENIED_MSG, Invite.SCAN_DENIED_NEXT)) {
            assertTrue(line, bannedWords(line).isEmpty())
            assertFalse(line, line.contains('\u2013'))
            assertFalse(line, line.contains('\u2014'))
        }
        assertEquals("Scan QR", Invite.SCAN_QR)
        assertEquals("The camera was not allowed.", Invite.SCAN_DENIED_MSG)
        assertEquals("Paste the join link or type the short code.", Invite.SCAN_DENIED_NEXT)
    }
}

/** Words a phone user must never see (#50): internals, "friendnet", "could not join". */
fun bannedWords(line: String): List<String> {
    val low = line.lowercase()
    return listOf("furl", "pb://", "introducer", "wormhole", "friendnet", "could not join").filter { low.contains(it) }
}
