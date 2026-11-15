package net.themark.leasegrid.sync.ui

import java.io.File
import java.io.FileOutputStream
import java.io.IOException

/**
 * Replace the pending-adds index as a whole.
 * The new bytes go to a temp file in the same directory, then that file is renamed
 * over the index. A write that stops leaves the previous index in place.
 * [stopAfter] is the fault a test uses. Production calls pass the whole body.
 */
internal fun writePendingIndex(dest: File, body: String, stopAfter: Int = Int.MAX_VALUE) {
    val parent = dest.parentFile ?: throw IOException("pending index has no directory")
    if (!parent.isDirectory && !parent.mkdirs()) {
        throw IOException("could not create the pending index directory")
    }
    val temp = File(parent, dest.name + ".tmp")
    val bytes = body.toByteArray(Charsets.UTF_8)
    try {
        FileOutputStream(temp).use { out ->
            if (bytes.size > stopAfter) {
                if (stopAfter > 0) out.write(bytes, 0, stopAfter)
                throw IOException("pending index write stopped")
            }
            out.write(bytes)
        }
    } catch (exc: IOException) {
        temp.delete()
        throw exc
    }
    if (!temp.renameTo(dest)) {
        temp.delete()
        throw IOException("could not replace the pending index")
    }
}

internal fun deletePendingIndex(dest: File) {
    dest.delete()
    val parent = dest.parentFile ?: return
    File(parent, dest.name + ".tmp").delete()
}
