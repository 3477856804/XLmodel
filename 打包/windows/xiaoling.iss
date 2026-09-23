; 小凌 XIAOLING · Inno Setup 安装脚本（Windows）
; 用法：先 python packaging\build.py 产出 dist\xiaoling\，再
;       iscc packaging\windows\xiaoling.iss
#define MyAppName "小凌 XIAOLING"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "XIAOLING"
#define MyAppExeName "xiaoling.exe"

[Setup]
AppId={{8E4C1B52-9F31-4E3B-9C5A-XIAOLING0001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\XIAOLING
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputBaseFilename=xiaoling-setup-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
SetupIconFile=..\..\packaging\xiaoling.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "chinese"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"

[Files]
Source: "..\..\dist\xiaoling\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即启动小凌"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 仅在用户确认时才删除成长数据（默认保留，避免误删记忆与自研模型）
Type: filesandordirs; Name: "{app}\.star_core\tts"
Type: filesandordirs; Name: "{app}\.star_core\screenshots"
