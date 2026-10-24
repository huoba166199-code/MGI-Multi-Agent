import pytest
from agent.equipment_agent import intent_router

def test_equipment_intent_inspection():
    """测试：常规巡检意图（未提供报错码）"""
    queries = [
        "帮我处理一批新样本，顺便查一下机器故障",
        "看看测序仪状态",
        "做个常规巡检"
    ]
    for q in queries:
        state = {"query": q}
        result = intent_router(state)
        assert result["task_type"] == "inspection"
        assert "巡检" in result["intent_reason"] or "顺便查" in result["intent_reason"]

def test_equipment_intent_troubleshooting():
    """测试：具体排障意图（命中了具体故障规则）"""
    queries = [
        "仪器报了 ERR-503 错误",
        "测序仪有异响，帮我看看",
        "机器卡死中断了"
    ]
    for q in queries:
        state = {"query": q}
        result = intent_router(state)
        assert result["task_type"] == "troubleshooting"
        assert "故障" in result["intent_reason"]

def test_equipment_intent_fallback():
    """测试：兜底逻辑（未命中规则，但包含设备关键词，默认转巡检）"""
    state = {"query": "设备故障"}
    result = intent_router(state)
    assert result["task_type"] == "inspection"
    assert "默认巡检" in result["intent_reason"]