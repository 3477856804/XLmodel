# Windows 打包

## 构建后端
```bat
pip install -r requirements.txt
pip install pyinstaller
python -m PyInstaller packaging\backend.spec --noconfirm --distpath packaging\dist1 --workpath packaging\build1
```

## 合并前端（推荐）
```bat
python packaging\assemble_windows.py --zip
```
产物目录：`dist\小凌-Windows-x64\`（主程序 `小凌.exe` + `backend.exe`），并附带同名 zip。

## 做成安装包（可选）
1. 安装 [Inno Setup](https://jrsoftware.org/isdl.php)
2. 先完成上面的合并步骤，再执行：
```bat
iscc packaging\windows\xiaoling.iss
```
产物：`xiaoling-setup-0.0.1.exe`（带开始菜单/桌面快捷方式）。

## 图标
仓库自带 `frontend\assets\icon.ico`。
