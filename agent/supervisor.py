from .state import AgentState
import os
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek

load_dotenv()

llm = ChatDeepSeek(
    api_key=os.getenv("LLM_API_KEY"),
    api_base=os.getenv("LLM_API_BASE", "https://api.deepseek.com"),
    model=os.getenv("LLM_MODEL", "deepseek-chat")
)


def supervisor_node(state: AgentState):
    print("👨‍💼 [主管 Agent] 正在根据当前进度派发任务...")

    retry = state.get("retry_count", 0)
    audit_passed = state.get("audit_passed")
    eq_done = state.get("equipment_done", False)
    seq_done = state.get("sequence_done", False)
    comp_done = state.get("compliance_done", False)

    # 1. 如果底层工具（如子图读取文件）崩溃，直接终止并告警
    if state.get("error_msg"):
        print("🚨 主管告警：底层工具执行异常，强制终止！")
        return {"next_agent": "FINISH", "task_completed": False}

    # 2. 物理熔断逻辑：全部完成且合规
    if eq_done and seq_done and comp_done and audit_passed:
        print("🎉 主管确认：任务已完成且合规，强制结束流程。")
        return {"next_agent": "FINISH", "task_completed": True}

    # 3. 审核驳回，且还有重试机会：打回重写
    if audit_passed is False and comp_done and retry < 2:
        print(f"🔄 主管拦截：审核未通过，强制打回生信专家重写 (第 {retry + 1} 次)...")
        return {"next_agent": "sequence_analyst", "retry_count": retry + 1, "compliance_done": False}

    # 【新增修复逻辑 4】：审核未通过，且重试次数已耗尽（>=2次）
    if comp_done and audit_passed is False and retry >= 2:
        print("❌ 主管阻断：合规审核连续 3 次未通过，强制终止任务，拒绝带病放行！")
        return {
            "next_agent": "FINISH",
            "task_completed": False,
            "error_msg": "合规连续驳回，系统已强制阻断发布。"
        }

    # 5. 并行调度
    if not eq_done and not seq_done:
        print("👉 主管决策：并行调度设备排障与生信解读。")
        return {"next_agent": "parallel_exec"}

    # 6. 单独调度
    if not eq_done: return {"next_agent": "equipment_engineer"}
    if not seq_done: return {"next_agent": "sequence_analyst"}
    if seq_done and not comp_done: return {"next_agent": "compliance_officer"}

    # 兜底（正常情况下不会走到这里）
    return {"next_agent": "FINISH", "task_completed": False}