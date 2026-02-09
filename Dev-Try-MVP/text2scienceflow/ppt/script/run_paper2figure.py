from __future__ import annotations

"""
脚本用途: 运行 paper2fig_with_sam 工作流，将论文 PDF 转为图示并导出 PPT。

使用方式:
  python script/run_paper2figure_with_sam.py
"""

import argparse
import asyncio
import os
import sys
from dataclasses import fields

# Ensure local package is used instead of any globally installed one.
PPT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PPT_ROOT)

from dataflow_agent.state import Paper2FigureState, Paper2FigureRequest
from dataflow_agent.workflow import run_workflow
from dataflow_agent.utils import get_project_root, load_p2f_checkpoint


# ================== 可配置参数 ==================
# 论文 PDF 文件路径（默认使用仓库 input 目录下示例 PDF）
PAPER_FILE: str = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "input", "ClearAgent：AgenticBinaryAnalysisforEffective.pdf")
)

# 图像生成模型名称（用于生成实验图 / 示意图）
# 建议使用 SiliconFlow 支持的图像模型
GEN_FIG_MODEL: str = "gemini-nano-banana-2"

# 工作流名称（需与 workflow 注册名称一致）
WORKFLOW_NAME: str = "paper2fig_with_sam"
# =================================================

_NODE_ORDER = [
    "paper_idea_extractor",
    "figure_desc_generator",
    "figure_generator",
    "figure_layout_sam",
    "figure_mask_generator",
    "figure_icon_bg_remover",
    "figure_ppt_generator",
]

def _filter_kwargs(cls, data: dict) -> dict:
    names = {f.name for f in fields(cls)}
    return {k: v for k, v in data.items() if k in names}

def _next_node(last_completed: str) -> str:
    if last_completed in _NODE_ORDER:
        idx = _NODE_ORDER.index(last_completed) + 1
        if idx >= len(_NODE_ORDER):
            return "_end_"
        return _NODE_ORDER[idx]
    return ""

def _state_from_checkpoint(payload: dict, result_path: str) -> Paper2FigureState:
    state_dict = payload.get("state", {})
    if not isinstance(state_dict, dict):
        state_dict = {}
    req_dict = state_dict.get("request", {}) if isinstance(state_dict.get("request", {}), dict) else {}
    req = Paper2FigureRequest(**_filter_kwargs(Paper2FigureRequest, req_dict))
    state_kwargs = _filter_kwargs(Paper2FigureState, state_dict)
    state_kwargs.pop("request", None)
    state = Paper2FigureState(**state_kwargs)
    state.request = req
    state.result_path = result_path
    state.run_id = os.path.basename(result_path)
    return state

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paper2figure_with_sam workflow")
    parser.add_argument("--resume", dest="resume_run_id", default="", help="Resume by run_id")
    parser.add_argument("--resume-from", dest="resume_from", default="", help="Start from specific node")
    return parser.parse_args()


async def run_paper2figure_with_sam() -> Paper2FigureState:
    """
    执行 paper2figure_with_sam 工作流的主流程。

    返回:
        Paper2FigureState: 工作流执行结束后的最终状态对象。
    """
    args = _parse_args()
    resume_run_id = args.resume_run_id
    resume_from = args.resume_from

    if resume_from and not resume_run_id:
        raise RuntimeError("--resume-from requires --resume <run_id>")
    if resume_run_id:
        result_path = str(get_project_root() / "outputs" / "paper2figure" / resume_run_id)
        payload = load_p2f_checkpoint(result_path)
        if not payload:
            raise RuntimeError(f"Resume requested but no checkpoint found in {result_path}")
        state = _state_from_checkpoint(payload, result_path)
        last_completed = payload.get("last_completed_node", "")
        if resume_from:
            state.request.resume_from = resume_from
        else:
            state.request.resume_from = _next_node(last_completed)
        state.request.resume_run_id = resume_run_id
        # Ensure paper_file exists for downstream nodes that require it
        if not state.paper_file:
            state.paper_file = PAPER_FILE
    else:
        req = Paper2FigureRequest(
            gen_fig_model=GEN_FIG_MODEL,
            fig_desc_model="Pro/moonshotai/Kimi-K2.5",
            chart_model="Pro/moonshotai/Kimi-K2.5",
            technical_model="Pro/moonshotai/Kimi-K2.5",
        )
        state = Paper2FigureState(
            messages=[],
            agent_results={},
            request=req,
            paper_file=PAPER_FILE,
        )

    final_state: Paper2FigureState = await run_workflow(WORKFLOW_NAME, state)
    return final_state


def main() -> None:
    """
    同步入口: 运行异步主流程并打印关键输出路径与调试信息。
    """
    final_state = asyncio.run(run_paper2figure_with_sam())

    print("\n=== Workflow finished ===")
    print(f"paper_file      : {getattr(final_state, 'paper_file', None)}")
    print(f"ppt_path        : {getattr(final_state, 'ppt_path', None)}")
    print(f"fig_draft_path  : {getattr(final_state, 'fig_draft_path', None)}")
    print(f"fig_layout_path : {getattr(final_state, 'fig_layout_path', None)}")

    print("\n=== layout_items (len) ===")
    print(len(getattr(final_state, "layout_items", []) or []))

    print("\n=== fig_mask (len) ===")
    print(len(getattr(final_state, "fig_mask", []) or []))

    # 可选: 打印 agent_results 以便调试
    print("\n=== agent_results ===")
    print(getattr(final_state, "agent_results", {}))


if __name__ == "__main__":
    main()
