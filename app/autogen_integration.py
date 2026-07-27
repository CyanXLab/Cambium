"""
AutoGen Integration — 多 Agent 对话式协作。

AutoGen 提供基于对话的多 Agent 协作：
  - AssistantAgent: 有角色和 LLM 配置的 Agent
  - GroupChat: 多 Agent 群聊，自动管理发言顺序
  - TextMentionTermination: 通过 @mention 终止对话

与 LangGraph 的区别：
  - LangGraph: 状态图，适合结构化工作流（decompose → execute → review）
  - AutoGen: 对话式，适合开放讨论（Agent 互相问答直到达成共识）

Cambium 同时支持两者：
  - Swarm Task 执行 → LangGraph（结构化）
  - 居民讨论 → AutoGen（对话式）
"""
from __future__ import annotations
import json
import time
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path

try:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_agentchat.teams import RoundRobinGroupChat
    from autogen_agentchat.messages import TextMessage
    from autogen_core.models import ChatCompletionClient
    from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
    AUTOGEN_AVAILABLE = True
except ImportError:
    AUTOGEN_AVAILABLE = False


def is_available() -> bool:
    return AUTOGEN_AVAILABLE


async def run_autogen_discussion(
    db_path: Path,
    topic: str,
    resident_names: List[str],
    http_client_factory: Optional[Callable] = None,
    get_api_cfg: Optional[Callable] = None,
    max_rounds: int = 6,
) -> List[Dict]:
    """用 AutoGen GroupChat 运行多居民讨论。

    每个居民是一个 AssistantAgent，在 RoundRobinGroupChat 中依次发言。
    当某个居民说 "TERMINATE" 或达到最大轮次时停止。

    返回 [{resident, message, round}, ...]
    """
    if not AUTOGEN_AVAILABLE:
        return []

    from app import residents as residents_mod
    from app.llm_utils import extract_content

    if not http_client_factory or not get_api_cfg:
        return []

    api_cfg = get_api_cfg()
    model_name = api_cfg.get("api_model", "")

    # Create AutoGen ChatCompletionClient
    # AutoGen uses OpenAI-compatible API
    try:
        # Use the create method with OpenAI-compatible config
        model_client = ChatCompletionClient(
            model=model_name,
            base_url=api_cfg.get("api_base_url", ""),
            api_key=api_cfg.get("api_key", ""),
        )
    except Exception as e:
        print(f"[autogen] model client creation failed: {e}")
        return []

    # Create agents from residents
    agents = []
    agent_residents = []
    for name in resident_names:
        resident = None
        for r in residents_mod.list_residents(db_path, "default", status="active"):
            if r["name"].lower() == name.lower():
                resident = r
                break
        if not resident:
            continue

        system_prompt = resident.get("system_prompt", f"你是 {resident['name']}。")
        llm_overrides = resident.get("llm_config", {})
        agent_model = llm_overrides.get("model") or model_name

        try:
            agent = AssistantAgent(
                name=resident["name"],
                model_client=model_client,
                system_message=system_prompt + "\n\n讨论结束后说 TERMINATE。",
            )
            agents.append(agent)
            agent_residents.append(resident)
        except Exception as e:
            print(f"[autogen] agent {resident['name']} creation failed: {e}")

    if len(agents) < 2:
        return []

    # Create group chat
    termination = TextMentionTermination("TERMINATE") | MaxMessageTermination(max_rounds * len(agents))
    team = RoundRobinGroupChat(agents, termination_condition=termination)

    # Run the discussion
    results = []
    try:
        # Send the topic as the first message
        task = f"讨论话题：{topic}\n\n请各位依次发表看法，可以同意、反对或补充。讨论完成后说 TERMINATE。"

        # AutoGen 0.7+ uses run_stream or run
        import asyncio
        result_messages = await team.run(task=task)

        # Extract messages
        for msg in result_messages.messages:
            if hasattr(msg, 'source') and hasattr(msg, 'content'):
                results.append({
                    "resident": msg.source,
                    "message": msg.content,
                    "round": 0,  # AutoGen doesn't expose round directly
                })
                # Also save to swarm messages if there's a task
                residents_mod.update_resident_state(
                    db_path,
                    next((r["id"] for r in agent_residents if r["name"] == msg.source), ""),
                    focus=topic[:200],
                    opinion=str(msg.content)[:200],
                )

    except Exception as e:
        print(f"[autogen] discussion failed: {e}")
        # Fallback: return empty, caller should handle
        return []

    return results


async def run_autogen_swarm_task(
    db_path: Path,
    task_id: str,
    http_client_factory: Optional[Callable] = None,
    get_api_cfg: Optional[Callable] = None,
) -> Dict:
    """用 AutoGen 执行 Swarm Task。

    创建一个 GroupChat，包含：
    - Planner: 分解任务
    - Executor: 执行子任务
    - Critic: 审查结果
    - Summarizer: 综合最终结果

    Agent 之间通过对话协作，自动管理发言顺序。
    """
    if not AUTOGEN_AVAILABLE:
        # Fallback to LangGraph
        from app import langgraph_integration
        return await langgraph_integration.execute_swarm_via_langgraph(
            db_path, task_id, http_client_factory, get_api_cfg
        )

    from app import swarm as swarm_mod
    from app import residents as residents_mod

    task = swarm_mod.get_task(db_path, task_id)
    if not task:
        return {"error": "task not found"}

    update_status = swarm_mod.update_task(db_path, task_id, status="executing")
    swarm_mod.add_message(db_path, task_id, "system", f"AutoGen 任务开始: {task['title']}", message_type="system")

    # Select residents for the team
    planner = residents_mod._find_resident_by_role(db_path, "planner") if hasattr(residents_mod, '_find_resident_by_role') else None
    if not planner:
        for r in residents_mod.list_residents(db_path, "default", status="active"):
            if r["role"] == "planner":
                planner = r
                break

    critic = None
    for r in residents_mod.list_residents(db_path, "default", status="active"):
        if r["role"] == "critic":
            critic = r
            break

    architect = None
    for r in residents_mod.list_residents(db_path, "default", status="active"):
        if r["role"] == "architect":
            architect = r
            break

    if not planner or not critic:
        # Fallback
        return await langgraph_integration.execute_swarm_via_langgraph(
            db_path, task_id, http_client_factory, get_api_cfg
        )

    # Run discussion
    resident_names = [planner["name"], architect["name"] if architect else "Architect", critic["name"]]
    discussion = await run_autogen_discussion(
        db_path,
        f"任务: {task['title']}\n描述: {task['description']}",
        resident_names,
        http_client_factory,
        get_api_cfg,
        max_rounds=4,
    )

    # Save messages
    for msg in discussion:
        prefix = ""
        for r in residents_mod.list_residents(db_path, "default", status="active"):
            if r["name"] == msg["resident"]:
                prefix = residents_mod.build_resident_prefix(r)
                break
        swarm_mod.add_message(
            db_path, task_id,
            msg["resident"],
            msg["message"],
            message_type="result",
            round_num=msg.get("round", 0),
        )

    # Combine results
    final_result = "\n\n".join(
        f"### {msg['resident']}\n{msg['message']}"
        for msg in discussion
    )

    swarm_mod.update_task(db_path, task_id,
        status="completed",
        result=final_result,
        completed_at=int(time.time()),
    )
    swarm_mod.add_message(db_path, task_id, "system", "任务完成", message_type="system", round_num=99)

    return {
        "task_id": task_id,
        "status": "completed",
        "result": final_result,
        "messages": swarm_mod.get_messages(db_path, task_id),
        "engine": "autogen",
    }
