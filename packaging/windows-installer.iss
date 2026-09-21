; Inno Setup script for Leasegrid Sync (Windows x64).
; Driven by packaging/build-desktop.sh:
;   ISCC /DAppVersion=0.1.0 /DSourceDir=...\dist\leasegrid-sync /DOutDir=...\dist [/DIcon=...\icon.ico] windows-installer.iss
; Per-user install (no admin prompt); the onedir tree is copied as-is, so the
; bundled tahoe.exe / magic-folder.exe stay siblings of leasegrid-sync.exe.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #error SourceDir must point at the PyInstaller onedir output
#endif
#ifndef OutDir
  #define OutDir "."
#endif

[Setup]
AppId={{7E1C1A1E-2B4A-4B3D-9C3E-5A6B7C8D9E0F}
AppName=Leasegrid Sync
AppVersion={#AppVersion}
AppPublisher=Leasegrid
DefaultDirName={localappdata}\Programs\Leasegrid Sync
DefaultGroupName=Leasegrid Sync
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutDir}
OutputBaseFilename=Leasegrid_Sync-{#AppVersion}-win64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
#ifdef Icon
SetupIconFile={#Icon}
#endif
UninstallDisplayIcon={app}\leasegrid-sync.exe

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Leasegrid Sync"; Filename: "{app}\leasegrid-sync.exe"
Name: "{autodesktop}\Leasegrid Sync"; Filename: "{app}\leasegrid-sync.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\leasegrid-sync.exe"; Description: "Launch Leasegrid Sync"; Flags: nowait postinstall skipifsilent
