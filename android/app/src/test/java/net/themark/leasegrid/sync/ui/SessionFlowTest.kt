package net.themark.leasegrid.sync.ui

import kotlin.coroutines.Continuation
import kotlin.coroutines.EmptyCoroutineContext
import kotlin.coroutines.startCoroutine
import net.themark.leasegrid.sync.invite.Invite
import net.themark.leasegrid.sync.invite.bannedWords
import net.themark.leasegrid.sync.session.FolderRef
import net.themark.leasegrid.sync.session.ServerRef
import net.themark.leasegrid.sync.session.Session
import org.junit.Assert.assertEquals
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
        val saved = mutableListOf<Session>()
        val answers = ArrayDeque<List<ServerRef>?>()
        var learnThrows: Exception? = null
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
        assertClean(host)
        assertTrue(host.saved.isEmpty())
        // Retry must rerun join with the invite (a refresh has no session yet and learns nothing).
        host.retry!!.invoke()
        assertEquals(listOf(furl, furl), host.learnCalls)
        assertEquals(1, host.saved.size)
        assertNull(host.banner)
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
    fun retryAfterAParseFailUsesTheFieldAsItIsNow() {
        val host = Host("7-guitarist-revenge")
        host.answers.add(listOf(server))
        val flow = SessionFlow(host)
        flow.join()
        assertEquals(Invite.WORMHOLE_MSG, host.banner!!.message)
        assertNull(failNextLine(host.banner!!.next))
        assertTrue("a short code never reaches learn", host.learnCalls.isEmpty())
        host.inviteText = link
        host.retry!!.invoke()
        assertEquals(1, host.learnCalls.size)
        assertEquals(1, host.saved.size)
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
            FailBanner("Folder names are on this phone. Couldn't reach your computer to finish.", Invite.REFRESH_FAILED_NEXT),
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
