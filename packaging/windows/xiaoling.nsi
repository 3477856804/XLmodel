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
    ; 复制 Flutter 前端
    SetOutPath "$INSTDIR"
    File /r "..\..\frontend\build\windows\x64\runner\Release\*.*"

    ; 复制 Python 后端（PyInstaller onedir：dist/backend/）
    File /r "..\..\dist\backend\*.*"

    ; 复制模型资源
    SetOutPath "$INSTDIR\resources"
    File /r "..\..\resources\*.*"

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
