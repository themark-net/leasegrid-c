package net.themark.leasegrid.sync.ui

import android.Manifest
import android.app.Application
import android.content.pm.PackageManager
import com.google.zxing.client.android.Intents
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import net.themark.leasegrid.sync.invite.Invite
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

/**
 * #90 A6/A7 and F1: the Scan QR path from MainActivity's Android calls to what
 * the user sees, run against the real AppModel instead of reading source text.
 */
class ScanQrWiringTest {
    @get:Rule
    val tmp = TemporaryFolder()

    private val checked = mutableListOf<String>()
    private val requested = mutableListOf<String>()
    private val extrasRead = mutableListOf<String>()
    private var scannerOpens = 0
    private val grid = mutableListOf<String>()

    private val model: AppModel by lazy {
        AppModel(
            Application(),
            AppSeams(
                filesDir = tmp.newFolder("home"),
                scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined),
                io = Dispatchers.Unconfined,
                dispatch = { op, _ ->
                    grid += op
                    buildJsonObject { put("ok", true) }
                },
            ),
        )
    }

    /** MainActivity's wiring, with [permissionResult] as checkSelfPermission's answer. */
    private fun wiring(permissionResult: Int = PackageManager.PERMISSION_DENIED) = ScanQrWiring(
        model = { model },
        checkPermission = { name ->
            checked += name
            permissionResult
        },
        requestPermission = { name -> requested += name },
        launchScanner = { scannerOpens++ },
    )

    private fun assertDeniedCard() {
        assertEquals(Invite.SCAN_DENIED_MSG, model.fail?.message)
        assertEquals(Invite.SCAN_DENIED_NEXT, model.fail?.next)
    }

    @Test
    fun tapWithTheCameraAllowedOpensTheScannerAndAsksNothing() {
        wiring(PackageManager.PERMISSION_GRANTED).onScanTapped()
        assertEquals(listOf(Manifest.permission.CAMERA), checked)
        assertEquals(1, scannerOpens)
        assertEquals(emptyList<String>(), requested)
        assertNull(model.fail)
    }

    @Test
    fun tapWithoutTheCameraAsksForTheCameraOnceAndKeepsTheScannerShut() {
        wiring(PackageManager.PERMISSION_DENIED).onScanTapped()
        assertEquals(listOf(Manifest.permission.CAMERA), checked)
        assertEquals(listOf(Manifest.permission.CAMERA), requested)
        assertEquals(0, scannerOpens)
        assertNull(model.fail)
    }

    @Test
    fun yesToTheCameraPromptOpensTheScanner() {
        wiring().onPermissionAnswer(true)
        assertEquals(1, scannerOpens)
        assertNull(model.fail)
        assertEquals(emptyList<String>(), requested)
    }

    @Test
    fun noToTheCameraPromptShowsTheDeniedCardAndNoScanner() {
        wiring().onPermissionAnswer(false)
        assertEquals(0, scannerOpens)
        assertDeniedCard()
        assertTrue("a refusal has nothing to retry", !model.canRetry)
    }

    @Test
    fun aScannerThatLostTheCameraShowsTheDeniedCard() {
        wiring().onScanResult(null) { key ->
            extrasRead += key
            key == Intents.Scan.MISSING_CAMERA_PERMISSION
        }
        assertEquals(listOf(Intents.Scan.MISSING_CAMERA_PERMISSION), extrasRead)
        assertDeniedCard()
        assertEquals("", model.inviteText)
    }

    @Test
    fun aCancelledScanWithNoResultIntentChangesNothing() {
        model.inviteText = "typed before the scan"
        wiring().onScanResult(null) { null }
        assertNull(model.fail)
        assertEquals("typed before the scan", model.inviteText)
        assertEquals(0, scannerOpens)
    }

    @Test
    fun aScannedCodeFillsTheInviteFieldAndJoinsNothingYet() {
        wiring().onScanResult("7-guitarist-revenge") { false }
        assertEquals("7-guitarist-revenge", model.inviteText)
        assertNull(model.fail)
        assertEquals(emptyList<String>(), grid)
    }
}
