package net.themark.leasegrid.sync.session

import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.File

@Serializable
data class ServerRef(val furl: String, val nickname: String = "")

@Serializable
data class FolderRef(val name: String, val cap: String)

@Serializable
data class Session(
    val introducerFurl: String,
    val nickname: String = "leasegrid-sync",
    val shares: List<Int> = listOf(2, 3, 3),
    val folders: List<FolderRef> = emptyList(),
    val servers: List<ServerRef> = emptyList(),
)

/**
 * One JSON file, written only after join or import succeeds.
 * A failed decode never calls [save], so a bad passphrase leaves no home.
 */
class SessionStore(private val dir: File) {
    private val json = Json { ignoreUnknownKeys = true; prettyPrint = true }
    private val dest = File(dir, "session.json")
    private val tmp = File(dir, "session.json.tmp")

    fun exists(): Boolean = dest.isFile && dest.length() > 0

    fun load(): Session? {
        if (tmp.exists()) tmp.delete()
        if (!exists()) return null
        return try {
            json.decodeFromString(Session.serializer(), dest.readText(Charsets.UTF_8))
        } catch (_: Exception) {
            null
        }
    }

    fun save(session: Session) {
        dir.mkdirs()
        tmp.writeText(json.encodeToString(session), Charsets.UTF_8)
        if (dest.exists() && !dest.delete()) {
            throw IllegalStateException("could not replace session")
        }
        if (!tmp.renameTo(dest)) {
            tmp.copyTo(dest, overwrite = true)
            tmp.delete()
        }
    }

    fun clear() {
        dest.delete()
        tmp.delete()
    }
}
