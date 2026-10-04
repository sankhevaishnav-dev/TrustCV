' Starts TrustCV invisibly through pythonw.exe.
Option Explicit
Dim fso, shell, projectDir, launcher, pythonw, command
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
launcher = fso.BuildPath(projectDir, "desktop_launcher.py")
pythonw = fso.BuildPath(projectDir, ".venv\Scripts\pythonw.exe")
If Not fso.FileExists(pythonw) Then
  MsgBox "TrustCV's virtual environment was not found." & vbCrLf & "Run the setup commands in README.md first.", vbCritical, "TrustCV"
  WScript.Quit 1
End If
If Not fso.FileExists(launcher) Then
  MsgBox "desktop_launcher.py was not found in the TrustCV folder.", vbCritical, "TrustCV"
  WScript.Quit 1
End If
shell.CurrentDirectory = projectDir
command = Chr(34) & pythonw & Chr(34) & " " & Chr(34) & launcher & Chr(34)
shell.Run command, 0, False
