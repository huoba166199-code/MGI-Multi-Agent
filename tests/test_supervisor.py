import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.supervisor import supervisor_node
from agent.state import AgentState

def create_state(**kwargs) -> AgentState:
    base_state = {
        "messages": [],
        "next_agent": "",
        "device_id": "",
        "vcf_path": "",
        "report_draft": "",
        "task_completed": False,
        "audit_passed": False,
        "retry_count": 0,
        "equipment_done": False,
        "sequence_done": False,
        "compliance_done": False,
        "error_msg": ""
    }
    base_state.update(kwargs)
    return base_state

def test_initial_parallel_dispatch():
    """R-01: 初始状态（设备未做、生信未做），必须走向并行执行"""
    state = create_state()
    result = supervisor_node(state)
    assert result["next_agent"] == "parallel_exec"

def test_compliance_retry_dispatch():
    """R-02: 合规驳回且 retry<2，应打回生信重写，并清空合规状态"""
    state = create_state(
        equipment_done=True, 
        sequence_done=True, 
        compliance_done=True, 
        audit_passed=False, 
        retry_count=0
    )
    result = supervisor_node(state)
    assert result["next_agent"] == "sequence_analyst"
    assert result["retry_count"] == 1
    assert result["compliance_done"] is False

def test_error_handling():
    """R-03: 底层工具报错，必须直接熔断 FINISH，且任务状态必须是未完成(False)"""
    state = create_state(error_msg="子图读取VCF崩溃")
    result = supervisor_node(state)
    assert result["next_agent"] == "FINISH"
    # 【修正】：异常阻断的任务，绝不能算作完成
    assert result["task_completed"] is False 

def test_successful_completion():
    """R-04: 所有节点都完成，且合规审核通过，必须正常结束"""
    state = create_state(
        equipment_done=True, 
        sequence_done=True, 
        compliance_done=True, 
        audit_passed=True
    )
    result = supervisor_node(state)
    assert result["next_agent"] == "FINISH"
    assert result["task_completed"] is True

def test_max_retry_compliance_failed():
    """R-05: 连续驳回达到上限(2次)后，必须阻断发布，绝不能带病放行"""
    state = create_state(
        equipment_done=True, 
        sequence_done=True, 
        compliance_done=True, 
        audit_passed=False, 
        retry_count=2
    )
    result = supervisor_node(state)
    assert result.get("task_completed") is False, "致命业务漏洞：审核未通过，但系统却将任务标记为完成并放行！"
