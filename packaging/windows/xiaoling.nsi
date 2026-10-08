; 小凌 Windows 安装脚本 (NSIS) —— Inno Setup (xiaoling.iss) 的备选方案。
; 编译: makensis packaging/windows/xiaoling.nsi
; 路径均相对本文件所在目录（packaging/windows/）。正式发布包以 Inno 产物为准。

!define APP_NAME "小凌"
!define APP_VERSION "0.0.1"
!define APP_PUBLISHER "XiaoLing"
!define APP_EXE "小凌.exe"

Name "${APP_NAME}"
OutFile "XiaoLing-Setup-${APP_VERSION}.exe"
InstallDir "$LOCALAPPDATA\Programs\XiaoLing"
RequestExecutionLevel user
Unicode true

; 界面
!include "MUI2.nsh"
!define MUI_ICON "..\..\frontend\assets\icon.ico"
!define MUI_UNICON "..\..\frontend\assets\icon.ico"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

Section "Install"
    ; 使用 assemble_windows.py 产出的已合并目录（dist/小凌-Windows-x64）：
    ; 里面前端已重命名为 小凌.exe，与 backend.exe 同目录，前端才能自动拉起后端。
    ; 先跑：python packaging/assemble_windows.py
    SetOutPath "$INSTDIR"
    File /r "..\..\dist\小凌-Windows-x64\*.*"

    ; 创建快捷方式
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortCut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
    CreateShortCut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"

    ; 写注册表卸载信息
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\XiaoLing" "DisplayName" "${APP_NAME}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\XiaoLing" "UninstallString" "$INSTDIR\uninstall.exe"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\XiaoLing" "DisplayVersion" "${APP_VERSION}"

    ; 卸载程序
    WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Uninstall"
    ; 删除文件
    RMDir /r "$INSTDIR"
    ; 删除快捷方式
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    RMDir "$SMPROGRAMS\${APP_NAME}"
    Delete "$DESKTOP\${APP_NAME}.lnk"
    ; 清理注册表
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\XiaoLing"
SectionEnd
