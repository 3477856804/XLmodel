# 小凌 · 发布手册（仓库 / 官网 / 四平台产物）

> 目标：Windows / Linux / macOS / Android 四个平台各自独立下载，官网
> `xiaoling-4o6.pages.dev` 四个按钮各指向自己的产物，源码同时落在 Gitee 与 GitHub。

---

## 1. 源码仓库

| 平台 | 地址 | 说明 |
|---|---|---|
| GitHub | `https://github.com/3477856804/XLmodel` | 与 `XLmodel-release`（放安装包的仓库）同属一个账号 |
| Gitee | `https://gitee.com/COSMOnb666/XLmodel` | 与 `scripts/publish.py` 里的 `REPO_SLUG` 一致 |

远端已经在本地配好（`github` / `gitee` 两个 remote），推送只需 token：

```bash
export GITHUB_TOKEN=xxxxx   # https://github.com/settings/tokens  勾选 repo
export GITEE_TOKEN=xxxxx    # https://gitee.com/profile/personal_access_tokens
python tools/push_repos.py            # 仓库不存在会自动建（公开）
python tools/push_repos.py --private  # 想建私有库加这个
python tools/push_repos.py --dry-run  # 只看会做什么
```

脚本会把 token 临时写进 remote URL，推完立刻改回干净地址，不会留在 `.git/config` 里。

**提交前记得**：`.gitignore` 已排除 `resources/models/`、`*.vrm`、`frontend/build/`、
`.star_core/`、`data/` 与各类发布二进制，所以首次提交只有约 243 个文件 / 8 MB。

---

## 2. 官网（Cloudflare Pages）

- 源码：`website/index.html`（**单文件**，样式与脚本全内联，无外部依赖）
- 部署：`.github/workflows/deploy-pages.yml`，推送 `main` 且 `website/**` 有改动时自动部署
- 项目名：`xiaoling`

### ⚠️ 必须做：轮换 Cloudflare Token

旧版 `deploy-pages.yml` 曾把 API Token **硬编码** 在工作流里。现已改为读取 Secrets，
但那枚令牌只要出现过就该作废。请去 Cloudflare 后台把它 **Rotate（轮换）**，
然后在 GitHub 仓库 `Settings → Secrets and variables → Actions` 里加：

- `CF_API_TOKEN`
- `CF_ACCOUNT_ID`

### 下载区

四个卡片对应四个**独立**产物，互不夹带：

| 平台 | 资产名 | 体积 | 内容 |
|---|---|---|---|
| Windows | `xiaoling-setup-0.0.1.exe` | ~330 MB | `xiaoling.exe` + `backend.exe` + `flutter_windows.dll` + `data/` + `resources/` |
| Linux | `XiaoLing-x86_64.AppImage` | ~366 MB | Linux bundle + `backend` |
| macOS | `xiaoling-macos.dmg` | ~345 MB | `.app`（内含 `backend`） |
| Android | `xiaoling-android-v0.0.1.apk` | ~114 MB | arm64-v8a / armeabi-v7a / x86_64 + Chaquopy Python |

已核验：Windows 包与 Android 包内**不含**其他平台的二进制（`.exe/.dll/.dmg/.AppImage` 均无）。
Linux / macOS 是 CI 上各自独立的构建产物，天然单平台。

每个按钮下方另有「镜像慢？GitHub 直连」，用于 ghfast.top 加速镜像抽风时兜底。

---

## 3. 桌面端真 3D 是怎么实现的

Flutter 侧用 `flutter_inappwebview` 打开后端起的本地 HTTP 服务上的
`viewer.html`，页面里跑 **three.js + @pixiv/three-vrm** 直接渲染 VRM 0.0 模型。

```
Flutter InAppWebView
   └─ http://127.0.0.1:<port>/viewer.html?model=小凌.vrm
        └─ 后端 webpanel.py 静态服务（只读白名单目录）
             ├─ /viewer.html
             ├─ /vendor/three.module.js、three-vrm.module.js、GLTFLoader…
             └─ /models/*.vrm   （resources/models 与 .star_core/models）
```

选它的原因：原先的 `model_viewer_plus` 在桌面端会崩 —— 它内部走
`webview_flutter`，而后者只有 Android/iOS 实现，桌面触发
`'WebViewPlatform.instance != null'` 断言。`flutter_inappwebview` 四端都有实现：

| 平台 | WebView 引擎 | 运行期要求 |
|---|---|---|
| Windows | WebView2 (Edge Chromium) | Win11 自带；Win10 需装 WebView2 Runtime。**构建期**还需 NuGet |
| macOS | WKWebView | 系统自带 |
| Linux | WPE WebKit | `libwpewebkit` / `libwebkit2gtk-4.1`（见 `packaging/linux/install_deps.sh`） |
| Android | 系统 WebView | 已在 `AndroidManifest.xml` 打开 `usesCleartextTraffic`（要访问 127.0.0.1） |

### 已知的两个构建坑（已修）

1. **Windows 需要 NuGet**：`flutter_inappwebview_windows` 构建时会用
   `nuget install` 拉 WebView2 / CppWinRT / WIL / nlohmann.json。
   本机 VS Build Tools 没带，已装官方 `nuget.exe` 并加入用户 PATH。
   CI（windows-2022）自带，不受影响。
2. **MSVC 14.5x 的 STL1011**：插件还在用 `<experimental/coroutine>`，新版 MSVC
   把它标成硬错误。已在 `frontend/windows/CMakeLists.txt` 加
   `-D_SILENCE_EXPERIMENTAL_COROUTINE_DEPRECATION_WARNINGS`。

### 版本约束

`flutter_inappwebview` 必须 ≥ `6.2.0-beta.3` —— 稳定版 6.1.5 **没有 Linux 实现**。
它要求 Flutter ≥ 3.32 / Dart ≥ 3.8，所以 CI 的 `FLUTTER_VERSION` 已从 3.24 提到 **3.47.6**。

### 排查 3D 白屏

后端启动时加环境变量开访问日志，就能看到 WebView 到底来没来取东西：

```bash
XIAOLING_ACCESS_LOG=1 python main.py --no-web
```

页面内的失败会走 `console.error`，Flutter 侧以 `[3D]` 前缀打印出来。

---

## 4. 构建产物（GitHub Release）

`.github/workflows/build-all.yml` 在推送 `main` 时构建四平台并挂到 Release
（tag `flutter-v0.0.1`，仓库 `3477856804/XLmodel-release`）。

当前 Release 里有 6 个资产，其中 `xiaoling-windows-x64.zip` 与
`xiaoling-linux-x64.tar.gz` 是早期遗留的**重复**副本，官网不引用；
后续可考虑清理，避免用户下错。
