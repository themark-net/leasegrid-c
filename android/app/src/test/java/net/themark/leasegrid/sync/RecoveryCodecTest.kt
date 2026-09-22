package net.themark.leasegrid.sync

import net.themark.leasegrid.sync.invite.Invite
import net.themark.leasegrid.sync.invite.InviteFail
import net.themark.leasegrid.sync.recovery.ImportFail
import net.themark.leasegrid.sync.recovery.RecoveryCodec
import net.themark.leasegrid.sync.session.Session
import net.themark.leasegrid.sync.session.SessionStore
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
    fun joinStaysDisabledUntilAckAndText() {
        assertFalse(Invite.joinEnabled(false, "pb://abcabcdefghij/swissnumswiss"))
        assertFalse(Invite.joinEnabled(true, "  "))
        assertTrue(Invite.joinEnabled(true, "pb://abcabcdefghij/swissnumswiss"))
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
