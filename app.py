import streamlit as st
import uuid
from agent.graph import multi_agent_app
from langgraph.types import Command
import json

st.set_page_config(page_title="MGI Multi-Agent 协同中枢", page_icon="🏥", layout="wide")
st.title("🏥 华大基因测序全链路协同中枢 (Multi-Agent)")
st.caption("架构特性：并发执行 | 嵌套子图 | 结构化输出 | HITL人工审核")

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "history" not in st.session_state:
    st.session_state.history = []

config = {"configurable": {"thread_id": st.session_state.thread_id}}

# 渲染历史对话
for msg in st.session_state.history:
    role = "user" if msg.startswith("用户:") else "assistant"
    if role == "assistant" and msg.startswith("[变异解读专家]:"):
        # 【美化】如果是生信专家的 JSON，前端做个漂亮的解析展示
        try:
            json_str = msg.split("[变异解读专家]: ")[1]
            data = json.loads(json_str)
            st.chat_message("assistant").write(
                f"**[变异解读专家] 结构化分析结果：**\n- **基因**: {data.get('gene')}\n- **变异**: {data.get('variant')}\n- **评级**: `{data.get('acmg_level')}`\n- **摘要**: {data.get('summary')}")
        except:
            st.chat_message("assistant").write(msg)
    else:
        st.chat_message(role).write(msg)

# 【核心修复】：从图状态中判断是否挂起
state_info = multi_agent_app.get_state(config)
is_interrupted = bool(state_info.next and "compliance_officer" in state_info.next)

if not is_interrupted:
    if prompt := st.chat_input("请输入业务需求..."):
        st.session_state.history.append(f"用户: {prompt}")

        initial_state = {
            "messages": st.session_state.history.copy(),
            "device_id": "MGI-T7-001",
            "vcf_path": "/data/tumor_sample_01.vcf"
        }

        with st.spinner("多智能体并发协作中..."):
            # 使用 stream 实时获取各个节点的输出
            for event in multi_agent_app.stream(initial_state, config=config):
                for node_name, node_state in event.items():
                    if "messages" in node_state:
                        for new_msg in node_state["messages"]:
                            if new_msg not in st.session_state.history:
                                st.session_state.history.append(new_msg)

        # 这里的 rerun 是必须的，它会让页面刷新并重新去读 get_state
        st.rerun()

# 当图处于挂起状态时，渲染审批 UI
if is_interrupted:
    st.warning("⚠️ 报告已生成并完成结构化。**需要主管人工审核确认后，方可签发。**")
    if st.button("✅ 批准签发", type="primary", use_container_width=True):
        with st.spinner("恢复图执行，签发中..."):
            # 恢复图，这会触发合规专家节点运行
            multi_agent_app.invoke(Command(resume=True), config=config)
            # 因为合规专家只是打勾，没有新消息，我们需要手动补一句，或者直接让图跑完
            st.rerun()