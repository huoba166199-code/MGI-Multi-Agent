from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver # 引入内存持久化
from .state import AgentState
from .supervisor import supervisor_node
from .workers import (
    sequence_analyst_agent,
    equipment_engineer_agent,
    compliance_officer_agent,
    parallel_execution_agent
)

workflow = StateGraph(AgentState)

workflow.add_node("supervisor", supervisor_node)
workflow.add_node("sequence_analyst", sequence_analyst_agent)
workflow.add_node("equipment_engineer", equipment_engineer_agent)
workflow.add_node("compliance_officer", compliance_officer_agent)
workflow.add_node("parallel_exec", parallel_execution_agent) # 挂载并行节点

workflow.set_entry_point("supervisor")

workflow.add_conditional_edges(
    "supervisor",
    lambda x: x["next_agent"],
    {
        "sequence_analyst": "sequence_analyst",
        "equipment_engineer": "equipment_engineer",
        "compliance_officer": "compliance_officer",
        "parallel_exec": "parallel_exec",
        "FINISH": END
    }
)

workflow.add_edge("sequence_analyst", "supervisor")
workflow.add_edge("equipment_engineer", "supervisor")
workflow.add_edge("compliance_officer", "supervisor")
workflow.add_edge("parallel_exec", "supervisor")

# 开启 HITL：在合规专家审核前强制中断，等待人工介入
memory = MemorySaver()
multi_agent_app = workflow.compile(
    checkpointer=memory,
    interrupt_before=["compliance_officer"]
)