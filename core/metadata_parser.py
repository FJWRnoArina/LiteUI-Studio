import json
import subprocess
from PIL import Image

import json
import subprocess
import ast  # 【新增】：Python 内置的语法解析树，专门用来对付畸形 JSON
from PIL import Image


def parse_json_safely(raw_data):
    """【满级防御】：不仅剥离多重外壳，还能修复被 Windows 命令行打碎的畸形 JSON"""
    if not raw_data:
        return None

    current_data = raw_data
    for _ in range(3):
        if isinstance(current_data, dict):
            return current_data
        if isinstance(current_data, str):
            try:
                # 尝试标准的 JSON 解析
                current_data = json.loads(current_data)
            except Exception:
                # 【终极后备】：如果标准 JSON 解析失败（比如双引号变成了单引号）
                # 尝试使用 Python 的抽象语法树（AST）将其作为字典结构强行求值
                try:
                    parsed = ast.literal_eval(current_data)
                    if isinstance(parsed, dict):
                        current_data = parsed
                    else:
                        break
                except Exception:
                    break  # 彻底没救了，跳出
        else:
            break

    return current_data if isinstance(current_data, dict) else None


def extract_comfyui_metadata(file_path):
    """跨媒体格式的元数据全域雷达探测器"""
    prompt_json = None

    # 1. 处理图像 (PNG, JPG, WEBP)
    if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
        try:
            with Image.open(file_path) as img:
                if 'prompt' in img.info:
                    prompt_json = parse_json_safely(img.info['prompt'])
                elif 'Comment' in img.info:  # 有的图片格式会将信息存入大写的 Comment
                    prompt_json = parse_json_safely(img.info['Comment'])
        except Exception as e:
            return f"❌ 读取图片元数据失败: {str(e)}"

    # 2. 处理视频 (MP4, WEBM)
        # 2. 处理视频 (MP4, WEBM)
    elif file_path.lower().endswith(('.mp4', '.webm', '.mkv')):
        try:
            cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', file_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            probe = json.loads(result.stdout)
            tags = probe.get('format', {}).get('tags', {})

            # 【核心修复】：不要使用 `or` 短路！
            # ComfyUI 的 Phase3 会写入一个残缺版的 'prompt'
            # 我们注入的完美融合版在 'comment' 里面
            # 逻辑：遍历所有的相关标签，解开后比对节点数量，选节点最多的那个字典！
            best_prompt_json = None
            max_nodes = 0

            for key in ['prompt', 'comment', 'title', 'description']:
                if key in tags:
                    parsed = parse_json_safely(tags[key])
                    if parsed and isinstance(parsed, dict):
                        num_nodes = len(parsed.keys())
                        if num_nodes > max_nodes:
                            max_nodes = num_nodes
                            best_prompt_json = parsed

            prompt_json = best_prompt_json
        except Exception as e:
            return f"❌ 无法读取视频参数。可能缺失 ffprobe，或者元数据已被抹除: {str(e)}"

    # 3. 智能解析并排版
    return format_parsed_metadata(prompt_json)


# ... [下方保留你原有的 format_parsed_metadata 函数，不需要修改] ...


def format_parsed_metadata(prompt):
    """精准探针：基于工作流特征探测，严格按照 PARAM_MAP 提取节点参数"""

    # 1. ================== 探测工作流类型 ==================
    is_wan_i2v = "257:286" in prompt

    # 探测 Wan2.2 是否启用了配音
    has_wan_audio = False
    if is_wan_i2v:
        audio_model_name = prompt.get("257:296:280", {}).get("inputs", {}).get("mmaudio_model")
        if audio_model_name and str(audio_model_name).strip().lower() != "none":
            has_wan_audio = True

    # 【核心修复】：精准探测 LTX-2.3 架构 (检查 23 号节点的 type 是否为 ltxv)
    is_ltx = False
    if "23" in prompt:
        clip_type = prompt.get("23", {}).get("inputs", {}).get("type", "")
        if str(clip_type).lower() == "ltxv":
            is_ltx = True

    # 遍历探测基础节点以区分 Flux 管线
    has_load_image = False
    for node in prompt.values():
        if isinstance(node, dict) and node.get("class_type") == "LoadImage":
            has_load_image = True
            break

    # 路由分配 (优先级：LTX > Wan > Flux)
    if is_ltx:
        wf_type = "ltx_video"
    elif is_wan_i2v:
        wf_type = "i2v_audio" if has_wan_audio else "i2v_noaudio"
    else:
        wf_type = "img2img" if has_load_image else "txt2img"

    # 2. ================== 精准提取核心参数 ==================
    data = {}

    def get_val(node_id, field):
        """安全提取助手，找不到时返回 Unknown"""
        return prompt.get(node_id, {}).get("inputs", {}).get(field, "Unknown")

    if wf_type == "txt2img":
        data['prompt'] = get_val("6", "text")
        data['seed'] = get_val("26", "noise_seed")
        data['steps'] = get_val("31", "steps")
        data['guidance'] = get_val("27", "guidance")
        data['width'] = get_val("28", "width")
        data['height'] = get_val("33", "value")
        data['batch_size'] = get_val("28", "batch_size")
        data['upscale'] = get_val("40", "scale_by")
        data['base_model'] = get_val("25", "unet_name")
        title_str = "🖼️ Flux2 文生图 (Txt2Img)"

    elif wf_type == "img2img":
        data['prompt'] = get_val("12", "text")
        data['width'] = get_val("8", "value")
        data['height'] = get_val("9", "value")
        data['steps'] = get_val("10:33", "steps")
        data['guidance'] = get_val("13", "guidance")
        data['seed'] = get_val("10:31", "noise_seed")
        data['base_model'] = get_val("1", "unet_name")
        title_str = "🎨 Flux2 图生图 (Img2Img)"

    elif wf_type == "i2v_audio":
        data['video_prompt'] = get_val("257:286", "value")
        data['separate_audio'] = get_val("257:301", "value")
        data['audio_prompt'] = get_val("257:299", "value")
        data['duration'] = get_val("257:229", "value")
        data['width'] = get_val("257:302", "value")
        data['height'] = get_val("257:303", "value")
        data['seed'] = get_val("257:237", "noise_seed")
        data['audio_seed'] = get_val("257:296:279", "seed")
        data['high_base'] = get_val("257:258", "unet_name")
        data['low_base'] = get_val("257:259", "unet_name")
        data['audio_model'] = get_val("257:296:280", "mmaudio_model")
        title_str = "🎞️🎵 Wan2.2 图生视频 [含配音] (Img2Vid + Audio)"

    elif wf_type == "i2v_noaudio":
        data['prompt'] = get_val("257:286", "value")
        data['duration'] = get_val("257:229", "value")
        data['width'] = get_val("257:302", "value")
        data['height'] = get_val("257:303", "value")
        data['seed'] = get_val("257:237", "noise_seed")
        data['high_base'] = get_val("257:258", "unet_name")
        data['low_base'] = get_val("257:259", "unet_name")
        title_str = "🎞️ Wan2.2 图生视频 [无配音] (Img2Vid)"

    elif wf_type == "ltx_video":
        data['prompt'] = get_val("15", "text")
        data['width'] = get_val("11", "value")
        data['height'] = get_val("12", "value")
        data['duration'] = get_val("18", "value")
        data['fps'] = get_val("20", "value")
        data['seed_1'] = get_val("61", "noise_seed")
        data['seed_2'] = get_val("69", "noise_seed")
        data['base_model'] = get_val("1", "unet_name")

        # 解析生成模式 (T2V 还是 I2V)
        t2v_mode = get_val("50", "value")
        if t2v_mode is True:
            data['mode'] = "文生视频 (Text to Video)"
        elif t2v_mode is False:
            data['mode'] = "图生视频 (Image to Video)"
        else:
            data['mode'] = "Unknown"

        title_str = "🌟 LTX-2.3 原生多模态视频 (Audio-Video)"

    # 3. ================== 动态提取 LoRA ==================
    loras = []
    for node_id, node in prompt.items():
        if not isinstance(node, dict): continue
        class_type = node.get("class_type", "")
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict): continue

        if class_type in ["LoraLoader", "LoraLoaderModelOnly"]:
            lora_name = inputs.get("lora_name")
            if lora_name: loras.append(f"{lora_name} (权重: {inputs.get('strength_model', 1.0)})")
        elif class_type == "Power Lora Loader (rgthree)":
            for k, v in inputs.items():
                if k.startswith("lora_") and isinstance(v, dict) and v.get("on"):
                    loras.append(f"{v.get('lora')} (权重: {v.get('strength')})")

    # 4. ================== 模块化 Markdown 排版 ==================
    md = f"### 📊 提取的生成参数 (Generation Metadata)\n"
    md += f"**识别到的工作流:** `{title_str}`\n\n"

    # 渲染生图版参数
    if wf_type in ["txt2img", "img2img"]:
        md += f"- **📏 尺寸 (Resolution):** `{data.get('width')} x {data.get('height')}`\n"
        md += f"- **🎲 随机种子 (Seed):** `{data.get('seed')}`\n"
        md += f"- **👣 步数 (Steps):** `{data.get('steps')}`\n"
        md += f"- **🎛️ 引导系数 (CFG/Guidance):** `{data.get('guidance')}`\n"

        if wf_type == "txt2img":
            md += f"- **🖼️ 批次大小 (Batch Size):** `{data.get('batch_size')}`\n"
            md += f"- **🔍 放大倍数 (Upscale):** `{data.get('upscale')}x`\n"

        md += f"\n#### 🧠 模型使用\n"
        md += f"- **基础底模:** `{data.get('base_model')}`\n"

    # 渲染 Wan2.2 视频参数
    elif wf_type.startswith("i2v"):
        md += f"- **📏 尺寸 (Resolution):** `{data.get('width')} x {data.get('height')}`\n"
        md += f"- **⏱️ 时长参数 (Duration):** `{data.get('duration')}`\n"
        md += f"- **🎲 画面随机种子 (Seed):** `{data.get('seed')}`\n"

        if wf_type == "i2v_audio":
            md += f"- **🎵 音效随机种子 (Audio Seed):** `{data.get('audio_seed')}`\n"
            md += f"- **🔀 启用独立音效提示词:** `{data.get('separate_audio')}`\n"

        md += f"\n#### 🧠 模型使用\n"
        md += f"- **高噪底模 (High Noise):** `{data.get('high_base')}`\n"
        md += f"- **低噪底模 (Low Noise):** `{data.get('low_base')}`\n"
        if wf_type == "i2v_audio":
            md += f"- **音效模型 (Audio Model):** `{data.get('audio_model')}`\n"

    # 渲染 LTX-2.3 视频参数
    elif wf_type == "ltx_video":
        md += f"- **🔄 生成模式 (Mode):** `{data.get('mode')}`\n"
        md += f"- **📏 尺寸 (Resolution):** `{data.get('width')} x {data.get('height')}`\n"
        md += f"- **⏱️ 时长参数 (Duration):** `{data.get('duration')} 秒`\n"
        md += f"- **🎞️ 视频帧率 (FPS):** `{data.get('fps')} fps`\n"
        md += f"- **🎲 基础渲染种子 (Base Seed):** `{data.get('seed_1')}`\n"
        md += f"- **🎲 潜空间放大种子 (Upscale Seed):** `{data.get('seed_2')}`\n"
        md += f"\n#### 🧠 模型使用\n"
        md += f"- **基础底模:** `{data.get('base_model')}`\n"

    # 渲染通用 LoRA
    if loras:
        md += "- **加载的 LoRA:**\n"
        for l in loras: md += f"  - `{l}`\n"
    else:
        md += "- **加载的 LoRA:** `无`\n\n"

    # 渲染提示词
    md += "\n#### ✨ 提示词 (Prompts)\n"
    if wf_type == "i2v_audio":
        md += f"**画面提示词:**\n> {data.get('video_prompt')}\n\n"
        md += f"**配音提示词:**\n> {data.get('audio_prompt')}\n\n"
    elif wf_type == "ltx_video":
        # 对于 LTX，提示词包含了极度珍贵的时间轴，必须展示！
        # 使用 replace 让带有换行的剧本在 markdown 的引用区块中也能正确换行
        formatted_prompt = str(data.get('prompt')).replace('\n', '\n> ')
        md += f"**导演时间轴提示词 (Temporal Prompt):**\n> {formatted_prompt}\n\n"
    else:
        md += f"> {data.get('prompt')}\n\n"

    return md