# TCM Inquiry Assistant (Report Version)

一个基于 **LangChain + 规则状态机 + BM25-RAG + SFT/LoRA 本地抽取实验链** 的 **中医问诊辅助系统**。

本项目定位为：

> **中医问诊辅助系统 / 中医问诊辅助模型**

不是医疗诊断模型，不输出确定性诊断结论。  
系统重点在于：

- 多轮问诊
- 状态累计
- 核心字段优先追问
- 风险提示
- 结构化最终结果输出
- RAG 检索增强
- SFT / LoRA 单轮结构化抽取实验
- 本地推理链验证

---

## 1. 项目定位与边界

本项目不是医疗诊断系统，不输出确定性诊断结果。  
当前系统的职责是：

- 收集问诊信息
- 进行多轮状态累计
- 优先补齐核心字段
- 识别高风险信号
- 在问诊结束后输出结构化结果
- 通过 RAG 增强结果解释与建议
- 通过 SFT / LoRA 改善单轮结构化抽取能力

### 当前明确边界

- 不做确定性诊断
- 不替代医生
- 不输出医疗处方
- 最终流程控制由程序负责，不完全依赖模型自由发挥
- RAG 当前只增强 `impression / advice`，不进入主状态机
- SFT / LoRA 当前只训练“单轮结构化抽取”，不重训整个系统

---

## 2. 已完成能力总览

当前项目已完成以下模块：

### 2.1 问诊主流程（report 版本）
已完成：

- 多轮问诊
- 累计状态 `RunState`
- 单轮结构化输出 `TurnOutput`
- 核心字段优先追问
- 风险识别与规则兜底
- 结束后生成 `FinalReport`

### 2.2 三态槽位设计
统一采用：

- `unknown`
- `none`
- `present`

适用于：

- `symptoms_status`
- `risk_flags_status`

并且明确：

- 空列表不等于未确认
- 必须由 `status` 字段表达确认状态

### 2.3 主诉与规则清洗
已完成：

- 泛化主诉过滤
- 弱有效主诉保留
- 主诉清洗函数
- duration 覆盖逻辑
- 否定句风险识别
- 并列否定识别
- 普通发热与持续高热区分
- 症状升级后风险重确认

### 2.4 FinalReport 结果层
问诊结束后输出：

- `summary`
- `impression`
- `advice`
- `triage_level`
- `info_complete`
- `missing_core_fields`
- `followup_needed`

### 2.5 BM25-RAG 检索增强
已完成：

- 本地知识库
- BM25 检索
- 基于主诉 / 风险状态生成 query
- 增强 `FinalReport.impression`
- 增强 `FinalReport.advice`

### 2.6 SFT / LoRA 实验链
已完成：

- SFT 数据集格式设计
- raw / processed 数据构建
- messages 格式转换
- manual-only 训练集筛选
- LoRA 本地训练
- adapter 保存
- adapter 推理测试
- 推理后规则纠偏
- 本地 SFT 独立运行入口

### 2.7 评估与调试
已完成：

- 测试集 `tests/report_test_cases.json`
- `scripts/eval_report.py`
- API 主链测试
- SFT 样本验证
- 推理链调试输出
- 失败样本定位与规则修复

---

## 3. 项目目录结构

```text id="wsk11u"
app/
  chains/
    report_chain.py
    rag_enhancer.py
    sft_infer_chain.py

  prompts/
    report_prompt.py
    rag_prompt.py
    sft_prompt.py

  rag/
    rag_retriever.py
    knowledge_base.txt

  schemas/
    report_schemas.py
    sft_schemas.py

  utils/
    sft_postprocess.py

scripts/
  run_report.py
  run_sft.py
  eval_report.py
  build_sft_dataset.py
  convert_sft_dataset.py
  filter_sft_manual_only.py
  train_sft_lora.py
  test_sft_lora_infer.py
  test_sft_chain.py

tests/
  report_test_cases.json
  sft_test_cases.json

docs/
  report_current_rules.md
  sft_data_design.md
  sft_training_plan.md

data/
  sft/
    raw/
    processed/