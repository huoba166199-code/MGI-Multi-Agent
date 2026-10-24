from langgraph.graph import StateGraph, END
from .state import AgentState
from .workers import equipment_engineer_node, sequence_analyst_node, compliance_officer_node


def parallel_exec(state: AgentState):
    # 如果携带了驳回意见，生信专家必须重新分析
    messages = state.get("messages", [])
    reject_msg = messages[-1] if messages else ""

    eq_res = equipment_engineer_node(state)
    seq_res = sequence_analyst_node(state)
    return {"equipment_report": eq_res.get("equipment_report"), "sequence_report": seq_res.get("sequence_report")}


workflow1 = StateGraph(AgentState)
workflow1.add_node("parallel_exec", parallel_exec)
workflow1.set_entry_point("parallel_exec")
workflow1.add_edge("parallel_exec", END)
mgi_agent_part1 = workflow1.compile()

workflow2 = StateGraph(AgentState)
workflow2.add_node("compliance_officer", compliance_officer_node)
workflow2.set_entry_point("compliance_officer")
workflow2.add_edge("compliance_officer", END)
mgi_agent_part2 = workflow2.compile()