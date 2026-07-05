import json
import urllib.request
import urllib.parse
import uuid
import websocket
import requests
import os
import subprocess
import shutil
import time


class Wan2VideoPipelineClient:
    def __init__(self, server_address="127.0.0.1:8188"):
        self.server_address = server_address
        self.client_id = str(uuid.uuid4())

        # 阶段 1：高噪管线参数路由
        self.MAP_HIGH = {
            "prompt": ("257:286", "value"),
            "duration": ("257:229", "value"),
            "width": ("257:302", "value"),
            "height": ("257:303", "value"),
            "seed": ("257:237", "noise_seed"),
            "high_base_model": ("257:258", "unet_name"),
        }

        # 阶段 2：低噪管线参数路由
        self.MAP_LOW = {
            "prompt": ("257:286", "value"),
            "duration": ("257:229", "value"),
            "width": ("257:302", "value"),
            "height": ("257:303", "value"),
            "seed": ("257:253", "noise_seed"),
            "low_base_model": ("257:259", "unet_name"),
        }

        # 阶段 3：插帧与配音参数路由
        self.MAP_INTERP = {
            "duration": ("257:229", "value"),
            "width": ("257:302", "value"),
            "height": ("257:303", "value"),
            "separate_audio": ("257:301", "value"),
            "audio_prompt": ("257:299", "value"),
            "audio_model": ("257:296:280", "mmaudio_model"),
            "audio_seed": ("257:296:279", "seed"),
            "video_prompt": ("257:286", "value"),  # 兜底传给配音节点用
        }

    # ========================== 通用底层工具 ==========================

    def free_vram(self):
        print("\n[♻️ VRAM Manage] Clear caches request sent...")
        try:
            response = requests.post(
                f"http://{self.server_address}/free",
                json={"unload_models": True, "free_memory": True},
                timeout=5
            )
            if response.status_code == 200:
                print("[♻️ VRAM Manage] Request received. Waiting for clearing...")
                time.sleep(3)  # 【关键】给显存释放留出时间，不要立马发下一个任务
            else:
                print(f"[!] Failed to clear caches: {response.status_code}")
        except Exception as e:
            print(f"[!] Network error: {e}")

    def _wait_for_completion(self, prompt_id):
        """统一的 WebSocket 监听器与防爆雷达"""
        ws = websocket.WebSocket()
        ws.connect(f"ws://{self.server_address}/ws?clientId={self.client_id}")
        try:
            while True:
                out = ws.recv()
                if isinstance(out, str):
                    message = json.loads(out)
                    if message['type'] == 'executing':
                        data = message['data']
                        if data['node'] is None and data['prompt_id'] == prompt_id:
                            return  # 执行成功
                    elif message['type'] == 'execution_error':
                        error_data = message['data']
                        error_msg = error_data.get('exception_message', 'Unknown Error')
                        node_id = error_data.get('node_id', 'Unknown Node')
                        if 'out of memory' in error_msg.lower() or 'allocate' in error_msg.lower() or 'oom' in error_msg.lower():
                            raise Exception(f"💥 Out Of Memory! Failed to allocate VRAM to Node [{node_id}].")
                        elif message['type'] == 'execution_interrupted':
                            raise Exception("🛑 Interrupted！")
                        elif "shapes cannot be multiplied" in error_msg.lower():
                            raise Exception(
                                f"❌ Error on Node [{node_id}]：Failed to load model! Ensure you are using the model based on Flux2-Klein-9B, with correct quantization.")
                        else:
                            raise Exception(
                                f"❌ An unexpected error happened on Node [{node_id}]: {error_msg}. Please feedback to the developer.")
        except websocket.WebSocketConnectionClosedException:
            raise Exception("💀 Disconnected with ComfyUI backend!")
        finally:
            ws.close()

    def _extract_output_filename(self, history, node_id):
        """防御性提取任意节点的输出文件名"""
        if node_id in history['outputs']:
            for key, data_list in history['outputs'][node_id].items():
                if isinstance(data_list, list) and len(data_list) > 0:
                    for item in data_list:
                        if isinstance(item, dict) and 'filename' in item:
                            return item['filename'], item.get('subfolder', ''), item.get('type', 'output')
        raise Exception(f"Can't extract file in Node {node_id}.")

    def _download_to_input_dir(self, filename, subfolder, folder_type, target_filename):
        """【核心黑魔法】：将上个阶段的输出文件，下载并直接塞进 ComfyUI 的 Input 目录，确保下个阶段能读到"""
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url = f"http://{self.server_address}/view?{urllib.parse.urlencode(data)}"

        # 定位项目内嵌的 backend_comfyui/input 目录
        project_root = os.path.dirname(os.path.dirname(__file__))
        input_dir = os.path.join(project_root, "backend_comfyui", "input")
        os.makedirs(input_dir, exist_ok=True)

        target_path = os.path.join(input_dir, target_filename)
        response = requests.get(url)
        with open(target_path, "wb") as f:
            f.write(response.content)

        return target_filename, target_path

    # ========================== 核心生成管线 ==========================

    def generate_pipeline(self, image_path, enable_audio,
                          high_lora=None, low_lora=None, **kwargs):

        # 0. 准备工作：上传图片
        print("Uploading image...")
        with open(image_path, "rb") as f:
            res = requests.post(f"http://{self.server_address}/upload/image", files={"image": f})
            uploaded_img_name = res.json()['name']

        # 盛放三个阶段的完整参数字典，最后用于合并注入 Metadata
        meta_merged_workflow = {}

        try:
            # =======================================================
            # 阶段 1：高噪潜变量生成 (High Noise)
            # =======================================================
            print("\n" + "=" * 50 + "\n 🚀 [Stage 1/3] High Noise Render\n" + "=" * 50)
            with open("core/workflows/Wan2.2_i2v_high_noise.json", "r", encoding="utf-8") as f:
                wf_high = json.load(f)

            wf_high["97"]["inputs"]["image"] = uploaded_img_name
            if high_lora:
                wf_high["257:276"]["inputs"]["lora_1"]["lora"] = high_lora["name"]
                wf_high["257:276"]["inputs"]["lora_1"]["strength"] = high_lora["strength"]
                wf_high["257:276"]["inputs"]["lora_1"]["on"] = True

            for k, v in kwargs.items():
                if k in self.MAP_HIGH:
                    node_id, field = self.MAP_HIGH[k]
                    if node_id in wf_high: wf_high[node_id]["inputs"][field] = v

            meta_merged_workflow.update(wf_high)
            pid_high = json.loads(urllib.request.urlopen(urllib.request.Request(f"http://{self.server_address}/prompt",
                                                                                data=json.dumps({"prompt": wf_high,
                                                                                                 "client_id": self.client_id}).encode(
                                                                                    'utf-8'))).read())['prompt_id']

            self._wait_for_completion(pid_high)

            # 提取 257:322 的 Latent 并转移至 Input 目录
            history_high = json.loads(urllib.request.urlopen(
                urllib.request.Request(f"http://{self.server_address}/history/{pid_high}")).read())[pid_high]
            lat_file, lat_sub, lat_type = self._extract_output_filename(history_high, "257:322")
            step1_latent_name = f"temp_phase1_{self.client_id}.latent"
            self._download_to_input_dir(lat_file, lat_sub, lat_type, step1_latent_name)

            self.free_vram()  # 【释放显存】

            # =======================================================
            # 阶段 2：低噪去噪与临时视频 (Low Noise)
            # =======================================================
            print("\n" + "=" * 50 + "\n 🚀 [Step 2/3] Low Noise Phase\n" + "=" * 50)
            with open("core/workflows/Wan2.2_i2v_low_noise.json", "r", encoding="utf-8") as f:
                wf_low = json.load(f)

            wf_low["97"]["inputs"]["image"] = uploaded_img_name
            wf_low["98"]["inputs"]["latent"] = step1_latent_name  # 接入上一阶段产物
            if low_lora:
                wf_low["257:277"]["inputs"]["lora_1"]["lora"] = low_lora["name"]
                wf_low["257:277"]["inputs"]["lora_1"]["strength"] = low_lora["strength"]
                wf_low["257:277"]["inputs"]["lora_1"]["on"] = True

            for k, v in kwargs.items():
                if k in self.MAP_LOW:
                    node_id, field = self.MAP_LOW[k]
                    if node_id in wf_low: wf_low[node_id]["inputs"][field] = v

            meta_merged_workflow.update(wf_low)
            pid_low = json.loads(urllib.request.urlopen(urllib.request.Request(f"http://{self.server_address}/prompt",
                                                                               data=json.dumps({"prompt": wf_low,
                                                                                                "client_id": self.client_id}).encode(
                                                                                   'utf-8'))).read())['prompt_id']

            self._wait_for_completion(pid_low)

            # 提取 257:324 的视频并转移至 Input 目录
            history_low = json.loads(urllib.request.urlopen(
                urllib.request.Request(f"http://{self.server_address}/history/{pid_low}")).read())[pid_low]
            vid_file, vid_sub, vid_type = self._extract_output_filename(history_low, "257:324")
            step2_video_name = f"temp_phase2_{self.client_id}.mp4"
            # 拿到这个视频的物理绝对路径，留给下一阶段用
            _, abs_temp_vid_path = self._download_to_input_dir(vid_file, vid_sub, vid_type, step2_video_name)

            self.free_vram()  # 【释放显存】

            # =======================================================
            # 阶段 3：插帧与配音 (Interpolation & Dubbing)
            # =======================================================
            print("\n" + "=" * 50 + "\n 🚀 [Step 3/3] Interpolation and Audio generation\n" + "=" * 50)
            with open("core/workflows/Wan2.2_i2v_interpolate_dubbing.json", "r", encoding="utf-8") as f:
                wf_interp = json.load(f)

            # VHS_LoadVideoPath 节点 (257:325) 极其强大，它直接支持读取电脑里的绝对路径
            abs_temp_vid_path = os.path.normpath(abs_temp_vid_path)
            wf_interp["257:325"]["inputs"]["video"] = abs_temp_vid_path

            # 如果用户没开配音，直接卸载模型让分支作废
            if not enable_audio:
                wf_interp["257:296:280"]["inputs"]["mmaudio_model"] = "None"

            for k, v in kwargs.items():
                if k in self.MAP_INTERP:
                    node_id, field = self.MAP_INTERP[k]
                    if node_id in wf_interp: wf_interp[node_id]["inputs"][field] = v

            meta_merged_workflow.update(wf_interp)
            pid_interp = json.loads(urllib.request.urlopen(
                urllib.request.Request(f"http://{self.server_address}/prompt",
                                       data=json.dumps({"prompt": wf_interp, "client_id": self.client_id}).encode(
                                           'utf-8'))).read())['prompt_id']

            self._wait_for_completion(pid_interp)

            # 提取 298 节点的最终结果并下载到用户的保存路径
            history_interp = json.loads(urllib.request.urlopen(
                urllib.request.Request(f"http://{self.server_address}/history/{pid_interp}")).read())[pid_interp]
            final_file, final_sub, final_type = self._extract_output_filename(history_interp, "298")

            # --- 核心性能优化：物理路径直接映射，免去 HTTP 下载 ---
            project_root = os.path.dirname(os.path.dirname(__file__))
            # 根据类型判断是在 output 还是 temp 文件夹
            base_folder = "output" if final_type == "output" else "temp"

            if final_sub:
                final_physical_path = os.path.join(project_root, "backend_comfyui", base_folder, final_sub, final_file)
            else:
                final_physical_path = os.path.join(project_root, "backend_comfyui", base_folder, final_file)

            final_physical_path = os.path.normpath(final_physical_path)
            print(f"\n🎉 Output video saved to: {final_physical_path}")

        finally:
            self.free_vram()

        # =======================================================
        # 结尾工作：物理层原地 Metadata 注入与临时文件销毁
        # =======================================================
        try:
            print("[*] Merging Metadata ...")
            # 直接在 ComfyUI 的 output 目录里做临时文件转换
            temp_mp4 = final_physical_path + ".temp.mp4"
            cmd = ['ffmpeg', '-y', '-i', final_physical_path, '-c', 'copy', '-metadata',
                   f'comment={json.dumps(meta_merged_workflow)}', temp_mp4]

            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 转换成功后，用带有 Metadata 的新文件覆盖原文件
            shutil.move(temp_mp4, final_physical_path)
            print("[*] ✅ Metadata Merged！")
        except Exception as e:
            print(f"[!] Failed to merge metadata, please check if FFmpeg is installed: {e}")

            # 销毁 input 里的临时中转文件
        input_dir = os.path.join(project_root, "backend_comfyui", "input")
        for f in [step1_latent_name, step2_video_name]:
            try:
                os.remove(os.path.join(input_dir, f))
            except:
                pass

        # 直接把物理路径返回给 WebUI
        return final_physical_path