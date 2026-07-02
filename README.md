***

# 🚀 LiteUI Studio

**Bring Heavy AI Video Models to 8GB Consumer GPUs.**  
让 8GB 显存的平民电脑，也能极其流畅地跑通百亿参数的前沿 AI 视频大模型。

LiteUI Studio 是一个极其轻量、开箱即用的本地 AI 创作工作站。它通过将底层的 ComfyUI 降级为无头引擎（Headless Backend），结合独立的高级显存调度策略，成功在 **8GB VRAM** 的消费级显卡上稳定部署了包括 **Wan2.2 (14B)** 和 **LTX-2.3 (34B)** 在内的顶级音视频多模态模型。

![UI Preview](https://github.com/FJWRnoArina/LiteUI-Studio/blob/main/preview.png = 768x512)

## ✨ 核心特性 (Features)

*   **⚡ 极限显存压榨 (8GB VRAM Friendly)**：内置微服务级的管线切片与“核弹级”显存洗地机制，彻底解决显存碎片化。连续生成 100 次，速度依然如初。
*   **📦 真正的解压即用 (Portable)**：内置深度优化过的 Python 运行环境与预编译 C++ 算子。**免装 Python、免装 Conda、免敲命令**，双击一键启动。
*   **🎬 旗舰级音视频管线 (All-in-One Studio)**：
    *   **Flux2**: 文生图 / 图生图 / 一键推送到视频。
    *   **Wan2.2**: 图生视频 / 动态配音混流 (MMAudio)。
    *   **LTX-2.3**: 导演级时间轴控制 / 声像画同轨原生生成。
*   **🛠️ 极客级交互体验 (UX)**：毫秒级 Metadata 原位注入、跨标签页无缝传图、一键定位本地输出文件、魔法参数放大镜。

---

## 💻 硬件要求 (Requirements)

*   **操作系统**: Windows 10 / 11 (64-bit)
*   **显卡**: NVIDIA GPU，**最少 8GB 显存** (建议更新至最新版显卡驱动)
*   **内存**: 建议 32GB RAM，并开启至少 20GB 的 Windows 虚拟内存。

---

## 🚀 快速开始 (Quick Start)

### 1. 准备环境工具
为实现零配置运行，请下载 [FFmpeg (Windows 版)](https://ffmpeg.org/download.html)，将其中的 `ffmpeg.exe` 和 `ffprobe.exe` 直接解压放入本项目的**根目录**中。

### 2. 下载并放置模型权重
由于模型文件巨大（合计约 40GB+），请自行前往 HuggingFace 下载对应格式（GGUF/Safetensors）的模型，并放置到 `backend_comfyui/models/` 的对应文件夹中：

```text
backend_comfyui/models/
 ├── unet/       # 放置大底模: Wan2.2-14B (GGUF), LTX-2.3-22B (GGUF), Flux2 (GGUF)
 ├── clip/       # 放置文本编码器: UMT5 (Wan用), Gemma-3-12B (LTX用)
 ├── vae/        # 放置解码器: Wan2.1_VAE, LTX Audio/Video VAE
 ├── loras/      # 放置你的风格化微调模型 (.safetensors)
 └── mmaudio/    # 放置 MMAudio 环境音效模型
```
*(注：如果不知道下载哪个，界面上拉开“底层模型高级设置”有默认的文件名提示。)*

### 3. 一键启动
双击项目根目录下的启动脚本：
*   ▶️ **`start.bat`** (或者 `run_litevideo.bat`)
*   终端会静默启动 AI 引擎，并在 5 秒后自动在浏览器中弹出控制台！开始你的创作吧！

---

## 🔬 致开发者 / 研究者 (For Developers & Recruiters)

本项目不仅仅是一个套壳 UI，其底层重构了多项 AI 基础设施（AI Infra）逻辑，欢迎查阅源码：

1. **前后端解耦架构 (Decoupled Architecture)**
   将 ComfyUI 作为常驻守护进程（Daemon），通过 WebSocket 进行事件通信与错误雷达嗅探，实现毫秒级打断与异常（如 OOM）精准捕获。
2. **零拷贝物理路由 (Zero-Copy I/O)**
   抛弃了传统的 HTTP 二进制流下载。前端通过 `os.path` 直接映射后端物理输出路径，配合 FFmpeg `-c copy` 实现 0.1秒内的 Metadata 原位重写与混流。
3. **管线切片与状态机 (Pipeline Slicing)**
   针对 Wan2.2 模型，使用 Python 将巨大的 DAG 计算图切分为 `High Noise` -> `Low Noise` -> `Interp & Dubbing` 三个独立生命周期，期间强制触发 PyTorch 显存重组（`expandable_segments`），挑战了 8GB 显卡的物理极限。
