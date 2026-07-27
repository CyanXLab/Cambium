"""
LangGraph Integration — 用 LangGraph 实现 Agent 协作工作流。

LangGraph 提供状态图（StateGraph），让多 Agent 协作变得结构化：
  - 每个 Resident 是一个节点（node）
  - 边（edge）定义执行顺序和条件路由
  - 状态（state）在节点间传递
  - 支持 checkpoint（断点恢复）

集成的部分：
  1. SwarmTask 执行用 LangGraph StateGraph 替代手动 for-loop
  2. Chat 中的多居民讨论用 LangGraph 的多节点图
  3. Life Loop 的反思流程用 LangGraph 的工作流
"""
from __future__ import annotations
import json
import time
from typing import Dict, List, Optional, Any, TypedDict, Annotated
from pathlib import Path

# LangGraph imports
try:
    from langgraph.graph import StateGraph, END
    from langgraph.graph.message import add_messages
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

from app.db_utils import safe_connect
from app.llm_utils import extract_content


# ============================================================
# State definitions for LangGraph
# ============================================================

if LANGGRAPH_AVAILABLE:
    class SwarmState(TypedDict):
        task_title: str
        task_description: str
        subtasks: List[Dict]
        results: Annotated[List[Dict], lambda x, y: x + y]
        messages: Annotated[List[str], lambda x, y: x + y]
        final_result: str
        status: str

    class DiscussionState(TypedDict):
        topic: str
        context: str
        resident_messages: Annotated[List[str], lambda x, y: x + y]
        final_answer: str


# ============================================================
# Swarm Task execution via LangGraph
# ============================================================

async def execute_swarm_via_langgraph(
    db_path: Path,
    task_id: str,
    http_client_factory=None,
    get_api_cfg=None,
) -> Dict:
    """用 LangGraph StateGraph 执行 Swarm Task。

    流程:
      decompose (Planner) → execute (各居民并行) → review (Critic) → finalize
    """
    from app import swarm as swarm_mod
    from app import residents as residents_mod

    task = swarm_mod.get_task(db_path, task_id)
    if not task:
        return {"error": "task not found"}

    if not LANGGRAPH_AVAILABLE:
        # Fallback to original execution
        return await swarm_mod.execute_swarm_task(
            db_path, task_id, http_client_factory, get_api_cfg
        )

    # Build the graph
    graph = StateGraph(SwarmState)

    # Node: decompose
    async def decompose_node(state: SwarmState) -> Dict:
        planner = _find_resident(db_path, "planner")
        if not planner:
            return {"subtasks": [{"title": state["task_title"], "assigned_to": "Cambium", "description": state["task_description"]}]}

        prompt = f"分解任务: {state['task_title']}\n描述: {state['task_description']}\n\n输出 JSON: {{\"subtasks\": [{{\"title\": \"...\", \"assigned_to\": \"Architect\", \"description\": \"...\"}}]}}"
        result = await _llm_call(planner, prompt, http_client_factory, get_api_cfg)
        subtasks = _parse_json(result).get("subtasks", [{"title": state["task_title"], "assigned_to": "Cambium", "description": state["task_description"]}])

        swarm_mod.add_message(db_path, task_id, "Planner",
            f"任务分解为 {len(subtasks)} 个子任务", message_type="proposal", round_num=0)

        return {"subtasks": subtasks, "status": "executing"}

    # Node: execute each subtask
    async def execute_node(state: SwarmState) -> Dict:
        results = []
        prev_context = ""
        for st in state["subtasks"]:
            resident = _find_resident(db_path, st.get("assigned_to", ""))
            if not resident:
                resident = _find_resident(db_path, "architect") or _find_resident(db_path, "general")

            if resident:
                prompt = f"子任务: {st['title']}\n描述: {st['description']}\n{prev_context}\n\n完成你的部分（200-500字）。"
                result_text = await _llm_call(resident, prompt, http_client_factory, get_api_cfg)

                prefix = residents_mod.build_resident_prefix(resident)
                swarm_mod.add_message(db_path, task_id, resident["name"],
                    result_text, message_type="result", round_num=1)
                results.append({"resident": resident["name"], "result": result_text})
                prev_context += f"\n[{resident['name']}]: {result_text[:200]}"
                residents_mod.update_resident_state(db_path, resident["id"],
                    focus=st["title"][:200], opinion=result_text[:200])

        return {"results": results, "status": "reviewing"}

    # Node: review
    async def review_node(state: SwarmState) -> Dict:
        critic = _find_resident(db_path, "critic")
        if not critic or not state.get("results"):
            return {"status": "completed"}

        combined = "\n\n".join(f"[{r['resident']}]: {r['result']}" for r in state["results"])
        review = await _llm_call(critic,
            f"审查以下结果:\n{combined}\n\n给出审查意见（100-300字）。",
            http_client_factory, get_api_cfg)

        swarm_mod.add_message(db_path, task_id, critic["name"],
            review, message_type="result", round_num=2)

        final = combined + f"\n\n### Critic 审查\n{review}"
        return {"final_result": final, "status": "completed"}

    # Add nodes
    graph.add_node("decompose", decompose_node)
    graph.add_node("execute", execute_node)
    graph.add_node("review", review_node)

    # Add edges
    graph.set_entry_point("decompose")
    graph.add_edge("decompose", "execute")
    graph.add_edge("execute", "review")
    graph.add_edge("review", END)

    # Compile and run
    app_graph = graph.compile()

    initial_state = SwarmState(
        task_title=task["title"],
        task_description=task["description"],
        subtasks=[],
        results=[],
        messages=[],
        final_result="",
        status="pending",
    )

    try:
        final_state = await app_graph.ainvoke(initial_state)

        # Save results
        swarm_mod.update_task(db_path, task_id,
            status="completed",
            result=final_state.get("final_result", ""),
            completed_at=int(time.time()),
        )
        swarm_mod.add_message(db_path, task_id, "system", "任务完成", message_type="system", round_num=3)

        return {
            "task_id": task_id,
            "status": "completed",
            "result": final_state.get("final_result", ""),
            "messages": swarm_mod.get_messages(db_path, task_id),
        }
    except Exception as e:
        print(f"[langgraph] execution failed: {e}")
        # Fallback to original
        return await swarm_mod.execute_swarm_task(
            db_path, task_id, http_client_factory, get_api_cfg
        )


# ============================================================
# Multi-resident discussion via LangGraph
# ============================================================

async def run_discussion_via_langgraph(
    db_path: Path,
    topic: str,
    resident_ids: List[str],
    http_client_factory=None,
    get_api_cfg=None,
) -> List[str]:
    """用 LangGraph 运行多居民讨论。"""
    from app import residents as residents_mod

    if not LANGGRAPH_AVAILABLE:
        # Fallback: sequential discussion
        messages = []
        prev = ""
        for rid in resident_ids:
            r = residents_mod.get_resident(db_path, rid)
            if not r:
                continue
            prompt = f"话题: {topic}\n{prev}\n你是 {r['name']}。发表看法（2-3句）。"
            msg = await _llm_call(r, prompt, http_client_factory, get_api_cfg)
            prefix = residents_mod.build_resident_prefix(r)
            messages.append(f"{prefix}{msg}")
            prev += f"\n[{r['name']}]: {msg}"
        return messages

    graph = StateGraph(DiscussionState)

    # Create a node for each resident
    for rid in resident_ids:
        resident = residents_mod.get_resident(db_path, rid)
        if not resident:
            continue

        async def make_node(res=resident):
            async def node_fn(state: DiscussionState) -> Dict:
                prev_msgs = "\n".join(state.get("resident_messages", []))
                prompt = f"话题: {state['topic']}\n\n{prev_msgs}\n\n你是 {res['name']}。发表你的看法（2-3句）。"
                msg = await _llm_call(res, prompt, http_client_factory, get_api_cfg)
                prefix = residents_mod.build_resident_prefix(res)
                return {"resident_messages": [f"{prefix}{msg}"]}
            return node_fn

        graph.add_node(f"resident_{rid}", await make_node())

    # Chain: resident_0 → resident_1 → ... → END
    nodes = [f"resident_{rid}" for rid in resident_ids if residents_mod.get_resident(db_path, rid)]
    if not nodes:
        return []

    graph.set_entry_point(nodes[0])
    for i in range(len(nodes) - 1):
        graph.add_edge(nodes[i], nodes[i + 1])
    graph.add_edge(nodes[-1], END)

    app_graph = graph.compile()

    initial_state = DiscussionState(
        topic=topic,
        context="",
        resident_messages=[],
        final_answer="",
    )

    try:
        final_state = await app_graph.ainvoke(initial_state)
        return final_state.get("resident_messages", [])
    except Exception as e:
        print(f"[langgraph] discussion failed: {e}")
        return []


# ============================================================
# Helpers
# ============================================================

async def _llm_call(resident, prompt, http_client_factory, get_api_cfg):
    if not http_client_factory or not get_api_cfg:
        return f"（{resident['name']} 会在这里执行，但 LLM 未配置）"
    try:
        import httpx
        api_cfg = get_api_cfg()
        llm_overrides = resident.get("llm_config", {})
        model = llm_overrides.get("model") or api_cfg.get("api_model", "")
        system_prompt = resident.get("system_prompt", f"你是 {resident['name']}。")
        async with http_client_factory(timeout=60.0) as client:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.6, "max_tokens": 800,
                "stream": False, "enable_thinking": False,
            }
            resp = await client.post(
                f"{api_cfg['api_base_url']}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {api_cfg['api_key']}",
                         "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            return extract_content(resp.json()) or f"（{resident['name']} 无输出）"
    except Exception as e:
        return f"（{resident['name']} 执行失败: {e}）"


def _find_resident(db_path, role_or_name):
    from app import residents
    for r in residents.list_residents(db_path, "default", status="active"):
        if r["role"] == role_or_name or r["name"].lower() == role_or_name.lower():
            return r
    return None


def _parse_json(text):
    import re
    if not text:
        return {}
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}
