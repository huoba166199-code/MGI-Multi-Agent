# MGI-Multi-Agent 协同中枢 — 工程踩坑与解决文档

## 一、 环境与依赖问题

**Q1：运行 `pytest` 时提示 `Command 'pytest' not found`？**
- **原因**：虽然进入了 `mgi_multi_agent` 的虚拟环境，但环境中尚未安装测试依赖。
- **解决**：不要去用系统级的 `sudo apt install`。直接在当前 conda 环境下执行 `pip install pytest -i https://pypi.tuna.tsinghua.edu.cn/simple` 即可。

**Q2：为什么建议不要直接在 `/mnt/d/` 下跑复杂的 LangGraph 流和测试？**
- **原因**：WSL2 跨系统访问 Windows 盘符（NTFS）时，底层 IO 性能极差，特别是在多智能体并发读写文件、频繁生成 `__pycache__` 或调用模型时，容易卡顿或偶发死锁。
- **解决**：开发初期可以用 `/mnt/d/`，但在跑压力测试或 Docker 构建时，建议 `cp -r /mnt/d/MGI-Multi-Agent ~/` 移到 Linux 原生 ext4 盘。

## 二、 逻辑与测试问题

**Q3：测试用例报 `AssertionError: assert 'parallel_exec' == 'sequence_analyst'`，主管为何乱派任务？**
- **原因**：`state.py` 里定义的字段是全称（如 `equipment_done`），但在写测试 Mock 数据时，为了偷懒写成了简写（`eq_done=True`）。`supervisor.py` 用 `.get("equipment_done")` 读不到值，以为是 False，于是错误地走向了并行调度。
- **解决**：修正测试用例中的字典键名，确保与 `AgentState` 严格一致。

**Q4：发现一个 P0 级业务漏洞：未通过合规审查的报告，被主管标记为“已完成”并放行？**
- **原因**：这是 TDD 抓出来的问题。`supervisor.py` 在合规专家连续驳回 2 次（`retry >= 2`）后，没有写兜底的异常判断。代码顺着逻辑滑落到了最后一行 `return {"next_agent": "FINISH", "task_completed": True}`，导致带病报告直接流出。
- **解决**：增加兜底熔断逻辑。当 `comp_done=True` 且 `audit_passed=False` 且 `retry >= 2` 时，强制返回 `{"next_agent": "FINISH", "task_completed": False, "error_msg": "..."}`。

**Q5：为什么 Supervisor 节点要加上 `state.get("error_msg")` 的判空拦截？**
- **原因**：多智能体嵌套子图时，如果底层生信分析（读取 VCF）崩溃抛出异常，若不在顶层主管处强制熔断（直接 FINISH），系统可能会带着空数据继续流转，导致后续合规专家和 LLM 浪费 Token 去分析空气。
- **解决**：主管节点首要拦截 `error_msg`，一旦有报错，直接终止并设为未完成。

