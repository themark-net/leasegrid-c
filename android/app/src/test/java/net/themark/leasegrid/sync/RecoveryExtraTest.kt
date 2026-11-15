package net.themark.leasegrid.sync

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files

/**
 * EXTRA_RECOVERY_FILE at the first read, before any retry.
 * A relative name inside the app files dir loads the same bytes as the absolute path.
 * A path that leaves that dir, relative or absolute, including through a symlink, must not return those bytes.
 */
class RecoveryExtraTest {
    @Test
    fun relativeNameInTheAppFilesDirLoadsTheSameBytesAsTheAbsolutePath() {
        val base = scratch()
        try {
            val name = "ok-plain.leasegrid-recovery"
            val seeded = File(base, name)
            seeded.writeBytes("plain-bundle".toByteArray())
            val relative = DogfoodIntents.readRecoverySeed(DogfoodIntents.recoveryFile(base, name))
            val absolute = DogfoodIntents.readRecoverySeed(
                DogfoodIntents.recoveryFile(base, seeded.absolutePath),
            )
            assertTrue(relative.readable)
            assertEquals("plain-bundle", relative.bytes!!.decodeToString())
            assertTrue(relative.bytes.contentEquals(absolute.bytes))
            assertEquals(name, absolute.name)
            val dotted = DogfoodIntents.readRecoverySeed(DogfoodIntents.recoveryFile(base, "./$name"))
            assertTrue(dotted.bytes!!.contentEquals(relative.bytes))
            val nestedDir = File(base, "sub")
            nestedDir.mkdirs()
            File(nestedDir, name).writeBytes("nested-bundle".toByteArray())
            val nested = DogfoodIntents.readRecoverySeed(DogfoodIntents.recoveryFile(base, "sub/$name"))
            assertEquals("nested-bundle", nested.bytes!!.decodeToString())
            val dots = File(base, "foo..bar.leasegrid-recovery")
            dots.writeBytes("dots-bundle".toByteArray())
            val dottedName = DogfoodIntents.readRecoverySeed(DogfoodIntents.recoveryFile(base, dots.name))
            assertEquals("dots-bundle", dottedName.bytes!!.decodeToString())
            val loaded = DogfoodIntents.loadRecoveryExtra(base, name)
            assertTrue(loaded.opensImport)
            assertFalse(loaded.rejected)
            assertEquals("plain-bundle", loaded.bytes!!.decodeToString())
            assertNull(loaded.banner)
            val missing = DogfoodIntents.loadRecoveryExtra(base, "missing.leasegrid-recovery")
            assertTrue(missing.opensImport)
            assertFalse(missing.rejected)
            assertNull(missing.bytes)
            assertEquals(DogfoodIntents.RECOVERY_MISS_BANNER, missing.banner)
            assertEquals(DogfoodIntents.RECOVERY_MISS_NEXT, missing.next)
            val nul = DogfoodIntents.loadRecoveryExtra(base, "ok\u0000name")
            assertTrue(nul.rejected)
            assertNull(nul.bytes)
            assertEquals(DogfoodIntents.RECOVERY_REJECT_BANNER, nul.banner)
        } finally {
            base.deleteRecursively()
        }
    }

    @Test
    fun absolutePathOutsideTheAppFilesDirIsRejectedAndNotRead() {
        val parent = scratch()
        try {
            val base = File(parent, "files").also { it.mkdirs() }
            val outside = File(parent, "elsewhere.leasegrid-recovery")
            outside.writeBytes("abs-bundle".toByteArray())
            val pointed = DogfoodIntents.recoveryFile(base, outside.absolutePath)
            assertFalse(pointed.canonicalFile == outside.canonicalFile)
            assertTrue(pointed.canonicalPath.startsWith(base.canonicalPath))
            val loaded = DogfoodIntents.readRecoverySeed(pointed)
            assertFalse(loaded.readable)
            assertNull(loaded.bytes)
            val viaLoad = DogfoodIntents.loadRecoveryExtra(base, outside.absolutePath)
            assertTrue(viaLoad.opensImport)
            assertTrue(viaLoad.rejected)
            assertNull(viaLoad.bytes)
            val banner = viaLoad.banner
            assertEquals(DogfoodIntents.RECOVERY_REJECT_BANNER, banner)
            assertEquals(DogfoodIntents.RECOVERY_REJECT_NEXT, viaLoad.next)
            assertFalse(banner!!.lowercase().contains("exception"))
            assertFalse(banner.contains("abs-bundle"))
            assertEquals("abs-bundle", outside.readText())
        } finally {
            parent.deleteRecursively()
        }
    }

    @Test
    fun relativePathThatLeavesTheAppFilesDirDoesNotReturnThoseBytes() {
        val parent = scratch()
        try {
            val base = File(parent, "files").also { it.mkdirs() }
            val outside = File(parent, "outside-secret")
            outside.writeBytes("secret-bytes".toByteArray())
            val escape = DogfoodIntents.readRecoverySeed(
                DogfoodIntents.recoveryFile(base, "../${outside.name}"),
            )
            assertFalse(escape.readable)
            assertNull(escape.bytes)
            val refused = DogfoodIntents.loadRecoveryExtra(base, "../${outside.name}")
            assertTrue(refused.opensImport)
            assertTrue(refused.rejected)
            assertNull(refused.bytes)
            val banner = refused.banner
            assertEquals(DogfoodIntents.RECOVERY_REJECT_BANNER, banner)
            assertEquals(DogfoodIntents.RECOVERY_REJECT_NEXT, refused.next)
            assertFalse(banner!!.lowercase().contains("exception"))
            assertFalse(banner.contains("secret"))
            val nestedEscape = DogfoodIntents.readRecoverySeed(
                DogfoodIntents.recoveryFile(base, "sub/../../${outside.name}"),
            )
            assertFalse(nestedEscape.readable)
            assertNull(nestedEscape.bytes)
            val pointed = DogfoodIntents.recoveryFile(base, "../${outside.name}")
            assertFalse(pointed.canonicalFile == outside.canonicalFile)
            assertTrue(pointed.canonicalPath.startsWith(base.canonicalPath))
            val link = File(base, "link")
            Files.createSymbolicLink(link.toPath(), outside.toPath())
            val viaLink = DogfoodIntents.readRecoverySeed(DogfoodIntents.recoveryFile(base, "link"))
            assertFalse(viaLink.readable)
            assertNull(viaLink.bytes)
            val sibling = File(parent, "files-evil").also { it.mkdirs() }
            File(sibling, "ok").writeBytes("evil-bytes".toByteArray())
            val prefix = DogfoodIntents.readRecoverySeed(
                DogfoodIntents.recoveryFile(base, "../files-evil/ok"),
            )
            assertFalse(prefix.readable)
            assertNull(prefix.bytes)
        } finally {
            parent.deleteRecursively()
        }
    }

    @Test
    fun aRestoredDeliveryTokenDoesNotMatchADifferentIntent() {
        val key = DogfoodIntents.deliveryKey(
            "android.intent.action.VIEW",
            null,
            "recovery.leasegrid-recovery",
            null,
        )
        val token = DogfoodIntents.deliveryToken(key)
        assertTrue(token.length >= 32)
        assertFalse(token.contains("recovery.leasegrid-recovery"))
        assertTrue(DogfoodIntents.sameDelivery(token, key))
        assertFalse(DogfoodIntents.sameDelivery(null, key))
        assertFalse(DogfoodIntents.sameDelivery(token, "$key-other"))
        assertEquals(token, DogfoodIntents.deliveryToken(key))
    }

    private fun scratch(): File {
        val dir = File.createTempFile("lg-recovery-extra", "")
        check(dir.delete())
        check(dir.mkdirs())
        return dir
    }
}
