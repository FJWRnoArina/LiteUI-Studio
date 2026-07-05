import subprocess
import time
import socket
import sys
import os



os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True,garbage_collection_threshold:0.8"
PYTHON_ENV = r"python\python.exe"


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def main():
    print("🚀 Initializing LiteUI Studio...")

    # 防呆设计：检查路径是否正确
    if not os.path.exists(PYTHON_ENV):
        print(f"❌ Cannot find Python interpreter! Please check the directory: {PYTHON_ENV}")
        sys.exit(1)


    comfy_dir = os.path.join(os.path.dirname(__file__), "backend_comfyui")
    comfy_main = os.path.join(comfy_dir, "main.py")

    comfy_process = subprocess.Popen(
        [
            PYTHON_ENV, comfy_main,
            "--fast",
            "--port", "8188",
            "--fp8_e4m3fn-text-enc"
        ],
        cwd=comfy_dir,
        stderr=subprocess.STDOUT
    )


    print("⏳ Waiting for AI engine starting ...")
    timeout = 3600
    start_time = time.time()
    while not is_port_in_use(8188):
        time.sleep(1)
        if time.time() - start_time > timeout:
            comfy_process.terminate()
            print("❌ Timed out! Please check if 'backend_comfyui' is set up correctly!")
            sys.exit(1)

    print("✅ AI engine started successfully!")

    # 3. 启动前端 WebUI
    print("🎨 Opening Gradio interface...")
    webui_process = subprocess.Popen(
        [PYTHON_ENV, "webui.py"],
        cwd=os.path.dirname(__file__)
    )

    try:
        # 保持主线程运行
        webui_process.wait()
    except KeyboardInterrupt:
        print("\n🛑 Closing... Clearing all caches ...")
    finally:
        # 4. 关闭时自动杀后台
        webui_process.terminate()
        comfy_process.terminate()
        print("👋 Goodbye!")


if __name__ == "__main__":
    main()