from .state import AgentState
from .observability import node_logger, log_event, app_logger
from langchain_deepseek import ChatDeepSeek
import os
from dotenv import load_dotenv

# 【新增引入】导入我们刚刚写好的设备专家子图包装节点
# 注意：需要确保你已经在 agent/ 目录下新建了 equipment_agent.py
from .equipment_agent import equipment_agent_node

load_dotenv()

llm = ChatDeepSeek(
    api_key=os.getenv("LLM_API_KEY"),
    api_base=os.getenv("LLM_API_BASE", "https://api.deepseek.com"),
    model=os.getenv("LLM_MODEL", "deepseek-chat")
)

# ==========================================
# 设备专家：直接使用子图，把名字伪装成原来的函数
# ==========================================
# 这样 graph.py 里的 parallel_exec 就不需要改调用了
equipment_engineer_node = equipment_agent_node


# ==========================================
# 生信专家：保持你原来的代码不变
# ==========================================
@node_logger("sequence_analyst")
def sequence_analyst_node(state: AgentState):
    messages = state.get("messages", [])
    user_input = messages[0] if messages else ""
    # 检查是否带着驳回意见
    reject_msg = messages[-1] if len(messages) > 1 and "驳回" in messages[-1] else ""

    prompt = f"你是资深生信专家。用户的原始指令是：'{user_input}'。请给出一段针对样本的基因变异解读分析草稿（约100字）。"
    if reject_msg:
        prompt += f"\n注意！主管驳回了你上一版的报告，理由是：{reject_msg}。请务必改正！"

    response = llm.invoke(prompt)
    return {"sequence_report": response.content}


# ==========================================
# 合规签发专家：保持你原来的代码不变
# ==========================================
@node_logger("compliance_officer")
def compliance_officer_node(state: AgentState):
    eq_rep = state.get("equipment_report", "")
    seq_rep = state.get("sequence_report", "")
    prompt = f"你是合规签发专家。请整合设备排障报告和生信分析报告，生成最终签发版报告。\n设备：{eq_rep}\n生信：{seq_rep}"
    response = llm.invoke(prompt)
    return {"final_report": response.content}