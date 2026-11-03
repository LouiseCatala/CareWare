#define AppName "CareWare"
#define AppVersion "0.1.0"
#define AppPublisher "CareWare"
#define AppExeName "CareWare.exe"
[Setup]
AppId={{2C77310B-4339-4E63-A154-9F3F2A20A900}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\CareWare
DefaultGroupName={#AppName}
OutputDir=installer_output
OutputBaseFilename=CareWare-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64compatible
MinVersion=10.0
[Files]
Source: "dist\CareWare\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
[Icons]
Name: "{group}\CareWare"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\CareWare"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"
[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch CareWare"; Flags: nowait postinstall skipifsilent

[Code]
function HasWebView2: Boolean;
var
  Version: String;
  Key: String;
begin
  Key := 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  Result := (RegQueryStringValue(HKLM32, Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0'));
  if not Result then
    Result := (RegQueryStringValue(HKCU, Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0'));
end;

function InitializeSetup: Boolean;
begin
  Result := HasWebView2;
  if not Result then
    MsgBox('CareWare requires Microsoft Edge WebView2 Runtime. Install the Evergreen Runtime from https://developer.microsoft.com/microsoft-edge/webview2/ and run setup again. No CareWare files have been installed.', mbError, MB_OK);
end;
