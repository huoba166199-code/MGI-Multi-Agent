import streamlit as st
import uuid
import io
from agent.graph import mgi_agent_part1, mgi_agent_part2
from agent.observability import set_trace_id, audit

# 尝试导入 docx，如果没有安装则降级
try:
    from docx import Document

    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

st.set_page_config(page_title="MGI Multi-Agent 协同中枢", page_icon="🧬", layout="wide")

# ==========================================
# 侧边栏：身份与历史记忆
# ==========================================
with st.sidebar:
    st.header("👤 当前身份")
    role = st.radio("切换视角演示", ["发起人 (实验员)", "审批人 (科室主管)"])

    st.divider()

    st.header("🗂️ 历史签发记录")
    if "history" not in st.session_state:
        st.session_state.history = []

    if not st.session_state.history:
        st.caption("暂无历史记录")
    else:
        for idx, record in enumerate(reversed(st.session_state.history)):
            if st.button(f"📄 {record['title']}", key=f"hist_{idx}", use_container_width=True):
                st.session_state.current_view = record
                st.rerun()

st.title("🧬 MGI Multi-Agent 协同中枢")

# 初始化状态
if "messages" not in st.session_state:
    st.session_state.messages = []
if "waiting_approval" not in st.session_state:
    st.session_state.waiting_approval = False
if "current_state" not in st.session_state:
    st.session_state.current_state = {}
if "retry_count" not in st.session_state:
    st.session_state.retry_count = 0
if "has_run" not in st.session_state:
    st.session_state.has_run = False
if "user_prompt" not in st.session_state:
    st.session_state.user_prompt = ""
if "current_view" not in st.session_state:
    st.session_state.current_view = None
# 【新增】：持久化 trace_id
if "trace_id" not in st.session_state:
    st.session_state.trace_id = ""

# ==========================================
# 视图 1：历史记录查看模式
# ==========================================
if st.session_state.current_view is not None:
    record = st.session_state.current_view
    st.info(f"📂 正在查看历史记录：**{record['title']}**")
    with st.container(border=True):
        st.markdown(record['final_report'])
    if st.button("⬅️ 返回当前工作台"):
        st.session_state.current_view = None
        st.rerun()
    st.stop()

# ==========================================
# 视图 2：当前工作台（渲染历史对话）
# ==========================================
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# ==========================================
# 视图 3：发起新任务
# ==========================================
if not st.session_state.waiting_approval and not st.session_state.has_run:
    if prompt := st.chat_input("请输入指令（例如：帮我处理一批新样本，顺便查一下机器故障）..."):
        st.session_state.user_prompt = prompt

        # 【修复】：保存到 session_state 并展示
        st.session_state.trace_id = set_trace_id()
        st.caption(f"当前链路 Trace ID: `{st.session_state.trace_id}`")

        st.chat_message("user").write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.status("主管 Agent 正在并发调度专家...", expanded=True) as status:
            st.write("🛠️ 唤醒设备排障专家...")
            st.write("🧬 唤醒生信分析专家...")

            # 【修复】：执行前强制重新注入 trace_id
            set_trace_id(st.session_state.trace_id)
            res = mgi_agent_part1.invoke({"messages": [prompt]})

            st.write("✅ 专家并发执行完毕。")
            status.update(label="双专家结果已汇总", state="complete", expanded=False)

        st.session_state.current_state = res
        st.session_state.waiting_approval = True
        st.session_state.has_run = True
        st.rerun()

# ==========================================
# 视图 4：审批区
# ==========================================
if st.session_state.waiting_approval:
    res = st.session_state.current_state
    eq_draft = res.get("equipment_report", "无")
    seq_draft = res.get("sequence_report", "无")

    st.info(f"📋 **双专家并发执行结果（当前重试次数：{st.session_state.retry_count}）**")
    col_a, col_b = st.columns(2)
    with col_a:
        with st.container(border=True):
            st.markdown("### 🛠️ 设备排障专家草稿")
            st.write(eq_draft)
    with col_b:
        with st.container(border=True):
            st.markdown("### 🧬 生信分析专家草稿")
            st.write(seq_draft)

    st.divider()

    if role == "发起人 (实验员)":
        st.warning("⚠️ 报告已提交，等待主管审核。")
    else:
        st.warning("⚠️ 触发合规审核，请主管操作。")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ 主管批准：整合并签发", type="primary", use_container_width=True):
                audit(operator_id="supervisor_01", role="supervisor", action="approve", target="task_001",
                      decision="approved")
                with st.spinner("合规专家正在融合报告..."):
                    # 【修复】：执行前强制重新注入 trace_id
                    set_trace_id(st.session_state.trace_id)
                    final_res = mgi_agent_part2.invoke({"equipment_report": eq_draft, "sequence_report": seq_draft})
                    final_doc = final_res.get("final_report", "报告生成失败")

                    st.chat_message("assistant").write("### ✅ 最终报告（已签发）\n\n" + final_doc)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": "### ✅ 最终报告（已签发）\n\n" + final_doc})

                    st.session_state.history.append({
                        "title": st.session_state.user_prompt[:15] + "...",
                        "final_report": final_doc,
                        "date": "刚刚"
                    })

                    st.session_state.waiting_approval = False
                    st.session_state.has_run = False
                    st.session_state.retry_count = 0
                    st.rerun()
        with col2:
            if st.button("❌ 驳回：退回重写", use_container_width=True):
                audit(operator_id="supervisor_01", role="supervisor", action="reject", target="task_001",
                      decision="rejected")
                if st.session_state.retry_count >= 2:
                    st.error("🚨 连续驳回已达 2 次，触发物理熔断！流程强制终止，拒绝带病放行！")
                    st.session_state.messages.append(
                        {"role": "assistant", "content": "🚨 连续驳回已达 2 次，触发物理熔断！流程强制终止。"})
                    st.session_state.waiting_approval = False
                    st.session_state.has_run = False
                    st.session_state.retry_count = 0
                    st.rerun()
                else:
                    st.session_state.retry_count += 1
                    st.session_state.waiting_approval = False
                    st.session_state.has_run = False
                    with st.spinner(f"退回重写中（第 {st.session_state.retry_count} 次）..."):

                        # 【修复】：执行前强制重新注入 trace_id
                        set_trace_id(st.session_state.trace_id)
                        res = mgi_agent_part1.invoke(
                            {"messages": [st.session_state.user_prompt, "驳回：报告不完整，请补充临床意义。"]})

                        st.session_state.current_state = res
                        st.session_state.waiting_approval = True
                        st.session_state.has_run = True
                    st.rerun()

# ==========================================
# 视图 5：导出下载区
# ==========================================
if not st.session_state.waiting_approval and len(st.session_state.messages) > 0:
    last_msg = st.session_state.messages[-1]
    if last_msg["role"] == "assistant" and "最终报告" in last_msg["content"]:
        pure_report = last_msg["content"].replace("### ✅ 最终报告（已签发）\n\n", "")
        st.divider()
        st.markdown("#### 📥 报告导出与归档")
        st.caption("根据医疗合规要求，请下载并打印报告，由主管签字后归档。")

        col_down1, col_down2 = st.columns(2)
        with col_down1:
            st.download_button(
                label="📄 下载 Markdown 报告",
                data=pure_report,
                file_name=f"mgi_report_{uuid.uuid4().hex[:6]}.md",
                mime="text/markdown",
                use_container_width=True
            )
        with col_down2:
            if HAS_DOCX:
                doc = Document()
                doc.add_heading('MGI Multi-Agent 最终签发报告', 0)
                doc.add_paragraph(pure_report)
                bio = io.BytesIO()
                doc.save(bio)
                st.download_button(
                    label="📝 下载 Word (docx) 报告",
                    data=bio.getvalue(),
                    file_name=f"mgi_report_{uuid.uuid4().hex[:6]}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
            else:
                st.info("💡 提示：安装 `python-docx` 即可解锁 Word 导出功能。")