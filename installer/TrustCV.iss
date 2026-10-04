#define AppName "TrustCV"
#define AppVersion "0.1.0"
#define AppPublisher "TrustCV Team"
#define PackageDir AddBackslash(SourcePath) + "..\dist\TrustCV"

[Setup]
AppId={{F4C83364-907C-41A1-9A3E-7D3C1BD63A47}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\TrustCV
DefaultGroupName=TrustCV
OutputDir={#AddBackslash(SourcePath)}..\dist\installer
OutputBaseFilename=TrustCV-Setup
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
UninstallDisplayIcon={app}\TrustCV.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "{#PackageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\TrustCV"; Filename: "{app}\TrustCV.exe"
Name: "{autodesktop}\TrustCV"; Filename: "{app}\TrustCV.exe"

[Run]
Filename: "{app}\TrustCV.exe"; Description: "Launch TrustCV"; Flags: postinstall nowait skipifsilent
