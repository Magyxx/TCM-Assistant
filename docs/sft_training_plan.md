# SFT / LoRA 训练计划（第一版）

## 1. 训练目标

训练 `report_turn_extraction` 单轮结构化抽取任务。

## 2. 训练输入输出

### 输入
- system prompt
- 历史状态 `state_json`
- 当前轮用户输入 `user_input`

### 输出
- 严格 JSON 形式的 `TurnOutput`

## 3. 推荐流程

1. 先构造原始样本：`build_sft_dataset.py`
2. 再转成 messages 格式：`convert_sft_dataset.py`
3. 再做 LoRA 训练：`train_sft_lora.py`
4. 最后用 `eval_sft_extract.py` 跑核心字段一致性评估

## 4. 首批实验建议

- 先用小模型验证流程是否通
- 先不追求极高分
- 先看以下错误是否下降：
  - 泛化主诉误判
  - 否定句高危误判
  - 并列否定误判
  - 发热误抽持续高热

## 5. 推荐命令

```bash
python scripts/build_sft_dataset.py
python scripts/convert_sft_dataset.py
python scripts/train_sft_lora.py --model-name Qwen/Qwen2.5-1.5B-Instruct --bf16
```

## 6. 当前训练脚本说明

训练脚本使用：
- `transformers.Trainer`
- `peft.LoraConfig`
- `datasets.Dataset`

当前是一个偏稳的“先跑通版本”，适合你先把流程搭起来。

## 7. 后续可升级方向

- 换成 TRL 的 `SFTTrainer`
- 只训练 assistant 区段损失
- 增加更细粒度的字段级评估
- 单独维护 hard cases 训练集
- 加 4bit / QLoRA