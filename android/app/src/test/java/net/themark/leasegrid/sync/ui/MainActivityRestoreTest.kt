package net.themark.leasegrid.sync.ui

import java.io.File
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Rotation and process death build a new activity. The launch intent is still
 * the recovery VIEW that called beginRecoveryImport. Applying it again wipes
 * the joined home and cancels a transfer that is still pending.
 * Compose and the activity are not started here.
 */
class MainActivityRestoreTest {
    private fun source(): String {
        val candidates = listOf(
            File("src/main/java/net/themark/leasegrid/sync/MainActivity.kt"),
            File("app/src/main/java/net/themark/leasegrid/sync/MainActivity.kt"),
        )
        val file = candidates.firstOrNull { it.isFile }
            ?: error("MainActivity.kt not found from ${File(".").absolutePath}")
        return file.readText()
    }

    private fun functionBody(source: String, signature: String): String {
        val start = source.indexOf(signature)
        assertTrue("missing $signature", start >= 0)
        val next = source.indexOf("\n    override fun ", start + signature.length)
        val nextPrivate = source.indexOf("\n    private fun ", start + signature.length)
        val end = listOf(next, nextPrivate).filter { it >= 0 }.minOrNull() ?: source.length
        return source.substring(start, end)
    }

    @Test
    fun rotationRestoresTheDeliveryTokenBeforeTheIntentIsApplied() {
        val text = source()
        val onCreate = functionBody(text, "override fun onCreate")
        val restored = onCreate.indexOf("savedInstanceState?.getString")
        val noted = onCreate.indexOf("noteIntent")
        assertTrue("onCreate applies the intent before it restores the delivery token", restored in 0 until noted)
        val save = functionBody(text, "override fun onSaveInstanceState")
        assertTrue(text.contains("DogfoodIntents.deliveryToken"))
        assertTrue(save.contains("appliedToken"))
        assertTrue("the saved state must be the token, not the raw invite", !save.contains("EXTRA_INVITE"))
        assertTrue("the saved state must be the token, not the recovery path", !save.contains("EXTRA_RECOVERY_FILE"))
    }

    @Test
    fun aLateRecoveryReadChecksThatCancelHasNotRetiredIt() {
        val read = functionBody(source(), "private fun readRecoveryFile")
        assertTrue(read.contains("if (!model.recoveryReadCurrent(epoch)) return"))
    }
}
