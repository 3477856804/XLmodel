#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VRM → FBX 批量转换脚本（Blender 命令行运行）

用法（在本地电脑装了 Blender 后运行）：
    blender --background --python vrm_to_fbx.py -- models/小凌.vrm resources/models/小凌.fbx

批量转换：
    blender --background --python vrm_to_fbx.py -- --batch models/ resources/models/
"""
import bpy
import sys
import os
from pathlib import Path


def convert_vrm_to_fbx(vrm_path: str, fbx_path: str):
    """单个 VRM 转 FBX"""
    print(f"转换: {vrm_path} -> {fbx_path}")

    # 清空场景
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # 导入 VRM
    try:
        bpy.ops.import_scene.vrm(filepath=vrm_path)
        print(f"  VRM 导入成功")
    except Exception as e:
        print(f"  VRM 导入失败: {e}")
        return False

    # 导出 FBX
    try:
        bpy.ops.export_scene.fbx(
            filepath=fbx_path,
            use_selection=False,
            bake_space_transform=True,
            mesh_smooth_type='FACE',
            add_leaf_bones=False,
            bake_anim=True,
        )
        print(f"  FBX 导出成功: {fbx_path}")
        return True
    except Exception as e:
        print(f"  FBX 导出失败: {e}")
        return False


def batch_convert(input_dir: str, output_dir: str):
    """批量转换目录下所有 VRM"""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    vrm_files = list(input_path.glob("*.vrm"))
    print(f"找到 {len(vrm_files)} 个 VRM 文件")

    success = 0
    for vrm_file in vrm_files:
        fbx_file = output_path / (vrm_file.stem + ".fbx")
        if convert_vrm_to_fbx(str(vrm_file), str(fbx_file)):
            success += 1

    print(f"\n转换完成: {success}/{len(vrm_files)} 成功")


if __name__ == "__main__":
    # Blender 命令行参数在 -- 后面
    argv = sys.argv
    if "--" in argv:
        args = argv[argv.index("--") + 1:]
    else:
        args = []

    if len(args) == 1 and args[0] == "--batch":
        # 批量模式
        batch_convert("models/", "resources/models/")
    elif len(args) == 2:
        # 单个文件
        convert_vrm_to_fbx(args[0], args[1])
    else:
        print("用法:")
        print("  单个: blender --background --python vrm_to_fbx.py -- input.vrm output.fbx")
        print("  批量: blender --background --python vrm_to_fbx.py -- --batch")
