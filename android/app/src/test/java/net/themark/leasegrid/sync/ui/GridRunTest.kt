package net.themark.leasegrid.sync.ui

import kotlin.coroutines.CoroutineContext
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Runnable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The cancelled join used to set busy=false from its finally after a newer
 * join had already set busy=true. These two dispatchers keep that order
 * observable: the newer job starts, then the older finally runs.
 */
class GridRunTest {
    @Test
    fun cancelledJobDoesNotClearBusyWhileANewerJobRuns() {
        val main = QueueDispatcher()
        val io = QueueDispatcher()
        val scope = CoroutineScope(SupervisorJob() + main)
        var busy = false
        val run = GridRun(scope, setBusy = { busy = it }, setFail = {})
        run.launch {
            withContext(io) {
                suspendCancellableCoroutine<Unit> { }
            }
        }
        assertTrue(main.runNext())
        assertTrue(busy)
        assertTrue(io.runNext())

        run.launch {
            withContext(io) {
                suspendCancellableCoroutine<Unit> { }
            }
        }
        assertTrue("newer job should start on main", main.runNext())
        assertTrue(busy)
        // The older job was parked on io. Its cancellation resumes there, then
        // its finally is posted back to main. Run that before the newer job ends.
        assertTrue("older cancellation should resume on io", io.runNext())
        assertTrue("older finally should post to main", main.runNext())
        assertTrue(
            "older finally cleared busy while the newer job was still running. " +
                "main=${main.waiting} io=${io.waiting}",
            busy,
        )
    }

    @Test
    fun currentJobClearsBusyWhenItFinishes() {
        val main = QueueDispatcher()
        val scope = CoroutineScope(SupervisorJob() + main)
        var busy = false
        val run = GridRun(scope, setBusy = { busy = it }, setFail = {})
        var ran = false
        run.launch { ran = true }
        main.drain()
        assertTrue(ran)
        assertFalse(busy)
    }

    @Test
    fun cancelClearsBusyWhileTheJobIsStillRunning() {
        val main = QueueDispatcher()
        val io = QueueDispatcher()
        val scope = CoroutineScope(SupervisorJob() + main)
        var busy = false
        val run = GridRun(scope, setBusy = { busy = it }, setFail = {})
        run.launch {
            withContext(io) {
                suspendCancellableCoroutine<Unit> { }
            }
        }
        assertTrue(main.runNext())
        assertTrue(busy)
        run.cancel()
        assertFalse("cancel left the spinner on", busy)
        io.drain()
        main.drain()
        assertFalse("the cancelled job turned busy back on", busy)
    }

    @Test
    fun busyClearsAfterAnErrorAndTheErrorReachesTheHandler() {
        val main = QueueDispatcher()
        val scope = CoroutineScope(SupervisorJob() + main)
        var busy = false
        var seen: Exception? = null
        val run = GridRun(scope, setBusy = { busy = it }, setFail = {})
        run.launch(onError = { seen = it }) { throw IllegalStateException("boom") }
        main.drain()
        assertTrue("the error did not reach the handler: $seen", seen is IllegalStateException)
        assertFalse("busy stayed on after the error", busy)
    }
}

/** Records dispatched blocks so the test chooses which job resumes. */
private class QueueDispatcher : CoroutineDispatcher() {
    private val tasks = ArrayDeque<Runnable>()
    val waiting: Int get() = tasks.size

    override fun dispatch(context: CoroutineContext, block: Runnable) {
        tasks.add(block)
    }

    fun runNext(): Boolean {
        val task = tasks.removeFirstOrNull() ?: return false
        task.run()
        return true
    }

    fun drain() {
        while (tasks.isNotEmpty()) runNext()
    }
}
