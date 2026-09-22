package net.themark.leasegrid.sync.recovery

import org.bouncycastle.crypto.generators.SCrypt
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.security.MessageDigest
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.Mac
import javax.crypto.spec.IvParameterSpec
import javax.crypto.spec.SecretKeySpec

/** U4 `*.leasegrid-recovery` v1. Same envelope as desktop `recovery.py`. */
const val RECOVERY_VERSION = 1

const val IMPORT_FAIL_MSG =
    "could not import this recovery key. Wrong passphrase, corrupt file, or incompatible grid."
const val IMPORT_FAIL_NEXT =
    "check the passphrase; try the file from your backup; Retry."
const val SCARY_LOSS =
    "Loss of your recovery key and this device can mean TOTAL LOSS of access. " +
        "There is no reset password. Leasegrid cannot recover it for you."

class ImportFail(val banner: String, val next: String) : Exception(banner)

data class FolderCap(
    val name: String,
    val collective: String,
)

data class RecoveryBundle(
    val introducerFurl: String,
    val shares: List<Int>,
    val nickname: String,
    val folders: List<FolderCap>,
)

object RecoveryCodec {
    private val json = Json { ignoreUnknownKeys = true }

    fun decode(data: ByteArray, passphrase: String): RecoveryBundle {
        val text = try {
            data.toString(Charsets.UTF_8)
        } catch (_: Exception) {
            throw ImportFail(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
        }
        val envelope = try {
            json.parseToJsonElement(text).jsonObject
        } catch (_: Exception) {
            throw ImportFail(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
        }
        val version = envelope["leasegrid-recovery"]?.jsonPrimitive?.intOrNull
        if (version != RECOVERY_VERSION) {
            throw ImportFail(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
        }
        val encrypted = envelope["encrypted"]?.jsonPrimitive?.booleanOrNull == true
        val bundle = if (!encrypted) {
            envelope["bundle"]?.jsonObject ?: throw ImportFail(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
        } else {
            decryptBundle(envelope, passphrase)
        }
        return parseBundle(bundle)
    }

    private fun decryptBundle(envelope: JsonObject, passphrase: String): JsonObject {
        val kdf = envelope["kdf"]?.jsonObject ?: throw ImportFail(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
        if (kdf["name"]?.jsonPrimitive?.contentOrNull != "scrypt") {
            throw ImportFail(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
        }
        try {
            val salt = b64(kdf["salt"]?.jsonPrimitive?.contentOrNull ?: "")
            val n = kdf["n"]?.jsonPrimitive?.intOrNull ?: (1 shl 15)
            val r = kdf["r"]?.jsonPrimitive?.intOrNull ?: 8
            val p = kdf["p"]?.jsonPrimitive?.intOrNull ?: 1
            val key = scryptKey(passphrase, salt, n, r, p)
            val token = envelope["ciphertext"]?.jsonPrimitive?.contentOrNull ?: ""
            val plain = fernetDecrypt(key, token)
            return json.parseToJsonElement(plain.toString(Charsets.UTF_8)).jsonObject
        } catch (exc: ImportFail) {
            throw exc
        } catch (_: Exception) {
            throw ImportFail(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
        }
    }

    private fun parseBundle(data: JsonObject): RecoveryBundle {
        if (data["version"]?.jsonPrimitive?.intOrNull != RECOVERY_VERSION) {
            throw ImportFail(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
        }
        val furl = data["introducer_furl"]?.jsonPrimitive?.contentOrNull ?: ""
        if (!furl.startsWith("pb://")) {
            throw ImportFail(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
        }
        val sharesEl = data["shares"]?.jsonArray ?: throw ImportFail(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
        if (sharesEl.size != 3) throw ImportFail(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
        val shares = sharesEl.map { it.jsonPrimitive.intOrNull ?: throw ImportFail(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT) }
        val folders = mutableListOf<FolderCap>()
        val rawFolders = data["folders"]?.jsonArray
        if (rawFolders != null) {
            for (item in rawFolders) {
                val obj = item.jsonObject
                val name = obj["name"]?.jsonPrimitive?.contentOrNull ?: throw ImportFail(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
                val cap = obj["collective_dircap"]?.jsonPrimitive?.contentOrNull
                    ?: throw ImportFail(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
                if (name.isBlank() || !cap.startsWith("URI:")) {
                    throw ImportFail(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
                }
                folders.add(FolderCap(name, cap))
            }
        }
        val nickname = data["nickname"]?.jsonPrimitive?.contentOrNull ?: "leasegrid-sync"
        return RecoveryBundle(furl, shares, nickname, folders)
    }

    private fun scryptKey(passphrase: String, salt: ByteArray, n: Int, r: Int, p: Int): ByteArray {
        val raw = SCrypt.generate(passphrase.toByteArray(Charsets.UTF_8), salt, n, r, p, 32)
        return Base64.getUrlEncoder().withoutPadding().encode(raw)
    }

    /** cryptography.fernet: version || timestamp || iv || ciphertext || hmac. */
    private fun fernetDecrypt(keyB64: ByteArray, token: String): ByteArray {
        val key = b64Url(String(keyB64, Charsets.US_ASCII))
        if (key.size != 32) throw ImportFail(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
        val signing = key.copyOfRange(0, 16)
        val encryption = key.copyOfRange(16, 32)
        val data = b64Url(token)
        if (data.size < 1 + 8 + 16 + 16 + 32 || data[0] != 0x80.toByte()) {
            throw ImportFail(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
        }
        val signed = data.copyOfRange(0, data.size - 32)
        val mac = data.copyOfRange(data.size - 32, data.size)
        val hmac = Mac.getInstance("HmacSHA256")
        hmac.init(SecretKeySpec(signing, "HmacSHA256"))
        val expect = hmac.doFinal(signed)
        if (!MessageDigest.isEqual(expect, mac)) {
            throw ImportFail(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
        }
        val iv = data.copyOfRange(9, 25)
        val ciphertext = data.copyOfRange(25, data.size - 32)
        val cipher = Cipher.getInstance("AES/CBC/PKCS5Padding")
        cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(encryption, "AES"), IvParameterSpec(iv))
        return cipher.doFinal(ciphertext)
    }

    private fun b64(text: String): ByteArray = Base64.getDecoder().decode(text)
    private fun b64Url(text: String): ByteArray {
        val cleaned = text.trim()
        val pad = (4 - cleaned.length % 4) % 4
        return Base64.getUrlDecoder().decode(cleaned + "=".repeat(pad))
    }
}
