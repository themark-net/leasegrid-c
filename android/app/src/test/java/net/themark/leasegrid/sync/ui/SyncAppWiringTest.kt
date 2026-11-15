package net.themark.leasegrid.sync.ui

import java.io.File
import org.junit.Assert.assertEquals
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
}
