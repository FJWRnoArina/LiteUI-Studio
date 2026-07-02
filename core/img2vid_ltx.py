import json
import urllib.request
import urllib.parse
import uuid
import websocket
import requests
import os
import subprocess
import shutil


class LTXVideoClient:
    def __init__(self, server_address="127.0.0.1:8188"):
        self.server_address = server_address
        self.client_id = str(uuid.uuid4())

        # 针对 LTX-2.3 (带原生配音与时间轴) 的参数路由表
        self.PARAM_MAP = {
            "base_model": ("1", "unet_name"),
            "width": ("11", "value"),
            "height": ("12", "value"),
            "prompt": ("15", "text"),
            "duration": ("18", "value"),
            "fps": ("20", "value"),
            "seed": ("61", "noise_seed"),
            "t2v_mode": ("50", "value"),
            "folder": ("48","filename_prefix")
        }

    def free_vram(self):
        """【核弹级洗地】"""
        print("\n[♻️ VRAM 管家] 任务结束，正在向引擎发送强制冲洗指令...")
        try:
            response = requests.post(
                f"http://{self.server_address}/free",
                json={"unload_models": True, "free_memory": True},
                timeout=5
            )
            if response.status_code == 200:
                print("[♻️ VRAM 管家] 显存洗地请求已成功送达引擎！\n")
        except Exception as e:
            print(f"[!] 显存洗地请求网络出错: {e}")

    def upload_image(self, image_path):
        """上传首帧参考图"""
        print(f"[*] 正在上传首帧参考图片: {image_path}")
        with open(image_path, "rb") as f:
            res = requests.post(f"http://{self.server_address}/upload/image", files={"image": f})
        if res.status_code == 200:
            return res.json()['name']
        raise Exception(f"图片上传失败: {res.text}")

    def generate_ltx_video(self, template_path, image_path, lora_list=None, **kwargs):
        """LTX-2.3 旗舰级多模态生成管线"""

        # 1. 上传初始图
        uploaded_filename = self.upload_image(image_path)

        # 2. 加载工作流 JSON
        with open(template_path, "r", encoding="utf-8") as f:
            workflow = json.load(f)

        # 3. 注入图像节点 (节点 9)
        workflow["9"]["inputs"]["image"] = uploaded_filename

        # 4. 动态注入 LoRA (节点 21: rgthree)
        if lora_list is not None:
            node_21_inputs = workflow["21"]["inputs"]
            keys_to_delete = [k for k in node_21_inputs.keys() if k.startswith("lora_")]
            for k in keys_to_delete:
                del node_21_inputs[k]

            for i, lora in enumerate(lora_list, start=1):
                node_21_inputs[f"lora_{i}"] = {
                    "on": True,
                    "lora": lora["name"],
                    "strength": lora["strength"]
                }

        # 5. 智能参数注入与双重 Seed 分配
        # LTX 包含基础渲染(61)和潜空间放大(69)两个采样器。如果前端只传了一个 seed，我们自动错开分配。
        if "seed" in kwargs:
            kwargs["seed_1"] = kwargs["seed"]
            kwargs["seed_2"] = kwargs["seed"] + 1024

        for param_key, param_value in kwargs.items():
            if param_key in self.PARAM_MAP:
                node_id, json_field = self.PARAM_MAP[param_key]
                if node_id in workflow:
                    workflow[node_id]["inputs"][json_field] = param_value
                    print(f"[*] 参数更新: {param_key} -> {param_value}")

        # 6. 发送任务并监听 (带 OOM 拦截)
        ws = websocket.WebSocket()
        ws.connect(f"ws://{self.server_address}/ws?clientId={self.client_id}")

        prompt_id = json.loads(urllib.request.urlopen(urllib.request.Request(
            f"http://{self.server_address}/prompt",
            data=json.dumps({"prompt": workflow, "client_id": self.client_id}).encode('utf-8')
        )).read())['prompt_id']

        print(f"\n🚀 LTX-2.3 原生多模态任务已提交 (ID: {prompt_id})")
        print(f"[*] 该管线支持原生对口型与时间轴，请在终端关注 12B/22B 极限解码进度...")

        try:
            while True:
                out = ws.recv()
                if isinstance(out, str):
                    message = json.loads(out)
                    if message['type'] == 'executing':
                        data = message['data']
                        if data['node'] is None and data['prompt_id'] == prompt_id:
                            break
                    elif message['type'] == 'execution_error':
                        error_data = message['data']
                        error_msg = error_data.get('exception_message', 'Unknown Error')
                        node_id = error_data.get('node_id', '未知节点')
                        if 'out of memory' in error_msg.lower() or 'allocate' in error_msg.lower() or 'oom' in error_msg.lower():
                            raise Exception(f"💥 显存爆炸 (OOM)! 节点 [{node_id}] 请求分配显存失败。")
                        elif message['type'] == 'execution_interrupted':
                            raise Exception("🛑 任务已被用户手动打断！")
                        elif "shapes cannot be multiplied" in error_msg.lower():
                            raise Exception(
                                f"❌ 在节点 [{node_id}] 发生错误：模型加载失败！请确认按照提示加载了正确架构的模型。")
                        else:
                            raise Exception(f"❌ 节点 [{node_id}] 发生未知的内部错误，请向开发者反馈: {error_msg}")

            # 7. 解析零拷贝物理路径 (节点 48: VHS_VideoCombine)
            history = json.loads(urllib.request.urlopen(
                urllib.request.Request(f"http://{self.server_address}/history/{prompt_id}")).read())[prompt_id]
            target_node_id = "48"

            if target_node_id not in history['outputs']:
                raise Exception("未找到目标视频输出！")

            final_file = None
            node_output = history['outputs'][target_node_id]
            for key, data_list in node_output.items():
                if isinstance(data_list, list) and len(data_list) > 0:
                    for item in data_list:
                        if isinstance(item, dict) and 'filename' in item:
                            final_file = item
                            break
                if final_file: break

            if not final_file:
                raise Exception("视频生成失败，未能提取文件名。")

            project_root = os.path.dirname(os.path.dirname(__file__))
            base_folder = "output" if final_file.get('type', 'output') == "output" else "temp"
            subfolder = final_file.get('subfolder', '')

            if subfolder:
                final_physical_path = os.path.join(project_root, "backend_comfyui", base_folder, subfolder,
                                                   final_file['filename'])
            else:
                final_physical_path = os.path.join(project_root, "backend_comfyui", base_folder, final_file['filename'])

            final_physical_path = os.path.normpath(final_physical_path)
            print(f"\n🎉 LTX 视频已生成于: {final_physical_path}")

        except websocket.WebSocketConnectionClosedException:
            raise Exception("💀 与 ComfyUI 的连接意外断开！可能是底层崩溃。")
        finally:
            ws.close()
            self.free_vram()

        # 8. 原位注入 Metadata
        try:
            print("[*] 正在向带有原生配音的 LTX MP4 注入 Metadata...")
            temp_mp4 = final_physical_path + ".temp.mp4"
            cmd = ['ffmpeg', '-y', '-i', final_physical_path, '-c', 'copy', '-metadata',
                   f'comment={json.dumps(workflow)}', temp_mp4]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            shutil.move(temp_mp4, final_physical_path)
            print("[*] ✅ LTX Metadata 原位注入成功！")
        except Exception as e:
            print(f"[!] Metadata 注入失败: {e}")

        return final_physical_path