from .state import AgentState
import os
import json
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END
from typing import TypedDict
from pydantic import BaseModel, Field

load_dotenv()

llm = ChatDeepSeek(
    api_key=os.getenv("LLM_API_KEY"),
    api_base=os.getenv("LLM_API_BASE", "https://api.deepseek.com"),
    model=os.getenv("LLM_MODEL", "deepseek-chat")
)


# ==================== 优化 4：定义结构化输出模型 ====================
class ClinicalReport(BaseModel):
    gene: str = Field(description="变异基因名称")
    variant: str = Field(description="变异位点，如 c.123A>T")
    acmg_level: str = Field(description="ACMG评级，如 Pathogenic, VUS")
    summary: str = Field(description="临床解读摘要")


# ==================================================================

# ==================== 优化 2：工具异常隔离 ====================
class VcfSubState(TypedDict):
    vcf_path: str
    raw_content: str
    analysis_result: str
    sub_error: str


def read_vcf_node(state: VcfSubState):
    print("      [子图] 正在读取 VCF 文件内容...")
    try:
        local_path = os.path.join("data", "tumor_sample_01.vcf")
        if not os.path.exists(local_path):
            raise FileNotFoundError("找不到 VCF 文件")
        with open(local_path, "r", encoding="utf-8") as f:
            return {"raw_content": f.read(), "sub_error": ""}
    except Exception as e:
        print(f"      [子图] ❌ 工具执行失败: {e}")
        return {"raw_content": "", "sub_error": str(e)}  # 捕获异常，不让程序崩溃


def analyze_variant_node(state: VcfSubState):
    if state.get("sub_error"):
        return {"analysis_result": json.dumps({"error": state["sub_error"]})}

    print("      [子图] 正在对变异进行 ACMG 评级...")
    prompt = f"分析以下 VCF 内容，提取基因、变异、ACMG等级和摘要：\n{state['raw_content']}"

    # 强制 LLM 输出 Pydantic 结构
    structured_llm = llm.with_structured_output(ClinicalReport)
    res = structured_llm.invoke([HumanMessage(content=prompt)])

    # 转为 JSON 字符串存入 state，方便下游解析
    return {"analysis_result": res.model_dump_json()}


sub_builder = StateGraph(VcfSubState)
sub_builder.add_node("read_vcf", read_vcf_node)
sub_builder.add_node("analyze", analyze_variant_node)
sub_builder.set_entry_point("read_vcf")
sub_builder.add_edge("read_vcf", "analyze")
sub_builder.add_edge("analyze", END)
sequence_subgraph = sub_builder.compile()


# =============================================================

def sequence_analyst_agent(state: AgentState):
    print("🧬 [生信专家] 启动内部子图流转...")
    sub_res = sequence_subgraph.invoke({"vcf_path": state.get("vcf_path", "")})

    # 如果子图报错，向上传递异常
    if "error" in sub_res['analysis_result']:
        return {"error_msg": "生信子图执行失败", "next_agent": "supervisor"}

    return {
        "messages": [f"[变异解读专家]: {sub_res['analysis_result']}"],
        "report_draft": sub_res['analysis_result'],
        "sequence_done": True,
        "next_agent": "supervisor"
    }


def equipment_engineer_agent(state: AgentState):
    device = state.get("device_id", "未知设备")
    prompt = f"你是售后工程师，{device} 报错流路压力低，请给出简短维修建议。"
    res = llm.invoke([HumanMessage(content=prompt)])
    return {
        "messages": [f"[设备排障专家]: {res.content}"],
        "equipment_done": True,
        "next_agent": "supervisor"
    }


def compliance_officer_agent(state: AgentState):
    print("🛡️ [合规审核专家] 正在审核...")
    draft = state.get("report_draft", "")

    try:
        # 优化 4：解析 JSON，而不是找关键词
        report_data = json.loads(draft)
        if not report_data.get("acmg_level"):
            raise ValueError("缺失 ACMG 等级")
    except Exception:
        print("❌ 审核不通过：报告格式不合规！")
        return {
            "messages": ["[合规审核专家]: 审核不通过！报告结构不合规或缺失字段，打回重写！"],
            "audit_passed": False,
            "compliance_done": True,
            "next_agent": "supervisor"
        }

    print("✅ 审核通过，准备签发。")
    return {
        "messages": ["[合规审核专家]: 报告格式合规，审核通过，已签发。"],
        "audit_passed": True,
        "compliance_done": True,
        "next_agent": "supervisor"
    }


import concurrent.futures


def parallel_execution_agent(state: AgentState):
    print("⚡ [并行节点] 同时启动排障专家和生信专家...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_eq = executor.submit(equipment_engineer_agent, state)
        future_seq = executor.submit(sequence_analyst_agent, state)

        eq_result = future_eq.result()
        seq_result = future_seq.result()

    return {
        "messages": eq_result["messages"] + seq_result["messages"],
        "report_draft": seq_result.get("report_draft", ""),
        "equipment_done": True,
        "sequence_done": True,
        "next_agent": "supervisor"
    }