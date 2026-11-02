package net.themark.leasegrid.sync

import androidx.compose.ui.semantics.SemanticsConfiguration
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import net.themark.leasegrid.sync.invite.Invite
import net.themark.leasegrid.sync.invite.InviteFail
import net.themark.leasegrid.sync.recovery.IMPORT_FAIL_MSG
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

    @Test
    fun badRecoveryFileFailsClosed() {
        // A damaged file must be the import card, never a raw parser exception.
        // Retry stays available. Nothing here returns a bundle.
        val samples = listOf(
            "this is not a recovery file".toByteArray(),
            """{"leasegrid-recovery":1,"encrypted":false,"bundle":"not-a-bundle"}""".toByteArray(),
            """{"leasegrid-recovery":1,"encrypted":false,"bundle":{"version":1,"introducer_furl":"pb://hashhashhash@127.0.0.1:1/swissnumswiss","shares":1}}""".toByteArray(),
            """{"leasegrid-recovery":1,"encrypted":false,"bundle":{"version":1,"introducer_furl":"not-a-link","shares":[2,3,3]}}""".toByteArray(),
        )
        for (sample in samples) {
            try {
                RecoveryCodec.decode(sample, "")
                error("expected fail")
            } catch (exc: ImportFail) {
                assertEquals(IMPORT_FAIL_MSG, exc.banner)
                assertTrue(exc.next.contains("Retry"))
            }
        }
    }

    private fun assertImportCard(sample: ByteArray, passphrase: String = "") {
        try {
            RecoveryCodec.decode(sample, passphrase)
            error("expected the import card")
        } catch (exc: ImportFail) {
            assertEquals(IMPORT_FAIL_MSG, exc.banner)
            assertTrue(exc.next.contains("Retry"))
        }
    }

    private fun plain(bundle: String) =
        """{"leasegrid-recovery":1,"encrypted":false,"bundle":$bundle}""".toByteArray()

    private fun bundle(furl: String = "pb://hashhashhash@127.0.0.1:1/swissnumswiss", shares: String = "[2,3,3]", folders: String = "[]") =
        """{"version":1,"introducer_furl":"$furl","shares":$shares,"folders":$folders}"""

    @Test
    fun deeplyNestedJsonIsTheImportCardNotACrash() {
        val deep = "[".repeat(200_000) + "]".repeat(200_000)
        assertImportCard(plain(deep))
        assertImportCard(plain(bundle(folders = deep)))
        assertImportCard(("{\"a\":".repeat(100_000) + "1" + "}".repeat(100_000)).toByteArray())
        // Brackets inside strings are not nesting: a normal file still imports.
        val named = bundle(folders = """[{"name":"[[[[{{{{","collective_dircap":"URI:DIR2:x:y"}]""")
        assertEquals("[[[[{{{{", RecoveryCodec.decode(plain(named), "").folders.single().name)
    }

    @Test(timeout = 10_000)
    fun hugeScryptParamsAreTheImportCardAndFailFast() {
        val salt = java.util.Base64.getEncoder().encodeToString(ByteArray(16))
        fun envelope(kdf: String) =
            """{"leasegrid-recovery":1,"encrypted":true,"kdf":{"name":"scrypt","salt":"$salt",$kdf},"ciphertext":"x"}""".toByteArray()
        val bad = listOf(
            "\"n\":${1 shl 30},\"r\":8,\"p\":1",
            "\"n\":${1 shl 21},\"r\":1,\"p\":1",
            "\"n\":${1 shl 17},\"r\":8,\"p\":1",
            "\"n\":${1 shl 15},\"r\":100000,\"p\":1",
            "\"n\":${1 shl 15},\"r\":8,\"p\":100000",
            "\"n\":${(1 shl 15) + 1},\"r\":8,\"p\":1",
            "\"n\":0,\"r\":8,\"p\":1",
            "\"n\":-32768,\"r\":8,\"p\":1",
            "\"n\":\"lots\",\"r\":8,\"p\":1",
            "\"n\":1e30,\"r\":8,\"p\":1",
        )
        for (kdf in bad) assertImportCard(envelope(kdf), "correct horse")
    }

    @Test
    fun theDesktopScryptParamsStillImport() {
        val bundle = RecoveryCodec.decode(fixture("ok-pass.leasegrid-recovery"), "correct horse")
        assertEquals("pb://hashhashhash@127.0.0.1:45001/swissnumswiss", bundle.introducerFurl)
    }

    @Test
    fun aRecoveryFileOverTheSizeCapIsTheImportCard() {
        val ok = fixture("ok-plain.leasegrid-recovery")
        val padded = String(ok).replaceFirst("{", "{\"pad\":\"" + "x".repeat(1 shl 20) + "\",").toByteArray()
        assertTrue(padded.size > (1 shl 20))
        assertImportCard(padded)
        val justUnder = String(ok).replaceFirst("{", "{\"pad\":\"" + "x".repeat((1 shl 20) - ok.size - 16) + "\",").toByteArray()
        assertTrue(justUnder.size <= (1 shl 20))
        assertEquals("Photos", RecoveryCodec.decode(justUnder, "").folders.single().name)
    }

    @Test
    fun aRecoveryFurlGetsTheSameCheckAsAPastedLink() {
        val bad = listOf(
            "pb://@127.0.0.1:1/swissnumswiss",
            "pb://hashhashhash/swissnumswiss",
            "pb://hashhashhash@127.0.0.1:1/ab",
            "pb://hashhashhash@127.0.0.1:1/ab#swissnumswiss",
            "pb://hash%00hash@127.0.0.1:1/swissnumswiss",
            "pb://hash\\u0090hash@127.0.0.1:1/swissnumswiss",
            "pb://x",
        )
        for (furl in bad) assertImportCard(plain(bundle(furl = furl)))
        val marked = bundle(furl = "\\u200Bpb://hashhashhash@127.0.0.1:1/swissnumswiss")
        assertEquals("pb://hashhashhash@127.0.0.1:1/swissnumswiss", RecoveryCodec.decode(plain(marked), "").introducerFurl)
    }

    @Test
    fun badSharesAndFoldersAreTheImportCard() {
        for (shares in listOf("[2,3]", "[2,3,3,3]", "[0,3,3]", "[4,3,3]", "[2,4,3]", "[2,3,300]")) {
            assertImportCard(plain(bundle(shares = shares)))
        }
        val badFolders = listOf(
            """[{"name":"","collective_dircap":"URI:DIR2:x:y"}]""",
            """[{"name":"Photos","collective_dircap":"not-a-cap"}]""",
            """[{"collective_dircap":"URI:DIR2:x:y"}]""",
            """[{"name":"Photos"}]""",
            """["Photos"]""",
        )
        for (folders in badFolders) assertImportCard(plain(bundle(folders = folders)))
        val good = RecoveryCodec.decode(plain(bundle(folders = """[{"name":"Photos","collective_dircap":"URI:DIR2:x:y"}]""")), "")
        assertEquals(listOf(2, 3, 3), good.shares)
        assertEquals("URI:DIR2:x:y", good.folders.single().collective)
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
            // Desktop label pinned in Invite.SHOW_FULL_JOIN_LINK; no Next line (#50).
            assertEquals(Invite.WORMHOLE_MSG, exc.banner)
            assertTrue(exc.banner, exc.banner.contains(Invite.SHOW_FULL_JOIN_LINK))
            assertEquals("", exc.next)
            assertFalse(exc.next.lowercase().contains("pb://"))
            assertFalse(exc.next.lowercase().contains("furl"))
        }
    }

    @Test
    fun inviteFailPathsDoNotNameAFurl() {
        // Every InviteFail throw: empty, short code, web URL, garbage,
        // leasegrid link with no hash, fragment with no i=, i= that is not a
        // pb address, and a malformed pb:// value.
        val samples = listOf(
            "",
            "7-guitarist-revenge",
            "https://example.test/tahoe",
            "not-a-code",
            "leasegrid:join",
            "#v=1&n=2",
            "#v=1&i=not-a-link",
            "pb://short",
        )
        for (sample in samples) {
            try {
                Invite.parse(sample)
                error("expected fail for $sample")
            } catch (exc: InviteFail) {
                assertFalse(
                    "$sample banner: ${exc.banner}",
                    exc.banner.lowercase().contains("pb://") || exc.banner.lowercase().contains("furl"),
                )
                assertFalse(
                    "$sample next: ${exc.next}",
                    exc.next.lowercase().contains("pb://") || exc.next.lowercase().contains("furl"),
                )
            }
        }
    }

    @Test
    fun webUrlWithoutInviteIsRejected() {
        try {
            Invite.parse("https://example.test/tahoe")
            error("expected fail")
        } catch (exc: InviteFail) {
            assertEquals(Invite.WEB_URL_MSG, exc.banner)
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
