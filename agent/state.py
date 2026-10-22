from typing import TypedDict, List, Annotated
import operator

class AgentState(TypedDict):
    messages: Annotated[List[str], operator.add]
    next_agent: str
    device_id: str
    vcf_path: str
    report_draft: str
    task_completed: bool
    audit_passed: bool
    retry_count: int
    equipment_done: bool
    sequence_done: bool
    compliance_done: bool
    # === 新增：用于记录 Tool 执行的异常信息 ===
    error_msg: str