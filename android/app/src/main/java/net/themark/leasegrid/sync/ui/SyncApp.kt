@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package net.themark.leasegrid.sync.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import net.themark.leasegrid.sync.recovery.SCARY_LOSS

private val THREAT = listOf(
    "Friendnet trust — unpaid by default. This is not Dropbox-the-company and not Filecoin.",
    "No storage proofs — dead nodes are dropped. This phone does not offer storage.",
    "Transport honesty — the invite may claim I2P or Tor. Reads may use LAN or WAN.",
    "Recovery — lose the recovery key and your devices and access can be gone forever. Import the same U4 recovery key. There is no reset password.",
)

@Composable
fun SyncApp(model: AppModel, onPickRecovery: () -> Unit) {
    MaterialTheme {
        Surface(modifier = Modifier.fillMaxSize()) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                when (val place = model.place) {
                    Place.Welcome -> Welcome(model, onPickRecovery)
                    Place.Import -> Import(model, onPickRecovery)
                    Place.Folders -> Folders(model)
                    is Place.Folder -> FolderDetail(model, place)
                    is Place.Downloading -> Downloading(model, place)
                    is Place.Ready -> Ready(model, place)
                    Place.About -> About(model)
                    Place.Settings -> Settings(model)
                }
            }
        }
    }
}

@Composable
private fun Welcome(model: AppModel, onPickRecovery: () -> Unit) {
    Text("Leasegrid Sync", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
    Text("See your folders on this phone. Download files when you need them.")
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Read before you join", fontWeight = FontWeight.SemiBold)
            THREAT.forEachIndexed { index, line ->
                Text("${index + 1}. $line", style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
    val inviteFocus = remember { FocusRequester() }
    LaunchedEffect(model.acknowledged) {
        if (!model.acknowledged) return@LaunchedEffect
        // After the checkbox, the field must own the IME so adb `input text` lands.
        kotlinx.coroutines.delay(50)
        runCatching { inviteFocus.requestFocus() }
    }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Checkbox(
            checked = model.acknowledged,
            onCheckedChange = { model.acknowledged = it },
            modifier = Modifier
                .testTag("threat_ack")
                .semantics { contentDescription = "threat_ack" },
        )
        Text("I understand the four points above.")
    }
    OutlinedTextField(
        value = model.inviteText,
        onValueChange = { model.inviteText = it },
        modifier = Modifier
            .fillMaxWidth()
            .testTag("invite_field")
            .focusRequester(inviteFocus)
            .semantics { contentDescription = "invite_field" },
        label = { Text("Invite") },
        placeholder = { Text("paste invite…") },
        singleLine = true,
        keyboardOptions = KeyboardOptions(
            keyboardType = KeyboardType.Uri,
            imeAction = ImeAction.Done,
        ),
        keyboardActions = KeyboardActions(onDone = { if (model.joinEnabled()) model.join() }),
    )
    Button(
        onClick = { model.join() },
        enabled = model.joinEnabled() && !model.busy,
        modifier = Modifier
            .fillMaxWidth()
            .testTag("join_button")
            .semantics { contentDescription = "join_button" },
    ) { Text(if (model.busy) "Joining…" else "Join friendnet") }
    TextButton(
        onClick = onPickRecovery,
        modifier = Modifier
            .testTag("import_recovery_button")
            .semantics { contentDescription = "import_recovery_button" },
    ) { Text("Import recovery key instead…") }
    FailCard(model)
    if (model.busy) CircularProgressIndicator()
}

@Composable
private fun Import(model: AppModel, onPickRecovery: () -> Unit) {
    TextButton(onClick = { model.goWelcome() }) { Text("←  Import recovery key") }
    Text("Use a *.leasegrid-recovery file exported from desktop Sync (U4). Same format.")
    Text(SCARY_LOSS, fontWeight = FontWeight.Medium)
    OutlinedButton(onClick = onPickRecovery, modifier = Modifier.fillMaxWidth()) {
        Text(if (model.pickedName.isBlank()) "Choose recovery file" else model.pickedName)
    }
    val passphraseFocus = remember { FocusRequester() }
    LaunchedEffect(model.pickedName) {
        if (model.pickedBytes == null) return@LaunchedEffect
        kotlinx.coroutines.delay(50)
        runCatching { passphraseFocus.requestFocus() }
    }
    OutlinedTextField(
        value = model.passphrase,
        onValueChange = { model.passphrase = it },
        modifier = Modifier
            .fillMaxWidth()
            .testTag("passphrase_field")
            .focusRequester(passphraseFocus)
            .semantics { contentDescription = "passphrase_field" },
        label = { Text("Passphrase (if any)") },
        visualTransformation = PasswordVisualTransformation(),
        singleLine = true,
        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
    )
    Button(
        onClick = { model.importRecovery() },
        enabled = !model.busy && model.pickedBytes != null,
        modifier = Modifier
            .fillMaxWidth()
            .testTag("import_confirm")
            .semantics { contentDescription = "import_confirm" },
    ) { Text(if (model.busy) "Importing…" else "Import recovery key") }
    OutlinedButton(onClick = { model.goWelcome() }, modifier = Modifier.fillMaxWidth()) { Text("Cancel") }
    FailCard(model)
}

@Composable
private fun Folders(model: AppModel) {
    var menu by remember { mutableStateOf(false) }
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
        Text("Folders", style = MaterialTheme.typography.headlineSmall, modifier = Modifier.weight(1f))
        TextButton(onClick = { menu = true }) { Text("More") }
        DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
            DropdownMenuItem(text = { Text("Refresh") }, onClick = { menu = false; model.refresh() })
            DropdownMenuItem(text = { Text("About / Recovery") }, onClick = { menu = false; model.goAbout() })
            DropdownMenuItem(text = { Text("Settings") }, onClick = { menu = false; model.goSettings() })
        }
    }
    val online = model.session?.servers?.isNotEmpty() == true
    Text(if (online) "Online · unpaid" else "Offline · unpaid")
    Text("This phone does not offer storage. Offer and Credit are not on this screen.", style = MaterialTheme.typography.bodySmall)
    FailCard(model)
    val folders = model.session?.folders.orEmpty()
    if (folders.isEmpty()) {
        Text("No folders yet.")
        Text("Join reached this friendnet. Import a recovery key from desktop Sync to see folder names. This phone cannot invent folders.")
        OutlinedButton(onClick = { model.goImport() }) { Text("Import recovery key…") }
    } else {
        folders.forEach { folder ->
            Card(modifier = Modifier.fillMaxWidth(), onClick = { model.openFolder(folder) }) {
                Column(Modifier.padding(14.dp)) {
                    Text(folder.name, fontWeight = FontWeight.Medium)
                    Text(if (online) "Available" else "Checking…", style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
    if (model.busy) LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
}

@Composable
private fun FolderDetail(model: AppModel, place: Place.Folder) {
    TextButton(onClick = { model.goFolders() }) { Text("← ${place.folder.name}") }
    FailCard(model)
    if (place.children.isEmpty()) {
        Text("This folder has no files this phone can list.")
    }
    place.children.forEach { row ->
        Card(
            modifier = Modifier.fillMaxWidth(),
            onClick = { model.openChild(row, place.folder) },
        ) {
            Column(Modifier.padding(14.dp)) {
                Text(row.name, fontWeight = FontWeight.Medium)
                val kind = if (row.kind == "dir") "Folder" else "${row.size} bytes · Tap to download"
                Text(kind, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
    if (model.busy) LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
}

@Composable
private fun Downloading(model: AppModel, place: Place.Downloading) {
    TextButton(onClick = { model.cancelDownload() }) { Text("← ${place.name}") }
    Text("Downloading…")
    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
    OutlinedButton(onClick = { model.cancelDownload() }) { Text("Cancel") }
    Text("When finished: Open with…")
    FailCard(model)
}

@Composable
private fun Ready(model: AppModel, place: Place.Ready) {
    TextButton(onClick = { model.goFolders() }) { Text("← ${place.name}") }
    Text("Downloaded on this phone.")
    Text(place.file.name, style = MaterialTheme.typography.bodySmall)
    Button(onClick = { model.openReady(place.file) }, modifier = Modifier.fillMaxWidth()) {
        Text("Open with…")
    }
    FailCard(model)
}

@Composable
private fun About(model: AppModel) {
    TextButton(onClick = { model.goFolders() }) { Text("← About / Recovery") }
    Text("Recovery keys are exported from Leasegrid Sync on your computer (U4).")
    Text("This phone imports that same *.leasegrid-recovery file to restore folder access (read / download).")
    Text(SCARY_LOSS, fontWeight = FontWeight.Medium)
    Text("To add folders or export a new key, use desktop Sync. This phone does not write or sync files back.")
    Button(onClick = { model.goImport() }, modifier = Modifier.fillMaxWidth()) { Text("Import recovery key…") }
    FailCard(model)
}

@Composable
private fun Settings(model: AppModel) {
    TextButton(onClick = { model.goFolders() }) { Text("← Settings") }
    Text("Transport honesty: an invite may name I2P or Tor. File reads use the storage address the friendnet announced, which may be LAN or WAN. Loopback addresses are also tried via the emulator host alias.")
    Text("Write, Magic Folder sync, Offer, and Credit stay on desktop Sync. They are not on this phone.")
    OutlinedButton(onClick = { model.clearDownloads() }, modifier = Modifier.fillMaxWidth()) {
        Text("Clear downloads on this phone")
    }
    OutlinedButton(onClick = { model.forgetThisPhone() }, modifier = Modifier.fillMaxWidth()) {
        Text("Forget this phone’s session")
    }
    FailCard(model)
}

@Composable
private fun FailCard(model: AppModel) {
    val banner = model.fail ?: return
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("FAIL — ${banner.message}", fontWeight = FontWeight.SemiBold)
            Text("Next: ${banner.next}")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { model.retryFail() }) { Text("Retry") }
                OutlinedButton(onClick = { model.dismissFail() }) { Text("Dismiss") }
            }
        }
    }
    Spacer(Modifier.height(4.dp))
}
