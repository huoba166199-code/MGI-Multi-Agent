import re
import json
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_deepseek import ChatDeepSeek
import os
from dotenv import load_dotenv
from .observability import node_logger, log_event, app_logger

load_dotenv()

llm = ChatDeepSeek(
    api_key=os.getenv("LLM_API_KEY"),
    api_base=os.getenv("LLM_API_BASE", "https://api.deepseek.com"),
    model=os.getenv("LLM_MODEL", "deepseek-chat")
)


# 子图内部状态
class EquipmentState(TypedDict):
    query: str
    task_type: str
    intent_reason: str
    equipment_report: str


# ---------------- 路由与节点 ----------------

@node_logger("equipment_intent_router")
def intent_router(state: EquipmentState):
    query = state.get("query", "")

    # 1. 规则硬拦截（优先判断具体故障）
    trouble_patterns = [r"ERR-\d+", r"错误码", r"报错", r"报警", r"异响", r"漏液", r"卡死", r"中断"]
    if any(re.search(p, query, re.IGNORECASE) for p in trouble_patterns):
        return {"task_type": "troubleshooting", "intent_reason": "命中具体故障规则"}

    # 2. 规则拦截（巡检意图）
    inspect_patterns = [r"顺便查", r"巡检", r"检查一下", r"看看状态", r"健康检查", r"查一下机器"]
    if any(re.search(p, query, re.IGNORECASE) for p in inspect_patterns):
        return {"task_type": "inspection", "intent_reason": "命中常规巡检规则"}

    # 3. 模糊兜底：说了机器/设备但没有报错码 -> 默认巡检
    if "故障" in query or "机器" in query or "设备" in query:
        return {"task_type": "inspection", "intent_reason": "无具体报错，默认巡检"}

    # 4. LLM 兜底（极少走到）
    return {"task_type": "inspection", "intent_reason": "未命中规则，大模型兜底判为巡检"}


@node_logger("equipment_inspection")
def inspection_node(state: EquipmentState):
    query = state.get("query", "")
    prompt = f"""
    你是华大智造资深测序仪巡检专家。用户的指令是：“{query}”。
    【业务判定】本次是常规健康巡检。
    【强制规则】绝对禁止反问用户“具体报错是什么”。请直接输出一份包含【电源网络确认】、【试剂与流动池效期】、【温控光路状态】、【管路排气建议】的常规巡检清单，字数150字左右。
    """
    return {"equipment_report": llm.invoke(prompt).content}


@node_logger("equipment_troubleshooting")
def troubleshooting_node(state: EquipmentState):
    query = state.get("query", "")
    prompt = f"""
    你是华大智造资深测序仪排障专家。用户的指令是：“{query}”。
    【业务判定】本次是具体故障排障。请针对报错现象给出排查步骤，字数150字左右。
    """
    return {"equipment_report": llm.invoke(prompt).content}


# ---------------- 构建子图 ----------------
def route_decision(state: EquipmentState):
    return state.get("task_type", "inspection")


eq_workflow = StateGraph(EquipmentState)
eq_workflow.add_node("router", intent_router)
eq_workflow.add_node("inspection", inspection_node)
eq_workflow.add_node("troubleshooting", troubleshooting_node)

eq_workflow.set_entry_point("router")
eq_workflow.add_conditional_edges(
    "router",
    route_decision,
    {"inspection": "inspection", "troubleshooting": "troubleshooting"}
)
eq_workflow.add_edge("inspection", END)
eq_workflow.add_edge("troubleshooting", END)

equipment_subgraph = eq_workflow.compile()


# ---------------- 包装给父图用的节点 ----------------
@node_logger("equipment_agent_wrapper")
def equipment_agent_node(state: dict):
    """父图调用的入口，只传 query，只接 report"""
    messages = state.get("messages", [])
    query = messages[0] if messages else ""

    # 调用子图
    res = equipment_subgraph.invoke({"query": query})

    log_event(app_logger, "subgraph_exit", "equipment subgraph finished",
              task_type=res.get("task_type"), reason=res.get("intent_reason"))

    return {"equipment_report": res.get("equipment_report", "")}