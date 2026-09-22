package net.themark.leasegrid.sync

import androidx.compose.ui.semantics.SemanticsConfiguration
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import net.themark.leasegrid.sync.invite.Invite
import net.themark.leasegrid.sync.invite.InviteFail
import net.themark.leasegrid.sync.recovery.ImportFail
import net.themark.leasegrid.sync.recovery.RecoveryCodec
import net.themark.leasegrid.sync.session.Session
import net.themark.leasegrid.sync.session.SessionStore
import net.themark.leasegrid.sync.ui.dogfoodProbe
import net.themark.leasegrid.sync.ui.joinControlEnabled
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class RecoveryCodecTest {
    private fun fixture(name: String): ByteArray {
        val stream = javaClass.classLoader!!.getResourceAsStream("recovery/$name")
            ?: error("missing fixture $name")
        return stream.use { it.readBytes() }
    }

    @Test
    fun plaintextRecoveryMatchesDesktopBundle() {
        val bundle = RecoveryCodec.decode(fixture("ok-plain.leasegrid-recovery"), "")
        assertEquals("pb://hashhashhash@127.0.0.1:45001/swissnumswiss", bundle.introducerFurl)
        assertEquals(listOf(2, 3, 3), bundle.shares)
        assertEquals("nimo", bundle.nickname)
        assertEquals("Photos", bundle.folders.single().name)
        assertTrue(bundle.folders.single().collective.startsWith("URI:DIR2:"))
    }

    @Test
    fun passphraseRoundTripUsesDesktopFernet() {
        val bundle = RecoveryCodec.decode(fixture("ok-pass.leasegrid-recovery"), "correct horse")
        assertEquals("Photos", bundle.folders.single().name)
        assertEquals("pb://hashhashhash@127.0.0.1:45001/swissnumswiss", bundle.introducerFurl)
    }

    @Test
    fun wrongPassphraseFailsClosed() {
        try {
            RecoveryCodec.decode(fixture("ok-pass.leasegrid-recovery"), "nope")
            error("expected fail")
        } catch (exc: ImportFail) {
            assertTrue(exc.banner.contains("Wrong passphrase"))
            assertTrue(exc.next.contains("Retry"))
        }
    }

    @Test
    fun corruptFileFailsClosed() {
        try {
            RecoveryCodec.decode(fixture("corrupt.leasegrid-recovery"), "")
            error("expected fail")
        } catch (exc: ImportFail) {
            assertTrue(exc.banner.startsWith("could not import"))
        }
    }
}

class InviteTest {
    @Test
    fun extraRecoveryKeyReopensImportAndSeedsFile() {
        val welcome = DogfoodIntents.deliveryKey("android.intent.action.MAIN", null, null, null)
        val pass = DogfoodIntents.deliveryKey(
            "android.intent.action.MAIN",
            null,
            "ok-pass.leasegrid-recovery",
            null,
        )
        assertTrue(DogfoodIntents.shouldDeliver(null, welcome))
        assertTrue(DogfoodIntents.shouldDeliver(welcome, pass))
        assertFalse(DogfoodIntents.shouldDeliver(pass, pass))
        assertTrue(DogfoodIntents.opensImport("ok-pass.leasegrid-recovery"))
        assertFalse(DogfoodIntents.opensImport(null))
        assertFalse(DogfoodIntents.opensImport("  "))
        val dir = java.io.File.createTempFile("lg-files", "").also {
            it.delete()
            it.mkdirs()
        }
        val relative = DogfoodIntents.recoveryFile(dir, "ok-pass.leasegrid-recovery")
        val missing = DogfoodIntents.readRecoverySeed(relative)
        assertFalse(missing.readable)
        assertNull(missing.bytes)
        relative.writeBytes("mock-recovery".toByteArray())
        val seed = DogfoodIntents.readRecoverySeed(relative)
        assertTrue(seed.readable)
        assertEquals("ok-pass.leasegrid-recovery", seed.name)
        assertEquals("mock-recovery", seed.bytes!!.decodeToString())
        val absolute = DogfoodIntents.recoveryFile(dir, relative.absolutePath)
        assertEquals(relative.absolutePath, absolute.path)
    }

    @Test
    fun debugInviteExtraDoesNotSkipThreatAck() {
        val furl = "pb://hashhashhash@127.0.0.1:45001/swissnumswiss"
        val text = DogfoodIntents.inviteText(furl, null)
        assertEquals(furl, text)
        assertFalse(Invite.joinEnabled(false, text!!))
        assertTrue(Invite.joinEnabled(true, text))
        assertEquals("from-query", DogfoodIntents.inviteText(null, "from-query"))
        assertEquals(null, DogfoodIntents.inviteText("  ", "  "))
    }

    @Test
    fun joinStaysDisabledUntilAckAndText() {
        assertFalse(Invite.joinEnabled(false, "pb://abcabcdefghij/swissnumswiss"))
        assertFalse(Invite.joinEnabled(true, "  "))
        assertTrue(Invite.joinEnabled(true, "pb://abcabcdefghij/swissnumswiss"))
    }

    @Test
    fun uncheckedJoinControlIsDisabled() {
        assertFalse(joinControlEnabled(false, "", busy = false))
        assertFalse(joinControlEnabled(false, "pb://abcabcdefghij/swissnumswiss", busy = false))
        assertTrue(probeDisabled(false, ""))
    }

    @Test
    fun checkedEmptyJoinControlIsDisabled() {
        assertFalse(joinControlEnabled(true, "", busy = false))
        assertFalse(joinControlEnabled(true, "   ", busy = false))
        assertTrue(probeDisabled(true, "   "))
    }

    @Test
    fun checkedNonblankJoinControlIsEnabled() {
        assertTrue(joinControlEnabled(true, "pb://abcabcdefghij/swissnumswiss", busy = false))
        assertFalse(joinControlEnabled(true, "pb://abcabcdefghij/swissnumswiss", busy = true))
        assertFalse(probeDisabled(true, "pb://abcabcdefghij/swissnumswiss"))
    }

    private fun probeDisabled(acknowledged: Boolean, invite: String): Boolean {
        val config = SemanticsConfiguration()
        val enabled = joinControlEnabled(acknowledged, invite, busy = false)
        config.dogfoodProbe("join_button", enabled) {}
        assertEquals(listOf("join_button"), config[SemanticsProperties.ContentDescription])
        return config.getOrNull(SemanticsProperties.Disabled) != null
    }

    @Test
    fun parsesFurlAndJoinUrl() {
        val furl = "pb://hashhashhash@127.0.0.1:45001/swissnumswiss"
        assertEquals(furl, Invite.parse(furl).furl)
        val url = "leasegrid:join#v=1&i=$furl&n=2&h=3&t=3"
        val parsed = Invite.parse(url)
        assertEquals(furl, parsed.furl)
        assertEquals(listOf(2, 3, 3), parsed.shares)
    }

    @Test
    fun wormholeIsInAppFailNotASilentJoin() {
        try {
            Invite.parse("7-guitarist-revenge")
            error("expected fail")
        } catch (exc: InviteFail) {
            assertTrue(exc.next.contains("pb://"))
        }
    }

    @Test
    fun webUrlWithoutInviteIsRejected() {
        try {
            Invite.parse("https://example.test/tahoe")
            error("expected fail")
        } catch (exc: InviteFail) {
            assertTrue(exc.banner.contains("web URL") || exc.next.contains("web UI"))
        }
    }
}

class SessionStoreTest {
    @Test
    fun failedImportDoesNotCreateAHome() {
        val dir = File.createTempFile("lg-session", "").also { it.delete() }
        dir.mkdirs()
        val store = SessionStore(dir)
        assertFalse(store.exists())
        try {
            RecoveryCodec.decode("{\"leasegrid-recovery\": 99}\n".toByteArray(), "x")
            error("expected fail")
        } catch (_: ImportFail) {
        }
        assertFalse(File(dir, "session.json").exists())
        assertNull(store.load())
    }

    @Test
    fun saveIsReadableAndClearRemovesIt() {
        val dir = File.createTempFile("lg-session", "").also { it.delete() }
        dir.mkdirs()
        val store = SessionStore(dir)
        store.save(Session(introducerFurl = "pb://hashhashhash@127.0.0.1:1/swissnumswiss"))
        assertEquals("pb://hashhashhash@127.0.0.1:1/swissnumswiss", store.load()!!.introducerFurl)
        store.clear()
        assertNull(store.load())
    }
}
