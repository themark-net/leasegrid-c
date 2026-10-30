package net.themark.leasegrid.sync.ui

import kotlin.coroutines.Continuation
import kotlin.coroutines.EmptyCoroutineContext
import kotlin.coroutines.startCoroutine
import net.themark.leasegrid.sync.invite.Invite
import net.themark.leasegrid.sync.invite.ParsedInvite
import net.themark.leasegrid.sync.invite.bannedWords
import net.themark.leasegrid.sync.session.ServerRef
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

// #50 B2: what a failed learn() puts on screen, and what Retry does. Pure JVM fakes.
class JoinFlowTest {
    private val link = "leasegrid:join#v=1&i=pb://hashhashhash@127.0.0.1:45001/swissnumswiss&n=2&h=3&t=3"

    private class Screen {
        var banner: FailBanner? = null
        var retry: (() -> Unit)? = null
        val joined = mutableListOf<List<ServerRef>>()
        val learnCalls = mutableListOf<String>()

        fun lines(): List<String> {
            val b = banner ?: return emptyList()
            return listOfNotNull(b.message, failNextLine(b.next))
        }
    }

    private fun flow(screen: Screen, field: () -> String, learn: suspend (String) -> List<ServerRef>?) = JoinFlow(
        text = field,
        launch = { block -> block.startCoroutine(Continuation(EmptyCoroutineContext) { it.getOrThrow() }) },
        learn = { furl ->
            screen.learnCalls += furl
            learn(furl)
        },
        show = { banner, again ->
            screen.banner = banner
            screen.retry = again
        },
        joined = { _: ParsedInvite, servers -> screen.joined += servers },
    )

    private fun assertJoinFailedCard(screen: Screen) {
        assertEquals(FailBanner(Invite.JOIN_FAILED, Invite.JOIN_FAILED_NEXT), screen.banner)
        assertEquals(listOf("Couldn't reach your computer.", "Next: ${Invite.JOIN_FAILED_NEXT}"), screen.lines())
        for (line in screen.lines()) {
            assertEquals(line, emptyList<String>(), bannedWords(line))
        }
    }

    @Test
    fun unreachableShowsJoinFailedAndRetryRerunsJoin() {
        val screen = Screen()
        var field = link
        val answers = ArrayDeque(listOf<List<ServerRef>?>(null, listOf(ServerRef("pb://s@h:1/x", "s1"))))
        val join = flow(screen, { field }) { answers.removeFirst() }
        join.join()
        assertJoinFailedCard(screen)
        assertEquals(1, screen.learnCalls.size)
        assertTrue(screen.joined.isEmpty())
        assertEquals(link, field)
        // Retry must rerun join with the invite (a refresh has no session yet and learns nothing).
        val retry = screen.retry
        assertNotNull(retry)
        screen.banner = null
        retry!!.invoke()
        assertEquals(2, screen.learnCalls.size)
        assertEquals(screen.learnCalls[0], screen.learnCalls[1])
        assertEquals(1, screen.joined.size)
        assertNull(screen.banner)
    }

    @Test
    fun timeoutThrowShowsTheSameCardNotTheRawError() {
        val screen = Screen()
        val join = flow(screen, { link }) {
            throw IllegalStateException("could not join this friendnet. Introducer is unreachable. (TimeoutError)")
        }
        join.join()
        assertJoinFailedCard(screen)
        assertTrue(screen.lines().none { it.contains("Timeout") || it.contains("Exception") })
    }

    @Test
    fun retryAfterAParseFailUsesTheFieldAsItIsNow() {
        val screen = Screen()
        var field = "7-guitarist-revenge"
        val join = flow(screen, { field }) { listOf(ServerRef("pb://s@h:1/x")) }
        join.join()
        assertEquals(Invite.WORMHOLE_MSG, screen.banner!!.message)
        assertNull(failNextLine(screen.banner!!.next))
        assertTrue("a short code never reaches learn", screen.learnCalls.isEmpty())
        field = link
        screen.retry!!.invoke()
        assertEquals(1, screen.learnCalls.size)
        assertEquals(1, screen.joined.size)
    }
}
