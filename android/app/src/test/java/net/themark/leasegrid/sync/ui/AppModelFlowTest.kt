package net.themark.leasegrid.sync.ui

import android.app.Application
import java.io.File
import kotlin.coroutines.CoroutineContext
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Runnable
import kotlinx.coroutines.SupervisorJob
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.addJsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import net.themark.leasegrid.sync.invite.Invite
import net.themark.leasegrid.sync.session.FolderRef
import net.themark.leasegrid.sync.session.ServerRef
import net.themark.leasegrid.sync.session.Session
import net.themark.leasegrid.sync.session.SessionStore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

/**
 * The real AppModel with a fake grid: join, import cancel, download cancel, and
 * what the fail card says when the grid bridge itself throws at each call site.
 */
class AppModelFlowTest {
    @get:Rule
    val tmp = TemporaryFolder()

    private val folder = FolderRef("Photos", "URI:DIR2:test-only", authorSeedB64 = "dGVzdC1vbmx5")
    private val introducer = "pb://test-only@127.0.0.1:1/swissnumswiss"
    private val learned = listOf(ServerRef("pb://test-only@127.0.0.1:2/storage", "s1"))

    private lateinit var home: File

    private fun model(
        saved: Session? = null,
        io: CoroutineContext = Dispatchers.Unconfined,
        grid: (String, String) -> JsonObject,
    ): AppModel {
        home = tmp.newFolder("home")
        if (saved != null) SessionStore(File(home, "leasegrid")).save(saved)
        return AppModel(
            Application(),
            AppSeams(
                filesDir = home,
                scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined),
                io = io,
                dispatch = grid,
                freeBytes = { Long.MAX_VALUE },
            ),
        )
    }

    private fun joined() = Session(introducerFurl = introducer, folders = listOf(folder), servers = learned)

    private fun learnReply() = buildJsonObject {
        put("ok", true)
        putJsonArray("servers") {
            for (server in learned) addJsonObject {
                put("furl", server.furl)
                put("nickname", server.nickname)
            }
        }
    }

    private fun stored(): Session? = SessionStore(File(home, "leasegrid")).load()

    private fun fixture(name: String): ByteArray =
        javaClass.classLoader!!.getResourceAsStream("recovery/$name")!!.use { it.readBytes() }

    // The bridge fails the way Chaquopy does: the exception text names a Python class and a furl.
    private val bridgeDown = IllegalStateException("FileNotFoundError: [Errno 2] pb://test-only@127.0.0.1:1/secret")

    private fun assertPlainCard(card: FailBanner?) {
        assertNotNull("no fail card", card)
        for (text in listOf(card!!.message, card.next)) {
            assertFalse(text, Regex("[A-Z][A-Za-z]*(Error|Exception)\\b").containsMatchIn(text))
            assertFalse(text, text.contains("pb://"))
            assertFalse(text, text.contains("Errno"))
        }
    }

    @Test
    fun joinSavesWhatTheGridLearnedAndKeepsTheTypedLink() {
        val ops = mutableListOf<String>()
        val model = model { op, _ ->
            ops += op
            learnReply()
        }
        model.acknowledged = true
        model.inviteText = introducer

        model.join()

        assertEquals(listOf("learn"), ops)
        assertEquals(Place.Folders, model.place)
        assertEquals(learned, model.session!!.servers)
        assertEquals(introducer, model.session!!.introducerFurl)
        assertEquals("the join was not written to the store", model.session, stored())
        assertEquals(introducer, model.inviteText)
        assertFalse(model.busy)
        assertNull(model.fail)
    }

    @Test
    fun aJoinThatCannotLearnShowsJoinFailedAndOneRetryJoins() {
        var calls = 0
        val model = model { _, _ ->
            calls += 1
            if (calls == 1) throw bridgeDown
            learnReply()
        }
        model.acknowledged = true
        model.inviteText = introducer

        model.join()

        assertEquals(Invite.JOIN_FAILED, model.fail?.message)
        assertPlainCard(model.fail)
        assertEquals(introducer, model.inviteText)
        assertNull(stored())
        model.retryFail()
        model.retryFail()
        assertEquals("two Retry taps should join once", 2, calls)
        assertEquals(learned, model.session?.servers)
        assertEquals(Place.Folders, model.place)
    }

    @Test
    fun cancelOnImportStopsTheImportSavesNothingAndStaysOnWelcome() {
        val io = IoQueue()
        val ops = mutableListOf<String>()
        val model = model(io = io) { op, _ ->
            ops += op
            learnReply()
        }
        model.goImport()
        model.onPicked("ok-plain.leasegrid-recovery", fixture("ok-plain.leasegrid-recovery"))
        model.importRecovery()
        assertTrue(model.busy)

        model.cancelImport()
        io.drain()

        assertEquals(Place.Welcome, model.place)
        assertNull("a cancelled import still saved a session", model.session)
        assertNull("a cancelled import still wrote the store", stored())
        assertEquals("a cancelled import still asked the grid", emptyList<String>(), ops)
        assertFalse(model.busy)
        assertNull(model.fail)
    }

    @Test
    fun anImportThatIsNotCancelledSavesAndOpensFolders() {
        val io = IoQueue()
        val model = model(io = io) { _, _ -> learnReply() }
        model.goImport()
        model.onPicked("ok-plain.leasegrid-recovery", fixture("ok-plain.leasegrid-recovery"))
        model.importRecovery()
        io.drain()
        io.drain()

        assertEquals(Place.Folders, model.place)
        assertEquals("Photos", model.session?.folders?.single()?.name)
        assertEquals(model.session, stored())
        assertFalse(model.busy)
    }

    @Test
    fun cancelDownloadStopsItAndItNeverLandsOnReady() {
        val io = IoQueue()
        var calls = 0
        val model = model(saved = joined(), io = io) { _, _ ->
            calls += 1
            buildJsonObject { put("ok", true) }
        }
        model.download("photo.jpg", "URI:CHK:test-only", folder)
        assertTrue(model.place is Place.Downloading)
        assertTrue(model.busy)

        model.cancelDownload()
        io.drain()

        assertEquals(Place.Folders, model.place)
        assertEquals("a cancelled download still called the grid", 0, calls)
        assertFalse(model.busy)
        assertNull(model.fail)
    }

    @Test
    fun aFolderLoadWhoseBridgeThrowsShowsPlainCopy() {
        val model = model(saved = joined()) { _, _ -> throw bridgeDown }
        model.openFolder(folder)
        assertEquals("could not complete that.", model.fail?.message)
        assertPlainCard(model.fail)
        assertFalse(model.busy)
    }

    @Test
    fun aDownloadWhoseBridgeThrowsShowsPlainCopy() {
        val model = model(saved = joined()) { _, _ -> throw bridgeDown }
        model.download("photo.jpg", "URI:CHK:test-only", folder)
        assertPlainCard(model.fail)
        assertFalse(model.place is Place.Ready)
    }

    @Test
    fun anAddWhoseBridgeThrowsShowsPlainCopy() {
        val ops = mutableListOf<String>()
        val model = model(saved = joined()) { op, _ ->
            ops += op
            throw bridgeDown
        }
        model.onFilePicked(folder, "notes.txt", byteArrayOf(1, 2, 3))
        assertEquals(listOf("put"), ops)
        assertEquals(WriteCopy.ADD_FAIL, model.fail?.message)
        assertPlainCard(model.fail)
    }

    @Test
    fun aRemoveWhoseBridgeThrowsShowsPlainCopy() {
        val ops = mutableListOf<String>()
        val model = model(saved = joined()) { op, _ ->
            ops += op
            if (op == "list") {
                buildJsonObject {
                    put("ok", true)
                    putJsonArray("children") {
                        addJsonObject {
                            put("name", "notes.txt")
                            put("kind", "file")
                            put("cap", "URI:CHK:test-only")
                            put("size", 3)
                        }
                    }
                }
            } else {
                throw bridgeDown
            }
        }
        model.openFolder(folder)
        model.askRemove("notes.txt", "URI:CHK:test-only")
        model.confirmRemove()
        assertEquals(listOf("list", "remove"), ops)
        assertEquals(WriteCopy.REMOVE_FAIL, model.fail?.message)
        assertPlainCard(model.fail)
    }
}

private class IoQueue : CoroutineDispatcher() {
    private val tasks = ArrayDeque<Runnable>()

    override fun dispatch(context: CoroutineContext, block: Runnable) {
        tasks.add(block)
    }

    fun drain() {
        while (tasks.isNotEmpty()) tasks.removeFirst().run()
    }
}
