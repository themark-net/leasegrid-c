package net.themark.leasegrid.sync

import net.themark.leasegrid.sync.ui.Chip
import net.themark.leasegrid.sync.ui.ChildRow
import net.themark.leasegrid.sync.ui.FolderWriteBoard
import net.themark.leasegrid.sync.ui.StageAdd
import net.themark.leasegrid.sync.ui.WriteCopy
import net.themark.leasegrid.sync.ui.WriteSheet
import net.themark.leasegrid.sync.ui.chipText
import net.themark.leasegrid.sync.ui.directoryWritable
import net.themark.leasegrid.sync.ui.keepBothName
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
}
