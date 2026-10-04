@file:OptIn(
    androidx.compose.material3.ExperimentalMaterial3Api::class,
    androidx.compose.foundation.ExperimentalFoundationApi::class,
)

package net.themark.leasegrid.sync.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
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
import androidx.compose.ui.semantics.clearAndSetSemantics
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
fun SyncApp(model: AppModel, onPickRecovery: () -> Unit, onAddFile: () -> Unit) {
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
                    is Place.Folder -> FolderDetail(model, place, onAddFile)
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
            modifier = Modifier.semantics(mergeDescendants = true) {
                dogfoodField("threat_ack")
            },
        )
        Text("I understand the four points above.")
    }
    OutlinedTextField(
        value = model.inviteText,
        onValueChange = { model.inviteText = it },
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 56.dp)
            .focusRequester(inviteFocus)
            .semantics(mergeDescendants = true) { dogfoodField("invite_field") },
        label = { Text("Invite") },
        placeholder = { Text("paste invite…") },
        singleLine = true,
        keyboardOptions = KeyboardOptions(
            keyboardType = KeyboardType.Uri,
            imeAction = ImeAction.Done,
        ),
        keyboardActions = KeyboardActions(onDone = { if (model.joinEnabled()) model.join() }),
    )
    val joinOn = joinControlEnabled(model.acknowledged, model.inviteText, model.busy)
    ProbeButton(
        name = "join_button",
        enabled = joinOn,
        onClick = { model.join() },
        label = if (model.busy) "Joining…" else "Join friendnet",
    )
    ProbeButton(
        name = "import_recovery_button",
        enabled = true,
        onClick = onPickRecovery,
        label = "Import recovery key instead…",
        filled = false,
    )
    FailCard(model)
    if (model.busy) CircularProgressIndicator()
}

@Composable
private fun Import(model: AppModel, onPickRecovery: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .semantics { dogfoodField("import_screen") },
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        ImportBody(model, onPickRecovery)
    }
}

@Composable
private fun ImportBody(model: AppModel, onPickRecovery: () -> Unit) {
    TextButton(onClick = { model.goWelcome() }) { Text("←  Import recovery key") }
    Text("Use a *.leasegrid-recovery file exported from desktop Sync (U4). Same format.")
    Text(SCARY_LOSS, fontWeight = FontWeight.Medium)
    OutlinedButton(onClick = onPickRecovery, modifier = Modifier.fillMaxWidth()) {
        Text(if (model.pickedName.isBlank()) "Choose recovery file" else model.pickedName)
    }
    val passphraseFocus = remember { FocusRequester() }
    val passphraseBring = remember { BringIntoViewRequester() }
    LaunchedEffect(model.pickedBytes) {
        if (model.pickedBytes == null) return@LaunchedEffect
        kotlinx.coroutines.delay(50)
        runCatching { passphraseBring.bringIntoView() }
        runCatching { passphraseFocus.requestFocus() }
    }
    OutlinedTextField(
        value = model.passphrase,
        onValueChange = { model.passphrase = it },
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 56.dp)
            .focusRequester(passphraseFocus)
            .bringIntoViewRequester(passphraseBring)
            .semantics(mergeDescendants = true) { dogfoodField("passphrase_field") },
        label = { Text("Passphrase (if any)") },
        visualTransformation = PasswordVisualTransformation(),
        singleLine = true,
        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
    )
    ProbeButton(
        name = "import_confirm",
        enabled = !model.busy && model.pickedBytes != null,
        onClick = { model.importRecovery() },
        label = if (model.busy) "Importing…" else "Import recovery key",
    )
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
private fun FolderDetail(model: AppModel, place: Place.Folder, onAddFile: () -> Unit) {
    TextButton(onClick = { model.goFolders() }) { Text("← ${place.folder.name}") }
    val writable = model.folderWritable(place.folder)
    if (!writable) {
        Text(WriteCopy.READ_ONLY)
    }
    WriteSheetCard(model)
    FailCard(model)
    val rows = model.visibleFiles(place)
    if (rows.isEmpty()) {
        Text("This folder has no files this phone can list.")
    }
    rows.forEach { row ->
        if (row.kind == "dir") {
            Card(
                modifier = Modifier.fillMaxWidth(),
                onClick = {
                    model.openChild(ChildRow(row.name, "dir", row.cap, row.size), place.folder)
                },
            ) {
                Column(Modifier.padding(14.dp)) {
                    Text(row.name, fontWeight = FontWeight.Medium)
                    Text("Folder", style = MaterialTheme.typography.bodySmall)
                }
            }
        } else {
            FileRowCard(model, place.folder, row)
        }
    }
    if (writable) {
        ProbeButton(
            name = "add_file",
            enabled = !model.busy,
            onClick = onAddFile,
            label = WriteCopy.ADD,
        )
    }
    if (model.busy) LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
}

@Composable
private fun FileRowCard(model: AppModel, folder: net.themark.leasegrid.sync.session.FolderRef, row: VisibleFile) {
    val label = chipText(row)
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(row.name, fontWeight = FontWeight.Medium)
            if (row.chip == Chip.Pending) {
                Text(label, style = MaterialTheme.typography.bodySmall)
                if (showPendingProgress(row)) {
                    LinearProgressIndicator(
                        progress = { row.progress.coerceIn(0f, 0.9f) },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
                val actions = rowActions(model.folderWritable(folder), row)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if ("Retry" in actions) {
                        Button(onClick = { model.retryUpload(row.name) }) { Text("Retry") }
                    }
                    if ("Cancel" in actions) {
                        OutlinedButton(onClick = { model.askDiscard(row.name) }) { Text("Cancel") }
                    }
                }
            } else {
                Text(
                    "$label · ${formatByteSize(row.size)}",
                    style = MaterialTheme.typography.bodySmall,
                )
                val actions = rowActions(model.folderWritable(folder), row)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if ("Open" in actions) {
                        TextButton(onClick = {
                            model.openChild(ChildRow(row.name, "file", row.cap, row.size), folder)
                        }) { Text("Open") }
                    }
                    if ("Remove" in actions) {
                        TextButton(onClick = { model.askRemove(row.name, row.cap) }) { Text("Remove") }
                    }
                }
            }
        }
    }
}

@Composable
private fun WriteSheetCard(model: AppModel) {
    when (val sheet = model.writeSheet()) {
        null -> return
        is WriteSheet.Clash -> {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("${sheet.name} is already in ${sheet.folder}.", fontWeight = FontWeight.Medium)
                    Button(onClick = { model.replaceClash() }, modifier = Modifier.fillMaxWidth()) {
                        Text("Replace")
                    }
                    Button(onClick = { model.keepBothClash() }, modifier = Modifier.fillMaxWidth()) {
                        Text("Keep both")
                    }
                    OutlinedButton(onClick = { model.cancelClash() }, modifier = Modifier.fillMaxWidth()) {
                        Text("Cancel")
                    }
                }
            }
        }
        is WriteSheet.Remove -> {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        "Remove ${sheet.name} from ${sheet.folder} on the friendnet?",
                        fontWeight = FontWeight.Medium,
                    )
                    Text("Other Sync computers will lose this copy.")
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = { model.confirmRemove() }) { Text("Remove") }
                        OutlinedButton(onClick = { model.cancelSheet() }) { Text("Cancel") }
                    }
                }
            }
        }
        is WriteSheet.Discard -> {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Discard ${sheet.name}?", fontWeight = FontWeight.Medium)
                    Text("It is not on the friendnet yet.")
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = { model.confirmDiscard() }) { Text("Discard") }
                        OutlinedButton(onClick = { model.cancelSheet() }) { Text("Cancel") }
                    }
                }
            }
        }
    }
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
    Text(WriteCopy.DESKTOP_FOLDERS)
    Text("This phone can add a file to a folder it already shows. It does not create folders or export a new key.")
    Button(onClick = { model.goImport() }, modifier = Modifier.fillMaxWidth()) { Text("Import recovery key…") }
    FailCard(model)
}

@Composable
private fun Settings(model: AppModel) {
    TextButton(onClick = { model.goFolders() }) { Text("← Settings") }
    Text("Transport honesty: an invite may name I2P or Tor. File reads use the storage address the friendnet announced, which may be LAN or WAN. Loopback addresses are also tried via the emulator host alias.")
    Text(WriteCopy.DESKTOP_FOLDERS)
    Text("This phone can add a file to a folder it already shows. There is no write-sync setting here. Offer and Credit are not on this screen.")
    OutlinedButton(onClick = { model.clearDownloads() }, modifier = Modifier.fillMaxWidth()) {
        Text("Clear downloads on this phone")
    }
    OutlinedButton(onClick = { model.forgetThisPhone() }, modifier = Modifier.fillMaxWidth()) {
        Text("Forget this phone’s session")
    }
    FailCard(model)
}

@Composable
private fun ProbeButton(
    name: String,
    enabled: Boolean,
    onClick: () -> Unit,
    label: String,
    filled: Boolean = true,
) {
    // Size lives on this node. clearAndSetSemantics keeps a single content-desc
    // whose enabled bit matches [enabled], instead of a zero-bounds sibling.
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 48.dp)
            .clearAndSetSemantics { dogfoodProbe(name, enabled, onClick) },
    ) {
        if (filled) {
            Button(onClick = onClick, enabled = enabled, modifier = Modifier.fillMaxWidth()) {
                Text(label)
            }
        } else {
            TextButton(onClick = onClick, enabled = enabled, modifier = Modifier.fillMaxWidth()) {
                Text(label)
            }
        }
    }
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
