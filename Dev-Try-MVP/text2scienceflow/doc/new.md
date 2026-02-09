

两条生成链路：

- freeform（DeepPresenter）：先做研究文稿，再做 HTML 视觉页，再转成 PPT/PDF
- template（PPTAgent）：先选模板布局，再按结构化元素逐页生成 PPTX

“断点续跑”

- 检查点机制在 [state.py](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#) + [paths.py](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)。
- 自动检测从哪一步继续：[detect_start_stage(...)](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)。
- [state.json](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#) 记录每阶段 pending/running/completed/failed。
- 所以换风格通常只需从 plan 或 generate 重跑，不必重新解析论文。

**1) [run_paper2figure.py](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)（paper2fig_with_sam）**
实际入口见 [run_paper2figure.py (line 28)](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)、[run_paper2figure.py (line 50)](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)，对应图在 [wf_paper2figure_with_sam.py (line 94)](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)。
执行链路（PDF 模式）是：

1. _start_ 初始化输出目录 outputs/paper2figure/<ts>，见 [wf_paper2figure_with_sam.py (line 900)](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)。

2. paper_idea_extractor 从 PDF 抽论文核心思路，见 [wf_paper2figure_with_sam.py (line 149)](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)。

3. figure_desc_generator 把论文思路转成“绘图描述”，见 [wf_paper2figure_with_sam.py (line 157)](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)。

4. figure_generator 先生成“完整图”，再二次编辑生成“空框模板图”，见 [wf_paper2figure_with_sam.py (line 167)](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)。

5. figure_layout_sam 对模板图做 SAM 分割，再 PNG->SVG->EMF 得到背景框架层，见 [wf_paper2figure_with_sam.py (line 230)](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)、[wf_paper2figure_with_sam.py (line 316)](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)。

   > - 直接 PNG 当背景会糊、放缩失真，且不可编辑。
   > - SVG 在 PPT 里兼容性不稳定；EMF 在 Windows/Office 下兼容更好。
   >   代码里也明确写了这个目的，见 [bg_tool.py (line 903)](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)。
   > - 所以用 PNG->SVG->EMF，得到“可缩放 + 更可编辑 + Office 友好”的背景框架层。

6. figure_mask_generator 对完整图做 MinerU 递归解析，提取文本块和图像块（内容层），见 [wf_paper2figure_with_sam.py (line 365)](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)。

7. figure_icon_bg_remover 给图像元素抠背景，见 [wf_paper2figure_with_sam.py (line 648)](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)。

8. figure_ppt_generator 合成 PPT：背景框架层(EMF) + 内容层(text/image)，见 [wf_paper2figure_with_sam.py (line 689)](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)。

核心原理：
这是“文本结构化 -> SVG/PNG 渲染 -> PPT 封装”流程，不走 SAM/MinerU 的复杂拆图重建，重点在“技术路线语义表达”

1.输入图片/pdf/文字之后进行预处理

2.ocr识别文字公式



## Edit-Banana

**整体主流程（当前仓库实现）**

1. 输入图片后先做预处理（可选超分），建立共享上下文 ProcessingContext。入口在 [main.py](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)。
2. 先跑文字链路：OCR 识别文本/公式，生成一份“文字专用 drawio XML”并暂存。核心在 [restorer.py](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)。
3. 再跑图形链路：SAM3 按提示词组分批提取元素（背景、基本图形、图片类、箭头），并做组内/组间去重。核心在 [sam3_info_extractor.py](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)。
4. 对不同元素分别处理并生成各自 XML 片段：
   - 图片/icon：抠图或转 base64 图片单元格（[icon_picture_processor.py](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)）
   - 基本图形：取填充色/描边色/线宽，转矢量样式（[basic_shape_processor.py](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)）
   - 箭头：尽量骨架化为矢量路径，失败则回退为图片（[arrow_processor.py](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)）
5. 可选质量评估与补救：
   - 评估覆盖率，找漏检区域（[metric_evaluator.py](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)）
   - 对漏检区域直接裁剪成 picture 元素补进去（[refinement_processor.py](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)）
6. 最后统一合并：
   - 收集所有 XML 片段（图形+文字）
   - 按层级排序（背景→图形→图片→箭头→文字）
   - 重新分配 mxCell id，输出最终 [.drawio.xml](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)
     核心在 [xml_merger.py](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#)。

**这个设计的关键原理**

- **职责拆分**：每类元素单独处理，降低互相干扰。
- **分层合成**：通过 layer_level 控制 DrawIO 的前后遮挡关系。
- **保底策略**：不能矢量化就回退成图片，优先保证“视觉不丢失”。
- **坐标一致性**：若前面做过超分，合并时会把坐标缩回原图尺度，保证文本与图形对齐。

**入口形态**

- CLI：python main.py -i ...
- API：[server_pa.py](https://file+.vscode-resource.vscode-cdn.net/Users/oujiazhan/.vscode/extensions/openai.chatgpt-0.4.71-darwin-x64/webview/#) 的 /convert 本质也是调用同一条 Pipeline。