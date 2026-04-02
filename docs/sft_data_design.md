# SFT 数据集设计文档

## 1. 目标

当前项目的 SFT / LoRA 目标不是替代整个问诊系统，而是训练一个**单轮结构化抽取器**。

### 输入
- `state_json`: 当前轮之前的累计状态
- `user_input`: 当前轮用户输入

### 输出
- 标准 `TurnOutput` 风格 JSON

## 2. 当前任务边界

- 项目是“中医问诊辅助系统”，不是诊断模型
- 模型负责本轮抽取
- 程序负责流程控制
- `next_question` 最终由程序决定
- `FinalReport` 仍由程序生成
- RAG 只增强 `impression / advice`

## 3. 数据主格式

主格式建议使用 `jsonl`，每行一个样本。

```json
{
  "task": "report_turn_extraction",
  "id": "sft_0001",
  "system_prompt": "...",
  "input": {
    "state_json": {...},
    "user_input": "我肚子疼两天了，还有点腹泻。"
  },
  "output": {
    "chief_complaint": "肚子疼",
    "duration": "两天",
    "symptoms": ["腹泻"],
    "symptoms_status": "present",
    "risk_flags": [],
    "risk_flags_status": "unknown",
    "next_question": null,
    "summary": "..."
  },
  "meta": {
    "source": "manual",
    "difficulty": "easy",
    "tags": ["single_turn", "chief_complaint"]
  }
}
```

## 4. 字段说明

### 顶层字段
- `task`: 当前固定为 `report_turn_extraction`
- `id`: 样本唯一 ID
- `system_prompt`: 训练时使用的系统提示词
- `input`: 输入内容
- `output`: 标准标签
- `meta`: 来源、难度、标签等信息

### input
- `state_json`: 历史累计状态
- `user_input`: 当前轮用户输入

### output
- `chief_complaint`
- `duration`
- `symptoms`
- `symptoms_status`
- `sleep`
- `appetite`
- `stool_urine`
- `risk_flags`
- `risk_flags_status`
- `next_question`
- `summary`

## 5. 三态规则

统一三态：
- `unknown`
- `none`
- `present`

原则：
- 空列表不等于已确认没有
- 是否确认取决于 `status`
- 数据标注必须和线上规则一致

## 6. 标签体系

### 轮次类型
- `single_turn`
- `multi_turn_context`

### 抽取类型
- `chief_complaint`
- `duration`
- `symptom_present`
- `symptom_none`
- `risk_present`
- `risk_none`
- `risk_unknown`

### 错误专项
- `generic_complaint_invalid`
- `weak_valid_complaint`
- `negation_detection`
- `parallel_negation`
- `fever_not_high_risk`
- `none_to_present`
- `risk_recheck_after_symptom_upgrade`
- `new_risk_added_later`

## 7. 首批优先覆盖的错误类型

1. 泛化主诉误判
2. 否定句高危误判
3. 并列否定误判
4. 普通发热误判持续高热
5. `unknown -> none`
6. `unknown -> present`
7. `none -> present`
8. 症状升级后风险重确认
9. 后续新增高危
10. 弱有效主诉

## 8. 数据来源建议

### 第一来源
- `tests/report_test_cases.json`

### 第二来源
- 当前多轮调试日志

### 第三来源
- 人工补充专项难例

## 9. 数据规模建议

### 第一阶段
- 80 ~ 150 条高质量样本
- 先验证格式、训练脚本和 LoRA 是否有效

### 第二阶段
- 300 ~ 800 条

## 10. 训练集 / 验证集 / 错误专项集

### 训练集
- 覆盖面尽量广

### 验证集
- 留困难样本
- 同一个 case 的不同轮最好不要打散到 train / val 两边

### 错误专项集
- 否定句
- 并列否定
- 发热误抽高热
- 泛化主诉
- `none -> present`

## 11. 关键标注原则

SFT 标签应当尽量体现**当前系统认为的正确结果**，而不是复刻历史模型错误。

例如：
- 旧模型把“发热”误抽成“持续高热”
- 当前标签必须写成修正规则后的正确输出，而不是把历史错误当标签