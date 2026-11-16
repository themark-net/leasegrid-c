package net.themark.leasegrid.sync.ui

import kotlin.coroutines.Continuation
import kotlin.coroutines.EmptyCoroutineContext
import kotlin.coroutines.startCoroutine
import net.themark.leasegrid.sync.invite.Invite
import net.themark.leasegrid.sync.invite.RedeemOutcome
import net.themark.leasegrid.sync.invite.bannedWords
import net.themark.leasegrid.sync.session.FolderRef
import net.themark.leasegrid.sync.session.ServerRef
import net.themark.leasegrid.sync.session.Session
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

// #50: what a failed learn() puts on screen, and what Retry does. Pure JVM fakes.
class SessionFlowTest {
    private val link = "leasegrid:join#v=1&i=pb://hashhashhash@127.0.0.1:45001/swissnumswiss&n=2&h=3&t=3"
    private val furl = "pb://hashhashhash@127.0.0.1:45001/swissnumswiss"
    private val server = ServerRef("pb://s@h:1/x", "s1")

    /** A fake AppModel. [answers] feeds learn(); an empty queue means "unreachable". */
    private class Host(override var inviteText: String = "") : FlowHost {
        override var session: Session? = null
        var banner: FailBanner? = null
        var retry: (() -> Unit)? = null
        val learnCalls = mutableListOf<String>()
        val redeemCalls = mutableListOf<String>()
        val saved = mutableListOf<Session>()
        val answers = ArrayDeque<List<ServerRef>?>()
        val redeemAnswers = ArrayDeque<RedeemOutcome>()
        var learnThrows: Exception? = null
        var redeemThrows: Exception? = null
        var saveThrows: Exception? = null

        override fun launch(label: String, block: suspend () -> Unit) {
            // Same shape as runGrid: a new attempt clears the banner, a throw is caught.
            banner = null
            block.startCoroutine(Continuation(EmptyCoroutineContext) { result ->
                result.exceptionOrNull()?.let { banner = FailBanner("generic", "") }
            })
        }

        override suspend fun learn(furl: String): List<ServerRef>? {
            learnCalls += furl
            learnThrows?.let { throw it }
            return answers.removeFirstOrNull()
        }

        override suspend fun redeem(code: String): RedeemOutcome {
            redeemCalls += code
            redeemThrows?.let { throw it }
            return redeemAnswers.removeFirstOrNull() ?: RedeemOutcome("expired")
        }

        override fun save(next: Session) {
            saveThrows?.let { throw it }
            saved += next
            session = next
        }

        override fun show(banner: FailBanner, again: () -> Unit) {
            this.banner = banner
            retry = again
        }

        fun lines(): List<String> {
            val b = banner ?: return emptyList()
            return listOfNotNull(b.message, failNextLine(b.next))
        }
    }

    private fun assertClean(host: Host) {
        for (line in host.lines()) {
            assertEquals(line, emptyList<String>(), bannedWords(line))
            assertTrue(line, !line.contains("Timeout") && !line.contains("Exception"))
        }
    }

    private fun assertNoPaste(host: Host) {
        for (line in host.lines()) {
            val low = line.lowercase()
            assertTrue("Folders screen has no link field: $line", !low.contains("paste") && !low.contains("join link"))
        }
    }

    @Test
    fun unreachableJoinShowsJoinFailedAndRetryRerunsJoin() {
        val host = Host(link)
        host.answers.addAll(listOf(null, listOf(server)))
        val flow = SessionFlow(host)
        flow.join()
        assertEquals(FailBanner(Invite.JOIN_FAILED, Invite.JOIN_FAILED_NEXT), host.banner)
        assertEquals(listOf("Couldn't reach your computer.", "Next: ${Invite.JOIN_FAILED_NEXT}"), host.lines())
        assertTrue("a learn() failure is not a paste problem", !host.banner!!.next.lowercase().contains("paste"))
        assertClean(host)
        assertTrue(host.saved.isEmpty())
        // Retry must rerun join with the invite (a refresh has no session yet and learns nothing).
        host.retry!!.invoke()
        assertEquals(listOf(furl, furl), host.learnCalls)
        assertEquals(1, host.saved.size)
        assertNull(host.banner)
    }

    @Test
    fun aTrailingMarkOrWrappedLinkJoinsTheCleanFurl() {
        val samples = listOf("$furl.", "$furl).", "\"$furl\"", "<$furl>", "($furl)")
        for (raw in samples) {
            val host = Host(raw)
            host.answers.add(listOf(server))
            SessionFlow(host).join()
            assertEquals(raw, listOf(furl), host.learnCalls)
            assertEquals(furl, host.saved.single().introducerFurl)
            assertNull(raw, host.banner)
        }
    }

    @Test
    fun failedJoinKeepsThePastedText() {
        for (raw in listOf(link, "7-guitarist-revenge", "not-a-code")) {
            val host = Host(raw)
            SessionFlow(host).join()
            assertNotNull(raw, host.banner)
            assertEquals(raw, host.inviteText)
            host.retry!!.invoke()
            assertEquals(raw, host.inviteText)
        }
    }

    @Test
    fun timeoutThrowShowsTheSameCardNotTheRawError() {
        val host = Host(link)
        host.learnThrows = IllegalStateException("could not join this friendnet. Introducer is unreachable. (TimeoutError)")
        SessionFlow(host).join()
        assertEquals(FailBanner(Invite.JOIN_FAILED, Invite.JOIN_FAILED_NEXT), host.banner)
        assertClean(host)
    }

    @Test
    fun aCancelledJoinPaintsNothing() {
        val host = Host(link)
        host.learnThrows = kotlin.coroutines.cancellation.CancellationException("newer attempt")
        SessionFlow(host).join()
        // The fake launch maps an escaped throw to "generic"; JOIN_FAILED must not appear.
        assertEquals(FailBanner("generic", ""), host.banner)
        assertTrue(host.saved.isEmpty())
        // A newer attempt replaces that. The cancelled job must not paint over it.
        host.learnThrows = null
        host.answers.add(listOf(server))
        SessionFlow(host).join()
        assertNull(host.banner)
        assertEquals(1, host.saved.size)
        assertEquals(listOf(furl, furl), host.learnCalls)
    }

    @Test(timeout = 5000)
    fun retryAfterAHundredKilobytePasteJoinsTheCorrectedLink() {
        val target = 100 * 1024
        val blow = buildString(target) {
            append('1')
            while (length + 2 < target) append("-a")
            append('!')
        }
        assertTrue(blow.length > 90 * 1024)
        val host = Host(blow)
        SessionFlow(host).join()
        assertEquals(Invite.GARBAGE_MSG, host.banner!!.message)
        assertEquals(Invite.NO_NEXT, host.banner!!.next)
        assertTrue(host.learnCalls.isEmpty())
        assertTrue(host.saved.isEmpty())
        assertClean(host)
        host.inviteText = link
        host.answers.add(listOf(server))
        host.retry!!.invoke()
        assertEquals(listOf(furl), host.learnCalls)
        assertEquals(1, host.saved.size)
        assertNull(host.banner)
    }

    @Test
    fun retryAfterAMalformedPasteJoinsTheCorrectedLink() {
        val host = Host("pb://hashhashhash@127.0.0.1:45001/")
        host.answers.add(listOf(server))
        val flow = SessionFlow(host)
        flow.join()
        assertEquals(Invite.MALFORMED_MSG, host.banner!!.message)
        assertEquals(Invite.NO_NEXT, host.banner!!.next)
        assertTrue("a broken link must not reach learn", host.learnCalls.isEmpty())
        assertTrue(host.saved.isEmpty())
        host.inviteText = link
        host.retry!!.invoke()
        assertEquals(listOf(furl), host.learnCalls)
        assertEquals(1, host.saved.size)
        assertNull(host.banner)
        assertClean(host)
    }

    @Test
    fun aMarkedPasteJoinsAndAMarksOnlyPasteRecoversOnRetry() {
        val marked = Host("\uFEFF\u200B$link\u200B")
        marked.answers.add(listOf(server))
        SessionFlow(marked).join()
        assertEquals(listOf(furl), marked.learnCalls)
        assertEquals(1, marked.saved.size)
        assertNull(marked.banner)
        assertClean(marked)

        val blank = Host("\u200B\uFEFF")
        SessionFlow(blank).join()
        assertEquals(Invite.EMPTY_MSG, blank.banner!!.message)
        assertEquals(Invite.NO_NEXT, blank.banner!!.next)
        assertTrue(blank.learnCalls.isEmpty())
        assertTrue(blank.saved.isEmpty())
        assertClean(blank)
        blank.inviteText = link
        blank.answers.add(listOf(server))
        blank.retry!!.invoke()
        assertEquals(listOf(furl), blank.learnCalls)
        assertNull(blank.banner)
    }

    @Test
    fun retryAfterAParseFailUsesTheFieldAsItIsNow() {
        val host = Host("not-a-code")
        host.answers.add(listOf(server))
        val flow = SessionFlow(host)
        flow.join()
        assertEquals(Invite.GARBAGE_MSG, host.banner!!.message)
        assertNull(failNextLine(host.banner!!.next))
        assertTrue("a broken paste must not reach learn", host.learnCalls.isEmpty())
        assertTrue(host.redeemCalls.isEmpty())
        host.inviteText = link
        host.retry!!.invoke()
        assertEquals(1, host.learnCalls.size)
        assertEquals(1, host.saved.size)
    }

    @Test
    fun aJoinLinkDoesNotRedeem() {
        val host = Host(link)
        host.answers.add(listOf(server))
        SessionFlow(host).join()
        assertTrue(host.redeemCalls.isEmpty())
        assertEquals(listOf(furl), host.learnCalls)
        assertNull(host.banner)
    }

    @Test
    fun aShortCodeRedeemsThenLearnsAndABadAddressDoesNot() {
        val host = Host("7-Guitarist-Revenge")
        host.redeemAnswers.add(RedeemOutcome("ok", furl, listOf(2, 3, 3)))
        host.answers.add(listOf(server))
        SessionFlow(host).join()
        assertEquals(listOf("7-guitarist-revenge"), host.redeemCalls)
        assertEquals(listOf(furl), host.learnCalls)
        assertEquals(listOf(2, 3, 3), host.saved.single().shares)
        assertEquals(furl, host.saved.single().introducerFurl)
        assertNull(host.banner)
        assertEquals("7-Guitarist-Revenge", host.inviteText)

        val badShares = Host("7-guitarist-revenge")
        badShares.redeemAnswers.add(RedeemOutcome("ok", furl, listOf(3, 2, 3)))
        badShares.answers.add(listOf(server))
        SessionFlow(badShares).join()
        assertEquals(listOf(2, 3, 3), badShares.saved.single().shares)

        val badAddress = Host("7-guitarist-revenge")
        badAddress.redeemAnswers.add(RedeemOutcome("ok", "not-an-address", listOf(2, 3, 3)))
        SessionFlow(badAddress).join()
        assertTrue(badAddress.learnCalls.isEmpty())
        assertTrue(badAddress.saved.isEmpty())
        assertEquals(Invite.GARBAGE_MSG, badAddress.banner!!.message)
        assertEquals(Invite.NO_NEXT, badAddress.banner!!.next)
        assertEquals("7-guitarist-revenge", badAddress.inviteText)
    }

    @Test
    fun redeemFailuresDoNotLearnAndRetryCanRecover() {
        val cases = listOf(
            "expired" to FailBanner(Invite.CODE_EXPIRED, Invite.CODE_EXPIRED_NEXT),
            "rejected" to FailBanner(Invite.CODE_REJECTED, Invite.CODE_REJECTED_NEXT),
            "relay" to FailBanner(Invite.CODE_RELAY, Invite.CODE_RELAY_NEXT),
            "timeout" to FailBanner(Invite.CODE_TIMEOUT, Invite.CODE_TIMEOUT_NEXT),
            "mystery" to FailBanner(Invite.CODE_REJECTED, Invite.CODE_REJECTED_NEXT),
        )
        for ((status, banner) in cases) {
            val host = Host("7-guitarist-revenge")
            host.redeemAnswers.add(RedeemOutcome(status))
            SessionFlow(host).join()
            assertEquals(status, banner, host.banner)
            assertTrue(status, host.learnCalls.isEmpty())
            assertTrue(status, host.saved.isEmpty())
            assertEquals("7-guitarist-revenge", host.inviteText)
            assertClean(host)
            host.inviteText = link
            host.answers.add(listOf(server))
            host.retry!!.invoke()
            assertEquals(status, listOf(furl), host.learnCalls)
            assertEquals(status, listOf("7-guitarist-revenge"), host.redeemCalls)
            assertEquals(status, 1, host.saved.size)
            assertNull(status, host.banner)
        }
    }

    @Test
    fun retryOnAnExpiredCodeRedeemsAgainAndStillDoesNotLearn() {
        val host = Host("7-guitarist-revenge")
        host.redeemAnswers.add(RedeemOutcome("expired"))
        host.redeemAnswers.add(RedeemOutcome("expired"))
        SessionFlow(host).join()
        host.retry!!.invoke()
        assertEquals(listOf("7-guitarist-revenge", "7-guitarist-revenge"), host.redeemCalls)
        assertTrue(host.learnCalls.isEmpty())
        assertTrue(host.saved.isEmpty())
        assertEquals(Invite.CODE_EXPIRED, host.banner!!.message)
        assertEquals("7-guitarist-revenge", host.inviteText)
    }

    @Test
    fun nobodyAnsweredThenRetryLearnsWhenTheDesktopAnswers() {
        val host = Host("7-guitarist-revenge")
        host.redeemAnswers.add(RedeemOutcome("timeout"))
        host.redeemAnswers.add(RedeemOutcome("ok", furl, null))
        host.answers.add(listOf(server))
        SessionFlow(host).join()
        assertEquals(Invite.CODE_TIMEOUT, host.banner!!.message)
        assertTrue(host.learnCalls.isEmpty())
        host.retry!!.invoke()
        assertEquals(listOf(furl), host.learnCalls)
        assertEquals(listOf(2, 3, 3), host.saved.single().shares)
        assertNull(host.banner)
    }

    @Test
    fun aLearnFailureAfterRedeemShowsTheLearnCard() {
        val host = Host("7-guitarist-revenge")
        host.redeemAnswers.add(RedeemOutcome("ok", furl, listOf(2, 3, 3)))
        SessionFlow(host).join()
        assertEquals(FailBanner(Invite.JOIN_FAILED, Invite.JOIN_FAILED_NEXT), host.banner)
        assertEquals(listOf(furl), host.learnCalls)
        assertTrue(host.saved.isEmpty())
        assertClean(host)
    }

    @Test
    fun aThrownRedeemDoesNotShowTheExceptionAndDoesNotLearn() {
        val host = Host("7-guitarist-revenge")
        host.redeemThrows = IllegalStateException("pb://secret and could not join this friendnet")
        SessionFlow(host).join()
        assertEquals(Invite.CODE_RELAY, host.banner!!.message)
        assertEquals(Invite.CODE_RELAY_NEXT, host.banner!!.next)
        assertTrue(host.learnCalls.isEmpty())
        assertClean(host)
        assertFalse(host.banner!!.message.contains("secret"))
    }

    @Test
    fun aCancelledRedeemPaintsNothingAndDoesNotLearn() {
        val host = Host("7-guitarist-revenge")
        host.redeemThrows = kotlin.coroutines.cancellation.CancellationException("leave")
        SessionFlow(host).join()
        assertEquals(FailBanner("generic", ""), host.banner)
        assertTrue(host.learnCalls.isEmpty())
        assertTrue(host.saved.isEmpty())
    }

    @Test
    fun retryAfterALearnFailUsesTheFieldAsItIsNow() {
        val host = Host(link)
        val flow = SessionFlow(host)
        flow.join()
        assertEquals(Invite.JOIN_FAILED, host.banner!!.message)
        assertEquals(listOf(furl), host.learnCalls)
        val other = "pb://otherotheroth@127.0.0.1:45001/otherswiss"
        host.inviteText = other
        host.answers.add(listOf(server))
        host.retry!!.invoke()
        assertEquals(listOf(furl, other), host.learnCalls)
        assertEquals(other, host.saved.single().introducerFurl)
        assertNull(host.banner)
    }

    @Test
    fun refreshFailShowsRefreshCopyAndRetryRefreshes() {
        for (throws in listOf(false, true)) {
            val host = Host()
            host.session = Session(introducerFurl = furl, servers = listOf(server))
            if (throws) host.learnThrows = IllegalStateException("Introducer is unreachable. (TimeoutError)")
            val flow = SessionFlow(host)
            flow.refresh()
            assertEquals(FailBanner(Invite.JOIN_FAILED, Invite.REFRESH_FAILED_NEXT), host.banner)
            assertEquals(
                listOf(
                    "Couldn't reach your computer.",
                    "Next: Check that Leasegrid Sync is open on your computer and this phone is online, then tap Retry.",
                ),
                host.lines(),
            )
            assertNoPaste(host)
            assertClean(host)
            // Retry runs refresh (learn again for the saved session), not join.
            host.learnThrows = null
            host.answers.add(listOf(server, server))
            host.retry!!.invoke()
            assertEquals(listOf(furl, furl), host.learnCalls)
            assertNull(host.banner)
            assertEquals(2, host.saved.single().servers.size)
        }
    }

    @Test
    fun importThatSavedButCouldNotLearnReassures() {
        val host = Host()
        val flow = SessionFlow(host)
        launchNow {
            flow.finishImport(furl) { learned ->
                Session(introducerFurl = furl, folders = listOf(FolderRef("Photos", "URI:DIR2:x:y")), servers = learned ?: emptyList())
            }
        }
        assertEquals("Photos", host.saved.single().folders.single().name)
        assertEquals(
            FailBanner("Saved on this phone. Couldn't reach your computer to finish.", Invite.REFRESH_FAILED_NEXT),
            host.banner,
        )
        assertNoPaste(host)
        assertClean(host)
        host.answers.add(listOf(server))
        host.retry!!.invoke()
        assertEquals(listOf(furl, furl), host.learnCalls)
        assertEquals(listOf(server), host.session!!.servers)
    }

    @Test
    fun importWhoseSaveFailsDoesNotClaimTheNamesAreSaved() {
        val host = Host()
        host.saveThrows = IllegalStateException("disk full")
        val flow = SessionFlow(host)
        var thrown: Throwable? = null
        launchNow(onError = { thrown = it }) {
            flow.finishImport(furl) { learned -> Session(introducerFurl = furl, servers = learned ?: emptyList()) }
        }
        assertNotNull("the save failure reaches the caller's generic fail", thrown)
        assertNull(host.banner)
        assertTrue(host.saved.isEmpty())
    }

    @Test
    fun aCancelledImportSavesNothingAndALaterImportSaves() {
        val host = Host()
        host.learnThrows = kotlin.coroutines.cancellation.CancellationException("stop")
        var escaped: Throwable? = null
        launchNow(onError = { escaped = it }) {
            SessionFlow(host).finishImport(furl) {
                Session(introducerFurl = furl, servers = emptyList())
            }
        }
        assertTrue(escaped is kotlin.coroutines.cancellation.CancellationException)
        assertTrue(host.saved.isEmpty())
        assertNull(host.banner)
        host.learnThrows = null
        host.answers.add(listOf(server))
        launchNow {
            SessionFlow(host).finishImport(furl) { learned ->
                Session(introducerFurl = furl, servers = learned ?: emptyList())
            }
        }
        assertEquals(1, host.saved.size)
        assertEquals(listOf(server), host.session!!.servers)
        assertNull(host.banner)
    }

    @Test
    fun importThatLearnedShowsNoBanner() {
        val host = Host()
        host.answers.add(listOf(server))
        launchNow { SessionFlow(host).finishImport(furl) { learned -> Session(introducerFurl = furl, servers = learned!!) } }
        assertNull(host.banner)
        assertEquals(listOf(server), host.session!!.servers)
    }

    private fun launchNow(onError: (Throwable) -> Unit = { fail("unexpected: $it") }, block: suspend () -> Unit) {
        block.startCoroutine(Continuation(EmptyCoroutineContext) { r -> r.exceptionOrNull()?.let(onError) })
    }
}
