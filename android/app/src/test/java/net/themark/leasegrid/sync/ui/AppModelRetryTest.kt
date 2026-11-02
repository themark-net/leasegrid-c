package net.themark.leasegrid.sync.ui

import android.app.Application
import java.io.File
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
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
 * Drives the real AppModel: a grid call fails, the fail card and its Retry
 * are on screen, and two Retry taps run the action once.
 * The grid is a fake. Coroutines run in place, so each tap finishes before the next.
 */
class AppModelRetryTest {
    @get:Rule
    val tmp = TemporaryFolder()

    private val folder = FolderRef("Photos", "URI:DIR2:test-only")

    private fun model(grid: (String, String) -> JsonObject): AppModel {
        val home = tmp.newFolder("home")
        SessionStore(File(home, "leasegrid")).save(
            Session(
                introducerFurl = "pb://test-only@127.0.0.1:1/intro",
                folders = listOf(folder),
                servers = listOf(ServerRef("pb://test-only@127.0.0.1:1/storage", "s1")),
            ),
        )
        return AppModel(
            Application(),
            AppSeams(
                filesDir = home,
                scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined),
                io = Dispatchers.Unconfined,
                dispatch = grid,
            ),
        )
    }

    @Test
    fun aFolderLoadThatThrowsShowsTheCardAndADoubleTapRetriesOnce() {
        var calls = 0
        val model = model { op, _ ->
            assertEquals("list", op)
            calls += 1
            if (calls == 1) throw IllegalStateException("grid down")
            buildJsonObject {
                put("ok", true)
                putJsonArray("children") { }
            }
        }

        model.openFolder(folder)

        val card = model.fail
        assertNotNull("a grid failure showed no fail card, so there is no Retry", card)
        assertEquals("could not complete that.", card!!.message)
        assertEquals(
            "Next: Retry. If it repeats, check the network and the invite.",
            failNextLine(card.next),
        )
        assertFalse(card.message.contains("IllegalStateException"))
        assertFalse("busy stayed on after the failure", model.busy)
        assertEquals(1, calls)

        model.retryFail()
        assertEquals("Retry did not run the folder load", 2, calls)
        model.retryFail()
        assertEquals("a second Retry tap ran the folder load again", 2, calls)
        assertNull(model.fail)
        assertEquals(Place.Folder(folder, emptyList()), model.place)
    }

    @Test
    fun aDownloadThatFailsShowsTheCardAndADoubleTapRetriesOnce() {
        var calls = 0
        val model = model { op, payload ->
            assertEquals("download", op)
            calls += 1
            if (calls == 1) {
                // What leasegrid_read.dispatch returns when the write fails.
                return@model buildJsonObject {
                    put("ok", false)
                    put("message", "could not download this file. Network error or not enough free space.")
                    put("next", "check network / free space; Retry.")
                }
            }
            val dest = Json.parseToJsonElement(payload).jsonObject["dest"]!!.jsonPrimitive.content
            File(dest).writeBytes(byteArrayOf(1, 2, 3))
            buildJsonObject { put("ok", true) }
        }

        model.download("photo.jpg", "URI:CHK:test-only", folder)

        val card = model.fail
        assertNotNull("a failed download showed no fail card, so there is no Retry", card)
        assertEquals("could not download this file. Network error or not enough free space.", card!!.message)
        assertEquals("Next: check network / free space; Retry.", failNextLine(card.next))
        assertFalse(model.busy)

        model.retryFail()
        model.retryFail()
        assertEquals("two Retry taps should run the download once", 2, calls)
        val ready = model.place
        assertTrue("download did not finish after Retry: $ready", ready is Place.Ready)
        assertEquals("photo.jpg", (ready as Place.Ready).name)
    }

    @Test
    fun aDownloadWhoseGridCallThrowsDoesNotNameTheClassAndRetriesOnce() {
        var calls = 0
        val model = model { _, payload ->
            calls += 1
            if (calls == 1) throw IllegalStateException("grid down")
            val dest = Json.parseToJsonElement(payload).jsonObject["dest"]!!.jsonPrimitive.content
            File(dest).writeBytes(byteArrayOf(1))
            buildJsonObject { put("ok", true) }
        }

        model.download("notes.txt", "URI:CHK:test-only", folder)

        val card = model.fail
        assertNotNull(card)
        assertEquals("check network / free space; Retry.", card!!.next)
        assertFalse(card.message.contains("IllegalStateException"))
        model.retryFail()
        model.retryFail()
        assertEquals(2, calls)
        assertTrue(model.place is Place.Ready)
    }

    @Test
    fun dismissThenRetryDoesNothing() {
        var calls = 0
        val model = model { _, _ ->
            calls += 1
            throw IllegalStateException("grid down")
        }
        model.openFolder(folder)
        assertNotNull(model.fail)
        model.dismissFail()
        model.retryFail()
        assertEquals("Retry after Dismiss ran the folder load", 1, calls)
        assertNull(model.fail)
    }
}
