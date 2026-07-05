import urllib.error
import warnings
import gradio as gr
import os
import random
import subprocess
import platform
import time
import requests
from core.txt2img_en import t2iClient
from core.image2vid_en import Wan2VideoPipelineClient
from core.img2img_en import FluxImg2ImgClient
from core.metadata_parser_en import (extract_comfyui_metadata)
from core.img2vid_ltx_en import LTXVideoClient
from core.video_interp_en import VideoInterpClient

warnings.filterwarnings("ignore", message=".*HTTP_422_UNPROCESSABLE_ENTITY.*")
warnings.filterwarnings("ignore", category=DeprecationWarning)

# ==========================================
# 1. config and tool functions
# ==========================================

COMFYUI_OUTPUT_DIR = r"backend_comfyui\output"
LORA_DIR = r"backend_comfyui\models\loras"
UNET_DIR = r"backend_comfyui\models\diffusion_models"
MMAUDIO_DIR = r"backend_comfyui\models\mmaudio"
MAX_LORAS = 10


def get_model_list(directory, valid_extensions, default_models):
    """Scan model list"""
    if not os.path.exists(directory):
        return default_models
    models = [f for f in os.listdir(directory) if f.endswith(valid_extensions)]

    return list(dict.fromkeys(default_models + models))


def get_lora_list():
    return get_model_list(LORA_DIR, ('.safetensors', '.pt', '.gguf'), ["None"])


def get_unet_list():
    # Load default models
    return get_model_list(UNET_DIR, ('.gguf', '.safetensors', '.pt'), [
        "Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf",
        "Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf"
    ])


def get_mmaudio_list():
    return get_model_list(MMAUDIO_DIR, ('.safetensors', '.pt'), [
        "mmaudio_large_44k_v2_fp16.safetensors"
    ])


def open_output_folder(mode: str):

    try:
        current_os = platform.system()
        if mode != "":
            if mode == "t2i":
                output_path = COMFYUI_OUTPUT_DIR + r"\txt2img"
            elif mode == "i2i":
                output_path = COMFYUI_OUTPUT_DIR + r"\img2img"
            elif mode == "i2v":
                output_path = COMFYUI_OUTPUT_DIR + r"\img2vid"
            elif mode == "mmaudio":
                output_path = r"backend_comfyui\models\mmaudio"
            elif mode == "lora":
                output_path = r"backend_comfyui\models\loras"
            elif mode == "model":
                output_path = r"backend_comfyui\models\diffusion_models"
            elif mode == "interp":
                output_path = COMFYUI_OUTPUT_DIR + r"\highfps_fixed"
        else:
            output_path = COMFYUI_OUTPUT_DIR

        if not os.path.exists(output_path):
            os.makedirs(output_path, exist_ok=True)

        if current_os == "Windows":
            subprocess.Popen(fr'explorer.exe ".\{output_path}"')
        elif current_os == "Darwin":  # macOS
            subprocess.call(["open", output_path])
        else:  # Linux
            subprocess.call(["xdg-open", output_path])
        # 弹个小绿窗，反馈交互
        gr.Info("📂 Folder opened!")
    except Exception as e:
        raise gr.Error(f"Failed to open the folder: {str(e)}")


def interrupt_comfyui_task():
    """Send interrupt to ComfyUI backend"""
    try:
        # ComfyUI 自带的硬中断接口
        requests.post(f"http://127.0.0.1:8188/interrupt", timeout=3)
        gr.Info("🛑 Interrupt Send! Clearing all caches ...")
    except Exception as e:
        gr.Warning("Failed to send interrupt. Please check if backend ComfyUI is online.")


# ==========================================
# 2. Wrappers
# ==========================================

# ----- Txt2Img (Flux) 桥接函数 -----
def generate_t2i_wrapper(prompt, width, height, steps, guidance, upscale_factor, seed, randomize_seed, base_model,
                         *lora_args):
    start_time = time.time()

    if randomize_seed:
        seed = random.randint(1, 999999999999999)

    lora_names = lora_args[:MAX_LORAS]
    lora_weights = lora_args[MAX_LORAS:]
    lora_list = [{"name": n, "strength": w} for n, w in zip(lora_names, lora_weights) if n != "None"]

    try:
        client = t2iClient()
        result_img = client.generate_txt2img(
            template_path="core/workflows/txt2img.json", lora_list=lora_list,
            prompt=prompt, width=width, height=height, steps=steps, guidance=guidance, upscale_factor=upscale_factor,
            seed=seed,
            base_model=base_model
        )

        end_time = time.time()
        gr.Info(f"✅ Complete! Time usage: {int(end_time - start_time)}s")

        return result_img, seed

    except ConnectionRefusedError:
        raise gr.Error(
            "❌ Can't connect to ComfyUI backend! Please ensure the backend is started (Port 8188). Please wait if the engine is just started.")

    except FileNotFoundError:
        raise gr.Error("❌ Key files missing! Please check integrity of the files and try again.")

    except urllib.error.HTTPError:
        raise gr.Error("❌ Failed to load model! Please ensure the model is in the required format.")

    except Exception as e:
        raise gr.Error(str(e))


def add_lora_slot(count):
    new_count = min(count + 1, MAX_LORAS)
    if new_count == 5: gr.Warning("⚠️ Warning: Loading more than 5 LoRAs can cause Out Of Memory!")
    return [new_count] + [gr.update(visible=(i < new_count)) for i in range(MAX_LORAS)]


def make_remove_fn(index_to_remove):
    def remove_fn(count, *args):
        names = list(args[:MAX_LORAS]);
        weights = list(args[MAX_LORAS:])
        names.pop(index_to_remove);
        weights.pop(index_to_remove)
        names.append("None");
        weights.append(1.0)
        new_count = max(1, count - 1)
        if new_count == 1 and count == 1: names[0] = "None"
        return [new_count] + [gr.update(visible=(i < new_count)) for i in range(MAX_LORAS)] + \
            [gr.update(value=names[i]) for i in range(MAX_LORAS)] + \
            [gr.update(value=weights[i]) for i in range(MAX_LORAS)]

    return remove_fn


# ----- Img2Vid (Wan2.2) Wrapper -----
def generate_i2v_wrapper(image_path, prompt, duration, width, height, seed, randomize_seed,
                         high_lora_name, high_lora_str, low_lora_name, low_lora_str,
                         enable_audio, separate_audio, audio_prompt,
                         high_base, low_base, audio_model):
    try:
        start_time = time.time()
        if image_path is None:
            raise gr.Error("❌ Please upload at least one image!")

        if randomize_seed:
            seed = random.randint(1, 999999999999999)

        high_lora = {"name": high_lora_name, "strength": high_lora_str} if high_lora_name != "None" else None
        low_lora = {"name": low_lora_name, "strength": low_lora_str} if low_lora_name != "None" else None

        gr.Info(f"🚀 Img2Vid task started! \nDuration: {duration}s (check terminal for progress)")

        # 【核心调用】：新的大修版引擎
        client = Wan2VideoPipelineClient()
        video_path = client.generate_pipeline(
            image_path=image_path,
            enable_audio=enable_audio,
            high_lora=high_lora,
            low_lora=low_lora,
            prompt=prompt,
            video_prompt=prompt,
            duration=duration,
            width=width,
            height=height,
            seed=seed,
            audio_seed=seed + 1024,
            separate_audio=separate_audio,
            audio_prompt=audio_prompt if separate_audio else prompt,
            high_base_model=high_base,
            low_base_model=low_base,
            audio_model=audio_model
        )
        end_time = time.time()
        gr.Info(f"✅ Complete! Time usage: {int(end_time - start_time)}s")

        return video_path, seed


    except ConnectionRefusedError:
        raise gr.Error(
            "❌ Can't connect to ComfyUI backend! Please ensure the backend is started (Port 8188). Please wait if the engine is just started.")

    except FileNotFoundError:
        raise gr.Error("❌ Key files missing! Please check integrity of the files and try again.")

    except urllib.error.HTTPError:
        raise gr.Error("❌ Failed to load model! Please ensure the model is in the required format.")

    except Exception as e:
        raise gr.Error(str(e))


# ----- Img2Img (Flux) 桥接函数 -----
def generate_i2i_wrapper(image_path, prompt, width, height, steps, guidance, seed, randomize_seed, base_model,
                         *lora_args):
    try:
        start_time = time.time()
        if image_path is None:
            raise gr.Error("❌ Please upload at least one image!")

        if randomize_seed: seed = random.randint(1, 999999999999999)
        lora_names = lora_args[:MAX_LORAS];
        lora_weights = lora_args[MAX_LORAS:]
        lora_list = [{"name": n, "strength": w} for n, w in zip(lora_names, lora_weights) if n != "None"]

        client = FluxImg2ImgClient()
        result_img = client.generate_img2img(
            template_path="core/workflows/img2img.json",
            input_image_path=image_path,
            lora_list=lora_list,
            prompt=prompt, width=width, height=height, steps=steps,
            guidance=guidance, seed=seed, base_model=base_model
        )

        end_time = time.time()
        gr.Info(f"✅ Complete! Time usage: {int(end_time - start_time)}s")

        return result_img, seed


    except ConnectionRefusedError:
        raise gr.Error(
            "❌ Can't connect to ComfyUI backend! Please ensure the backend is started (Port 8188). Please wait if the engine is just started.")


    except FileNotFoundError:
        raise gr.Error("❌ Key files missing! Please check integrity of the files and try again.")

    except urllib.error.HTTPError:
        raise gr.Error("❌ Failed to load model! Please ensure the model is in the required format.")

    except Exception as e:
        raise gr.Error(str(e))


def generate_ltx_wrapper(mode, image_path, prompt, width, height, duration, fps, seed, randomize_seed, base_model,
                         *lora_args):
    try:
        start_time = time.time()
        # Decide mode selected
        is_t2v = (mode == "Text to Video")


        if image_path is None:
            if is_t2v:
                import PIL.Image
                dummy_path = "ltx_dummy_black.png"
                if not os.path.exists(dummy_path):
                    PIL.Image.new("RGB", (64, 64), "black").save(dummy_path)
                image_path = dummy_path
            else:
                raise gr.Error("❌ Please upload at least one image!")

        if randomize_seed: seed = random.randint(1, 999999999999999)
        lora_names = lora_args[:MAX_LORAS];
        lora_weights = lora_args[MAX_LORAS:]
        lora_list = [{"name": n, "strength": w} for n, w in zip(lora_names, lora_weights) if n != "None"]

        gr.Info(f"🎬 LTX2.3 task started! \nThis could take a long period, please check the progress in terminal...")

        if is_t2v:
            folder_select = "txt2vid/LTX-2.3"
        else:
            folder_select = "img2vid/LTX-2.3"

        client = LTXVideoClient()
        video_path = client.generate_ltx_video(
            template_path="core/workflows/LTX_i2v.json",
            image_path=image_path,
            lora_list=lora_list,
            prompt=prompt,
            width=width,
            height=height,
            duration=duration,
            fps=fps,
            seed=seed,
            base_model=base_model,
            t2v_mode=is_t2v,
            folder=folder_select,
        )

        end_time = time.time()
        gr.Info(f"✅ Complete! Time usage: {int(end_time - start_time)}s")

        return video_path, seed

    except ConnectionRefusedError:
        raise gr.Error(
            "❌ Can't connect to ComfyUI backend! Please ensure the backend is started (Port 8188). Please wait if the engine is just started.")

    except FileNotFoundError:
        raise gr.Error("❌ Key files missing! Please check integrity of the files and try again.")

    except urllib.error.HTTPError:
        raise gr.Error("❌ Failed to load model! Please ensure the model is in the required format.")

    except Exception as e:
        raise gr.Error(str(e))


# ----- Video Interpolation (插帧) 桥接函数 -----
def generate_interp_wrapper(video_path, multiplier):
    try:
        if not video_path:
            raise gr.Error("❌ Please upload at least one video!")

        gr.Info(f"🚀 Video interpolation task started! (Multiplier: {multiplier}x)")

        client = VideoInterpClient()
        result_video = client.generate_interpolation(
            template_path="core/workflows/highfps_fix.json",
            input_video_path=video_path,
            multiplier=multiplier
        )
        return result_video
    except Exception as e:
        raise gr.Error(str(e))


# ==========================================
# 3. 构建现代风格 Gradio 网页界面
# ==========================================
theme = gr.themes.Soft(
    primary_hue="indigo", neutral_hue="slate",
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"],
    font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "ui-monospace", "Consolas"]
)

custom_css = """
* { border-radius: 4px !important; }
.gr-button { font-weight: 600; }
.delete-btn { min-width: 40px !important; color: #ef4444 !important; background: transparent !important; border: 1px solid #ef4444 !important; }
.delete-btn:hover { background: #fef2f2 !important; }
.swap-btn { margin-top: 28px !important; min-width: 42px !important; max-width: 42px !important; padding: 0 !important; font-size: 1.2em !important; background: transparent !important; border: 1px solid #52525b !important;}
.swap-btn:hover { background: rgba(100, 100, 100, 0.2) !important; }
"""

with (gr.Blocks(theme=theme, css=custom_css, title="LiteUI Studio") as demo):
    gr.Markdown("# 🚀 LiteUI Studio")
    gr.Markdown("A lightweight local AI studio based on ComfyUI backend.")
    lora_choices = get_lora_list()
    unet_choices = get_unet_list()
    mmaudio_choices = get_mmaudio_list()

    with gr.Tabs() as main_tabs:

        # ==========================================
        # TAB 1: 图像生成 (Flux)
        # ==========================================
        with gr.Tab("🖼️ Text to Image (Flux2)", id="tab_t2i"):
            with gr.Row():
                with gr.Column(scale=4):
                    t2i_prompt = gr.Textbox(label="Prompt", lines=3, placeholder="Natural language prompt supported...")
                    with gr.Accordion("🛠️ Base Model", open=False):
                        gr.HTML("""
                                <div style='background-color: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); padding: 8px; border-radius: 4px; margin-bottom: 8px;'>
                                    <span style='color: #ef4444; font-size: 0.9em; font-weight: bold;'>⚠️ Warning: Please use GGUF model based on Flux.2 Klein 9B, or the program can't start!</span>
                                </div>
                                """)
                        t2i_base_model = gr.Dropdown(choices=unet_choices, value="flux-2-klein-9b-Q4_K_M.gguf",
                                                     label="Base Model", interactive=True)
                        t2i_model_open_folder_btn = gr.Button("📂 Open Model Folder", size="lg")

                    with gr.Accordion("🛠️ Parameters", open=True):
                        with gr.Row():
                            t2i_width = gr.Slider(label="Width", minimum=512, maximum=2048, step=16, value=1024,
                                                  scale=10)
                            t2i_swap_btn = gr.Button("🔄", elem_classes="swap-btn", scale=1)
                            t2i_height = gr.Slider(label="Height", minimum=512, maximum=2048, step=16, value=1024,
                                                   scale=10)
                        with gr.Row():
                            t2i_steps = gr.Slider(label="Step", minimum=1, maximum=20, step=1, value=4)
                            t2i_guidance = gr.Slider(label="Guidance", minimum=1.0, maximum=10.0, step=0.1,
                                                     value=4.0)
                        with gr.Row():
                            t2i_upscale_factor = gr.Slider(label="Upscaler", minimum=1, maximum=10, step=0.05,
                                                           value=1, info="No more than 3.00 Recommended.")
                        with gr.Row():
                            t2i_seed = gr.Number(label="Seed", value=88888888, precision=0)
                            t2i_rand_seed = gr.Checkbox(label="🎲 Randomize", value=True)

                    with gr.Accordion("🪄 LoRA Loader", open=False):
                        current_lora_count = gr.State(1)
                        lora_rows, lora_names, lora_weights, remove_btns = [], [], [], []
                        for i in range(MAX_LORAS):
                            with gr.Row(visible=(i == 0)) as row:
                                name = gr.Dropdown(choices=lora_choices, value="None", label=f"LoRA {i + 1}", scale=6)
                                weight = gr.Slider(minimum=-2.0, maximum=2.0, step=0.05, value=1.0, label="Weight",
                                                   scale=3)
                                rm_btn = gr.Button("🗑️", scale=1, elem_classes="delete-btn")
                                lora_rows.append(row);
                                lora_names.append(name);
                                lora_weights.append(weight);
                                remove_btns.append(rm_btn)
                        add_lora_btn = gr.Button("➕ Add LoRA", size="sm")
                        t2i_lora_open_folder_btn = gr.Button("📂 Open LoRA Folder", size="lg")

                    gr.Markdown(
                        "<span style='color: gray; font-size: 0.9em;'>⏱️ <b>Estimated time</b>：RTX 5060 1024x1024: <b>30s</b>。</span>")
                    t2i_btn = gr.Button("🚀 Generate Image", variant="primary", size="lg")
                    t2i_stop_btn = gr.Button("🛑 Interrupt", variant="stop", size="lg", scale=1)

                with gr.Column(scale=5):
                    t2i_output_img = gr.Image(label="Result", format="png", width=800, height=600,
                                              interactive=False)
                    t2i_output_seed = gr.Number(label="Seed", interactive=False)
                    with gr.Row():
                        send_to_i2i_btn = gr.Button("📤 Send to Img2Img", size="lg")
                        send_to_i2v_btn = gr.Button("📤 Send to Img2Vid", size="lg")
                        t2i_open_folder_btn = gr.Button("📂 Open Output Folder", size="lg", scale=1)

        # ==========================================
        # TAB 2: I2I (Flux)
        # ==========================================
        with gr.Tab("🎨 Image to Image (Flux2)", id="tab_i2i"):
            with gr.Row():
                with gr.Column(scale=4):
                    # type="filepath" 会自动保存上传的图片供后端读取
                    i2i_image = gr.Image(label="Input Image", type="filepath", height=256)
                    i2i_prompt = gr.Textbox(label="Prompt", lines=3, placeholder="Natural language prompt supported...")

                    with gr.Accordion("🛠️ Base Model", open=False):
                        gr.HTML("""
                                <div style='background-color: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); padding: 8px; border-radius: 4px; margin-bottom: 8px;'>
                                    <span style='color: #ef4444; font-size: 0.9em; font-weight: bold;'>⚠️ Warning: Please use GGUF model based on Flux.2 Klein 9B, or the program can't start!</span>
                                </div>
                                """)
                        i2i_base_model = gr.Dropdown(choices=unet_choices, value="flux-2-klein-9b-Q4_K_M.gguf",
                                                     label="Base Model", interactive=True)
                        i2i_model_open_folder_btn = gr.Button("📂 Open Model Folder", size="lg")

                    with gr.Accordion("🛠️ Parameters", open=True):
                        with gr.Row():
                            i2i_width = gr.Slider(label="Width", minimum=512, maximum=2048, step=16, value=1024,
                                                  scale=10)
                            i2i_swap_btn = gr.Button("🔄", elem_classes="swap-btn", scale=1)
                            i2i_height = gr.Slider(label="Height", minimum=512, maximum=2048, step=16, value=1024,
                                                   scale=10)
                        with gr.Row():
                            i2i_steps = gr.Slider(label="Step", minimum=1, maximum=20, step=1, value=4)
                            i2i_guidance = gr.Slider(label="Guidance", minimum=1.0, maximum=10.0, step=0.1,
                                                     value=4.0)
                        with gr.Row():
                            i2i_seed = gr.Number(label="Seed", value=88888888, precision=0)
                            i2i_rand_seed = gr.Checkbox(label="🎲 Randomize", value=True)

                    with gr.Accordion("🪄 LoRA Loader", open=False):
                        i2i_current_lora_count = gr.State(1)
                        i2i_lora_rows, i2i_lora_names, i2i_lora_weights, i2i_remove_btns = [], [], [], []
                        for i in range(MAX_LORAS):
                            with gr.Row(visible=(i == 0)) as row:
                                name = gr.Dropdown(choices=lora_choices, value="None", label=f"LoRA {i + 1}", scale=6)
                                weight = gr.Slider(minimum=-2.0, maximum=2.0, step=0.05, value=1.0, label="Weight",
                                                   scale=3)
                                rm_btn = gr.Button("🗑️", scale=1, elem_classes="delete-btn")
                                i2i_lora_rows.append(row);
                                i2i_lora_names.append(name);
                                i2i_lora_weights.append(weight);
                                i2i_remove_btns.append(rm_btn)
                        i2i_add_lora_btn = gr.Button("➕ Add LoRA", size="sm")
                        i2i_lora_open_folder_btn = gr.Button("📂 Open LoRA Folder", size="lg")

                    gr.Markdown(
                        "<span style='color: gray; font-size: 0.9em;'>⏱️ <b>Estimated time:</b>：RTX 5060 1024x1024: <b>60s</b>。</span>")
                    i2i_btn = gr.Button("🚀 Generate Img2Img", variant="primary", size="lg")
                    i2i_stop_btn = gr.Button("🛑 Interrupt", variant="stop", size="lg", scale=1)

                with gr.Column(scale=5):
                    i2i_output_img = gr.Image(label="Result", format="png", width=800, height=600,
                                              interactive=False)
                    i2i_output_seed = gr.Number(label="Seed", interactive=False)
                    with gr.Row():
                        send_i2i_to_i2v_btn = gr.Button("📤 Send to Img2Vid", size="lg")
                        i2i_open_folder_btn = gr.Button("📂 Open ", size="lg", scale=1)

        # ==========================================
        # TAB 3: 视频生成 (Wan2.2)
        # ==========================================
        with gr.Tab("🎞️ Generate Video (Wan2.2)", id="tab_i2v"):
            with gr.Row():
                with gr.Column(scale=4):
                    i2v_image = gr.Image(label="Input Image", type="filepath", height=256)
                    i2v_prompt = gr.Textbox(label="Video Prompt", lines=2,
                                            placeholder="Natural language prompt supported...")

                    with gr.Accordion("🛠️ Advanced Models", open=False):
                        gr.HTML("""
                        <div style='background-color: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); padding: 8px; border-radius: 4px; margin-bottom: 8px;'>
                            <span style='color: #ef4444; font-size: 0.9em; font-weight: bold;'>⚠️ Warning: Use default model if you are not familiar with backend! Use incorrect model could cause crash!</span>
                        </div>
                        """)
                        i2v_high_base = gr.Dropdown(choices=unet_choices, value="Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf",
                                                    label="High Noise Base Model", interactive=True)

                        i2v_low_base = gr.Dropdown(choices=unet_choices, value="Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf",
                                                   label="Low Noise Base Model", interactive=True)
                        # 这个音频底模也受总开关控制，默认情况被锁死
                        i2v_audio_model = gr.Dropdown(choices=mmaudio_choices,
                                                      value="mmaudio_large_44k_v2_fp16.safetensors",
                                                      label="MMAudio Model", interactive=True)

                        i2v_model_open_folder_btn = gr.Button("📂 Open Model Folder", size="lg")
                        i2v_mmaudio_open_folder_btn = gr.Button("📂 Open MMAudio Folder", size="lg")

                    with gr.Accordion("⚙️ Video Setting", open=True):
                        with gr.Row():
                            i2v_width = gr.Slider(label="Width", minimum=256, maximum=1024, step=16, value=512,
                                                  scale=10)
                            i2v_swap_btn = gr.Button("🔄", elem_classes="swap-btn", scale=1)
                            i2v_height = gr.Slider(label="Height", minimum=256, maximum=1024, step=16, value=768,
                                                   scale=10)
                        with gr.Row():
                            i2v_duration = gr.Slider(label="Duration", minimum=1, maximum=30, step=1, value=5)
                            
                        with gr.Row():
                            i2v_seed = gr.Number(label="High Noise Seed", value=1234567, precision=0)
                            i2v_rand_seed = gr.Checkbox(label="🎲 Randomize", value=True)

                    with gr.Accordion("🪄 Wan2.2 LoRA (High/Low)", open=False):
                        gr.Markdown("Wan2.2 requires both High noise and Low noise versions of LoRA.")
                        with gr.Row():
                            i2v_high_lora = gr.Dropdown(choices=lora_choices, value="None", label="High Noise LoRA",
                                                        scale=3)
                            i2v_high_str = gr.Slider(minimum=0.0, maximum=2.0, step=0.05, value=1.0, label="Weight",
                                                     scale=1)
                        with gr.Row():
                            i2v_low_lora = gr.Dropdown(choices=lora_choices, value="None", label="Low Noise LoRA",
                                                       scale=3)
                            i2v_low_str = gr.Slider(minimum=0.0, maximum=2.0, step=0.05, value=1.0, label="Weight",
                                                    scale=1)

                        i2v_lora_open_folder_btn = gr.Button("📂 Open LoRA Folder", size="lg")

                    with gr.Accordion("🎵 Audio Generation", open=True):
                        i2v_enable_audio = gr.Checkbox(label="🔊 Enable Audio Engine", value=False)

                        # 【修改 1】：在 label 里混入 HTML 的 span 标签，利用 title 属性实现鼠标悬浮提示
                        i2v_separate_audio = gr.Checkbox(
                            label="🔀 Separate Audio Prompt",
                            info="When disabled, the video prompt is used as audio prompt",
                            value=False,
                            interactive=False
                        )

                        # 【修改 2】：把 visible=False 改为 interactive=False，让它初始可见但变灰不可输入
                        i2v_audio_prompt = gr.Textbox(
                            label="Audio Prompt",
                            lines=2,
                            placeholder="Please enter word prompt separated by commas (Use GenAI if needed)...",
                            interactive=False
                        )

                    gr.HTML("""
                    <div style='background-color: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.3); padding: 12px; border-radius: 6px; margin-bottom: 10px; line-height: 1.6;'>
                        <span style='color: #f59e0b; font-weight: bold; font-size: 1em;'>⏳ Warning:</span>
                        <span style='color: var(--body-text-color); font-size: 0.9em;'>Video generation is GPU consuming.</span><br>
                        <span style='color: var(--body-text-color); font-size: 0.9em;'>Do not refresh page when task is started. Audio generation could take 20%~30% of extra time. Please view the progress in terminal.</span>
                    </div>
                    """)
                    i2v_btn = gr.Button("🎬 Generate Video", variant="primary", size="lg")
                    i2v_stop_btn = gr.Button("🛑 Interrupt", variant="stop", size="lg", scale=1)

                with gr.Column(scale=5):
                    i2v_output_vid = gr.Video(label="Result", width=800, height=600, interactive=False)
                    i2v_output_seed = gr.Number(label="Seed", interactive=False)

                    i2v_open_folder_btn = gr.Button("📂 Open Output Folder", size="lg")

        # ==========================================
        # TAB 5: LTX-2.3 (Native Audio-Video)
        # ==========================================
        with gr.Tab("🌟 Video Generation (LTX-2.3)", id="tab_ltx"):
            with gr.Row():
                with gr.Column(scale=4):
                    # 模式选择器
                    ltx_mode = gr.Radio(
                        choices=["Text to Video", "Image to Video"],
                        value="Text to Video",
                        label="🎥 Generation Mode"
                    )

                    # 图片上传框 (默认隐藏，只有选了 I2V 才弹出来)
                    ltx_image = gr.Image(label="Input Image", type="filepath", height=256,
                                         visible=False)

                    ltx_prompt = gr.Textbox(
                        label="🎬 Temporal Prompt",
                        lines=7,
                        value='A woman at a chair and looks towards the camera.\n\n0-1 seconds : She takes off her hat.\n1-8 seconds: She talks with a soft British accent and says "You are now testing LTX model."\n8-10 seconds: She stands up and puts on her hat again.\n\nStyle: Wes Anderson style, rigid, pastel color palette.',
                        info="Human speaking voice supported!"
                    )

                    with gr.Accordion("⚙️ Video Setting", open=True):
                        with gr.Row():
                            ltx_width = gr.Slider(label="Width", minimum=256, maximum=1024, step=16,
                                                  value=512,
                                                  scale=10)
                            ltx_swap_btn = gr.Button("🔄", elem_classes="swap-btn", scale=1)
                            ltx_height = gr.Slider(label="Height", minimum=256, maximum=1024, step=16,
                                                   value=768, scale=10)
                        with gr.Row():
                            ltx_duration = gr.Slider(label="Duration", minimum=1, maximum=20, step=1,
                                                     value=10)
                            ltx_fps = gr.Slider(label="FPS", minimum=8, maximum=60, step=1, value=24)
                        with gr.Row():
                            ltx_seed = gr.Number(label="Base Seed", value=88888888, precision=0)
                            ltx_rand_seed = gr.Checkbox(label="🎲 Randomize", value=True)

                    with gr.Accordion("🛠️ Base Model and LoRA", open=False):
                        gr.HTML("""
                                <div style='background-color: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); padding: 8px; border-radius: 4px; margin-bottom: 8px;'>
                                    <span style='color: #ef4444; font-size: 0.9em; font-weight: bold;'>⚠️ Warning: Use default model if you are not familiar with backend! Use incorrect model could cause crash!</span>
                                </div>
                                """)
                        ltx_base_model = gr.Dropdown(choices=unet_choices,
                                                     value="ltx-2.3-22b-distilled-1.1-Q4_K_M.gguf",
                                                     label="LTX Base Model", interactive=True)

                        ltx_current_lora_count = gr.State(1)
                        ltx_lora_rows, ltx_lora_names, ltx_lora_weights, ltx_remove_btns = [], [], [], []
                        for i in range(MAX_LORAS):
                            with gr.Row(visible=(i == 0)) as row:
                                name = gr.Dropdown(choices=lora_choices, value="None", label=f"LoRA {i + 1}",
                                                   scale=6)
                                weight = gr.Slider(minimum=-2.0, maximum=2.0, step=0.05, value=1.0,
                                                   label="Weight",
                                                   scale=3)
                                rm_btn = gr.Button("🗑️", scale=1, elem_classes="delete-btn")
                                ltx_lora_rows.append(row);
                                ltx_lora_names.append(name);
                                ltx_lora_weights.append(weight);
                                ltx_remove_btns.append(rm_btn)
                        ltx_add_lora_btn = gr.Button("➕ 添加 LoRA", size="sm")

                    gr.HTML("""
                        <div style='background-color: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.3); padding: 12px; border-radius: 6px; margin-bottom: 10px; line-height: 1.6;'>
                            <span style='color: #f59e0b; font-weight: bold; font-size: 1em;'>⏳ Warning:</span>
                            <span style='color: var(--body-text-color); font-size: 0.9em;'>This model supports both video generation and audio dubbing.</span><br>
                            <span style='color: var(--body-text-color); font-size: 0.9em;'>Do not refresh when the task is started.</span>
                        </div>
                        """)
                    ltx_btn = gr.Button("🎬 Generate Video", variant="primary", size="lg")
                    ltx_stop_btn = gr.Button("🛑 Interrupt", variant="stop", size="lg", scale=1)

                with gr.Column(scale=5):
                    ltx_output_vid = gr.Video(label="Result", width=800, height=600,
                                              interactive=False)
                    ltx_output_seed = gr.Number(label="Seed", interactive=False)
                    ltx_send_to_interp_btn = gr.Button("📤 Send to Video interpolation", size="lg", scale=2)
                    ltx_open_folder_btn = gr.Button("📂 Open Output Folder", size="lg")

        # ==========================================
        # TAB: 视频插帧 (Video Interpolation)
        # ==========================================
        with gr.Tab("🎞️ Video Interpolation", id="tab_interp"):
            with gr.Row():
                with gr.Column(scale=4):
                    # 视频输入组件，允许用户直接拖拽或从其他页面传过来
                    interp_input_vid = gr.Video(label="Input Video", sources=["upload"], height=256, )

                    with gr.Accordion("⚙️ Parameters", open=True):
                        # 倍率滑块，step=1 强制为整数
                        interp_multiplier = gr.Slider(
                            label="Multiplier",
                            minimum=2, maximum=8, step=1, value=2,
                            info="Increase FPS by ×N (2 or 4 recommended).)"
                        )

                    with gr.Row():
                        interp_btn = gr.Button("🚀 Interpolate", variant="primary", size="lg",
                                               scale=4)
                        interp_stop_btn = gr.Button("🛑 Interrupt", variant="stop", size="lg", scale=1)

                    gr.HTML("""
                            <div style='background-color: rgba(11, 158, 245, 0.15); border: 1px solid rgba(11, 158, 245, 0.3); padding: 12px; border-radius: 6px; margin-bottom: 10px; line-height: 1.6;'>

                                <span style='color: var(--body-text-color); font-size: 0.9em;'>ℹ️ If you see a number of "Comfy-VFI: Clearing cache... Done cache clearing", just ignore them.</span>
                            </div>
                            """)

                with gr.Column(scale=5):
                    interp_output_vid = gr.Video(label="Result", width=800, height=600, interactive=False)
                    interp_open_folder_btn = gr.Button("📂 Open Output Folder", size="lg")

        with gr.Tab("🔍 Metadata Inspector", id="tab_inspector"):
            gr.Markdown("Upload an image or video generated in this studio to get metadata!")

            with gr.Row():
                with gr.Column(scale=4):
                    # gr.File 是最完美的容器，因为它既能接图，也能接视频！
                    inspector_input = gr.File(label="📁 Upload Image or Video", file_types=["image", "video"],
                                              type="filepath")
                    mi_open_folder_btn = gr.Button("📂 Open Output Folder", size="lg")

                with gr.Column(scale=5):
                    # 用 Markdown 组件来渲染我们排版好的文字结果
                    inspector_output = gr.Markdown(value="*Parameters are shown here...*", elem_classes="markdown-output")

            # 注入一点专属的 CSS 边框让 Markdown 看起来像个控制台
            gr.HTML("""
            <style>
            .markdown-output { background: rgba(30,41,59, 0.5); padding: 20px; border-radius: 8px; border: 1px solid #334155; min-height: 400px; }
            </style>
            """)


    # ==========================================
    # 4. 绑定事件逻辑
    # ==========================================
    def update_audio_states(enable_audio_val, separate_audio_val):
        # 规则 1：只要开了总开关，子开关和底模下拉框就亮起 (可用)
        sub_switch_interactive = enable_audio_val
        model_interactive = enable_audio_val

        # 规则 2：只有总开关和子开关【同时】开启，文本框才允许输入
        prompt_interactive = bool(enable_audio_val and separate_audio_val)

        return (
            gr.update(interactive=sub_switch_interactive),  # 给 i2v_separate_audio
            gr.update(interactive=prompt_interactive),  # 给 i2v_audio_prompt
            gr.update(interactive=model_interactive)  # 给 i2v_audio_model
        )


    # 把两个开关的触发事件，全部绑定到这同一个“大脑”上
    audio_state_inputs = [i2v_enable_audio, i2v_separate_audio]
    audio_state_outputs = [i2v_separate_audio, i2v_audio_prompt, i2v_audio_model]

    i2v_enable_audio.change(fn=update_audio_states, inputs=audio_state_inputs, outputs=audio_state_outputs)
    i2v_separate_audio.change(fn=update_audio_states, inputs=audio_state_inputs, outputs=audio_state_outputs)

    # 宽高交换
    swap_fn = lambda w, h: (h, w)

    t2i_swap_btn.click(fn=swap_fn, inputs=[t2i_width, t2i_height], outputs=[t2i_width, t2i_height])
    i2v_swap_btn.click(fn=swap_fn, inputs=[i2v_width, i2v_height], outputs=[i2v_width, i2v_height])
    i2i_swap_btn.click(fn=swap_fn, inputs=[i2i_width, i2i_height], outputs=[i2i_width, i2i_height])

    t2i_open_folder_btn.click(fn=lambda: open_output_folder(mode="t2i"), inputs=None, outputs=None)
    i2v_open_folder_btn.click(fn=lambda: open_output_folder(mode="i2v"), inputs=None, outputs=None)
    i2i_open_folder_btn.click(fn=lambda: open_output_folder(mode="i2i"), inputs=None, outputs=None)
    mi_open_folder_btn.click(fn=lambda: open_output_folder(mode=""), inputs=None, outputs=None)
    ltx_open_folder_btn.click(fn=lambda: open_output_folder(mode=""), inputs=None, outputs=None)
    interp_open_folder_btn.click(fn=lambda: open_output_folder(mode="interp"), inputs=None, outputs=None)

    t2i_model_open_folder_btn.click(fn=lambda: open_output_folder(mode="model"), inputs=None, outputs=None)
    i2i_model_open_folder_btn.click(fn=lambda: open_output_folder(mode="model"), inputs=None, outputs=None)
    i2v_model_open_folder_btn.click(fn=lambda: open_output_folder(mode="model"), inputs=None, outputs=None)

    t2i_lora_open_folder_btn.click(fn=lambda: open_output_folder(mode="lora"), inputs=None, outputs=None)
    i2i_lora_open_folder_btn.click(fn=lambda: open_output_folder(mode="lora"), inputs=None, outputs=None)
    i2v_lora_open_folder_btn.click(fn=lambda: open_output_folder(mode="lora"), inputs=None, outputs=None)
    i2v_mmaudio_open_folder_btn.click(fn=lambda: open_output_folder(mode="mmaudio"), inputs=None, outputs=None)

    t2i_stop_btn.click(fn=interrupt_comfyui_task, inputs=None, outputs=None)
    i2i_stop_btn.click(fn=interrupt_comfyui_task, inputs=None, outputs=None)
    i2v_stop_btn.click(fn=interrupt_comfyui_task, inputs=None, outputs=None)
    ltx_stop_btn.click(fn=interrupt_comfyui_task, inputs=None, outputs=None)

    # --- Tab 1 事件 ---
    add_lora_btn.click(fn=add_lora_slot, inputs=[current_lora_count], outputs=[current_lora_count] + lora_rows)
    all_t2i_inputs = [current_lora_count] + lora_names + lora_weights
    all_t2i_outputs = [current_lora_count] + lora_rows + lora_names + lora_weights
    for i in range(MAX_LORAS):
        remove_btns[i].click(fn=make_remove_fn(i), inputs=all_t2i_inputs, outputs=all_t2i_outputs)

    t2i_btn.click(
        fn=generate_t2i_wrapper,
        inputs=[t2i_prompt, t2i_width, t2i_height, t2i_steps, t2i_guidance, t2i_upscale_factor, t2i_seed,
                t2i_rand_seed, t2i_base_model] + lora_names + lora_weights,
        outputs=[t2i_output_img, t2i_output_seed]
    )


    # 发送图片至其他tab
    def verify_and_pass_img(img):
        """动作 1：纯粹负责校验并传递图片数据"""
        if img is None:
            raise gr.Error("❌ Please generate an image!")
        return img


    def jump_to_ltx_tab():
        """动作 2：纯粹负责触发前端标签页跳转"""
        return gr.update(selected="tab_ltx")


    def jump_to_i2i_tab():
        """动作 2：纯粹负责触发前端标签页跳转"""
        return gr.update(selected="tab_i2i")


    send_to_i2i_btn.click(
        fn=verify_and_pass_img,
        inputs=[t2i_output_img],
        outputs=[i2i_image]
    ).then(
        fn=jump_to_i2i_tab,
        inputs=None,
        outputs=[main_tabs]
    )

    send_to_i2v_btn.click(
        fn=verify_and_pass_img,
        inputs=[t2i_output_img],
        outputs=[i2v_image]
    ).then(
        fn=verify_and_pass_img,
        inputs=[t2i_output_img],
        outputs=[ltx_image]
    ).then(
        fn=jump_to_ltx_tab,
        inputs=None,
        outputs=[main_tabs]
    )

    # --- Tab 2 事件 ---
    i2i_add_lora_btn.click(fn=add_lora_slot, inputs=[i2i_current_lora_count],
                           outputs=[i2i_current_lora_count] + i2i_lora_rows)
    all_i2i_inputs = [i2i_current_lora_count] + i2i_lora_names + i2i_lora_weights
    all_i2i_outputs = [i2i_current_lora_count] + i2i_lora_rows + i2i_lora_names + i2i_lora_weights
    for i in range(MAX_LORAS):
        i2i_remove_btns[i].click(fn=make_remove_fn(i), inputs=all_i2i_inputs, outputs=all_i2i_outputs)

    i2i_btn.click(
        fn=generate_i2i_wrapper,
        inputs=[i2i_image, i2i_prompt, i2i_width, i2i_height, i2i_steps, i2i_guidance, i2i_seed, i2i_rand_seed,
                i2i_base_model] + i2i_lora_names + i2i_lora_weights,
        outputs=[i2i_output_img, i2i_output_seed]
    )

    send_i2i_to_i2v_btn.click(
        fn=verify_and_pass_img,
        inputs=[i2i_output_img],
        outputs=[i2v_image]
    ).then(
        fn=verify_and_pass_img,
        inputs=[i2i_output_img],
        outputs=[ltx_image]
    ).then(
        fn=jump_to_ltx_tab,
        inputs=None,
        outputs=[main_tabs]
    )

    # --- Tab 3 事件 ---
    i2v_btn.click(
        fn=generate_i2v_wrapper,
        inputs=[
            i2v_image, i2v_prompt, i2v_duration, i2v_width, i2v_height,
            i2v_seed, i2v_rand_seed,
            i2v_high_lora, i2v_high_str, i2v_low_lora, i2v_low_str,
            i2v_enable_audio, i2v_separate_audio, i2v_audio_prompt,  # 【新增的配音参数传入】
            i2v_high_base, i2v_low_base, i2v_audio_model
        ],
        outputs=[i2v_output_vid, i2v_output_seed]
    )


    # --- Tab 4 (LTX-2.3) 专属动态 UI 逻辑 ---
    def toggle_ltx_mode(mode_val):
        """如果选了 I2V，则显示图片框；否则隐藏"""
        return gr.update(visible=(mode_val == "Image to Video"))


    ltx_mode.change(fn=toggle_ltx_mode, inputs=[ltx_mode], outputs=[ltx_image])

    # 反转宽高逻辑
    ltx_swap_btn.click(fn=swap_fn, inputs=[ltx_width, ltx_height], outputs=[ltx_width, ltx_height])

    # LoRA 逻辑
    ltx_add_lora_btn.click(fn=add_lora_slot, inputs=[ltx_current_lora_count],
                           outputs=[ltx_current_lora_count] + ltx_lora_rows)
    all_ltx_inputs = [ltx_current_lora_count] + ltx_lora_names + ltx_lora_weights
    all_ltx_outputs = [ltx_current_lora_count] + ltx_lora_rows + ltx_lora_names + ltx_lora_weights
    for i in range(MAX_LORAS):
        ltx_remove_btns[i].click(fn=make_remove_fn(i), inputs=all_ltx_inputs, outputs=all_ltx_outputs)

    # 生成核心逻辑
    ltx_btn.click(
        fn=generate_ltx_wrapper,
        inputs=[ltx_mode, ltx_image, ltx_prompt, ltx_width, ltx_height, ltx_duration, ltx_fps, ltx_seed, ltx_rand_seed,
                ltx_base_model] + ltx_lora_names + ltx_lora_weights,
        outputs=[ltx_output_vid, ltx_output_seed]
    )


    # ==========================================
    # 跨页面流转：发送至插帧页面
    # ==========================================
    def verify_and_pass_vid(vid):
        if vid is None:
            raise gr.Error("❌ Please generate a video!")
        return vid


    def jump_to_interp_tab():
        return gr.update(selected="tab_interp")


    # 假设你给 LTX 或 Wan2.2 的发送按钮命名为 send_to_interp_btn
    ltx_send_to_interp_btn.click(
        fn=verify_and_pass_vid,
        inputs=[ltx_output_vid],  # 或者是 ltx_output_vid
        outputs=[interp_input_vid]
    ).then(
        fn=jump_to_interp_tab,
        inputs=None,
        outputs=[main_tabs]
    )

    # --- 视频插帧 事件 ---
    interp_btn.click(
        fn=generate_interp_wrapper,
        inputs=[interp_input_vid, interp_multiplier],
        outputs=[interp_output_vid]
    )
    interp_stop_btn.click(fn=interrupt_comfyui_task, inputs=None, outputs=None)


    # --- Tab 6 事件 ---
    def parse_metadata_wrapper(file_path):
        if not file_path:
            return "*Waiting to upload file...*"
        return extract_comfyui_metadata(file_path)


    inspector_input.change(
        fn=parse_metadata_wrapper,
        inputs=[inspector_input],
        outputs=[inspector_output]
    )

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, inbrowser=True)
