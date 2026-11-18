package net.themark.leasegrid.sync.ui

import com.google.zxing.client.android.Intents

/**
 * Scan QR wiring between MainActivity and AppModel. MainActivity hands in its
 * Android calls and forwards each callback value unchanged, so a JVM test drives
 * the tap, the permission check, the permission answer and the scan result
 * against the real AppModel.
 */
class ScanQrWiring(
    private val model: () -> AppModel,
    private val checkPermission: (String) -> Int,
    private val requestPermission: (String) -> Unit,
    private val launchScanner: () -> Unit,
) {
    /** Scan QR tapped: open the scanner if the camera is allowed, otherwise ask for it. */
    fun onScanTapped() {
        model().onScanTapped(
            cameraGranted = CameraGate.isGranted(checkPermission(CameraGate.PERMISSION)),
            launchScanner = launchScanner,
            askCamera = { requestPermission(CameraGate.PERMISSION) },
        )
    }

    /** The camera prompt's answer, passed in unchanged. */
    fun onPermissionAnswer(granted: Boolean) {
        model().onCameraAnswer(granted, launchScanner)
    }

    /** The scanner's result. [hasExtra] reads the result intent and is null when there is none. */
    fun onScanResult(contents: String?, hasExtra: (String) -> Boolean?) {
        model().onScanResult(
            contents = contents,
            missingCameraPermission = CameraGate.scanRefused(hasExtra(Intents.Scan.MISSING_CAMERA_PERMISSION)),
        )
    }
}
