# P7 Service, Memory & Persistence Design

## 目标
P7 将 P5/P6 已验证的 LangGraph runtime、P6 RAG evidence、安全边界和评估脚本产品化为最小服务闭环：FastAPI、SQLite 持久化、四层记忆、内部工具注册表、结构化 trace、Docker 复现和 gate 验证。

## 前置状态
- P5 Real Runtime Validation: ok/caution 可进入，real LLM provider 不可用时必须记录 caution。
- P6A Knowledge Pipeline: ok。
- P6B Runtime RAG: ok。
- P6C Source Governance: ok 时使用 approved runtime index；未完成时 gate 必须记录 `runtime_source_mode` 和 `p6c_source_governance_status`。

## 产品边界
系统是中医问诊辅助系统，不是诊断系统。它整理主诉、持续时间、伴随症状、睡眠、食欲、二便和风险信号，生成带证据和安全边界的问诊摘要；不诊断、不开方、不替代医生，高风险提示线下就医。

## 分层
- `app/api`: 请求校验、结构化响应、错误处理和 P7 增量端点。
- `app/services/p7_runtime.py`: API sidecar，将 turn/report 写入 P7 storage。
- `app/storage`: SQLite 默认实现和 PostgreSQL schema-ready adapter。
- `app/memory`: L1/L2/L3/L4 四层记忆。
- `app/tools`: P7 内部工具注册、权限和审计。
- `app/observability`: P7 trace schema、metrics 和 exporter。
- `app/rag`: P6 evidence 到 P7 storage record 的映射。

## Known Limitations
PostgreSQL 目前是 schema-ready，不强制生产部署。Docker smoke 依赖本机 Docker CLI。P7 不包含 MCP Server、多 Agent 工作站、医生审核后台、完整前端、GraphRAG、外部医疗 API、Kafka/Celery/Kubernetes 或多租户权限。

## P8/P2 候选项
可在后续阶段考虑真实 PostgreSQL driver、更多匿名 eval case、OpenTelemetry exporter、正式前端和人工审核流程，但不得改变当前医疗安全边界。
