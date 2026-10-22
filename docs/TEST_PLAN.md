# MGI-Multi-Agent 测试计划 (Supervisor 架构)

## 1. 测试目标
验证多智能体协同中枢在复杂业务流下的稳定性，重点覆盖：Supervisor 路由逻辑、并行节点状态合并、嵌套子图执行、HITL 中断恢复机制以及极端异常熔断。

## 2. 核心测试分层

| 测试层级 | 测试重点 | 工具 |
| :--- | :--- | :--- |
| **单元测试 (Unit)** | `supervisor_node` 的纯逻辑路由（不调 LLM，直接用 Mock State 测） | Pytest |
| **集成测试 (Integration)** | 并行节点 (`parallel_exec`) 和子图的执行与状态回传 | Pytest + LangGraph |
| **HITL 测试** | `interrupt_before=["compliance_officer"]` 的挂起与恢复 | Pytest + MemorySaver |
| **对抗与异常** | 底层报错触发 `error_msg`、重试次数超限（`retry>=2`）死锁问题 | Pytest |

## 3. 核心测试用例矩阵

### 3.1 路由分发逻辑 (Supervisor)
- [ ] **用例 R-01**: 初始状态 `eq_done=False`, `seq_done=False` -> 应路由至 `parallel_exec`。
- [ ] **用例 R-02**: 只有生信未做 (`eq_done=True`, `seq_done=False`) -> 应路由至 `sequence_analyst`。
- [ ] **用例 R-03**: 合规驳回 1 次 (`audit_passed=False`, `comp_done=True`, `retry=0`) -> 应路由至 `sequence_analyst` 且 `retry_count+1`。
- [ ] **用例 R-04**: 触发异常 (`error_msg="VCF读取失败"`) -> 应强制路由至 `FINISH`，跳过所有专家。
- [ ] **用例 R-05**: (发现Bug) 合规驳回 3 次 (`retry=2`) -> 期望：应触发物理熔断退出，实际：可能死锁/抛错。

### 3.2 并行执行与状态合并
- [ ] **用例 P-01**: 并行节点同时修改 `messages`，验证 `Annotated[list, operator.add]` 是否正确合并，没有互相覆盖。
- [ ] **用例 P-02**: 嵌套子图（生信专家）执行完毕后，是否正确将 `sequence_done=True` 和 `report_draft` 回传给主图。

### 3.3 HITL 中断与恢复
- [ ] **用例 H-01**: 生信专家完成后，流转到 `compliance_officer` 之前，验证图是否抛出中断（`state.next` 应为 `compliance_officer`）。
- [ ] **用例 H-02**: 模拟人工恢复执行（`Command(resume=True)`），验证合规专家节点是否能继续执行。

## 4. 准入与准出标准
- **准出**：P0 用例 100% 通过，修复 `retry>=2` 时的死锁 Bug，CI 流水线跑通。
