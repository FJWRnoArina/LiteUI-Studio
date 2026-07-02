[English](README.md) | **简体中文**

> [!NOTE]
> ✨ **声明**：本文档由**Gemini 3.1 Pro Preview**生成。本项目的实际效果取决于用户硬件配置。

# 🚀 LiteUI Studio

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

## 常见问题 (FAQ)

<details>
<summary><b>1. LiteUI-Studio 是付费项目吗？</b></summary>
<br>
LiteUI-Studio 完全开源免费且没有付费内容，GitHub 发布地址为：<a href="https://github.com/FJWRnoArina/LiteUI-Studio/">FJWRnoArina/LiteUI-Studio</a>。
</details>

<details>
<summary><b>2. 与主流的 SD-webui 和 ComfyUI 有什么区别？</b></summary>
<br>
<b>SD-webui</b> 和 <b>ComfyUI</b> 对于入门用户都存在一定门槛：SD-webui 需要手动设置繁杂的底层参数（CLIP、VAE、步数、重绘幅度等）且显存管理一般；ComfyUI 门槛更高，需要熟知节点逻辑。
<br><br>
<b>LiteUI-Studio</b> 以 ComfyUI API 为底层架构，结合其优秀的显存管理，通过 webui 包装复杂的文生图、图生图和视频生成工作流，极大简化了用户的使用体验。
</details>

<details>
<summary><b>3. LiteUI-Studio 是基于 ComfyUI 架构吗？为什么不自主设计？</b></summary>
<br>
<b>是的。</b> <code>/core/workflows</code> 中的文件均可直接在 ComfyUI 中打开。运行时也可直接访问 <code>http://127.0.0.1:8188/</code>。<br><br>
<b>不自主设计的原因：</b> 整合开源项目最大的痛点是兼容性。<code>transformers</code>、<code>xformer</code>、模型库和量化库之间的版本极难对齐。ComfyUI 完美解决了模型管线与量化之间的兼容性问题，因此成为我们的底层首选。
</details>

<details>
<summary><b>4. 支持生成任何内容吗？</b></summary>
<br>
生成内容取决于用户选择的模型及输入的提示词。请在<b>严格遵守本项目的免责声明与当地法律法规</b>的前提下使用。
</details>

<details>
<summary><b>5. 遇到看不懂的参数、报错，或者不知道怎么写提示词怎么办？</b></summary>
<br>
<ul>
  <li><b>参数/报错：</b> 先尝试重启软件。若不行，请将内容复制或截图给 AI（豆包、ChatGPT、Gemini）查询，或在 GitHub 提出 Issue。</li>
  <li><b>提示词：</b> 直接让主流 AI 模型帮您代写，随后复制使用即可。</li>
</ul>
</details>

<details>
<summary><b>6. 为什么无法加载我提供的模型或 LoRA？</b></summary>
<br>
目前（截至2026年7月），为兼顾低显存与高质量，LiteUI-Studio <b>仅支持</b>以下三个模型的 GGUF 量化版本及其微调模型：<code>FLUX.2-klein-9B</code>、<code>Wan2.2-I2V-A14B</code>、<code>LTX-2.3</code>。
<br><br>
请确保提供的 LoRA 也适配上述模型。注意：生图的 LoRA 不能用于生视频，反之亦然。如需使用其他模型，请使用原版 ComfyUI。
</details>

<details>
<summary><b>7. 生成质量不如预期如何解决？如何追溯生成参数？</b></summary>
<br>
<ul>
  <li><b>提升质量：</b> 因使用了量化精简版模型，质量可能受轻微影响。可尝试多次生成、修改提示词或提高采样步数。</li>
  <li><b>参数追溯：</b> 将满意的图片/视频上传至 Metadata 读取器即可查看所有生成参数。</li>
</ul>
</details>

<details>
<summary><b>8. 同样是视频生成，Wan2.2 和 LTX2.3 有什么区别？</b></summary>
<br>
<b>Wan2.2</b> 目前不支持自带配音和对口型（LiteUI-Studio 为其额外装配了 MMAudio 配音模块，但不支持人声台词）；<br>
<b>LTX-2.3</b> 原生支持配音和台词，并能自动对口型。
</details>
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
