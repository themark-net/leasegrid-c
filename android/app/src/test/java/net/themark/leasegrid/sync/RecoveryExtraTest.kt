package net.themark.leasegrid.sync

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files

/**
 * EXTRA_RECOVERY_FILE at the intent boundary.
 * Fail: a relative name is not joined onto the app files dir, so the first frame
 * never gets the bytes and import confirm stays unset (conf_enabled=None).
 * Recover: the same bytes as the absolute path, before any retry.
 * Fail: a relative path leaves the app files dir. Recover: no bytes, a plain sentence,
 * and the activity offers the file picker instead of reading that path again.
 */
class RecoveryExtraTest {
    @Test
    fun relativeNameInTheAppFilesDirLoadsTheSameBytesAsTheAbsolutePath() {
        val base = scratch()
        try {
            val name = "ok-plain.leasegrid-recovery"
            val seeded = File(base, name)
            seeded.writeBytes("plain-bundle".toByteArray())
            val relative = DogfoodIntents.loadRecoveryExtra(base, name)
            val absolute = DogfoodIntents.loadRecoveryExtra(base, seeded.absolutePath)
            assertTrue(relative.opensImport)
            assertFalse(relative.rejected)
            assertNull(relative.banner)
            assertEquals(name, relative.name)
            assertEquals("plain-bundle", relative.bytes!!.decodeToString())
            assertTrue(relative.bytes.contentEquals(absolute.bytes))
            assertEquals(name, absolute.name)
            val dotted = DogfoodIntents.loadRecoveryExtra(base, "./$name")
            assertTrue(dotted.bytes!!.contentEquals(relative.bytes))
            val nestedDir = File(base, "sub")
            nestedDir.mkdirs()
            File(nestedDir, name).writeBytes("nested-bundle".toByteArray())
            val nested = DogfoodIntents.loadRecoveryExtra(base, "sub/$name")
            assertEquals("nested-bundle", nested.bytes!!.decodeToString())
            assertFalse(nested.rejected)
            val dots = File(base, "foo..bar.leasegrid-recovery")
            dots.writeBytes("dots-bundle".toByteArray())
            val dottedName = DogfoodIntents.loadRecoveryExtra(base, dots.name)
            assertEquals("dots-bundle", dottedName.bytes!!.decodeToString())
        } finally {
            base.deleteRecursively()
        }
    }

    @Test
    fun absolutePathOutsideTheAppFilesDirStillLoads() {
        val parent = scratch()
        try {
            val base = File(parent, "files").also { it.mkdirs() }
            val outside = File(parent, "elsewhere.leasegrid-recovery")
            outside.writeBytes("abs-bundle".toByteArray())
            val loaded = DogfoodIntents.loadRecoveryExtra(base, outside.absolutePath)
            assertTrue(loaded.opensImport)
            assertFalse(loaded.rejected)
            assertEquals("abs-bundle", loaded.bytes!!.decodeToString())
            assertNull(loaded.banner)
        } finally {
            parent.deleteRecursively()
        }
    }

    @Test
    fun missingFileInsideTheAppFilesDirOpensImportWithAPlainSentence() {
        val base = scratch()
        try {
            val loaded = DogfoodIntents.loadRecoveryExtra(base, "missing.leasegrid-recovery")
            assertTrue(loaded.opensImport)
            assertFalse(loaded.rejected)
            assertNull(loaded.bytes)
            val banner = checkNotNull(loaded.banner)
            val next = checkNotNull(loaded.next)
            assertEquals(DogfoodIntents.RECOVERY_MISS_BANNER, banner)
            assertEquals(DogfoodIntents.RECOVERY_MISS_NEXT, next)
            assertPlain(banner)
            assertPlain(next)
        } finally {
            base.deleteRecursively()
        }
    }

    @Test
    fun relativePathThatLeavesTheAppFilesDirDoesNotReturnThoseBytes() {
        val parent = scratch()
        try {
            val base = File(parent, "files").also { it.mkdirs() }
            val outside = File(parent, "outside-secret")
            outside.writeBytes("secret-bytes".toByteArray())
            val escape = DogfoodIntents.loadRecoveryExtra(base, "../${outside.name}")
            assertTrue(escape.opensImport)
            assertTrue(escape.rejected)
            assertNull(escape.bytes)
            val banner = checkNotNull(escape.banner)
            val next = checkNotNull(escape.next)
            assertEquals(DogfoodIntents.RECOVERY_REJECT_BANNER, banner)
            assertEquals(DogfoodIntents.RECOVERY_REJECT_NEXT, next)
            assertPlain(banner)
            assertPlain(next)
            assertFalse(banner.contains("secret"))
            val nestedEscape = DogfoodIntents.loadRecoveryExtra(base, "sub/../../${outside.name}")
            assertTrue(nestedEscape.rejected)
            assertNull(nestedEscape.bytes)
            val pointed = DogfoodIntents.recoveryFile(base, "../${outside.name}")
            assertFalse(pointed.canonicalFile == outside.canonicalFile)
            assertTrue(pointed.canonicalPath.startsWith(base.canonicalPath))
            val link = File(base, "link")
            Files.createSymbolicLink(link.toPath(), outside.toPath())
            val viaLink = DogfoodIntents.loadRecoveryExtra(base, "link")
            assertTrue(viaLink.rejected)
            assertNull(viaLink.bytes)
            val sibling = File(parent, "files-evil").also { it.mkdirs() }
            File(sibling, "ok").writeBytes("evil-bytes".toByteArray())
            val prefix = DogfoodIntents.loadRecoveryExtra(base, "../files-evil/ok")
            assertTrue(prefix.rejected)
            assertNull(prefix.bytes)
        } finally {
            parent.deleteRecursively()
        }
    }

    @Test
    fun blankExtraDoesNotOpenImport() {
        val base = scratch()
        try {
            val blank = DogfoodIntents.loadRecoveryExtra(base, "  ")
            val missing = DogfoodIntents.loadRecoveryExtra(base, null)
            assertFalse(blank.opensImport)
            assertFalse(missing.opensImport)
            assertNull(blank.bytes)
            assertNull(missing.bytes)
            assertNull(blank.banner)
        } finally {
            base.deleteRecursively()
        }
    }

    private fun assertPlain(text: String) {
        val lower = text.lowercase()
        assertFalse(text, lower.contains("exception"))
        assertFalse(text, text.contains("java."))
        assertFalse(text, lower.contains("nullpointer"))
        assertFalse(text, lower.contains("ioexception"))
        assertFalse(text, text.contains("\n"))
    }

    private fun scratch(): File {
        val dir = File.createTempFile("lg-recovery-extra", "")
        check(dir.delete())
        check(dir.mkdirs())
        return dir
    }
}
