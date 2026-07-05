import json
import urllib.request
import urllib.parse
import uuid
import websocket
import requests
import os
import subprocess
import shutil


class VideoInterpClient:
    def __init__(self, server_address="127.0.0.1:8188"):
        self.server_address = server_address
        self.client_id = str(uuid.uuid4())

        # 针对插帧工作流的参数路由表
        self.PARAM_MAP = {
            "video_path": ("3", "video"),
            "multiplier": ("5", "value"),
        }

    def free_vram(self):
        """【核弹级洗地】"""
        print("\n[♻️ VRAM Manage] Clearing all caches...")
        try:
            response = requests.post(
                f"http://{self.server_address}/free",
                json={"unload_models": True, "free_memory": True},
                timeout=5
            )
            if response.status_code == 200:
                print("[♻️ VRAM Manage] Clear caches request sent...\n")
        except Exception as e:
            print(f"[!] Network error when sending request: {e}")

    def _extract_raw_metadata(self, file_path):
        try:
            cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', file_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            probe = json.loads(result.stdout)
            tags = probe.get('format', {}).get('tags', {})
            # 兼容我们之前写入的 comment 或 prompt 标签
            return tags.get('comment') or tags.get('prompt') or tags.get('title')
        except Exception as e:
            print(f"[!] Failed to extract metadata: {e}")
            return None

    def _inject_metadata(self, video_path, metadata_str):
        if not metadata_str:
            return
        print("[*] Merging metadata to HighFPS video...")
        try:
            temp_file = video_path + ".temp.mp4"
            cmd = [
                'ffmpeg', '-y', '-i', video_path,
                '-c', 'copy',
                '-metadata', f'comment={metadata_str}',
                temp_file
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            shutil.move(temp_file, video_path)
            print("[*] ✅ Metadata merged！")
        except Exception as e:
            print(f"[!] Failed to merge metadata: {e}")

    def _queue_prompt(self, prompt_workflow):
        p = {"prompt": prompt_workflow, "client_id": self.client_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request(f"http://{self.server_address}/prompt", data=data)
        return json.loads(urllib.request.urlopen(req).read())

    def generate_interpolation(self, template_path, input_video_path, multiplier=4, **kwargs):
        """独立的视频插帧(VFI)核心引擎"""

        # 1. 解析绝对路径：VHS_LoadVideoPath 支持直接读取本地硬盘任意位置的文件
        abs_video_path = os.path.normpath(os.path.abspath(input_video_path))
        print(f"[*] Ready to load video: {abs_video_path}")

        raw_metadata_str = self._extract_raw_metadata(abs_video_path)

        # 2. 加载工作流 JSON
        with open(template_path, "r", encoding="utf-8") as f:
            workflow = json.load(f)

        # 3. 参数注入
        if "3" in workflow:
            workflow["3"]["inputs"]["video"] = abs_video_path
        if "5" in workflow:
            workflow["5"]["inputs"]["value"] = int(multiplier)  # 强制转为整数

        # 4. 发送任务并监听 (带有三层异常防爆雷达)
        ws = websocket.WebSocket()
        ws.connect(f"ws://{self.server_address}/ws?clientId={self.client_id}")

        prompt_id = self._queue_prompt(workflow)['prompt_id']
        print(f"\n🚀 Interpolation started (ID: {prompt_id})")
        print(f"[*] Using RIFE to upscale FPS by ×{multiplier}，Please wait...")

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
                        node_id = error_data.get('node_id', 'Unknown node')
                        if 'out of memory' in error_msg.lower() or 'allocate' in error_msg.lower() or 'oom' in error_msg.lower():
                            raise Exception(
                                f"💥 Out Of Memory! Failed to allocate VRAM to Node [{node_id}]. Please lower the resolution or upscale factor.")
                        else:
                            raise Exception(f"❌ An unexpected error happened on Node [{node_id}]: {error_msg}")

                    elif message['type'] == 'execution_interrupted':
                        raise Exception("🛑 Interrupted！")

            # 5. 解析并定位原生物理保存路径 (节点 6: VHS_VideoCombine)
            req = urllib.request.Request(f"http://{self.server_address}/history/{prompt_id}")
            history = json.loads(urllib.request.urlopen(req).read())[prompt_id]
            target_node_id = "6"
            final_file = None

            if target_node_id in history['outputs']:
                node_output = history['outputs'][target_node_id]
                for key, data_list in node_output.items():
                    if isinstance(data_list, list) and len(data_list) > 0:
                        for item in data_list:
                            if isinstance(item, dict) and 'filename' in item:
                                final_file = item
                                break
                    if final_file: break

            if not final_file:
                raise Exception("Interpolation failed. Can't get generated video.")

            project_root = os.path.dirname(os.path.dirname(__file__))
            base_folder = "output" if final_file.get('type', 'output') == "output" else "temp"
            subfolder = final_file.get('subfolder', '')

            if subfolder:
                final_physical_path = os.path.join(project_root, "backend_comfyui", base_folder, subfolder,
                                                   final_file['filename'])
            else:
                final_physical_path = os.path.join(project_root, "backend_comfyui", base_folder, final_file['filename'])

            final_physical_path = os.path.normpath(final_physical_path)
            self._inject_metadata(final_physical_path, raw_metadata_str)
            print(f"\n🎉 HighFPS video saved to: {final_physical_path}")

            return final_physical_path

        except websocket.WebSocketConnectionClosedException:
            raise Exception("💀 Disconnected with ComfyUI backend!")
        finally:
            ws.close()
            self.free_vram()
