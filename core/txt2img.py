import json
import urllib.request
import urllib.parse
import uuid
import websocket
import io
import gradio as gr
from PIL import Image
import requests


class t2iClient:
    def __init__(self, server_address="127.0.0.1:8188"):
        self.server_address = server_address
        self.client_id = str(uuid.uuid4())

        # 【神级工程思维：建立统一的“参数路由表”】
        # 字典格式："你想暴露给前端的参数名": ("JSON中的节点ID", "JSON中的字段名")
        # 以后想让用户改什么参数，只需要在这个表里加一行即可，下面的核心代码一行都不用改！
        self.PARAM_MAP = {
            "prompt": ("6", "text"),
            "seed": ("26", "noise_seed"),
            "steps": ("31", "steps"),
            "guidance": ("27", "guidance"),
            "width": ("28", "width"),
            "height": ("33", "value"),
            "batch_size": ("28", "batch_size"),
            "upscale_factor": ("40", "scale_by"),
            "base_model": ("25", "unet_name")
        }

    # ... (此处省略 _queue_prompt, _get_image, _get_history，和上一版完全一样) ...
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

    def generate_txt2img(self, template_path="txt2img.json", lora_list=None, **kwargs):
        """
        极其通用的生成引擎
        :param template_path: JSON 模板路径
        :param lora_list: 包含字典的列表，例如 [{"name": "xx.safetensors", "strength": 0.8}]
        :param kwargs: 任意数量的关键参数，只要在 PARAM_MAP 里定义过，就会自动覆盖！
        """
        with open(template_path, "r", encoding="utf-8") as f:
            workflow = json.load(f)

        # ---------------------------------------------------------
        # 需求 1：动态注入多 LoRA (针对 rgthree 节点的魔法)
        # ---------------------------------------------------------
        if lora_list is not None:
            # 找到 43 号 Power Lora Loader 节点
            node_43_inputs = workflow["43"]["inputs"]

            # 第一步：把模板里自带的 lora_1, lora_2 删掉（清空占位符，防止污染）
            keys_to_delete = [k for k in node_43_inputs.keys() if k.startswith("lora_")]
            for k in keys_to_delete:
                del node_43_inputs[k]

            # 第二步：根据用户传入的 lora_list，动态生成新的 lora 字典
            for i, lora in enumerate(lora_list, start=1):
                if lora["name"] != "None":
                    node_43_inputs[f"lora_{i}"] = {
                        "on": True,
                        "lora": lora["name"],
                        "strength": lora["strength"]
                    }
            print(f"[*] 成功注入 {len(lora_list)} 个 LoRA 模型。")

        # ---------------------------------------------------------
        # 需求 2：通用的参数修改逻辑
        # ---------------------------------------------------------
        for param_key, param_value in kwargs.items():
            if param_key in self.PARAM_MAP:
                node_id, json_field = self.PARAM_MAP[param_key]
                if node_id in workflow:
                    workflow[node_id]["inputs"][json_field] = param_value
                    print(f"[*] 参数已更新: {param_key} -> {param_value}")
            else:
                print(f"[警告] 参数 '{param_key}' 未在 PARAM_MAP 中注册，已被忽略。")

        # ---------------------------------------------------------
        # 发送任务并监听 (和上版一样)
        # ---------------------------------------------------------
        ws = websocket.WebSocket()
        ws.connect(f"ws://{self.server_address}/ws?clientId={self.client_id}")

        prompt_id = self._queue_prompt(workflow)['prompt_id']
        print(f"[*] 任务已提交，开始生成 (Prompt ID: {prompt_id})...")

        gr.Info(f"🚀 图片生成任务已提交后台！\n单张图片预估耗时30~60秒，去喝杯咖啡吧☕")

        try:
            try:
                while True:
                    out = ws.recv()
                    if isinstance(out, str):
                        message = json.loads(out)

                        # 1. 正常执行完毕
                        if message['type'] == 'executing':
                            data = message['data']
                            if data['node'] is None and data['prompt_id'] == prompt_id:
                                break

                        # 2. 嗅探到 ComfyUI 传来的错误信息
                        elif message['type'] == 'execution_error':
                            error_data = message['data']
                            error_msg = error_data.get('exception_message', 'Unknown Error')
                            node_id = error_data.get('node_id', '未知节点')

                            # 检查是否包含 OOM 的关键词
                            if 'out of memory' in error_msg.lower() or 'allocate' in error_msg.lower() or 'oom' in error_msg.lower():
                                raise Exception(f"💥 显存爆炸 (OOM)! 节点 [{node_id}] 请求分配显存失败。")
                            elif message['type'] == 'execution_interrupted':
                                raise Exception("🛑 任务已被用户手动打断！")
                            elif "shapes cannot be multiplied" in error_msg.lower():
                                raise Exception(
                                    f"❌ 在节点 [{node_id}] 发生错误：模型加载失败！请确认按照提示加载了正确架构的模型。")
                            else:
                                raise Exception(f"❌ 节点 [{node_id}] 发生未知的内部错误，请向开发者反馈: {error_msg}")

                # 3. 嗅探到服务端突然死亡 (进程崩溃)
            except websocket.WebSocketConnectionClosedException:
                raise Exception("💀 与 ComfyUI 的连接意外断开！可能是底层崩溃。")

            history = self._get_history(prompt_id)[prompt_id]

            output_images = []
            for node_id in history['outputs']:
                node_output = history['outputs'][node_id]
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
        print("\n[♻️ VRAM 管家] 任务结束，正在向引擎发送强制冲洗指令...")
        try:
            # 必须使用 requests.post 的 json 参数，它会自动带上正确的 Headers！
            response = requests.post(
                f"http://{self.server_address}/free",
                json={"unload_models": True, "free_memory": True},
                timeout=5
            )

            if response.status_code == 200:
                print("[♻️ VRAM 管家] 显存洗地请求已成功送达引擎！\n")
            else:
                print(f"[!] 显存洗地可能失败，服务器返回状态码: {response.status_code}")

        except Exception as e:
            print(f"[!] 显存洗地请求网络出错: {e}")


# ==========================================
# 优雅的调用方式测试
# ==========================================
if __name__ == "__main__":
    comfy = t2iClient()

    # 构建用户想用的 LoRA 列表 (你可以在这里加任意多个，不想用就传 [])
    my_loras = [
        # {"name": "lenovo_flux_klein9b.safetensors", "strength": 1.0},
        # {"name": "klein_snofs_v1_4.safetensors", "strength": 0.6}  # 第二个画风稍微弱一点
    ]

    # 调用变得极其简洁！你只需把想要覆盖的参数作为 key=value 传进去
    result_img = comfy.generate_txt2img(
        template_path="workflows/txt2img.json",
        lora_list=my_loras,

        # 以下参数因为在 PARAM_MAP 注册过，会自动被替换！
        prompt="a cyberpunk cat reading a physics book, neon lights, 4k",
        upscale_factor=2,
        seed=88888888,
        width=1008,
        height=1008,
        batch_size=1,
        steps=5
    )

    if result_img:
        result_img[0].show()
        for img in result_img:
            img.save("output/flux2_img.png")