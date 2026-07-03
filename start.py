import subprocess
import time
import socket
import sys
import os


# 【核心修改】：强行指定 AKI 整合包的 Python 解释器路径
# 秋叶包的 Python 解释器通常存放在 python 文件夹下的 python.exe
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True,garbage_collection_threshold:0.8"
PYTHON_ENV = r"python\python.exe"


def is_port_in_use(port):
    """检查 ComfyUI 的 8188 端口是否已经准备就绪"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def main():
    print("🚀 正在启动 LiteUI Studio...")

    # 防呆设计：检查路径是否正确
    if not os.path.exists(PYTHON_ENV):
        print(f"❌ 找不到 Python 解释器！请检查路径是否正确: {PYTHON_ENV}")
        sys.exit(1)

    # 1. 后台静默启动内嵌的 ComfyUI
    comfy_dir = os.path.join(os.path.dirname(__file__), "backend_comfyui")
    comfy_main = os.path.join(comfy_dir, "main.py")

    comfy_process = subprocess.Popen(
        [
            PYTHON_ENV, comfy_main,
            "--fast",
            "--port", "8188",
            "--fp8_e4m3fn-text-enc"  # 核心加速指令：强制 T5 文本编码器使用 8 位精度，拯救 8G 显卡！
        ],
        cwd=comfy_dir,
        stderr=subprocess.STDOUT
    )

    # 2. 轮询等待 8188 端口亮起
    print("⏳ 等待 AI 引擎热机 ...")
    timeout = 3600
    start_time = time.time()
    while not is_port_in_use(8188):
        time.sleep(1)
        if time.time() - start_time > timeout:
            comfy_process.terminate()
            print("❌ 引擎启动超时，请检查 backend_comfyui 是否配置正确。")
            sys.exit(1)

    print("✅ 底层 AI 引擎启动成功！")

    # 3. 启动前端 WebUI
    print("🎨 正在拉起 Gradio 交互界面...")
    webui_process = subprocess.Popen(
        [PYTHON_ENV, "webui.py"],
        cwd=os.path.dirname(__file__)
    )

    try:
        # 保持主线程运行
        webui_process.wait()
    except KeyboardInterrupt:
        print("\n🛑 收到关闭指令，正在清理后台进程...")
    finally:
        # 4. 关闭时自动杀后台
        webui_process.terminate()
        comfy_process.terminate()
        print("👋 退出成功，所有系统资源已释放。")


if __name__ == "__main__":
    main()