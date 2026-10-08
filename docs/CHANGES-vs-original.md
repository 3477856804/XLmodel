# XLmodel-main · 原始版本 ↔ 已提交 Gitee 版本 · 改动对比清单

> 生成时间：2026-10-08
> 对比双方：
> - **原始**：`C:\Users\MVP\Desktop\XLmodel-main.zip`（2026-10-08 04:00 打包，1.4 MB）
> - **当前**：Gitee 仓库 `https://gitee.com/COSMOnb666/XLmodel` 的 `main` 分支内容
>
> 比对口径：对两边同名文件做 **SHA-256 全文哈希**比对，不看时间戳、不看文件大小；
> 文件清单以 `git ls-files`（即真正入库的内容）为准。

---

## 一、总览

| 类别 | 文件数 | 说明 |
|---|---:|---|
| **内容修改** | **26** | 两边都有、内容不同 |
| **新增** | **54** | 只存在于当前仓库 |
| ├ 本轮真正新建 | 17 | 这几轮开发新增的文件 |
| └ 项目自带、zip 未收录 | 37 | 原始项目本来就有，只是没被打包进压缩包 |
| **删除** | **0** | **没有任何文件被删除** |
| **内容完全一致** | 165 | 未被触碰 |

原始包 191 个文件 → 当前仓库 245 个文件。

> **零删除已验证**：比对结果为 0 条删除记录，符合"绝不删除任何文件"的红线。
> 包括那些已经失去用途的旧文件（如过期的 `packaging/build.py`、`xiaoling.spec`）
> 也全部保留，仅在 `packaging/README.md` 顶部加了"已失效，请勿使用"的说明。

---

## 二、 先说一个会影响判断的发现：原始 zip 是"部分导出"

这份 zip 只有 1.4 MB，**并非完整项目快照**。它只包含：

```
backend/ (30) docs/ (13) frontend/ (132) resources/ (9)
scripts/ (1) .github/ (4) 根目录 (4)
```

**完全缺失**这些目录：`packaging/`、`tests/`、`shared/`、`plugins/`、`skills/`、`tools/`、`website/`，
连根目录的 `requirements.txt` / `requirements-dev.txt` 都不在里面。

后果很直接：如果只看"新增 54 个"，会把一大堆**项目原本就有**的文件误当成这几轮新增的。
因此下面用**磁盘时间戳**做了二分：

- 集中在 `10-08 05:32 ~ 06:17` 的一批 → 项目落地时就存在，属 zip 打包遗漏
- 在 `10-08 10:49` 之后的 → 本轮开发时段真实产生

| 分组 | 数量 | 判定依据 |
|---|---:|---|
| A. 项目自带但 zip 未收录 | 37 | mtime 05:32–06:17 |
| B. 本轮真正新增/改写 | 17 | mtime 10:49 之后 |

> 其中 B 组有 3 个文件（`packaging/README.md`、`packaging/runtime_hook.py`、
> `packaging/linux/install_deps.sh`）严格说是"项目已有、本轮又改写了"，见第五节备注。

---

## 三、内容修改的 26 个文件（逐个说明）

按改动量排序。"增/删"为 diff 行数。

| # | 文件 | 原行数 | 现行数 | 增 | 删 |
|---|---|---:|---:|---:|---:|
| 1 | `backend/core/model.py` | 1509 | 2653 | +1224 | -80 |
| 2 | `frontend/lib/pages/settings_page.dart` | 2326 | 2819 | +627 | -134 |
| 3 | `frontend/lib/pages/model_store_page.dart` | 2316 | 2952 | +636 | -0 |
| 4 | `frontend/pubspec.lock` | 658 | 794 | +442 | -306 |
| 5 | `backend/core/plugin_system.py` | 695 | 952 | +283 | -26 |
| 6 | `frontend/lib/widgets/model_showcase.dart` | 1127 | 1323 | +231 | -35 |
| 7 | `backend/rpc/server.py` | 1891 | 1986 | +124 | -29 |
| 8 | `frontend/lib/main.dart` | 1316 | 1390 | +86 | -12 |
| 9 | `frontend/lib/pages/dashboard_page.dart` | 1733 | 1772 | +57 | -18 |
| 10 | `backend/core/engine.py` | 1545 | 1577 | +45 | -13 |
| 11 | `.gitignore` | 35 | 68 | +33 | -0 |
| 12 | `.github/workflows/deploy-pages.yml` | 20 | 29 | +14 | -5 |
| 13 | `frontend/lib/widgets/update_dialog.dart` | 1236 | 1248 | +14 | -2 |
| 14 | `frontend/pubspec.yaml` | 37 | 50 | +14 | -1 |
| 15 | `frontend/windows/CMakeLists.txt` | 108 | 119 | +11 | -0 |
| 16 | `frontend/macos/Flutter/GeneratedPluginRegistrant.swift` | 18 | 16 | +4 | -6 |
| 17 | `main.py` | 194 | 202 | +9 | -1 |
| 18 | `frontend/linux/flutter/generated_plugin_registrant.cc` | 19 | 19 | +4 | -4 |
| 19 | `frontend/lib/pages/chat_page.dart` | 1946 | 1951 | +6 | -1 |
| 20 | `backend/core/config.py` | 456 | 462 | +6 | -0 |
| 21 | `frontend/windows/flutter/generated_plugin_registrant.cc` | 17 | 17 | +3 | -3 |
| 22 | `.github/workflows/build-all.yml` | 179 | 182 | +4 | -1 |
| 23 | `frontend/android/app/src/main/AndroidManifest.xml` | 57 | 59 | +3 | -1 |
| 24 | `frontend/linux/flutter/generated_plugins.cmake` | 25 | 26 | +2 | -1 |
| 25 | `frontend/windows/flutter/generated_plugins.cmake` | 25 | 26 | +2 | -1 |
| 26 | `frontend/analysis_options.yaml` | 35 | 36 | +1 | -0 |

### 3.1 后端核心

#### `backend/core/model.py`（+1224 / -80）—— 改动最大的一个文件

这是"本地模型加载不了"那一串问题的集中修复：

1. **新增 GGUF 推理后端整段（+379 行）**
 原来只有 transformers 一条路，而 `AutoModelForCausalLM.from_pretrained` **读不了 GGUF**
 （GGUF 是 llama.cpp 的自包含量化格式，与 safetensors/HF 目录结构完全不同）。
 新加 `is_gguf_path()`、`find_gguf_in()`，并把 llama.cpp 封装成与 transformers 接近的调用接口，
 上层 `LocalModel` 无需关心底层差异。→ 你磁盘上的 `.gguf` 现在能被真正加载。
2. **模型扫描支持单文件权重** `iter_model_entries()` / `entry_name()` / `match_model_entry()`
 旧实现只认**目录**，导致直接丢在 `models/` 根目录下的 `.gguf` 永远扫不出来。
 现在目录与单文件权重一视同仁。
3. **推理后端自动分派**：有 `config.json` 走 transformers；没有但有 gguf 走 llama.cpp；
 transformers 不可用时目录里若有 gguf 仍可"救活"。
4. **身份断言过滤** `looks_like_identity_claim()` + `identity_hint()`
 解决"换了模型却还自称旧模型名"：模型有很强复读倾向，历史上说过一次"我基于 Qwen3.5"，
 之后每次换模型都照着念。现在把这类断言从上下文里剔除，断了复读源头。
5. **模型切换落盘** `_persist_active()` + `config.model.active` 字段
 以前 `model:use` 只改内存，重启退回默认小模型 → 表现为"本地模型没加载成功"。
6. **严格解析模型名**：不再在名字对不上时"静默返回任意一个可用模型"，
 选中的模型不存在时明确回退并提示。
7. **下载通道**：新增 HuggingFace 镜像 + 魔搭（ModelScope）多通道自动回退，
 `_channel_order()` / `_download_modelscope()`，解决国内直连 HF 超时。

#### `backend/core/config.py`（+6 / -0）

新增 `model.active` 字段。注释写得很明确：
`base_model` 记录"商店里下载的默认模型"，`active` 记录"此刻在用哪个"——两件事，以前混为一谈。

#### `backend/core/engine.py`（+45 / -13）

- 启动时优先恢复 `model.active`（上次选中的模型），而不是永远回到 `base_model`。
- 新增 `_model_ready()`。
- 路由分层：**确定性动作**（页面跳转、清空记忆、定时提醒、训练、帮助等）与模型无关，
 任何时候都由路由直接答；**闲聊类意图**（自我介绍、心情）有模型就交给模型，没模型才兜底。

#### `backend/core/plugin_system.py`（+283 / -26）

- **开关状态持久化**：`_state_path/_load_state/_save_state/_apply_state`。
 以前每次重启都回退到 `BUILTIN_PLUGINS` 默认值，打开的插件又关了。
- **安装能力**：`install_from_url()`（真实下载安装 zip）、`install_from_zip()`。
- **自建插件**：`create_plugin()` + `_plugin_template()`（生成模板代码）。
- 红线体现在注释里：*"已存在同名插件时，先把旧版移入隔离区再写入新版"* —— 不删除旧文件。

#### `backend/rpc/server.py`（+124 / -29）

- **新增 `settings:` 指令族**：`settings:options`（拉取可选项，返回 JSON）、
 `settings:set <点分路径> <值>`（写入）。
 设计考量写在注释里：*"这样不必为了加性别、可用性等字段去改 proto 并重新生成
 Dart/Python 桩代码"*。这是设置页去硬编码的基础。
- 修复状态里模型名不更新：以前取 `cfg['model']['base_model']`（静态配置值），
 换成本地 GGUF 后它不会变 → 模型商店里已切到 gpt-oss-20b，状态里还写着 Qwen2.5-0.5B。
 改为优先取实时模型。
- 单文件权重（`.gguf`）的真实路径解析修正（原来按 `store_dir/name` 拼，对单文件不成立）。

### 3.2 入口

#### `main.py`（+9 / -1）

`--no-web` 分支原本完全不启动任何 HTTP 服务。现在改为**也必须启动 3D 查看器服务**：
Flutter 是用 `--no-web` 拉起后端的，但桌面端真 3D 要靠后端把
`viewer.html` / three.js / `.vrm` 通过 HTTP 吐给 WebView。注释里说明了这个反直觉之处。

### 3.3 Flutter 前端

#### `frontend/lib/pages/settings_page.dart`（+627 / -134）—— 页面级改动最大

针对"设置里多处硬编码、滑��拖不动、推理后端复用渲染后端列表"的集中治理：

1. **6 个写死的选项列表改为后端下发**
 原先 `_Opt` 列表硬编码（人格/推理后端/线程/渲染模式/主题/语言/音色）。问题被逐条写在注释里：
 - 推理后端复用了渲染后端的列表（还带 macOS 专有的 Metal）
 - 线程数固定 2/4/6/8（本机是 28 线程）
 - 界面语言列了根本没翻译的语言
 - 音色表写的名字跟后端音色 ID 对不上
 现在全部由 `settings:options` 按本机真实情况生成，并带 fallback 兜底。
2. **推理后端与渲染后端彻底分离**
 新增 `_inferBackend`，与 `_render` 不再共用同一个 state（原来改一个另一个跟着动）。
3. **`file_picker` 之外**：滑块值由 `_sliders` 托管并持久化，防抖落盘。
 原来那些滑块传的是写死的常量 → 拖不动。
4. **音色写 ID 不写中文名**
 原来选中"晓晓"后 `UpdateSettings(voice: '晓晓')`，写进 `config.voice.id` 的是**中文显示名**，
 后端拿"晓晓"去合成必然失败。现在 value 是真实音色 ID（`zh-CN-XiaoxiaoNeural`）。
5. **主题模式真落盘**：原先选中只 `setState`，既不入库也不换肤。现在写进
 `XlThemeController` 统一持久化（避免两处各存一份互相打架）。
6. **性别不再靠名字猜**：原来用"名字里有没有 xiao/yun"判断性别，
 会把 Aria、ナナミ、曉佳全判成"中性"。现在取后端真实字段。
7. **未翻译的语言直接拦下并说明**，不让选完发现界面纹丝不动。
8. **Column 替代 ListView**（通用修复）：本区块外层已有滚动容器，再套一层可滚动组件
 会拿到无界高度约束 → 整页渲染空白。**"多平台通道点进去什么都没有"就是这个原因。**
9. 多平台通道卡片从"纯装饰（active 写死 true）"改为真实开关。

#### `frontend/lib/pages/model_store_page.dart`（+636 / -0）

针对"添加本地模型后看不到、登记按钮不确认、浏览与选文件重复"：

1. **加装 `file_picker`**（原来只有手填路径的文本框）→ 真正的目录选择弹窗。
2. **新增"已安装模型"汇总区** `_installedRows()` / `_installedSection()`
 注释点明痛点：*"之前只列商店里的模型，导致用户「添加」了本地模型却在这里看不到，
 以为添加失败 —— 这是最主要的使用困惑来源。"* 现在商店模型 + 本地登记模型统一列出，可直接切换。
3. **扫描 → 添加**两段式对话框 `_showLocalModelDialog()`：
 `model:scan <目录>` 先扫出所有可识别模型（目录形式 + 散落的单文件），
 再 `model:addlocal <路径>` 逐条添加。含 `group` / `gguf` / `local` / `format` / `complete` 标记。
4. **OpenAI 兼容接口** `_showApiEndpointDialog()` → `model:addapi`
 默认填 `http://127.0.0.1:1234`（LM Studio 端口）。
5. **`model:use` / `model:current`** 支持查询当前在���哪个模型并切换。

#### `frontend/lib/widgets/model_showcase.dart`（+231 / -35）—— 真 3D

- **移除 `model_viewer_plus`（`-`）**。它在桌面端必崩：内部走 `webview_flutter`，
 后者没有桌面实现，直接触发 `'WebViewPlatform.instance != null'` 断言。
- **改用 `InAppWebView`**（`+`）加载本地 `three.js` / `three-vrm` 页面，桌面端与移动端统一。
- 新增 `supports3DViewer` 五平台全 true、`_armWatchdog()` 12 秒超时兜底、
 `addJavaScriptHandler('xlViewer')` 接收 ready/error。

#### `frontend/pubspec.yaml`（+14 / -1）

移除 `model_viewer_plus: ^1.9.0`，加入 `flutter_inappwebview: ^6.2.0-beta.3`
（注释说明：稳定版 6.1.5 **没有 Linux 实现**，只有 beta.3 带 WPE WebKit，而项目要发四平台）。
`pubspec.lock`（+442/-306）随之自动更新。

#### `frontend/lib/main.dart`（+86 / -12）

- 新增 `_SoftErrorBox`：单个 widget 构建失败时**只显示局部占位**，不让整屏变红。
- `_startBackend()` 改为先 `ViewerPort.pick()` 挑空闲端口，再经 `--web-port` 传给后端。
- **`_appStarted` 闸门**：`runZonedGuarded` 的 onError 里 `runApp()` 会替换整个应用，
 必须只有"还没进主界面"时才降级到错误页 —— 之前点「工作台」整页变错误页就是缺这个。

#### 其余前端文件

| 文件 | 改动性质 |
|---|---|
| `dashboard_page.dart` (+57/-18) | 工作台页配合错误隔离与 3D 入口调整 |
| `chat_page.dart` (+6/-1) | 小幅调整 |
| `update_dialog.dart` (+14/-2) | 更新弹窗细节 |
| `theme_controller.dart` | 新增（见第五节） |
| `analysis_options.yaml` (+1) | lint 规则微调 |

### 3.4 构建配置（多为工具自动生成）

| 文件 | 改动说明 |
|---|---|
| `frontend/windows/CMakeLists.txt` (+11) | 在 `add_subdirectory(flutter)` **之前**加 `-D_SILENCE_EXPERIMENTAL_COROUTINE_DEPRECATION_WARNINGS`。MSVC 14.51 把 `<experimental/coroutine>` 标为硬错误（C2338: STL1011），插件用了它。**顺序不能反**，反了不生效。 |
| `frontend/android/app/src/main/AndroidManifest.xml` (+3) | `application` 节点加 `android:hardwareAccelerated="true"`（WebView 渲染 3D 必需）与 `android:usesCleartextTraffic="true"`（访问本机 http 后端）。 |
| `windows/flutter/generated_plugin_registrant.cc`、`generated_plugins.cmake`、`linux/flutter/*`、`macos/Flutter/GeneratedPluginRegistrant.swift` | **Flutter 自动生成**：注册 `flutter_inappwebview` 各平台插件。属引入新依赖后的必然产物。 |

### 3.5 仓库与 CI

| 文件 | 改动说明 |
|---|---|
| `.gitignore` (+33) | 补 Flutter 各平台 ephemeral、android 构建目录、发布二进制（`*.apk/*.exe/*.msix/*.AppImage/*.dmg`）。本次又追加了 `packaging/dist*/`、`packaging/build*/`。 |
| `.github/workflows/deploy-pages.yml` (+14/-5) | **移除明文 Cloudflare Token**，改为读 `${{ secrets.CF_API_TOKEN }}` / `CF_ACCOUNT_ID`；从 `website/` 取源码。 |
| `.github/workflows/build-all.yml` (+4/-1) | `FLUTTER_VERSION` 3.24.0 → **3.47.6**（新插件要求 Flutter ≥ 3.32）。 |

---

## 四、本轮真正新增的 17 个文件（逐个说明）

### 4.1 真 3D 渲染（核心新增）

| 文件 | 说明 |
|---|---|
| `resources/web/viewer.html` | 真 3D 渲染页。自实现轨道相机、三点布光、自动取景，含呼吸/眨眼/注视。失败上报走 `console.error`（否则远程排查时静默无痕）。暴露 `window.__xl = {autoRotate, zoomFactor, setDistance, view, exposure, reset}` 供 Flutter 调度。 |
| `resources/web/vendor/three.module.js` | three.js r160，**离线 vendor**（1.21 MB） |
| `resources/web/vendor/three-vrm.module.js` | `@pixiv/three-vrm` 1.0.7（2.02 MB）。选 1.x 是因为 VRM 0.0 + `KHR_materials_unlit` 只有 1.x 支持。 |
| `resources/web/vendor/addons/loaders/GLTFLoader.js` | GLTF 加载器（106 KB） |
| `resources/web/vendor/addons/utils/BufferGeometryUtils.js` | 几何工具（32 KB） |

> 全部**离线内置，不依赖任何 CDN** —— 这是"断网也能出 3D"的前提。

### 4.2 支撑 3D 的后端服务

| 文件 | 说明 |
|---|---|
| `backend/core/webpanel.py` | HTTP 静态服务：白名单目录 + 防目录穿越（拒绝 `..`、绝对路径、盘符）+ 只绑 `127.0.0.1`。路由 `/viewer.html`、`/vendor/*`、`/models/*`、`/api/vrm/list`。含 `_make_server()`（端口被占自动顺延最多 20 个）与 `serve_background()`。新增 `XIAOLING_ACCESS_LOG=1` 开关用于排障。 |
| `frontend/lib/services/viewer_port.dart` | 端口动态发现：`pick()` 挑空闲端口并 pin、`resolve()` 按 pin → 指定值 → 8765 → 8766~8785 顺序、`_alive()` 只认返回 200 的 `/viewer.html`。前端挑好端口后经 `--web-port` 传给后端。 |

### 4.3 设置项与主题

| 文件 | 说明 |
|---|---|
| `backend/core/options.py` | 平台感知的设置项生成器（`settings:options` 的数据来源）。按 `windows/macos/linux/android` 分别产出，**不以开发机现状为前提**（Metal 在 macOS 上正确保留）。含 TTS 引擎真实可用性探测。 |
| `frontend/lib/theme/theme_controller.dart` | 主题持久化控制器 `XlThemeController`，替代原先"选中只 setState"的假主题切换。 |
| `backend/core/fusion.py` | OpenAI 兼容接口（如 LM Studio）融合层的后端实现，支撑模型商店的"添加 API 接口"。 |

### 4.4 官网、文档与工具

| 文件 | 说明 |
|---|---|
| `website/index.html` | 官网源码**首次入库**。此前它在 `Desktop\新建文件夹 (3)\官网\` 下，导致 `.github/workflows/deploy-pages.yml` 一直是断的。已补第 4 个 **Android** 下载卡片、四张卡各自的"GitHub 直连"备用链接，`.download-grid` 改 `repeat(4,...)`。 |
| `docs/PUBLISHING.md` | 仓库地址、Pages Secrets 配置、四平台产物对照、真 3D 实现与排障、Gitee 推送的坑。 |
| `tools/push_repos.py` | 双仓库推送脚本。带令牌归属自动识别（调 `/api/v5/user` 取 login）、一次���推送（token 不落 `.git/config`）、重试、**非快进时拒绝 force push**。 |
| `tools/probe_viewer.js` | puppeteer 冒烟脚本（本机沙箱环境浏览器起不来，未成功执行，保留备用）。 |

### 4.5 备注：3 个"项目已有但本轮改写"的文件

这 3 个因 mtime 落在开发时段而被归入新增组，实际是原文件被改写：

| 文件 | 原本可能有 / 本轮改了什么 |
|---|---|
| `packaging/runtime_hook.py` | 新增数据目录隔离：frozen 时把 `XIAOLING_HOME` 指向 exe 同级 `runtime/`，解决后端 `data/` 与 Flutter Release 自带 `data/` 撞名。 |
| `packaging/README.md` | 顶部加" 本文件大部分内容已过期"提示，指向新流程 `docs/PACKAGING.md`。**未删除原文**（红线）。 |
| `packaging/linux/install_deps.sh` | 补 WPE WebKit 依赖（`libwebkit2gtk-4.1-0`、`libwpewebkit-1.1-3`、`wpebackend-fdo`），因为 Linux 端 WebView 走 WPE。 |

---

## 五、项目自带但 zip 未收录的 37 个文件（清单）

这些**不是本轮新增**，只是没被打包进那份 zip（依据：磁盘时间戳集中在 05:32–06:17 的项目落地时段）。

| 分组 | 文件 |
|---|---|
| 后端 | `backend/core/quarantine.py`、`backend/core/system.py`、`backend/renderer/__init__.py`、`backend/renderer/stage.py`、`backend/renderer/vrm_gltf.py` |
| 前端资源 | `frontend/assets/xiaoling.png` |
| 打包脚本（旧） | `packaging/build.py`、`packaging/xiaoling.spec`、`packaging/linux/AppRun`、`packaging/linux/build_appimage.sh`、`packaging/linux/xiaoling.desktop`、`packaging/macos/build_dmg.sh`、`packaging/macos/make_dmg.sh`、`packaging/termux/install.sh`、`packaging/windows/README.md`、`packaging/windows/xiaoling.iss`、`packaging/windows/xiaoling.nsi` |
| 依赖清单 | `requirements.txt`、`requirements-dev.txt` |
| 插件 | `plugins/builtin/hello_world/main.py`、`plugins/builtin/hello_world/manifest.json` |
| proto | `shared/proto/xiaoling.proto` |
| 脚本 | `scripts/make_sounds.py`、`publish.py`、`registry.json`、`setup.sh`、`start.sh`、`vrm_lib.py`、`vrm_preview.py`、`vrm_to_fbx.py`、`xiaoling_avatar.py` |
| 测试 | `tests/conftest.py`、`pytest.ini`、`test_contracts.py`、`test_growth.py`、`test_imports.py`、`test_renderer.py` |

> 注：其中的 `packaging/build.py` 与 `packaging/xiaoling.spec` 虽然存在于磁盘，
> 但引用的是 `xl.py`、`打包/`、`core/`、`models/`、`animations/` 等早已不存在的旧路径，
> **已经失效**；按红线未删除，仅在 README 里标注。

---

## 六、未改动的文件

**165 个文件内容完全一致（SHA-256 逐字节相同）**，主要分布在：

- `backend/core/` 大部分��块（除上述 5 个被改动的）
- `frontend/lib/pages/` 其余页面、`frontend/lib/services/` 其余服务
- `frontend/lib/widgets/` 其余组件、`frontend/lib/theme/`（除新增的 controller）
- `docs/` 下 13 个文档、`resources/materials`、`resources/sounds`

---

## 七、如何复现这份对比

对比工具已一并提交到仓库：

```bash
# 1) 总览：新增 / 删除 / 修改 / 一致 的数量与清单
python tools/diff_vs_original.py --zip C:\Users\MVP\Desktop\XLmodel-main.zip

# 2) 逐个文件的 +/- 行统计与变更片段
python tools/diff_detail.py

# 3) 区分「真新增」与「zip 打包遗漏」
python tools/classify_added.py
```

工具说明：
- `diff_vs_original.py` —— SHA-256 全文比对；自动跳过 `.git`、`__pycache__`、构建产物等噪声目录
- `diff_detail.py` —— 逐文件 diff，按改动量排序，可 `--files` 指定单个文件、`--max-lines` 控制输出
- `classify_added.py` —— 按 mtime 二分新增来源，`--hour-split` 可调分界

---

## 八、结论与待办

**已完成**：真 3D 桌面渲染、模型商店支持 GGUF 与本地模型、设置项去硬编码、
推理/渲染后端分离、四平台（Windows/Linux/macOS/Android）构建配置、
官网源码入库、Gitee 与 GitHub 双仓就绪、Windows exe 打包并实测通过。

**仍待办**（需你决策或操作）：
1. **Cloudflare Token 轮换（Rotate）** —— 历史提交 `5d0c464` 里曾含明文且已推到远端，
 实测该令牌**当前仍有效**，必须去后台轮换，并把新串配进 GitHub Secrets。
2. **GitHub 推送** —— 脚本与 remote 已就绪（`3477856804/XLmodel`），缺一枚 GitHub PAT。
3. Release 资产里 `xiaoling-windows-x64.zip` 与 `xiaoling-linux-x64.tar.gz`
 是早期重复副本，是否清理待你拍板。
