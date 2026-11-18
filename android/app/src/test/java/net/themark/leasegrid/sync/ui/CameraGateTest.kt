package net.themark.leasegrid.sync.ui

import android.content.pm.PackageManager
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
        assertTrue(CameraGate.isGranted(PackageManager.PERMISSION_GRANTED))
        assertFalse(CameraGate.isGranted(PackageManager.PERMISSION_DENIED))
        assertFalse(CameraGate.isGranted(PackageManager.PERMISSION_GRANTED + 1))
    }

    @Test
    fun onlyTheMissingPermissionExtraIsARefusal() {
        assertTrue(CameraGate.scanRefused(true))
        assertFalse(CameraGate.scanRefused(false))
        assertFalse(CameraGate.scanRefused(null))
    }
}
