package net.themark.leasegrid.sync.ui

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Cancel, the back arrow, and system Back on Import call [AppModel.cancelImport].
 * Compose is not executed here (`unitTests.isReturnDefaultValues`), so the
 * wiring is pinned as whole lines. T1c is the back arrow, T1d is Cancel.
 */
class SyncAppWiringTest {
    private fun source(): String {
        val candidates = listOf(
            File("src/main/java/net/themark/leasegrid/sync/ui/SyncApp.kt"),
            File("app/src/main/java/net/themark/leasegrid/sync/ui/SyncApp.kt"),
        )
        val file = candidates.firstOrNull { it.isFile }
            ?: error("SyncApp.kt not found from ${File(".").absolutePath}")
        return file.readText()
    }

    /** From [signature] up to the next top-level private fun, not including it. */
    private fun functionBody(source: String, signature: String): String {
        val start = source.indexOf(signature)
        assertTrue("missing $signature", start >= 0)
        val next = source.indexOf("\nprivate fun ", start + signature.length)
        return source.substring(start, if (next < 0) source.length else next)
    }

    @Test
    fun importCancelBackAndSystemBackCallCancelImport() {
        val text = source()
        val importFn = functionBody(text, "private fun Import(")
        val body = functionBody(text, "private fun ImportBody(")
        val lines = body.lines().map { it.trim() }
        // T1c
        assertTrue(
            lines.contains("TextButton(onClick = { model.cancelImport() }) { Text(\"←  Import recovery key\") }"),
        )
        // T1d
        assertTrue(
            lines.contains("OutlinedButton(onClick = { model.cancelImport() }, modifier = Modifier.fillMaxWidth()) { Text(\"Cancel\") }"),
        )
        // System back, only inside Import, and only that one call.
        val backs = text.lines().map { it.trim() }.filter { it.startsWith("BackHandler(") }
        assertEquals(listOf("BackHandler(onBack = { model.cancelImport() })"), backs)
        assertTrue(importFn.contains("BackHandler(onBack = { model.cancelImport() })"))
    }

    @Test
    fun scanQrButtonOnInviteCallsTheScanner() {
        val ui = source()
        val welcome = functionBody(ui, "private fun Welcome(")
        val lines = welcome.lines().map { it.trim() }
        assertTrue(
            lines.contains(
                "OutlinedButton(onClick = onScanQr, modifier = Modifier.fillMaxWidth()) { Text(Invite.SCAN_QR) }",
            ),
        )
        assertEquals(1, ui.lines().count { it.contains("Text(Invite.SCAN_QR)") })
        assertTrue(ui.contains("Place.Welcome -> Welcome(model, onPickRecovery, onScanQr)"))
        assertTrue(ui.contains("onScanQr: () -> Unit"))
        val activity = readRelative(
            "src/main/java/net/themark/leasegrid/sync/MainActivity.kt",
            "app/src/main/java/net/themark/leasegrid/sync/MainActivity.kt",
        )
        assertTrue(activity.contains("SyncApp(model, ::openRecoveryPicker, ::openAddPicker, ::openQrScanner)"))
        assertTrue(activity.contains("registerForActivityResult(ScanContract())"))
        assertTrue(activity.contains(".setDesiredBarcodeFormats(ScanOptions.QR_CODE)"))
        assertTrue(activity.contains(".setPrompt(Invite.SCAN_PROMPT)"))
        assertTrue(activity.contains(".setBeepEnabled(false)"))
        assertTrue(activity.contains(".setOrientationLocked(false)"))
        assertTrue(activity.contains("model.onScanned(result.contents)"))
        assertTrue(activity.contains("model.onScanDenied()"))
        assertTrue(activity.contains("Intents.Scan.MISSING_CAMERA_PERMISSION"))
        // #88 a: ask for the camera before the scanner opens.
        val opener = activity.substring(activity.indexOf("private fun openQrScanner()"))
            .substringBefore("\n    private fun ")
        assertTrue(opener, opener.contains("model.onScanTapped("))
        assertTrue(opener, opener.contains("Manifest.permission.CAMERA"))
        assertFalse("the scanner launches only from launchQrScanner", opener.contains("scanQr.launch("))
        assertTrue(activity.contains("registerForActivityResult(ActivityResultContracts.RequestPermission())"))
        assertTrue(activity.contains("model.onCameraAnswer(granted, ::launchQrScanner)"))
        assertEquals(1, activity.lines().count { it.contains("scanQr.launch(") })
        assertTrue(
            readRelative("src/main/AndroidManifest.xml", "app/src/main/AndroidManifest.xml")
                .contains("<uses-permission android:name=\"android.permission.CAMERA\" />"),
        )
        val manifest = readRelative("src/main/AndroidManifest.xml", "app/src/main/AndroidManifest.xml")
        assertTrue(manifest.contains("android:name=\"android.hardware.camera\" android:required=\"false\""))
        assertFalse(manifest.contains("android:name=\"android.hardware.camera\" android:required=\"true\""))
        assertTrue(manifest.contains("android:hardwareAccelerated=\"true\""))
        assertTrue(manifest.contains("android:screenOrientation=\"fullSensor\""))
        assertTrue(manifest.contains("tools:replace=\"screenOrientation\""))
    }

    @Test
    fun theFailCardOffersRetryOnlyWhenThereIsSomethingToRetry() {
        val card = functionBody(source(), "private fun FailCard(")
        val lines = card.lines().map { it.trim() }
        val gate = lines.indexOf("if (model.canRetry) {")
        val retry = lines.indexOf("Button(onClick = { model.retryFail() }) { Text(\"Retry\") }")
        val dismiss = lines.indexOf("OutlinedButton(onClick = { model.dismissFail() }) { Text(\"Dismiss\") }")
        assertTrue(card, gate >= 0 && retry == gate + 1)
        assertTrue("Dismiss stays outside the Retry gate", dismiss > retry + 1)
        assertEquals(1, card.lines().count { it.contains("model.retryFail()") })
    }

    private fun readRelative(vararg paths: String): String {
        val file = paths.map { File(it) }.firstOrNull { it.isFile }
            ?: error("${paths.first()} not found from ${File(".").absolutePath}")
        return file.readText()
    }
}
