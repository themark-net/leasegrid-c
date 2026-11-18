package net.themark.leasegrid.sync.ui

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
    fun onScanTapped() {
    }

    fun onPermissionAnswer(granted: Boolean) {
    }

    fun onScanResult(contents: String?, hasExtra: (String) -> Boolean?) {
    }
}
