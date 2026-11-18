package net.themark.leasegrid.sync.ui

import android.Manifest
import android.content.pm.PackageManager

/**
 * The camera-permission decisions behind Scan QR. MainActivity passes the raw
 * Android values in and hands the answers to AppModel, so a JVM test covers
 * them without an emulator.
 */
object CameraGate {
    /** The one permission Scan QR checks and asks for. */
    const val PERMISSION: String = Manifest.permission.CAMERA

    /** checkSelfPermission result. Only PERMISSION_GRANTED is a yes. */
    fun isGranted(checkResult: Int): Boolean = checkResult == PackageManager.PERMISSION_GRANTED

    /** The scanner's MISSING_CAMERA_PERMISSION extra. No intent or no extra is not a refusal. */
    fun scanRefused(missingPermissionExtra: Boolean?): Boolean = missingPermissionExtra == true
}
