import pytest
from unittest.mock import patch, MagicMock
from agent.graph import mgi_agent_part1
from agent.workers import compliance_officer_node


# ==========================================
# 测试 1：并行节点状态合并（拦截 graph 里的节点）
# ==========================================
@patch("agent.graph.sequence_analyst_node")
@patch("agent.graph.equipment_engineer_node")
def test_parallel_exec_merge(mock_eq_node, mock_seq_node):
    """测试：并行节点能否正确合并两个专家的返回状态"""
    # 模拟设备专家返回
    mock_eq_node.return_value = {"equipment_report": "Mock: 设备巡检正常"}
    # 模拟生信专家返回
    mock_seq_node.return_value = {"sequence_report": "Mock: 检出 BRCA1 变异"}

    # 运行 part1 图
    initial_state = {"messages": ["测试指令"]}
    result = mgi_agent_part1.invoke(initial_state)

    # 断言：状态没有互相覆盖
    assert result["equipment_report"] == "Mock: 设备巡检正常"
    assert result["sequence_report"] == "Mock: 检出 BRCA1 变异"

    # 断言：节点确实被调用了
    mock_eq_node.assert_called_once()
    mock_seq_node.assert_called_once()


# ==========================================
# 测试 2：合规节点的 Prompt 拼接与返回
# ==========================================
@patch("agent.workers.llm")
def test_compliance_officer_merge(mock_llm):
    """测试：合规节点能否将两份报告整合成最终报告"""
    # 模拟大模型的返回对象
    mock_response = MagicMock()
    mock_response.content = "Mock: 最终签发版报告"
    mock_llm.invoke.return_value = mock_response

    # 直接调用合规节点
    input_state = {
        "messages": [],
        "equipment_report": "设备跑得飞快",
        "sequence_report": "检出 TP53 变异"
    }
    result = compliance_officer_node(input_state)

    # 断言1：返回结果正确
    assert result["final_report"] == "Mock: 最终签发版报告"

    # 断言2：检查传给大模型的 Prompt 是否真的包含了这两份草稿
    args, _ = mock_llm.invoke.call_args
    prompt_sent_to_llm = args[0]
    assert "设备跑得飞快" in prompt_sent_to_llm
    assert "检出 TP53 变异" in prompt_sent_to_llm