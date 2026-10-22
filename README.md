[![Multi-Agent CI Tests](https://github.com/huoba166199-code/MGI-Multi-Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/huoba166199-code/MGI-Multi-Agent/actions/workflows/ci.yml)

# 🧬 MGI Multi-Agent 协同中枢 (Supervisor 架构)

这是一个面向基因测序全链路的 **多智能体并发协同系统**。系统基于 **LangGraph** 构建，实现了复杂医疗业务流的自动化调度、嵌套子图执行与人工在环审核。

## ✨ 核心特性
- **Supervisor 架构**：主管 Agent 动态感知全局状态，智能派发任务。
- **并发执行 (Parallel Execution)**：支持同时调度设备排障专家与生信解读专家，利用 `operator.add` 实现状态安全合并。
- **嵌套子图 (Nested Subgraph)**：将复杂的生信分析（VCF解析与ACMG评级）封装为独立子图，实现高度模块化。
- **物理熔断与 TDD**：通过 Pytest 驱动开发，抓出并封堵了“带病放行”的重试耗尽漏洞，确保审核未通过时绝对阻断。
- **HITL 人工审核**：利用 `interrupt_before` 机制，在合规签发前强制暂停，等待人工介入。

## 🚀 快速启动
1. 配置 `.env` (包含 `LLM_API_KEY` 等)
2. 一键构建并启动：`docker compose up -d --build`
3. 访问 `http://localhost:8503`

## 🧪 测试驱动 (TDD)
运行 `pip install pytest` 后，执行 `pytest tests/ -v`，5 个核心业务流测试用例全部通过。
