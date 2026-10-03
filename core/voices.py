#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""core.voices —— models与专属音色绑定
================================================

每个 VRM 角色绑一套 Edge-TTS 中文音色，切换模型时自动换音色：

    小凌.vrm               -> zh-CN-XiaoxiaoNeural（晓晓，活泼少女）
    Vivi.vrm               -> zh-CN-XiaohanNeural（晓涵，温柔知性）
    QuQu.vrm               -> zh-CN-XiaoyiNeural （晓伊，俏皮少女）
    Zome.vrm               -> zh-CN-YunxiNeural   （云希，阳光少年）
    Rabbit_Peridot.vrm     -> zh-CN-XiaoshuangNeural（晓双，可爱女童）
    Rabbit_Rubellite.vrm  -> zh-CN-XiaoyouNeural （晓悠，软萌女童）
    Imeris.vrm             -> zh-CN-YunyangNeural （云扬，沉稳青年）

- 模型文件名（不含扩展名）做 key；查不到时回退默认音色。
- 运行期由 set_current_model(vrm_path) 更新当前音色，get_current_voice() 供
  core.tts 在合成时取用——换角色即连声音一起换。
"""
from __future__ import annotations

from pathlib import Path

# 模型名（stem，即文件名去掉 .vrm）-> Edge-TTS 音色 + 备注
VOICE_MAP: dict[str, dict] = {
    '小凌':             {'voice': 'zh-CN-XiaoxiaoNeural',    'desc': '晓晓，活泼少女'},
    'Vivi':             {'voice': 'zh-CN-XiaohanNeural',    'desc': '晓涵，温柔知性'},
    'QuQu':             {'voice': 'zh-CN-XiaoyiNeural',     'desc': '晓伊，俏皮少女'},
    'Zome':             {'voice': 'zh-CN-YunxiNeural',      'desc': '云希，阳光少年'},
    'Rabbit_Peridot':   {'voice': 'zh-CN-XiaoshuangNeural', 'desc': '晓双，可爱女童'},
    'Rabbit_Rubellite': {'voice': 'zh-CN-XiaoyouNeural',    'desc': '晓悠，软萌女童'},
    'Imeris':           {'voice': 'zh-CN-YunyangNeural',   'desc': '云扬，沉稳青年'},
}

DEFAULT_VOICE = 'zh-CN-XiaoxiaoNeural'

# 当前激活角色的音色（模块级单例；切模型时更新）
_current_voice: str = DEFAULT_VOICE
_current_model: str = ''
_current_desc: str = ''


def info_for_model(vrm_path) -> dict:
    """返回某模型绑定的音色信息：{'voice','desc','model'}。无绑定时回退默认。"""
    stem = Path(str(vrm_path)).stem
    hit = VOICE_MAP.get(stem)
    if hit:
        return {'voice': hit['voice'], 'desc': hit['desc'], 'model': stem}
    return {'voice': DEFAULT_VOICE, 'desc': '默认音色（晓晓）', 'model': stem}


def set_current_model(vrm_path) -> dict:
    """切换当前角色，同步切换音色。返回当前音色信息。"""
    global _current_voice, _current_model, _current_desc
    info = info_for_model(vrm_path)
    _current_voice = info['voice']
    _current_model = info['model']
    _current_desc = info['desc']
    return info


def get_current_voice() -> str:
    return _current_voice


def get_current_desc() -> str:
    return _current_desc or '默认音色'


def describe() -> dict:
    return {'model': _current_model, 'voice': _current_voice, 'desc': _current_desc}


if __name__ == '__main__':
    import json
    rows = [{'model': k, **v} for k, v in VOICE_MAP.items()]
    print(json.dumps(rows, ensure_ascii=False, indent=2))
