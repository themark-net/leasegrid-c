package net.themark.leasegrid.sync.ui

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** The Scan QR permission line, without an Activity or an emulator. */
class CameraGateTest {
    @Test
    fun scanQrChecksAndAsksForTheCameraPermission() {
        assertEquals("android.permission.CAMERA", CameraGate.PERMISSION)
    }

    @Test
    fun onlyPermissionGrantedIsAYes() {
        assertTrue(CameraGate.isGranted(0))
        assertFalse(CameraGate.isGranted(-1))
        assertFalse(CameraGate.isGranted(1))
    }

    @Test
    fun onlyTheMissingPermissionExtraIsARefusal() {
        assertTrue(CameraGate.scanRefused(true))
        assertFalse(CameraGate.scanRefused(false))
        assertFalse(CameraGate.scanRefused(null))
    }

    private fun activitySource(): String {
        val file = listOf(
            File("src/main/java/net/themark/leasegrid/sync/MainActivity.kt"),
            File("app/src/main/java/net/themark/leasegrid/sync/MainActivity.kt"),
        ).firstOrNull { it.isFile } ?: error("MainActivity.kt not found from ${File(".").absolutePath}")
        return file.readText()
    }

    @Test
    fun mainActivityOnlyPassesAndroidValuesToTheGate() {
        val text = activitySource()
        assertTrue(text.contains("CameraGate.isGranted(ContextCompat.checkSelfPermission(this, CameraGate.PERMISSION))"))
        assertTrue(text.contains("askCamera.launch(CameraGate.PERMISSION)"))
        assertTrue(text.contains("CameraGate.scanRefused(result.originalIntent?.hasExtra(Intents.Scan.MISSING_CAMERA_PERMISSION))"))
        assertFalse("the Activity must not compare permission results itself", text.contains("PERMISSION_GRANTED"))
        assertFalse("the Activity must not name the camera permission itself", text.contains("Manifest.permission.CAMERA"))
    }
}
