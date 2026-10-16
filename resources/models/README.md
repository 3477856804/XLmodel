# resources/models —— 3D 形象资源

这个目录是 **3D 查看器的模型白名单根目录**，被以下三处读取：

- `backend/core/webpanel.py` → `_model_roots()` / `_resolve_model()`：
  把 `/models/<文件名>` 映射成这里的真实文件（只按文件名找，不接受路径穿越）。
- `backend/rpc/server.py` → `GetModelList`：递归扫描本目录列出可用形象。
- `resources/web/viewer.html`：`./models/<model>`，默认 `小凌.vrm`。

## 为什么以前「3D 人物模型加载不出来」

不是渲染代码坏了，是**资源从来不存在**：

- `.gitignore` 里 `resources/models/` + `*.vrm` + `*.vrma` 三条规则把这个目录整体忽略；
- 翻遍两个远端（Gitee / GitHub）的**全部提交历史**，没有任何一个 `.vrm/.glb/.gltf/.fbx/.pmx/.pmd`
  文件曾经被提交或删除过（`git rev-list --all` + 每个 commit 的 `ls-tree` 全量核对）。

所以 `viewer.html` 请求 `./models/小凌.vrm` 永远 404，前端一直停在「正在加载形象…」。
这次把内置形象真正入库，并在 `.gitignore` 里为它单独开了例外（只放行 `小凌.vrm`
和这个 README，用户自己丢进来的其它模型仍然不入库）。

## 当前内置形象：`小凌.vrm`

由本仓库自己的改造管线生成，**不是**外部成品模型：

```bash
python3 scripts/xiaoling_avatar.py build \
    --base <基底.vrm> \
    --face resources/materials/xiaoling.png \
    --out resources/models/小凌.vrm
```

管线做的事（全部在 `scripts/xiaoling_avatar.py` + `scripts/vrm_lib.py`，纯 Python + numpy + Pillow）：
服装贴图纯白化、程序化白丝、发色重染（浅亚麻金）、瞳色重绘（湛蓝）、
2D 立绘五官迁移、程序化白色连衣裙（自动蒙皮到 hips/spine/chest）、隐藏原配饰。

- 规格：VRM 0.x（`specVersion: "0.0"`），glTF 2.0 二进制，179 节点 / 54 根人形骨骼 /
  11 个网格基元 / 18 个材质 / 28 张贴图，约 18.5 MB。
- 表情：`blendShapeMaster` 带 `A/I/U/E/O`、`Blink`、`Blink_L/R`、`Angry/Fun/Joy/Sorrow/Surprised`
  与 `LookUp/Down/Left/Right`。three-vrm 1.0.7 会把 `Blink → blink`、`A → aa` 归一到
  VRM1 表情名，因此 viewer.html 的眨眼与口型驱动有效。
- 基底来源：ModelScope `oleehu/vrm-models`（仓库声明 Apache-2.0；VRM meta 里的
  `otherLicenseUrl` 指向 VRoid Hub 授权页，其中 redistribution=allow、modification=allow、
  个人与商业使用均 allow、credit=unnecessary）。改造后的形象按 VRM meta 记录为
  `title=小凌 XIAOLING`、`author=XIAOLING 项目组（基于原模型改造）`。

## 放自己的模型

把 `.vrm / .glb / .gltf / .fbx` 丢进本目录（或 `.star_core/models/`、
配置项 `model_extra_dirs` 指向的目录）即可，设置页的形象选择器会通过
`/api/vrm/list` 列出来。注意这些新文件默认被 `.gitignore` 忽略，不会被提交。
