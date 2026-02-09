# Edit Banana（draw.io(editbanana)）当前流程梳理

## 1. 项目目标
将输入的静态图（主要是图片）转换为可编辑的 DrawIO XML（并可扩展到 PPTX 场景）。
核心方式是：
- 用 SAM3 做元素级分割与分类
- 按元素类型分别重建（形状、箭头、图片、文字）
- 最后按层级合并为完整 DrawIO 文档

---

## 2. 入口与调度

### 2.1 CLI 入口
- 文件：`draw.io(editbanana)/main.py`
- 主流程入口：`Pipeline.process_image(...)`

### 2.2 Web 入口
- 文件：`draw.io(editbanana)/server_pa.py`
- `POST /convert` 最终也会调用 `Pipeline.process_image(...)`

### 2.3 辅助脚本入口
- 文件：`draw.io(editbanana)/scripts/merge_xml.py`
- 本质上是对 `main.py` 的调度封装，行为保持一致

---

## 3. 主流程（真实执行链）
1. 加载配置并初始化 Pipeline（`main.py`）
2. 可选预处理：小图超分（`_preprocess_image`）
3. 可选文字提取：`TextRestorer.process(...)`
4. SAM3 元素提取：`Sam3InfoExtractor.process(...)`
5. 元素后处理模块：
   - `IconPictureProcessor`（图标/图片）
   - `BasicShapeProcessor`（基础图形）
   - `ArrowProcessor`（箭头/连接线）
6. 对未覆盖元素补 XML 片段（`_generate_xml_fragments`）
7. `XMLMerger` 分层合并，输出 `*_merged.drawio.xml`

---

## 4. 核心模块与原理

## 4.1 SAM3InfoExtractor（检测层）
- 文件：`draw.io(editbanana)/modules/sam3_info_extractor.py`
- 关键思想：按提示词分组提取，不同组使用不同阈值策略
  - `background`
  - `shape`
  - `image`
  - `arrow`
- `SAM3Model` 在本地直接加载权重并推理：
  - `build_sam3_image_model(...)`
  - `Sam3Processor`
- 输出统一到 `ElementInfo` 结构（bbox/mask/polygon/score）

## 4.2 IconPictureProcessor（图片类重建）
- 文件：`draw.io(editbanana)/modules/icon_picture_processor.py`
- 处理 icon/picture/logo/chart/function_graph
- 典型流程：裁剪 -> 可选 RMBG 去背景 -> base64 嵌入 DrawIO image cell

## 4.3 BasicShapeProcessor（基础图形重建）
- 文件：`draw.io(editbanana)/modules/basic_shape_processor.py`
- 处理 rectangle/ellipse/diamond 等可矢量化图形
- 提取样式（填充色、描边色、边宽）并生成对应 mxCell
- 支持 CV 补检，弥补 SAM3 漏检矩形/容器

## 4.4 ArrowProcessor（箭头重建）
- 文件：`draw.io(editbanana)/modules/arrow_processor.py`
- 优先使用 mask 骨架提路径（vector edge）
- 失败时回退为图片方式嵌入
- 最终生成 DrawIO edge 风格 XML

## 4.5 TextRestorer（文字层）
- 文件：`draw.io(editbanana)/modules/text/restorer.py`
- OCR 默认对接本地 Azure 容器接口（默认 `http://localhost:5000`）
- 输出文字 XML，再在合并阶段叠到顶层

## 4.6 XMLMerger（融合层）
- 文件：`draw.io(editbanana)/modules/xml_merger.py`
- 只做“收集与合并”，不负责样式决策
- 合并规则：
  - 按层级排序（背景 -> 基础图形 -> 图片 -> 箭头 -> 文字）
  - 同层按面积排序（大元素先放底层）
  - 重分配 id，避免冲突

---

## 5. 数据结构与层级规范
- 文件：`draw.io(editbanana)/modules/data_types.py`
- 统一元素结构：`ElementInfo`
- 分层枚举：`LayerLevel`
  - `BACKGROUND = 0`
  - `BASIC_SHAPE = 1`
  - `IMAGE = 2`
  - `ARROW = 3`
  - `TEXT = 4`
  - `OTHER = 5`

这套层级保证输出可编辑图在视觉上尽量接近原图且不互相错误遮挡。

---

## 6. 当前实现现状（重点）

## 6.1 SAM 调用方式
当前主流程默认是“本地加载模型权重推理”，不是默认走 `sam3_service`。
- 本地加载点：`modules/sam3_info_extractor.py` 中 `SAM3Model.load()`

## 6.2 sam3_service 状态
仓库内有完整 `sam3_service`（`server.py` / `client.py`），支持 HTTP 常驻服务和负载均衡。
但主流程 `main.py` / `server_pa.py` 目前没有直接接入该 client 作为默认路径。

## 6.3 输入格式现状
- CLI 主流程在批处理分支只收集图片格式（jpg/png/bmp/tiff/webp）
- Web `/convert` 允许上传 pdf，但后续仍调用 `process_image`，需要关注 PDF 页转图流程是否在其他层补齐

---

## 7. 一句话总结
Edit Banana 当前是一个“分而治之”的工程化重建流水线：
先检测，再按类型重建，最后分层合并。
其优势是可控、可调、可扩展；当前默认 SAM 路径是本地模型推理，服务化 SAM 仍属于可选能力。

---

# PPT 子项目（ppt）当前流程梳理

## 1. 项目目标
将论文 PDF 的方法语义转成一张结构化技术图，再重建为可编辑 PPT 页面（当前实现是单次流程输出一个三页调试型 PPT）。

核心方式：
- 先抽取论文方法（语义层）
- 再生成“带内容图 + 空布局图”（视觉层）
- 分离提取布局框架与内容元素（结构层）
- 最后合成 PPT（渲染层）

---

## 2. 入口与框架

### 2.1 运行入口
- 文件：`ppt/script/run_paper2figure.py`
- 创建 `Paper2FigureRequest + Paper2FigureState`，调用 `run_workflow("paper2fig_with_sam", state)`

### 2.2 工作流调度
- 文件：`ppt/dataflow_agent/workflow/__init__.py`
- 自动发现 `wf_*.py` 并注册到运行时 registry
- `run_workflow` 构图后 `ainvoke(state)`

### 2.3 主工作流
- 文件：`ppt/dataflow_agent/workflow/wf_paper2figure_with_sam.py`
- 注册名：`paper2fig_with_sam`

---

## 3. 主流程（真实执行顺序）

链路由 workflow edges 固定为：
1. `paper_idea_extractor`
2. `figure_desc_generator`
3. `figure_generator`
4. `figure_layout_sam`
5. `figure_mask_generator`
6. `figure_icon_bg_remover`
7. `figure_ppt_generator`

另外 `_start_` 节点会先初始化统一输出目录 `outputs/paper2figure/<timestamp>`。

---

## 4. 各节点职责与原理

## 4.1 paper_idea_extractor（语义抽取）
- 从 `state.paper_file` 中读取前 10 页文本与标题作为 pre-tool 输入
- 通过 Agent（`paper_idea_extractor`）抽取论文方法相关核心内容
- 输出写入 `state.paper_idea`

原理：先把长论文压缩成“可生成图像”的方法语义，降低后续图像生成漂移。

## 4.2 figure_desc_generator（图描述生成）
- 根据 `paper_idea` + `style` 生成结构化 `fig_desc`
- 依据 `figure_complex` 选择不同 prompt 模板（easy/mid/hard）

原理：把论文语义转成“图形构图说明”，作为后续文生图输入。

## 4.3 figure_generator（两阶段图生成）
- 第一阶段：生成带内容图 `fig_draft_path`
- 第二阶段：对第一张图二次编辑，得到去文字/去内部细节的布局图 `fig_layout_path`

原理：强制拆成“内容图”和“布局图”，为后续双通道解析做准备。

## 4.4 figure_layout_sam（布局层提取）
- 对 `fig_layout_path` 做 SAM 分割，优先服务端（`localhost:8020`），失败 fallback 本地
- 后处理后得到 `layout_items`（layout_box）
- 每个布局块进一步 `PNG -> SVG -> EMF`
- 同时把归一化 bbox 映射成像素 `bbox_px`

原理：布局层只关注外框与结构，不混入文本/图标，确保 PPT 框架定位稳定。

## 4.5 figure_mask_generator（内容层提取）
- 对 `fig_draft_path` 调 MinerU HTTP 递归提取块
- 输出统一成 `fig_mask`（text/image/table + 像素 bbox）
- 当 MinerU 结果过粗时，借助 SAM 的 layout 分块再对子图做二次 MinerU 解析

原理：MinerU 偏内容理解，SAM 偏结构分块，二者结合提高细粒度召回。

## 4.6 figure_icon_bg_remover（图标净化）
- 对 `fig_mask` 中 `image/table` 元素做背景去除（RMBG）
- 更新元素 `img_path` 到透明背景版本

原理：减少图标白底/噪点，避免遮挡布局底层。

## 4.7 figure_ppt_generation（最终合成）
- 生成 PPT 三页：
  - 第1页：layout EMF + 内容层（text/image）
  - 第2页：仅 layout EMF（调试页）
  - 第3页：整幅 `fig_draft` 铺满（对照页）
- 坐标统一走“像素 -> 英寸 -> Emu”，保障元素对齐
- 输出 `state.ppt_path`

原理：分层渲染并做可视化对照，便于快速定位错位/漏检问题。

---

## 5. 关键状态字段（Paper2FigureState）
- `paper_file`：输入论文 PDF
- `paper_idea`：方法摘要
- `fig_draft_path`：带内容图
- `fig_layout_path`：空布局图
- `layout_items`：布局层（含 `bbox_px`, `emf_path`）
- `fig_mask`：内容层（文本/图像元素）
- `result_path`：本次运行输出根目录
- `ppt_path`：最终 PPT 路径

---

## 6. 工程特征与当前实现现状

## 6.1 双层重建策略
- 布局层（SAM）与内容层（MinerU）分开抽取，再在 PPT 中融合。
- 这是当前流程稳定性的核心设计。

## 6.2 容错策略
- SAM 服务端失败会自动 fallback 到本地推理。
- 各节点多处 try/except，尽量保证流程不中断并产出可调试结果。

## 6.3 依赖与运行条件
- LLM 图像生成接口（`DF_API_URL/DF_API_KEY`）
- SAM 权重/服务（本地或 HTTP）
- MinerU 服务端口（默认 8010）
- RMBG 模型（用于抠图）

---

## 7. 一句话总结
`ppt` 子项目是一个“语义驱动 + 双层视觉重建”的工作流系统：先从论文抽语义，再生成图，再分别提取布局与内容，最终按统一坐标体系组装成可编辑 PPT。

# 最新进度
## 2026-02-09 进度快照（可用于下次续跑）

### 1) 断点续跑已实现
- 支持 `--resume <run_id>` 与 `--resume-from <node>`
- checkpoint 目录：`ppt/outputs/paper2figure/<run_id>/checkpoints/`
- 主要改动文件：
  - `ppt/script/run_paper2figure.py`
  - `ppt/dataflow_agent/workflow/wf_paper2figure_with_sam.py`
  - `ppt/dataflow_agent/utils.py`
  - `ppt/dataflow_agent/state.py`

### 2) 当前可用 run_id
- `1770621096`
- 已生成 PPT：
  - `ppt/outputs/paper2figure/1770621096/presentation_1770625819.pptx`
  - `ppt/outputs/paper2figure/1770621096/presentation_1770627239.pptx`
  - `ppt/outputs/paper2figure/1770621096/presentation_1770627325.pptx`
- 最新 checkpoint 已写到：
  - `ppt/outputs/paper2figure/1770621096/checkpoints/`
  - 最近节点：`figure_ppt_generator`

### 3) 续跑示例命令
- 从指定节点续跑：
  - `source ~/.zshrc && python3 ppt/script/run_paper2figure.py --resume 1770621096 --resume-from figure_icon_bg_remover`
- 从最新完成节点的下一步自动续跑：
  - `source ~/.zshrc && python3 ppt/script/run_paper2figure.py --resume 1770621096`

### 4) 关键问题与状态
- **RMBG-2.0 自动下载仍失败**
  - 尝试在 `/tmp` 下载已开始，但未完成（模型体积很大）
  - `modelscope` 在当前 Anaconda 环境仍会触发 `UnicodeDecodeError`
  - 已加 UTF-8 环境变量，但问题仍存在
- **LLM 余额不足导致 fig_desc 质量差**
  - SiliconFlow 之前 403 余额不足，已提示已充值但尚未复跑验证
  - 计划：从 `paper_idea_extractor` 重新续跑生成更好的 `fig_desc`
- **MinerU HTTP 8010 不可达**
  - 仍走 CLI fallback，耗时但能出结果

### 5) 图像/LLM 配置
- 文本 LLM：`Pro/moonshotai/Kimi-K2.5`（SiliconFlow）
- 图像模型：`gemini-nano-banana-2`（UNIAPI）
- 说明：`fig_desc` 由 LLM 生成，图像由 UNIAPI 生成

### 6) GitHub 上传待处理
- 目标仓库：`git@github.com:AgentTeam-AT2APP/AI4Drawing.git`
- 需求：整个项目放到 `Dev-Try-MVP/` 子目录，分支 `main`
- 当前阻塞：缺少可用 SSH key 或 HTTP PAT 凭据
