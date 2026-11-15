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
        scopeDispatcher: CoroutineDispatcher = Dispatchers.Unconfined,
        grid: (String, String) -> JsonObject,
    ): AppModel {
        home = tmp.newFolder("home")
        if (saved != null) SessionStore(File(home, "leasegrid")).save(saved)
        return AppModel(
            Application(),
            AppSeams(
                filesDir = home,
                scope = CoroutineScope(SupervisorJob() + scopeDispatcher),
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
    fun aRefreshThatCannotLearnShowsTheRefreshNextLineAndOneRetryRefreshes() {
        var calls = 0
        val model = model(saved = joined()) { _, _ ->
            calls += 1
            if (calls == 1) throw bridgeDown
            learnReply()
        }

        model.refresh()

        assertEquals(Invite.JOIN_FAILED, model.fail?.message)
        assertEquals(Invite.REFRESH_FAILED_NEXT, model.fail?.next)
        assertPlainCard(model.fail)
        assertEquals(Place.Folders, model.place)
        assertEquals(joined().servers, model.session?.servers)
        model.retryFail()
        model.retryFail()
        assertEquals("two Retry taps should refresh once", 2, calls)
        assertEquals(learned, model.session?.servers)
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

    @Test
    fun unexpectedRetryAfterASaveFailureJoinsTheFieldAsItIsNow() {
        val first = "pb://test-only@127.0.0.1:1/swissnumswiss"
        val second = "pb://test-only@127.0.0.1:9/otherswiss"
        val learned = mutableListOf<String>()
        val model = model { op, payload ->
            assertEquals("learn", op)
            learned += payload
            learnReply()
        }
        model.acknowledged = true
        model.inviteText = first
        // learn succeeds, then save throws: the store path is a file, not a directory.
        val storeDir = File(home, "leasegrid")
        assertTrue(storeDir.delete() || !storeDir.exists())
        assertTrue(storeDir.createNewFile())

        model.join()

        assertEquals("could not complete that.", model.fail?.message)
        assertNull(model.session)
        assertEquals(1, learned.size)
        assertTrue(learned.single().contains(first))

        assertTrue(storeDir.delete())
        model.inviteText = second
        model.retryFail()

        assertEquals(2, learned.size)
        assertTrue("Retry learned the text from the first tap, not the field now", learned[1].contains(second))
        assertFalse(learned[1].contains(first))
        assertEquals(second, model.session?.introducerFurl)
        assertEquals(Place.Folders, model.place)
        assertNull(model.fail)
    }

    @Test
    fun aJoinTapKeepsTheTextFromTheTapWhenTheFieldChangesBeforeTheJobStarts() {
        val queue = IoQueue()
        val first = "pb://test-only@127.0.0.1:1/swissnumswiss"
        val second = "pb://test-only@127.0.0.1:9/otherswiss"
        val learned = mutableListOf<String>()
        val model = model(scopeDispatcher = queue) { _, payload ->
            learned += payload
            learnReply()
        }
        model.acknowledged = true
        model.inviteText = first
        model.join()
        assertTrue("the job started before the queue ran", learned.isEmpty())
        model.inviteText = second
        queue.drain()
        assertEquals(1, learned.size)
        assertTrue(learned.single().contains(first))
        assertFalse("a change before the job started replaced the tap", learned.single().contains(second))
        assertEquals(first, model.session?.introducerFurl)
    }

    @Test
    fun aPendingAddSurvivesProcessDeathAndRetrySendsIt() {
        home = tmp.newFolder("phone")
        SessionStore(File(home, "leasegrid")).save(joined())
        val queue = IoQueue()
        val puts = mutableListOf<String>()
        val grid = { op: String, _: String ->
            puts += op
            if (op == "list") {
                buildJsonObject {
                    put("ok", true)
                    putJsonArray("children") {}
                }
            } else {
                buildJsonObject {
                    put("ok", true)
                    put("cap", "URI:CHK:landed")
                    put("size", 3)
                }
            }
        }
        val first = AppModel(
            Application(),
            AppSeams(
                filesDir = home,
                scope = CoroutineScope(SupervisorJob() + queue),
                io = Dispatchers.Unconfined,
                dispatch = grid,
                freeBytes = { Long.MAX_VALUE },
            ),
        )
        first.onFilePicked(folder, "notes.txt", byteArrayOf(1, 2, 3))
        assertEquals("the upload should still be pending when the process dies", emptyList<String>(), puts)

        val second = AppModel(
            Application(),
            AppSeams(
                filesDir = home,
                scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined),
                io = Dispatchers.Unconfined,
                dispatch = grid,
                freeBytes = { Long.MAX_VALUE },
            ),
        )
        second.openFolder(folder)
        val open = second.place as Place.Folder
        val pending = second.visibleFiles(open).filter { it.chip == Chip.Pending }
        assertEquals("the add disappeared with the process", listOf("notes.txt"), pending.map { it.name })
        assertTrue(pending.single().failed)
        assertEquals(listOf("Retry", "Cancel"), rowActions(writable = true, pending.single()))
        second.retryUpload("notes.txt")
        assertTrue("Retry did not send the file", puts.contains("put"))
        assertFalse(second.visibleFiles(second.place as Place.Folder).any { it.chip == Chip.Pending && it.failed })
    }

    @Test
    fun aLeftoverPendingIndexTempDoesNotBecomeTheAdd() {
        home = tmp.newFolder("phone")
        SessionStore(File(home, "leasegrid")).save(joined())
        val queue = IoQueue()
        val grid = { op: String, _: String ->
            if (op == "list") {
                buildJsonObject {
                    put("ok", true)
                    putJsonArray("children") {}
                }
            } else {
                buildJsonObject {
                    put("ok", true)
                    put("cap", "URI:CHK:landed")
                    put("size", 3)
                }
            }
        }
        fun phone(dispatcher: CoroutineDispatcher = Dispatchers.Unconfined) = AppModel(
            Application(),
            AppSeams(
                filesDir = home,
                scope = CoroutineScope(SupervisorJob() + dispatcher),
                io = Dispatchers.Unconfined,
                dispatch = grid,
                freeBytes = { Long.MAX_VALUE },
            ),
        )
        val first = phone(queue)
        first.onFilePicked(folder, "notes.txt", byteArrayOf(1, 2, 3))
        val other = File(home, "pending/other.txt")
        other.parentFile!!.mkdirs()
        other.writeBytes(byteArrayOf(9))
        val temp = File(home, "leasegrid/pending-adds.json.tmp")
        temp.writeText(
            """{"rows":[{"folderCap":"URI:DIR2:test-only","name":"other.txt","size":1,"path":"pending/other.txt"}]}""",
        )
        val second = phone()
        second.openFolder(folder)
        val names = second.visibleFiles(second.place as Place.Folder)
            .filter { it.chip == Chip.Pending }
            .map { it.name }
        assertEquals(listOf("notes.txt"), names)
        assertFalse("a torn index temp was left next to the saved index", temp.exists())
    }

    @Test
    fun aClashQuestionSurvivesProcessDeathAndDoesNotUploadUntilReplace() {
        val puts = mutableListOf<String>()
        val first = phoneWithNotes(puts)
        first.openFolder(folder)
        assertTrue("the folder did not open", first.place is Place.Folder)
        first.onFilePicked(folder, "notes.txt", byteArrayOf(1, 2, 3))
        val sheet = first.writeSheet() as? WriteSheet.Clash
        assertNotNull("the phone did not ask what to do with the existing file", sheet)
        assertEquals("notes.txt", sheet!!.name)
        assertTrue(File(sheet.localPath).isFile)
        assertFalse("the question uploaded before a choice", puts.contains("put"))

        val second = phoneWithNotes(puts)
        val again = second.writeSheet() as? WriteSheet.Clash
        assertNotNull("the question disappeared with the process", again)
        assertEquals("notes.txt", again!!.name)
        assertEquals(sheet.folder, again.folder)
        assertTrue(File(again.localPath).isFile)
        assertFalse("a restored question uploaded on its own", puts.contains("put"))
        second.replaceClash()
        assertTrue("Replace did not send the file", puts.contains("put"))
    }

    @Test
    fun aRestoredClashCancelDeletesTheCopyAndDoesNotUpload() {
        val puts = mutableListOf<String>()
        val first = phoneWithNotes(puts)
        first.openFolder(folder)
        first.onFilePicked(folder, "notes.txt", byteArrayOf(1, 2, 3))
        val kept = (first.writeSheet() as? WriteSheet.Clash)?.localPath
        assertNotNull(kept)

        val second = phoneWithNotes(puts)
        assertNotNull("the question disappeared with the process", second.writeSheet())
        second.cancelClash()
        assertFalse("Cancel uploaded the file", puts.contains("put"))
        assertFalse(File(kept!!).isFile)

        val third = phoneWithNotes(puts)
        assertNull("Cancel came back after the process died", third.writeSheet())
        assertFalse(puts.contains("put"))
    }

    @Test
    fun aClashPathOutsideThePhoneFilesIsDroppedAndNotUploaded() {
        home = tmp.newFolder("phone")
        SessionStore(File(home, "leasegrid")).save(joined())
        val outside = File(tmp.root, "secret.txt")
        outside.writeBytes(byteArrayOf(9, 9, 9, 9))
        val index = File(home, "leasegrid/pending-adds.json")
        index.parentFile!!.mkdirs()
        index.writeText(
            """{"rows":[],"clash":{"folder":"Photos","folderCap":"URI:DIR2:test-only","name":"notes.txt","path":"../secret.txt","size":4}}""",
        )
        val puts = mutableListOf<String>()
        val model = AppModel(
            Application(),
            AppSeams(
                filesDir = home,
                scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined),
                io = Dispatchers.Unconfined,
                dispatch = { op, _ ->
                    puts += op
                    buildJsonObject { put("ok", true) }
                },
                freeBytes = { Long.MAX_VALUE },
            ),
        )
        assertNull("a path outside the phone files was offered as a choice", model.writeSheet())
        model.replaceClash()
        assertFalse("Replace uploaded a file outside the phone files", puts.contains("put"))
        assertEquals(4, outside.length())
    }

    private fun phoneWithNotes(puts: MutableList<String>): AppModel {
        if (!::home.isInitialized) {
            home = tmp.newFolder("phone")
            SessionStore(File(home, "leasegrid")).save(joined())
        }
        return AppModel(
            Application(),
            AppSeams(
                filesDir = home,
                scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined),
                io = Dispatchers.Unconfined,
                dispatch = { op, _ ->
                    puts += op
                    if (op == "list") {
                        buildJsonObject {
                            put("ok", true)
                            putJsonArray("children") {
                                addJsonObject {
                                    put("name", "notes.txt")
                                    put("kind", "file")
                                    put("cap", "URI:CHK:old")
                                    put("size", 1)
                                }
                            }
                        }
                    } else {
                        buildJsonObject {
                            put("ok", true)
                            put("cap", "URI:CHK:landed")
                            put("size", 3)
                        }
                    }
                },
                freeBytes = { Long.MAX_VALUE },
            ),
        )
    }

    @Test
    fun aPendingDirThePhoneCannotWriteSaysPermissionAndRetryWrites() {
        val puts = mutableListOf<String>()
        val model = model(saved = joined()) { op, _ ->
            puts += op
            buildJsonObject {
                put("ok", true)
                put("cap", "URI:CHK:landed")
                put("size", 3)
            }
        }
        val pending = File(home, "pending")
        pending.mkdirs()
        assertTrue(pending.setWritable(false, false))
        try {
            model.onFilePicked(folder, "notes.txt", byteArrayOf(1, 2, 3))
        } finally {
            pending.setWritable(true, true)
        }
        val card = model.fail
        assertNotNull(card)
        assertTrue(card!!.message.lowercase(), card.message.lowercase().contains("would not allow"))
        assertTrue(card.next.lowercase(), card.next.lowercase().contains("permission"))
        assertFalse(card.message.lowercase().contains("network"))
        assertPlainCard(card)
        assertFalse("the blocked write still uploaded", puts.contains("put"))
        model.retryFail()
        assertTrue("Retry did not write the file after the folder was writable", puts.contains("put"))
    }

    @Test
    fun aCancelledImportRejectsTheReadThatStartedBeforeCancel() {
        val model = model(saved = joined()) { _, _ -> learnReply() }
        val epoch = model.beginRecoveryImport()
        assertEquals(Place.Import, model.place)
        assertTrue(model.recoveryReadCurrent(epoch))
        model.cancelImport()
        assertEquals(Place.Welcome, model.place)
        assertFalse(model.recoveryReadCurrent(epoch))
        model.goImport()
        assertFalse("a later Import still accepted the cancelled read", model.recoveryReadCurrent(epoch))
    }

    @Test
    fun cancelImportDisarmsRetry() {
        var calls = 0
        val model = model { _, _ -> learnReply() }
        model.reportFail("could not import this recovery key.", "Retry.") { calls += 1 }
        model.cancelImport()
        model.retryFail()
        assertEquals(0, calls)
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
