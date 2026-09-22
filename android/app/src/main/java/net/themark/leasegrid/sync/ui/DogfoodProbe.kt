package net.themark.leasegrid.sync.ui

import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.SemanticsPropertyReceiver
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.testTag
import net.themark.leasegrid.sync.invite.Invite

/** Same gate the Join control uses. Busy keeps the control disabled. */
fun joinControlEnabled(acknowledged: Boolean, invite: String, busy: Boolean): Boolean {
    return Invite.joinEnabled(acknowledged, invite) && !busy
}

/**
 * One accessibility node for a button-shaped control.
 * UiAutomator reads content-desc and enabled. A separate testTag/contentDescription
 * modifier on Material3 Button publishes a zero-size node that stays enabled.
 */
fun SemanticsPropertyReceiver.dogfoodProbe(
    name: String,
    enabled: Boolean,
    onClick: (() -> Unit)? = null,
) {
    contentDescription = name
    testTag = name
    role = Role.Button
    if (enabled) {
        if (onClick != null) {
            this.onClick(label = name) {
                onClick()
                true
            }
        }
    } else {
        disabled()
    }
}

/** Content-desc and testTag on the text field itself. Does not clear editable text. */
fun SemanticsPropertyReceiver.dogfoodField(name: String) {
    contentDescription = name
    testTag = name
}
