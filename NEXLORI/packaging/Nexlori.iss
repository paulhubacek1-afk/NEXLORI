; Nexlori Windows installer. Builds from dist/Nexlori.exe after PyInstaller completes.
#ifndef MyAppVersion
  #define MyAppVersion "0.5.0"
#endif

[Setup]
AppId={{A67AA3C0-44A7-4F47-9E21-9216B70A1F73}
AppName=Nexlori
AppVersion={#MyAppVersion}
AppPublisher=Nexlori
AppPublisherURL=https://github.com/paulhubacek1-afk/NEXLORI
AppSupportURL=https://github.com/paulhubacek1-afk/NEXLORI/issues
AppUpdatesURL=https://github.com/paulhubacek1-afk/NEXLORI/releases
DefaultDirName={localappdata}\Programs\Nexlori
DefaultGroupName=Nexlori
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=nexlori.ico
UninstallDisplayIcon={app}\Nexlori.exe
OutputDir=..\dist
OutputBaseFilename=Nexlori-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes
UsePreviousGroup=yes
Uninstallable=yes

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknüpfung erstellen"; GroupDescription: "Zusätzliche Symbole:"; Flags: checkedonce

[Files]
Source: "..\dist\Nexlori.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Nexlori"; Filename: "{app}\Nexlori.exe"; IconFilename: "{app}\Nexlori.exe"; Comment: "Nexlori Browser"
Name: "{autodesktop}\Nexlori"; Filename: "{app}\Nexlori.exe"; IconFilename: "{app}\Nexlori.exe"; Tasks: desktopicon; Comment: "Nexlori Browser"

[Run]
Filename: "{app}\Nexlori.exe"; Description: "Nexlori jetzt starten"; Flags: postinstall nowait skipifsilent
