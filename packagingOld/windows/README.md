# Windows 打包

## 一键（推荐）
```bat
pip install -r requirements.txt
pip install pyinstaller
python packaging\build.py --zip
```
产物：`dist\xiaoling\xiaoling.exe`（目录版，推荐）+ `dist\xiaoling-windows-x64.zip`（便携包）
> 目录版比单文件版启动快得多，且 `.star_core`（记忆/适配器/成长日志）就在旁边，迁移只需搬文件夹。

## 做成安装包（可选）
1. 安装 [Inno Setup](https://jrsoftware.org/isdl.php)
2. 先跑上面的打包命令，再执行：
```bat
iscc packaging\windows\xiaoling.iss
```
产物：`xiaoling-setup-1.0.0.exe`（带开始菜单/桌面快捷方式、保留用户成长数据）

## 图标
把 `xiaoling.ico` 放到 `packaging\`，然后：
```bat
python packaging\build.py --icon packaging\xiaoling.ico
```
