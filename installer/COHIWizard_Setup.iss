; COHIWizard_Setup.iss  -  Windows installer for COHIWizard (Inno Setup 6)
;
; The installer does not contain COHIWizard itself. It installs
;   - a private Python 3.10 (nuget package, nothing registered in Windows)
;   - cohi_setup.py (current version from GitHub, bundled copy as fallback)
; and then runs cohi_setup.py, which creates the venv, installs the Python
; packages and opens the "COHIWizard setup" window for choosing modules and
; drivers. Modules can be changed later via the start menu entry
; "COHIWizard Setup" or the Setup menu of COHIWizard.
;
; Build with build_installer.ps1 (downloads the Python package into build\).

#ifndef AppVersion
  #define AppVersion "2.3"
#endif
#ifndef Branch
  #define Branch "cohiwizard_v2.3"
#endif
#define AppName "COHIWizard"
#define Repo "hermy-sf/COHIWizard"
#define SetupUrl "https://raw.githubusercontent.com/" + Repo + "/" + Branch + "/sources/cohi_setup.py"

[Setup]
AppId={{49BD31D8-5F39-4953-8001-24AB26608052}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=COHIRADIA
AppPublisherURL=https://github.com/{#Repo}
AppSupportURL=https://github.com/{#Repo}/issues
; per user, no administrator rights needed; same default as cohi_setup.py
PrivilegesRequired=lowest
DefaultDirName={%USERPROFILE}\{#AppName}
DisableProgramGroupPage=yes
DefaultGroupName={#AppName}
UsePreviousAppDir=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LicenseFile=..\LICENSE
; compact square version of sources\COHIWizard_ico4.ico (that one is too large for ISCC)
SetupIconFile=COHIWizard.ico
UninstallDisplayIcon={app}\COHIWizard.ico
UninstallDisplayName={#AppName} {#AppVersion}
OutputDir=Output
OutputBaseFilename=COHIWizard_Setup_{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
de.StatusSetup=Python-Pakete werden installiert (Konsolenfenster). Das kann 10 - 30 Minuten dauern, bitte Geduld. Danach öffnet sich das Fenster "COHIWizard setup".
en.StatusSetup=Installing the Python packages (console window). This can take 10 - 30 minutes, please be patient. Then the "COHIWizard setup" window opens.
de.SetupFailed=Das COHIWizard-Setup wurde mit Fehler %1 beendet.%n%nDie Meldungen stehen im Konsolenfenster. Sie können das Setup später über das Startmenü (COHIWizard Setup) erneut ausführen.
en.SetupFailed=COHIWizard setup ended with error %1.%n%nSee the messages in the console window. You can run the setup again later from the start menu (COHIWizard Setup).
de.ExecFailed=cohi_setup.py konnte nicht gestartet werden: %1
en.ExecFailed=Cannot start cohi_setup.py: %1
de.DownloadFailed=Die aktuelle Version von cohi_setup.py konnte nicht heruntergeladen werden, es wird die mitgelieferte verwendet.%n%n%1
en.DownloadFailed=The current cohi_setup.py could not be downloaded, the bundled version is used.%n%n%1
de.RemoveData=Sollen auch die Programmdateien im Installationsordner gelöscht werden?%n%n%1\sources%n%nDazu gehören die Konfiguration (config_wizard.yaml) und alle Daten, die dort gespeichert wurden (z. B. Aufnahmen in sources\out).%n%nBei "Nein" bleibt dieser Ordner erhalten.
en.RemoveData=Also delete the program files in the installation folder?%n%n%1\sources%n%nThis includes the configuration (config_wizard.yaml) and all data stored there (e.g. recordings in sources\out).%n%nWith "No" this folder is kept.
de.IconSetup=COHIWizard Setup (Module und Treiber verwalten)
en.IconSetup=COHIWizard Setup (manage modules and drivers)

[Files]
Source: "build\python\*"; DestDir: "{app}\python"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "COHIWizard.ico"; DestDir: "{app}"; Flags: ignoreversion
; fallback if GitHub cannot be reached during installation
Source: "..\sources\cohi_setup.py"; Flags: dontcopy

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\venv\Scripts\pythonw.exe"; Parameters: "COHIWizard.py"; WorkingDir: "{app}\sources"; IconFilename: "{app}\COHIWizard.ico"
Name: "{group}\{cm:IconSetup}"; Filename: "{app}\venv\Scripts\pythonw.exe"; Parameters: """{app}\sources\cohi_setup.py"" --stage2 --target ""{app}"""; WorkingDir: "{app}\sources"; IconFilename: "{app}\COHIWizard.ico"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"

[UninstallDelete]
; created by cohi_setup.py
Type: filesandordirs; Name: "{app}\venv"
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\documentation"
Type: files; Name: "{app}\requirements.txt"
Type: files; Name: "{app}\LICENSE"
Type: files; Name: "{app}\README.md"
Type: files; Name: "{app}\COHIWizard.bat"
Type: files; Name: "{app}\COHIWizard_setup.bat"
Type: files; Name: "{userdesktop}\COHIWizard.lnk"
Type: dirifempty; Name: "{app}"

[Code]
function GetSetupScript(): String;
begin
  Result := ExpandConstant('{tmp}\cohi_setup.py');
  try
    DownloadTemporaryFile('{#SetupUrl}', 'cohi_setup.py', '', nil);
  except
    Log('download of cohi_setup.py failed: ' + GetExceptionMessage);
    SuppressibleMsgBox(FmtMessage(CustomMessage('DownloadFailed'), [GetExceptionMessage]),
                       mbInformation, MB_OK, IDOK);
    ExtractTemporaryFile('cohi_setup.py');
  end;
end;

procedure RunCohiSetup();
var
  Py, Script, Params: String;
  ResultCode: Integer;
begin
  Py := ExpandConstant('{app}\python\python.exe');
  Script := GetSetupScript();
  WizardForm.StatusLabel.Caption := CustomMessage('StatusSetup');
  { stage 1 (console: venv + pip) starts stage 2 (setup window) and waits for it;
    on an error the console stays open so that the messages can be read }
  Params := '/c ""' + Py + '" "' + Script + '" --target "' + ExpandConstant('{app}') +
            '" --branch {#Branch} || (pause & exit 1)"';
  Log('cmd.exe ' + Params);
  if not Exec(ExpandConstant('{cmd}'), Params, ExpandConstant('{app}'), SW_SHOW,
              ewWaitUntilTerminated, ResultCode) then
    SuppressibleMsgBox(FmtMessage(CustomMessage('ExecFailed'), [SysErrorMessage(ResultCode)]),
                       mbError, MB_OK, IDOK)
  else if ResultCode <> 0 then
    SuppressibleMsgBox(FmtMessage(CustomMessage('SetupFailed'), [IntToStr(ResultCode)]),
                       mbError, MB_OK, IDOK);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    RunCohiSetup();
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Src: String;
begin
  if CurUninstallStep = usPostUninstall then begin
    Src := ExpandConstant('{app}\sources');
    if DirExists(Src) and
       (SuppressibleMsgBox(FmtMessage(CustomMessage('RemoveData'), [ExpandConstant('{app}')]),
                           mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES) then begin
      DelTree(Src, True, True, True);
      RemoveDir(ExpandConstant('{app}'));
    end;
  end;
end;
