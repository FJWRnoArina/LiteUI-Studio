[English](README.md) | **简体中文**

> [!NOTE]
> ✨ **声明**：本文档由**Gemini 3.1 Pro Preview**生成。本项目的实际效果取决于用户硬件配置。

# 🚀 LiteUI Studio

**下载链接（74.98 GB）：https://pan.baidu.com/s/1lJ3WSWmI-Zbt7jaSvYEyLA?pwd=gxyt**

LiteUI Studio 是一个开箱即用、完全独立的本地 AI 视听创作工作站。它以极其硬核的底层显存调度机制，将庞杂的节点式连线（ComfyUI）封装成了对人类直觉最友好的现代化交互界面。无需折腾复杂的代码环境，只需双击运行，即可在本地流畅驱动目前全球最前沿的图像与视频生成模型。

<img src="https://github.com/FJWRnoArina/LiteUI-Studio/blob/main/preview.png?raw=true" width="800">

---

## ✨ 核心亮点 (Features)

- 🎮 **真正的开箱即用**：内置经过极致调优的便携版 Python 环境（感谢[秋葉aaaki](https://space.bilibili.com/12566101/dynamic)大佬），**无需配置 Conda、无需敲击 `pip` 命令**，解压后双击 `.bat` 即可启动。
- 🎬 **大满贯旗舰引擎**：
  - **Flux2**：支持文生图、图生图，搭配 LoRA 实现电影级画质。
  - **Wan 2.2**：图生视频引擎，支持轻量无声模式与内置 MMAudio 环境音轨合成模式。
  - **LTX-2.3**：原生声像画同轨引擎，支持“导演时间轴”提示词（如 `0-1秒: 摘帽子, 1-8秒: 说话`），实现精准对口型。
- 🔄 **无缝流转工作流**：在“图像页”抽出的完美盲盒，点击“一键发送”，瞬间无缝流转至“视频页”作为初始帧，无需反复保存上传。
- 🔍 **Metadata读取器 (Metadata Inspector)**：支持“即抛即得”。将生成的原图或视频拖入提取器，瞬间还原当时的提示词、种子和参数配方。

---

## 💻 硬件要求 (Requirements)

- **硬盘空间**：88 GB（包含约75 GB的预装模型文件）
- **操作系统**: Windows 10 / 11
- **显卡**: **NVIDIA** GPU，显存 $\ge$ 8GB（强推 RTX 4060 / 3060 等消费级甜品卡）。6G显存请在合理调整生成参数后使用。
- **内存**: 推荐16~32GB（因为大模型置换需要占用系统内存，建议开启至少 20GB 的 Windows 虚拟内存）。若显存较低，请在合理调整生成参数后使用。

---

## 🛠️ 安装与使用 (Getting Started)

由于项目包含了完整的运行库但未包含动辄几十 GB 的模型权重，请在新电脑上按以下步骤进行初始化：

### 1. 准备 FFmpeg（核心组件）
本项目依赖 FFmpeg 进行极速的无损音视频混流与元数据注入。
- 请下载 Windows 版的 `ffmpeg.exe` 和 `ffprobe.exe`，并将它们**直接放在本项目的根目录下**（与 `start.bat` 同级）。

### 2. 一键启动
- 双击根目录下的 **`start.bat`**。
- 喝口水，等待终端显示“引擎启动成功”，现代化的控制台网页将自动在浏览器中弹出，尽情创作吧！

### 3. 添加更多模型和LoRA
- **注意**：**本模型仅支持GGUF量化模型。**添加的模型必须与预设模型的架构一致。如文生图模型只能是基于FLUX.2-klein-9B的其他微调版本（4B模型将会失效）。
- 1. **[Hugging Face](https://huggingface.co/)**
   * 全球最大的 AI 开源社区与学术界基石。
   * **推荐下载**：Flux2, Wan2.2, LTX-2.3 的量化模型和其他微调版本。
- 2. **[Civitai](https://civitai.com/)**
   * 全球最活跃的生成式 AI 创作者社区。
   * **推荐下载**：各类特定画风、特定人物或材质的 LoRA 模型。
   * *注：作为一个极度自由的创作者 UGC 社区，该平台包含海量由网民上传的生成内容。请在浏览和下载时自行甄别，并严格遵守本项目的免责声明与当地法律法规。*

---

## 💡 使用小贴士 (Tips)

- **硬件报警拦截**：如果你参数设置过高导致底层 OOM，网页右上角会立刻弹出清晰的中文红色报错，同时底层会自动清空显存，你无需重启软件即可重新调整参数生成。
- **强制急刹车**：生成途中如果发现提示词写错了，直接点击界面上的 `[🛑 打断]` 按钮，任务会瞬间终止并退回所有占用的显存。

---

### 🙋 常见问题（Q&A）

**Q: LiteUI-Studio是付费项目吗？**
> A: LiteUI-Studio完全开源免费且没有付费内容，GitHub发布地址为[FJWRnoArina/LiteUI-Studio](https://github.com/FJWRnoArina/LiteUI-Studio/) 。

**Q: LiteUI-Studio与主流的SD-webui和ComfyUI有什么区别？**
> A: SD-webui和ComfyUI对于入门用户都存在一定门槛。例如使用SD-webui需要用户手动设置底层模型、CLIP、VAE、负向提示词、引导强度、采样器、步数、CFG Scale、Upscaler、Denoising Strength、高清修复、VAE Tile等参数，且其显存管理不如ComfyUI。但ComfyUI的入门门槛更高，需要熟知节点作用、模块化管理和节点连接逻辑等。LiteUI-Studio通过以ComfyUI API为底层架构，结合其优秀的显存管理，通过webui包装复杂的文生图、图生图和视频生成工作流，极大简化了用户的使用体验。

**Q: LiteUI-Studio是基于ComfyUI架构吗？**
> A: 是的。在/core/workflows中的文件都是可以直接在ComfyUI中打开的工作流。实际上，在LiteUI-Studio运行时，可以直接访问http://127.0.0.1:8188/ 以打开ComfyUI。

**Q: 为什么不自主设计模型加载架构？**
> A: 这是LiteUI-Studio最开始设计时的尝试。然而整合各个开源项目最大的痛点是兼容性问题。在实操代码时发现transformers库，xformer，模型pipeline lib，量化lib和各种库之间的兼容性奇差，比如工具lib（torch，numpy，甚至python本身）版本对不齐，或者数层空映射（如果自己修到毕业都修不好）。ComfyUI很好地解决了模型管线和量化之间的兼容性问题，这是选择ComfyUI作为底层架构的重要原因之一。

**Q: LiteUI-Studio支持生成任何内容吗？**
> A: 生成的内容取决于用户选择的模型以及输入的提示词。请用户在严格遵守本项目的免责声明与当地法律法规的前提下使用LiteUI-Studio。

**Q: LiteUI-Studio中有一些我看不懂的选项或参数。**
> A: 可以将想要查询的内容复制/截图到搜索引擎或AI（豆包、ChatGPT、Gemini等）进行查询，以获取详细的帮助。

**Q: LiteUI-Studio在运行时遇到了我看不懂/无法修复的报错。**
> A: 一些报错不会影响正常运行，可以忽略；如果影响了运行，可以先将报错内容复制/截图到搜索引擎或AI（豆包、ChatGPT、Gemini等）进行查询。也可以尝试重启LiteUI-Studio。如果仍无法解决，请在本项目发布网址或GitHub提出。

**Q: LiteUI-Studio无法加载我提供的模型。**
> A: LiteUI-Studio目前仅支持FLUX.2-klein-9B、Wan2.2-I2V-A14B和LTX-2.3这三个模型的GGUF量化版本（及其他微调模型）。这些模型是目前（直到2026年7月）能在本地运行且显存有限的情况下质量最好的模型。如需使用其他模型，请下载使用SD-webui或ComfyUI。

**Q: LiteUI-Studio无法加载我提供的LoRA。**
> A: 请确保提供的LoRA适配的模型为FLUX.2-klein-9B、Wan2.2-I2V-A14B或LTX-2.3。注意：生成图片的LoRA不能用于生成视频，反之亦然。

**Q: 我不知道怎么写提示词。**
> A: 主流AI模型（豆包、ChatGPT、Gemini等）可以代写提示词，随后复制使用即可。

**Q: 我想追溯一个质量很好的图片/视频的生成参数。**
> A: 将其上传至Metadata读取器即可。

**Q: LiteUI-Studio生成结果的质量不如预期。**
> A: 为适配低显存，LiteUI-Studio预装的模型为经过精简的量化版本，这会一定程度上影响生成质量。可以尝试多次生成、修改提示词或提高采样步数。

**Q: 同样是视频生成，Wan2.2和LTX2.3有什么区别？**
> A: Wan2.2目前不支持自带配音和对口型，在LiteUI-Studio中额外装配了MMAudio配音模块（但不支持人声台词）。LTX2.3支持配音和台词（并自动对口型）。
  
---

**🤖 AI 辅助声明 (AI Usage Declaration):**

本项目的系统架构设计、核心逻辑代码的编写与 Debug、前端 UI 交互设计，以及**您正在阅读的这篇 README 文档**，均是在大语言模型（LLM）的深度参与和结对编程（Pair Programming）下辅助完成的。

---

特别感谢开源社区：
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) 提供的强大节点式推理后端。
- [Gradio](https://gradio.app/) 提供的优雅前端框架。
- [秋葉aaaki](https://space.bilibili.com/12566101) 大佬提供的极致优化的便携版 Windows 运行环境。

模型地址：
- [unsloth/FLUX.2-klein-9B-gguf](https://huggingface.co/unsloth/FLUX.2-klein-9B-GGUF)
- [QuantStack/Wan2.2-I2V-A14B-GGUF](https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF)
- [unsloth/LTX-2.3-GGUF](https://huggingface.co/unsloth/LTX-2.3-GGUF/tree/main)

 ---

## ⚖️ 免责声明 (Disclaimer)

1. **学术与交流目的**：本项目（LiteUI Studio）及其相关的代码、启动脚本、包装架构，仅供个人学习、学术研究与技术交流使用，**严禁用于任何商业用途**。
2. **生成内容责任**：本项目仅提供底层的工程调度架构，**本身不包含任何模型权重**。用户利用本项目及自行下载的开源 AI 模型（如 Flux、Wan、LTX 等）所生成的任何图像、视频、音频内容，其版权、法律责任及道德风险均由**使用者本人**承担。
3. **合法合规使用**：强烈呼吁用户在当地法律法规允许的范围内使用本软件。**严禁**使用本项目生成或传播涉及色情、暴力、散布虚假信息、侵犯他人肖像权/名誉权/著作权（如 Deepfake 恶意伪造）等违法违规内容。
4. **第三方协议约束**：使用本项目拉起的第三方模型及代码库，请务必严格遵守其原作者发布的开源协议。
5. **硬件风险**：AI 模型的推理会对 GPU 产生极高的满载压力。虽然本项目已尽力优化显存调度，但对于任何因长时间极限满载运行导致的硬件过热、损毁或数据丢失，开发者不承担任何直接或间接责任。
