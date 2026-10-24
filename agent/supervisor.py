from .state import AgentState
import os
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from .observability import node_logger, log_event, app_logger

load_dotenv()

llm = ChatDeepSeek(
    api_key=os.getenv("LLM_API_KEY"),
    api_base=os.getenv("LLM_API_BASE", "https://api.deepseek.com"),
    model=os.getenv("LLM_MODEL", "deepseek-chat")
)

@node_logger("supervisor")
def supervisor_node(state: AgentState):
    retry = state.get("retry_count", 0)
    audit_passed = state.get("audit_passed")
    eq_done = state.get("equipment_done", False)
    seq_done = state.get("sequence_done", False)
    comp_done = state.get("compliance_done", False)

    # 1. 异常短路熔断
    if state.get("error_msg"):
        log_event(app_logger, "route_decision", "supervisor route",
                  next_agent="FINISH", reason="error_short_circuit",
                  error_msg=state.get("error_msg"))
        return {"next_agent": "FINISH", "task_completed": False}

    # 2. 成功完成
    if eq_done and seq_done and comp_done and audit_passed:
        log_event(app_logger, "route_decision", "supervisor route",
                  next_agent="FINISH", reason="all_done_finish")
        return {"next_agent": "FINISH", "task_completed": True}

    # 3. 合规打回重试
    if audit_passed is False and comp_done and retry < 2:
        log_event(app_logger, "route_decision", "supervisor route",
                  next_agent="sequence_analyst", reason="audit_rejected_retry",
                  retry_count=retry + 1)
        return {"next_agent": "sequence_analyst", "retry_count": retry + 1, "compliance_done": False}

    # 4. 重试耗尽，强制熔断
    if comp_done and audit_passed is False and retry >= 2:
        log_event(app_logger, "circuit_break", "retry exhausted, force finish",
                  retry_count=retry, error_msg="合规连续驳回，强制阻断发布")
        return {
            "next_agent": "FINISH", 
            "task_completed": False, 
            "error_msg": "合规连续驳回，系统已强制阻断发布。"
        }

    # 5. 初始并行调度
    if not eq_done and not seq_done:
        log_event(app_logger, "route_decision", "supervisor route",
                  next_agent="parallel_exec", reason="initial_parallel")
        return {"next_agent": "parallel_exec"}

    # 6. 单点调度兜底
    if not eq_done: 
        log_event(app_logger, "route_decision", "supervisor route", next_agent="equipment_engineer", reason="eq_pending")
        return {"next_agent": "equipment_engineer"}
    if not seq_done: 
        log_event(app_logger, "route_decision", "supervisor route", next_agent="sequence_analyst", reason="seq_pending")
        return {"next_agent": "sequence_analyst"}
    if seq_done and not comp_done: 
        log_event(app_logger, "route_decision", "supervisor route", next_agent="compliance_officer", reason="compliance_pending")
        return {"next_agent": "compliance_officer"}
    
    return {"next_agent": "FINISH", "task_completed": False}
