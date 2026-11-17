package net.themark.leasegrid.sync.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

/**
 * The Retry button's action.
 * [pull] returns it once. A second pull is empty until [arm] again,
 * so a double tap cannot run the same action twice.
 */
internal class RetryOnce {
    private var action: (() -> Unit)? = null

    /** True while an action waits. The card shows Retry only then (#88). */
    var armed by mutableStateOf(false)
        private set

    fun arm(again: (() -> Unit)?) {
        action = again
        armed = again != null
    }

    fun pull(): (() -> Unit)? {
        val current = action
        action = null
        armed = false
        return current
    }
}
