package net.themark.leasegrid.sync

import net.themark.leasegrid.sync.ui.Chip
import net.themark.leasegrid.sync.ui.ChildRow
import net.themark.leasegrid.sync.ui.FolderWriteBoard
import net.themark.leasegrid.sync.ui.StageAdd
import net.themark.leasegrid.sync.ui.WriteCopy
import net.themark.leasegrid.sync.ui.WriteSheet
import net.themark.leasegrid.sync.ui.ADD_SILENCE_MS
import net.themark.leasegrid.sync.ui.VisibleFile
import net.themark.leasegrid.sync.ui.chipText
import net.themark.leasegrid.sync.ui.directoryWritable
import net.themark.leasegrid.sync.ui.keepBothName
import net.themark.leasegrid.sync.ui.rowActions
import net.themark.leasegrid.sync.ui.showPendingProgress
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The chip is a product rule, not a label we assert against itself.
 * These fail if a write is marked On friendnet before acknowledge,
 * if discard pretends to be a friendnet remove, or if a read-only cap
 * is treated as writable.
 */
class FolderWriteTest {
    private val cap = "URI:DIR2:writekey:fingerprint"

    @Test
    fun pendingStaysNotOnFriendnetUntilAcknowledge() {
        val board = FolderWriteBoard()
        val staged = board.stageAdd("Photos", cap, "receipt.pdf", "/tmp/receipt.pdf", 80, emptySet())
        assertTrue(staged is StageAdd.Ready)
        val pending = board.begin(cap, "receipt.pdf", "/tmp/receipt.pdf", 80)
        board.noteProgress(cap, "receipt.pdf", 0.99f)
        val row = board.visibleFiles(cap, emptyList()).single()
        assertEquals(Chip.Pending, row.chip)
        assertEquals(WriteCopy.PENDING, chipText(row))
        assertEquals("Not on friendnet yet", chipText(row))
        assertFalse(chipText(row).contains("computer"))
        assertFalse(chipText(row).contains("On friendnet"))
        assertTrue(row.progress <= 0.9f)

        assertTrue(board.acknowledge(cap, "receipt.pdf", pending.token))
        val landed = board.visibleFiles(
            cap,
            listOf(ChildRow("receipt.pdf", "file", "URI:CHK:abc:def:1:1:80", 80)),
        ).single()
        assertEquals("On friendnet", chipText(landed))
        assertFalse(chipText(landed).contains("computer"))
    }

    @Test
    fun clashCancelLeavesTheFolderUnchanged() {
        val board = FolderWriteBoard()
        val staged = board.stageAdd(
            "Photos",
            cap,
            "beach.jpg",
            "/tmp/beach.jpg",
            10,
            setOf("beach.jpg"),
        )
        assertTrue(staged is StageAdd.NeedsChoice)
        val sheet = board.sheet
        assertTrue(sheet is WriteSheet.Clash)
        assertEquals("beach.jpg", (sheet as WriteSheet.Clash).name)
        assertEquals("Photos", sheet.folder)
        board.cancelSheet()
        assertNull(board.sheet)
        assertTrue(board.visibleFiles(cap, listOf(ChildRow("beach.jpg", "file", "URI:CHK:x:y:1:1:10", 10))).single().chip == Chip.Landed)
        assertTrue(board.pendingFor(cap).isEmpty())
    }

    @Test
    fun keepBothNamesADistinctVisibleFile() {
        assertEquals("beach (phone).jpg", keepBothName("beach.jpg", setOf("beach.jpg")))
        assertEquals(
            "beach (phone 2).jpg",
            keepBothName("beach.jpg", setOf("beach.jpg", "beach (phone).jpg")),
        )
    }

    @Test
    fun discardIsNotRemove() {
        val board = FolderWriteBoard()
        board.begin(cap, "receipt.pdf", "/tmp/receipt.pdf", 80)
        board.askDiscard(cap, "receipt.pdf")
        assertTrue(board.sheet is WriteSheet.Discard)
        assertNull(board.confirmRemove())
        val dropped = board.confirmDiscard()
        assertEquals("receipt.pdf", dropped?.name)
        assertTrue(board.pendingFor(cap).isEmpty())

        board.askRemove("Photos", "beach.jpg", "URI:CHK:x:y:1:1:3")
        val remove = board.sheet
        assertTrue(remove is WriteSheet.Remove)
        assertEquals("Photos", (remove as WriteSheet.Remove).folder)
        assertTrue(board.confirmDiscard() == null)
        assertEquals("beach.jpg", board.confirmRemove()?.name)
    }

    @Test
    fun readOnlyCapHidesAdd() {
        assertTrue(directoryWritable(cap))
        assertFalse(directoryWritable("URI:DIR2-RO:readkey:fingerprint"))
        assertFalse(directoryWritable("URI:DIR2-CHK:key:ueb:1:1:4"))
        assertFalse(directoryWritable(""))
        assertEquals(
            "You can download from this folder. Adding files is not available here.",
            WriteCopy.READ_ONLY,
        )
    }

    @Test
    fun silenceShowsExistingFailAndDoesNotSayOnFriendnet() {
        val board = FolderWriteBoard()
        val pending = board.begin(cap, "lg44-live.txt", "/tmp/lg44-live.txt", 33)
        board.noteProgress(cap, "lg44-live.txt", 0.99f)
        assertFalse(board.noteSilence(cap, "lg44-live.txt", pending.token, ADD_SILENCE_MS - 1))
        var row = board.visibleFiles(cap, emptyList()).single()
        assertFalse(row.failed)
        assertTrue(showPendingProgress(row))
        assertEquals(WriteCopy.PENDING, chipText(row))
        assertEquals("Not on friendnet yet", chipText(row))

        assertTrue(board.noteSilence(cap, "lg44-live.txt", pending.token, ADD_SILENCE_MS))
        board.noteProgress(cap, "lg44-live.txt", 0.99f)
        row = board.visibleFiles(cap, emptyList()).single()
        assertTrue(row.failed)
        assertFalse(showPendingProgress(row))
        assertEquals(Chip.Pending, row.chip)
        assertEquals("Not on friendnet yet", chipText(row))
        assertFalse(chipText(row).contains("computer"))
        assertFalse(chipText(row).startsWith("On friendnet"))
        assertEquals(listOf("Retry", "Cancel"), rowActions(writable = true, row))

        assertTrue(board.acknowledge(cap, "lg44-live.txt", pending.token))
        val landed = board.visibleFiles(
            cap,
            listOf(ChildRow("lg44-live.txt", "file", "URI:CHK:a:b:1:1:33", 33)),
        ).single()
        assertEquals("On friendnet", chipText(landed))
        assertEquals(listOf("Open", "Remove"), rowActions(writable = true, landed))
    }

    @Test
    fun readOnlyFolderHidesRemove() {
        val landed = VisibleFile(
            name = "beach.jpg",
            chip = Chip.Landed,
            size = 3,
            cap = "URI:CHK:x:y:1:1:3",
        )
        val pending = VisibleFile(
            name = "lg44-live.txt",
            chip = Chip.Pending,
            size = 33,
            failed = false,
        )
        assertEquals(listOf("Open"), rowActions(writable = false, landed))
        assertFalse(rowActions(writable = false, landed).contains("Remove"))
        assertEquals(listOf("Open", "Remove"), rowActions(writable = true, landed))
        assertEquals(listOf("Cancel"), rowActions(writable = true, pending))
        assertFalse(rowActions(writable = false, pending).contains("Remove"))
    }
}
