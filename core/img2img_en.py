import json
import urllib.request
import urllib.parse
import uuid
import websocket
import requests
import io
import gradio as gr
from PIL import Image


class FluxImg2ImgClient:
    def __init__(self, server_address="127.0.0.1:8188"):
        self.server_address = server_address
        self.client_id = str(uuid.uuid4())

        # 针对图生图 JSON 的参数映射表
        self.PARAM_MAP = {
            "prompt": ("12", "text"),
            "width": ("8", "value"),
            "height": ("9", "value"),
            "steps": ("10:33", "steps"),
            "guidance": ("13", "guidance"),
            "seed": ("10:31", "noise_seed"),
            "base_model": ("1", "unet_name")  # 允许切换大模型
        }

    def upload_image(self, image_path):
        """将本地图片上传到 ComfyUI，供图生图使用"""
        print(f"[*] 正在上传参考图片: {image_path}")
        with open(image_path, "rb") as f:
            files = {"image": f}
            response = requests.post(f"http://{self.server_address}/upload/image", files=files)

        if response.status_code == 200:
            result = response.json()
            print(f"[*] Successfully upload image, named by server: {result['name']}")
            return result['name']
        else:
            raise Exception(f"Failed to upload image: {response.text}")

    def _queue_prompt(self, prompt_workflow):
        p = {"prompt": prompt_workflow, "client_id": self.client_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request(f"http://{self.server_address}/prompt", data=data)
        return json.loads(urllib.request.urlopen(req).read())

    def _get_image(self, filename, subfolder, folder_type):
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(data)
        req = urllib.request.Request(f"http://{self.server_address}/view?{url_values}")
        return urllib.request.urlopen(req).read()

    def _get_history(self, prompt_id):
        req = urllib.request.Request(f"http://{self.server_address}/history/{prompt_id}")
        return json.loads(urllib.request.urlopen(req).read())

    def generate_img2img(self, template_path, input_image_path, lora_list=None, **kwargs):
        """核心图生图生成引擎"""

        # 1. 上传参考图
        uploaded_filename = self.upload_image(input_image_path)

        # 2. 读取工作流模板
        with open(template_path, "r", encoding="utf-8") as f:
            workflow = json.load(f)

        # 3. 注入图片到 LoadImage 节点 (节点 6)
        if "6" in workflow:
            workflow["6"]["inputs"]["image"] = uploaded_filename
        else:
            raise Exception("Can't find LoadImage Node(6)")

        # 4. 处理 LoRA (节点 42)
        if lora_list is not None and "42" in workflow:
            node_42_inputs = workflow["42"]["inputs"]
            keys_to_delete = [k for k in node_42_inputs.keys() if k.startswith("lora_")]
            for k in keys_to_delete:
                del node_42_inputs[k]

            for i, lora in enumerate(lora_list, start=1):
                node_42_inputs[f"lora_{i}"] = {
                    "on": True,
                    "lora": lora["name"],
                    "strength": lora["strength"]
                }

        # 5. 通用参数动态注入
        for param_key, param_value in kwargs.items():
            if param_key in self.PARAM_MAP:
                node_id, json_field = self.PARAM_MAP[param_key]
                if node_id in workflow:
                    workflow[node_id]["inputs"][json_field] = param_value
                    print(f"[*] Parameter updated: {param_key} -> {param_value}")

        # 6. 发送任务并监听进度 (带 OOM 防御雷达)
        ws = websocket.WebSocket()
        ws.connect(f"ws://{self.server_address}/ws?clientId={self.client_id}")

        prompt_id = self._queue_prompt(workflow)['prompt_id']
        print(f"[*] Task submitted. Generating (Prompt ID: {prompt_id})...")

        gr.Info(f"🚀 Task submitted! \nGo get some coffee.☕")

        try:
            try:
                while True:
                    out = ws.recv()
                    if isinstance(out, str):
                        message = json.loads(out)

                        if message['type'] == 'executing':
                            data = message['data']
                            if data['node'] is None and data['prompt_id'] == prompt_id:
                                print("[*] 图像生成完毕！")
                                break

                        elif message['type'] == 'execution_error':
                            error_data = message['data']
                            error_msg = error_data.get('exception_message', 'Unknown Error')
                            node_id = error_data.get('node_id', 'Unknown Node')

                            if 'out of memory' in error_msg.lower() or 'allocate' in error_msg.lower() or 'oom' in error_msg.lower():
                                raise Exception(f"💥 Out Of Memory! Failed to allocate VRAM to Node [{node_id}].")
                            elif message['type'] == 'execution_interrupted':
                                raise Exception("🛑 Interrupted!")
                            elif "shapes cannot be multiplied" in error_msg.lower():
                                raise Exception(
                                    f"❌ Error on Node [{node_id}]：Failed to load model! Ensure you are using the model based on Flux2-Klein-9B, with correct quantization.")
                            else:
                                raise Exception(
                                    f"❌ An unexpected error happened on Node [{node_id}]: {error_msg}. Please feedback to the developer.")

            except websocket.WebSocketConnectionClosedException:
                raise Exception("💀 Disconnected with ComfyUI backend!")

            # 7. 从历史记录提取生成的图片 (SaveImage 是节点 5)
            history = self._get_history(prompt_id)[prompt_id]

            output_images = []
            target_node_id = "5"

            if target_node_id in history['outputs']:
                node_output = history['outputs'][target_node_id]
                if 'images' in node_output:
                    for image in node_output['images']:
                        image_data = self._get_image(image['filename'], image['subfolder'], image['type'])
                        img = Image.open(io.BytesIO(image_data))
                        output_images.append(img)

            return output_images[0] if output_images else None

        finally:
            ws.close()
            self.free_vram()

    def free_vram(self):
        """【核弹级洗地 v2.0】：修复了 Header 丢失导致的静默失效问题"""
        print("\n[♻️ VRAM Manage] Clear caches request sent..")
        try:
            # 必须使用 requests.post 的 json 参数，它会自动带上正确的 Headers！
            response = requests.post(
                f"http://{self.server_address}/free",
                json={"unload_models": True, "free_memory": True},
                timeout=5
            )

            if response.status_code == 200:
                print("[♻️ VRAM Manage] Caches cleared!\n")
            else:
                print(f"[!] Failed to clear caches with HTTP code: {response.status_code}")

        except Exception as e:
            print(f"[!] Network error when sending request: {e}")