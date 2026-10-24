from typing import TypedDict

class AgentState(TypedDict):
    messages: list
    equipment_report: str
    sequence_report: str
    final_report: str
    error_msg: str