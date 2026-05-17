下面是一份可以直接给团队使用的 **《AI 交易能力训练工作台功能设计计划书 v1.0》**。它的核心方向是：**前端三入口，后端一套统一智能底座，答辩时展示三大引擎与 MCP 工具调用链。**

---

# AI 交易能力训练工作台功能设计计划书 v1.0

## 1. 产品定位

### 1.1 产品名称

**AI 交易能力训练工作台**
英文名可用：

```text
AI Trading Ability Training Workspace
```

### 1.2 核心定位

本产品不是股票推荐系统，而是一个面向普通投资者的 **交易能力训练系统**。

核心表达：

> 我们不提供“买什么”，而是训练用户具备“如何决策与执行”的能力。

商业计划书中已经明确提出，当前投资者的问题不是“不会”，而是“做不到”；真正缺口在于执行能力，交易能力包括规则执行、风险控制、情绪管理和持续复盘能力。
因此，本产品的功能设计必须围绕 **行为训练、能力评估、复盘进化**，而不是围绕“荐股”“买卖点”“短期收益”。

### 1.3 产品形态

答辩版本建议采用：

```text
三入口前端工作台 + 后端三大 AI 引擎 + MCP 工具调用链
```

前端不是单纯问答框，而是三个明确任务入口：

```text
交易能力评估
行为训练
智能复盘
```

后端统一由一个 Orchestrator 调度：

```text
用户输入
  ↓
意图识别
  ↓
调用用户画像 / 交易记忆 / 研报检索 / 三大引擎 / 合规检查
  ↓
输出训练反馈报告
  ↓
写入长期记忆
```

---

## 2. 设计原则

### 2.1 三入口，不做单一聊天框

如果只有一个问答入口，用户和评委容易把产品理解成“股票 Chatbot”。因此首页必须展示三个明确入口：

```text
我想知道自己水平如何 → 交易能力评估
我正在交易或准备交易 → 行为训练
我做完一笔交易想总结 → 智能复盘
```

### 2.2 一个统一底座，不做三个割裂工具

虽然前端有三个入口，但底层必须共享同一套数据和工具：

```text
用户能力画像
交易记录
历史 session 记忆
研报 / 外部信息检索
三大 AI 引擎
合规输出控制
```

商业计划书里已经将核心训练系统定义为三大核心引擎：能力评估引擎、AI 训练引擎、AI 复盘引擎，并强调这是一个持续进化的能力训练系统。

### 2.3 输出训练反馈，不输出投资建议

系统不能输出：

```text
建议你买入
建议你卖出
建议你 20 元加仓
跌破 17 元止损
```

系统应该输出：

```text
当前交易计划不完整
当前不满足加仓训练规则
缺少止损条件
仓位与当前能力等级不匹配
本次训练任务是补全交易计划
```

商业计划书的合规部分明确写到，业务定位是投资教育而非投资顾问，不提供个股推荐、买卖点建议、实时交易信号或投资建议。

---

## 3. 用户角色与核心场景

### 3.1 目标用户

目标用户不是所有投资者，而是：

```text
有一定交易经验
长期盈亏不稳定
容易情绪化操作
想提升交易能力
愿意接受训练和复盘
```

### 3.2 核心用户场景

| 场景    | 用户问题             | 对应入口        |
| ----- | ---------------- | ----------- |
| 新用户进入 | 我现在交易能力怎么样？      | 交易能力评估      |
| 准备买入  | 我这笔交易计划是否合理？     | 行为训练        |
| 持仓中   | 我想加仓/减仓，但不知道是否冲动 | 行为训练        |
| 亏损后   | 我是不是又犯了老毛病？      | 智能复盘        |
| 盈利回撤  | 我为什么赚了又亏回去？      | 智能复盘        |
| 长期训练  | 我最近能力有没有提升？      | 用户画像 / 训练记录 |

---

## 4. 信息架构

建议前端页面结构如下：

```text
/
首页：三入口工作台

/assessment
交易能力评估页面

/training
行为训练页面

/review
智能复盘页面

/profile
用户能力画像页面

/memory
历史交易记忆页面

/demo
答辩演示模式：展示工具调用链
```

首页应该既有三个入口，也保留一个轻量智能输入框。

```text
顶部：核心 slogan
中部：三个入口卡片
底部：智能输入框
右侧或弹窗：合规提示
```

---

## 5. 前端功能设计

## 5.1 首页：三入口工作台

### 页面目标

让用户一眼理解：这不是荐股工具，而是交易能力训练系统。

### 页面模块

```text
1. Hero 区域
2. 三大入口卡片
3. 智能输入框
4. 最近一次能力画像摘要
5. 合规提示
```

### Hero 文案

```text
从“给答案”到“给能力”
我们不提供“买什么”，而是训练你具备“如何决策与执行”的能力。
```

### 三张入口卡片

#### 卡片一：交易能力评估

```text
标题：交易能力评估
说明：通过题单和交易记录，识别你的交易弱点，生成能力画像。
按钮：开始评估
```

#### 卡片二：行为训练

```text
标题：行为训练
说明：在交易前或持仓中，系统帮助你检查交易计划，生成行为约束任务。
按钮：进入训练
```

#### 卡片三：智能复盘

```text
标题：智能复盘
说明：复盘每一笔交易，分析错误来源，沉淀长期交易记忆。
按钮：开始复盘
```

### 智能输入框

占位文案：

```text
你也可以直接描述你的交易问题，例如：我今天买入某股票，仓位 30%，现在有点犹豫。
```

用户输入后，系统不直接回答，而是先识别入口：

```text
系统判断：这是“行为训练”场景
请补充：买入理由、止损计划、预期持有周期、最大可接受亏损
```

---

## 5.2 交易能力评估模块

### 功能目标

把用户模糊的“我交易不稳定”转化为可量化的能力画像。

题单文件中明确提出，交易能力评估不只看“会不会预测涨跌”，而是重点评估认知框架、风险控制、仓位管理、执行纪律、复盘能力和心理稳定性。

### 输入方式

评估入口提供两种方式：

```text
方式 A：快速题单评估
方式 B：导入历史交易/复盘记录
```

### 快速题单字段

答辩版本不建议放完整 45 题，可以做成 8–10 题短版：

```text
1. 单笔交易你最多愿意亏损总资金的百分之几？
2. 买入前是否设定止损？
3. 如果连续亏损 5 次，你如何处理？
4. 已有 70% 仓位时，出现新机会怎么办？
5. 你是否会补仓？补仓和加仓的区别是什么？
6. 你是否记录每一笔交易？
7. 亏损后是否有立刻想赚回来的冲动？
8. 请描述最近一笔失败交易。
```

### 评估维度

使用 5 个核心维度，每项 20 分，总分 100 分：

| 维度   | 评估重点              |
| ---- | ----------------- |
| 市场理解 | 是否理解不确定性、概率、周期和情绪 |
| 分析框架 | 是否有稳定判断逻辑         |
| 风险控制 | 是否先想亏多少，再想赚多少     |
| 执行纪律 | 是否能按计划交易          |
| 复盘能力 | 是否能从错误中提炼规则       |

这个评分方式与题单中的评分方法一致。

### 输出结果

评估结果页面展示：

```text
总分：58 / 100
交易者类型：规则型交易者早期
主要弱点：执行纪律、仓位管理
主要风险：追涨后不设止损，亏损后补仓倾向明显
推荐训练方向：交易前计划训练、止损执行训练、复盘记录训练
```

### 页面组件

```text
能力雷达图
维度评分卡片
用户类型标签
弱点分析
下一步训练建议
进入行为训练按钮
```

---

## 5.3 行为训练模块

### 功能目标

帮助用户在交易前或持仓中完成交易计划检查，防止冲动交易、追涨、盲目加仓、亏损补仓。

AI 训练引擎的核心功能是生成个性化训练任务、行为约束机制和动态训练路径。

### 入口场景

用户进入行为训练后，先选择场景：

```text
我准备买入
我已经持仓
我想加仓
我想减仓
我亏损后想补仓
我看到上涨想追
我想检查交易计划
```

### 输入字段

```text
股票名称/代码：选填
买入价格：选填
当前价格：选填
当前仓位：必填
计划加仓/减仓比例：选填
买入理由：必填
止损计划：必填
预期持有周期：必填
最大可接受亏损：必填
当前情绪状态：必填
```

### 后端处理逻辑

```text
1. 读取用户 profile
2. 读取历史 session memory
3. 判断是否存在历史重复行为
4. 根据股票/行业关键词调用研报检索工具，补充背景信息
5. 调用行为训练引擎
6. 调用合规检查工具
7. 输出训练反馈
8. 写入本次训练记录
```

### 输出结构

输出不叫“投资建议”，建议命名为：

```text
AI 交易训练反馈
```

内容包括：

```text
1. 交易计划完整度
2. 当前行为风险
3. 是否满足训练规则
4. 缺失信息
5. 行为约束任务
6. 下一次训练要求
```

### 输出示例

```text
交易计划完整度：46 / 100

系统判断：
当前不满足加仓训练规则。

原因：
1. 买入理由主要来自短期上涨，存在追涨倾向。
2. 未设置明确止损位置。
3. 当前仓位已超过你现阶段训练建议范围。
4. 缺少“判断错误时怎么办”的失效条件。

本次训练任务：
请补全交易计划，包括：
- 最大可接受亏损
- 止损触发条件
- 退出规则
- 复盘时间

合规提示：
以下内容仅用于交易能力训练，不构成任何投资建议。
```

---

## 5.4 智能复盘模块

### 功能目标

将用户的一笔交易转化为长期能力训练数据，识别错误模式，形成下一次训练任务。

商业计划书中将 AI 复盘引擎定义为：自动复盘每笔交易、分析错误原因、给出优化建议，并帮助用户形成正向反馈闭环。

### 输入字段

```text
股票名称/代码
买入时间
卖出时间
买入价格
卖出价格
仓位比例
买入理由
卖出理由
原计划是否执行
是否设置止损
是否临时改变计划
当时情绪状态
本次交易结果
用户自我总结
```

### 复盘分析维度

```text
计划完整性
执行一致性
风险控制
仓位管理
情绪干扰
错误类型
是否重复历史问题
```

### 错误类型分类

```text
追涨
杀跌
补仓失控
止损不执行
盈利拿不住
计划缺失
仓位过重
消息驱动
FOMO
报复性交易
```

### 输出结构

```text
1. 本次交易评分
2. 交易过程复盘
3. 错误归因
4. 历史重复模式
5. 下次改进规则
6. 写入长期记忆
```

### 输出示例

```text
本次交易过程评分：52 / 100

复盘结论：
本次亏损不主要来自信息不足，而来自交易前计划缺失和止损执行不明确。

错误归因：
- 买入理由偏情绪化
- 没有预设失效条件
- 下跌后临时改变计划
- 与历史第 3 次、第 7 次交易存在相似模式

系统为你生成的新规则：
未来 3 笔交易必须在买入前填写：
1. 入场理由
2. 止损位置
3. 最大亏损
4. 退出条件
5. 复盘时间

本次复盘已写入长期交易记忆。
```

---

## 5.5 用户画像与长期记忆模块

### 功能目标

让系统从“一次回答”变成“长期陪伴训练”。

plan.md 中已经提出，需要把用户之前找 GPT 复盘的交易记录规范化，并为每一个 session 整理记忆文档，反映用户在这次聊天中的决策。

### 用户画像内容

```json
{
  "user_id": "u_001",
  "trader_type": "经验型散户",
  "total_score": 58,
  "dimensions": {
    "market_understanding": 12,
    "analysis_framework": 13,
    "risk_control": 10,
    "execution_discipline": 8,
    "review_ability": 14
  },
  "weaknesses": ["止损执行弱", "追涨倾向", "仓位控制不稳定"],
  "training_stage": "foundation",
  "risk_level": "medium_high"
}
```

### 长期记忆内容

```json
{
  "session_id": "s_20260517_001",
  "timestamp": "2026-05-17",
  "related_stock": "某股票",
  "user_question": "我今天买了这只股票，仓位30%，该怎么办？",
  "decision_pattern": "追涨买入，止损计划缺失",
  "system_feedback": "不满足加仓训练规则，要求补全交易计划",
  "memory_tags": ["追涨", "止损缺失", "仓位偏高"]
}
```

### 页面展示

```text
最近能力变化
历史复盘列表
重复错误标签
训练任务完成情况
能力评分趋势
```

---

## 6. 后端功能设计

## 6.1 总体架构

建议架构：

```text
Frontend
  ↓
Backend API / Orchestrator
  ↓
Intent Router
  ↓
三大 AI 引擎
  ↓
MCP Tools
  ↓
Memory Store / Report Search / Compliance Guard
```

### 架构说明

```text
前端负责展示与收集结构化输入
Orchestrator 负责判断调用路径
三大引擎负责核心业务判断
MCP tools 负责可复用工具能力
Compliance Guard 负责合规输出检查
Memory Store 负责长期记忆沉淀
```

比赛主题是 Make something agents want，plan.md 也强调 agent 需要的不只是聊天框，而是一套能让它干活的环境和顺手的执行路径；你们计划中的核心服务也是构造 MCP 支持，包括用户问答、session 聊天记录整合和东方财富研报接口能力。

---

## 6.2 Orchestrator 调度逻辑

### 输入

```json
{
  "user_id": "u_001",
  "entry": "training",
  "message": "我今天买入某股票，仓位30%，现在想加仓",
  "form_data": {
    "stock": "xxx",
    "position": 30,
    "reason": "最近涨得很强",
    "stop_loss": "",
    "holding_period": "短线"
  }
}
```

### 处理流程

```text
1. classify_intent
2. validate_required_fields
3. load_user_profile
4. query_session_memory
5. call_research_tool if needed
6. call_target_engine
7. generate_structured_report
8. compliance_check
9. write_memory
10. return_response
```

### 输出

```json
{
  "intent": "behavior_training",
  "called_tools": [
    "user_profile_get",
    "session_memory_query",
    "broker_report_search",
    "training_engine_generate",
    "compliance_guard_check",
    "session_memory_write"
  ],
  "result": {
    "plan_score": 46,
    "risk_tags": ["追涨倾向", "止损缺失", "仓位偏高"],
    "training_decision": "不满足加仓训练规则",
    "tasks": [
      "补全止损条件",
      "写明最大可接受亏损",
      "设置交易失效条件"
    ]
  }
}
```

---

## 6.3 三大 AI 引擎设计

### A. 交易能力评估引擎

工具名：

```text
assessment_engine
```

输入：

```json
{
  "answers": [],
  "trade_records": [],
  "session_memories": []
}
```

处理：

```text
题单评分
交易行为识别
风险偏好判断
能力分层
弱点标签生成
```

输出：

```json
{
  "total_score": 58,
  "trader_type": "经验型散户",
  "dimension_scores": {
    "market_understanding": 12,
    "analysis_framework": 13,
    "risk_control": 10,
    "execution_discipline": 8,
    "review_ability": 14
  },
  "weaknesses": ["止损执行弱", "仓位管理不稳定"],
  "next_training_focus": ["交易前计划", "止损训练"]
}
```

---

### B. AI 行为训练引擎

工具名：

```text
training_engine
```

输入：

```json
{
  "user_profile": {},
  "current_trade_plan": {},
  "memory_patterns": [],
  "research_context": []
}
```

处理：

```text
交易计划完整度评分
行为风险识别
加仓/减仓训练规则检查
行为约束任务生成
训练路径更新
```

输出：

```json
{
  "plan_score": 46,
  "rule_status": "not_passed",
  "risk_tags": ["FOMO", "止损缺失"],
  "missing_fields": ["止损位置", "最大亏损", "失效条件"],
  "training_tasks": [
    "补全交易计划",
    "未来3笔交易必须先写止损",
    "复盘时检查是否临时改变计划"
  ]
}
```

---

### C. AI 智能复盘引擎

工具名：

```text
review_engine
```

输入：

```json
{
  "trade_record": {},
  "original_plan": {},
  "actual_behavior": {},
  "user_profile": {},
  "historical_memory": []
}
```

处理：

```text
交易过程还原
计划与实际行为对比
错误归因
历史模式匹配
改进规则生成
```

输出：

```json
{
  "review_score": 52,
  "mistake_types": ["计划缺失", "止损不执行"],
  "root_cause": "执行纪律不足，而非信息不足",
  "repeated_patterns": ["亏损后补仓", "追涨买入"],
  "new_rules": [
    "买入前必须填写失效条件",
    "亏损达到预设阈值时必须复盘而非补仓"
  ]
}
```

---

## 7. MCP 工具设计

建议第一版实现以下 MCP tools。

### 7.1 user_profile_get

作用：

```text
读取用户能力画像。
```

输入：

```json
{
  "user_id": "u_001"
}
```

输出：

```json
{
  "profile": {},
  "last_updated": "2026-05-17"
}
```

---

### 7.2 user_profile_update

作用：

```text
根据评估或复盘结果更新用户画像。
```

输入：

```json
{
  "user_id": "u_001",
  "profile_patch": {}
}
```

---

### 7.3 session_memory_query

作用：

```text
查询用户历史交易记忆。
```

输入：

```json
{
  "user_id": "u_001",
  "query": "追涨 止损 加仓",
  "limit": 5
}
```

---

### 7.4 session_memory_write

作用：

```text
把本次评估、训练或复盘结果写入长期记忆。
```

输入：

```json
{
  "user_id": "u_001",
  "session_summary": "",
  "decision_pattern": "",
  "tags": []
}
```

---

### 7.5 broker_report_search

作用：

```text
检索研报或外部背景信息。
```

输入：

```json
{
  "query": "AI 算力",
  "brokers": ["国泰海通", "长江证券", "开源证券"],
  "report_type": "all",
  "begin_date": "2026-01-01",
  "end_date": "2026-05-17",
  "limit": 10
}
```

websearch.md 中也建议第一版不要直接逆向券商 App，而是使用东方财富研报接口 + 机构名过滤 + PDF 原文链接解析，并可设计为 `broker_report_search` MCP 工具。

---

### 7.6 compliance_guard_check

作用：

```text
检查系统输出是否触碰投资建议边界。
```

检查规则：

```text
禁止直接推荐买入/卖出
禁止给出明确买卖点
禁止提供实时交易信号
禁止承诺收益
禁止使用“必涨”“稳赚”“一定”等表达
必须加入投资教育提示
```

---

## 8. API 设计

### 8.1 统一调度接口

```http
POST /api/orchestrate
```

请求：

```json
{
  "user_id": "u_001",
  "entry": "training",
  "message": "我今天买入某股票，仓位30%，现在想加仓",
  "form_data": {}
}
```

响应：

```json
{
  "entry": "training",
  "intent": "add_position_training",
  "tool_trace": [],
  "report": {}
}
```

---

### 8.2 能力评估接口

```http
POST /api/assessment/run
```

请求：

```json
{
  "user_id": "u_001",
  "answers": [],
  "trade_records": []
}
```

响应：

```json
{
  "score": 58,
  "profile": {},
  "weaknesses": [],
  "next_step": "进入行为训练"
}
```

---

### 8.3 行为训练接口

```http
POST /api/training/check
```

请求：

```json
{
  "user_id": "u_001",
  "scenario": "add_position",
  "trade_plan": {}
}
```

响应：

```json
{
  "plan_score": 46,
  "rule_status": "not_passed",
  "risk_tags": [],
  "training_tasks": []
}
```

---

### 8.4 智能复盘接口

```http
POST /api/review/run
```

请求：

```json
{
  "user_id": "u_001",
  "trade_record": {},
  "self_reflection": ""
}
```

响应：

```json
{
  "review_score": 52,
  "mistake_types": [],
  "root_cause": "",
  "new_rules": [],
  "memory_written": true
}
```

---

### 8.5 研报检索接口

```http
POST /api/research/search
```

请求：

```json
{
  "query": "AI 算力",
  "brokers": ["国泰海通", "长江证券", "开源证券"],
  "report_type": "industry",
  "limit": 5
}
```

响应：

```json
{
  "reports": [
    {
      "title": "",
      "broker": "",
      "date": "",
      "summary": "",
      "pdf_url": ""
    }
  ]
}
```

---

## 9. 答辩演示模式设计

建议专门做一个“答辩演示模式”，让评委看到系统真的在调用后端服务。

### 页面布局

```text
左侧：用户输入
中间：工具调用链
右侧：AI 训练反馈报告
底部：长期记忆写入结果
```

### 工具调用链展示

```text
1. user_profile_get       成功
2. session_memory_query   成功
3. broker_report_search   成功
4. training_engine        成功
5. compliance_guard_check 成功
6. session_memory_write   成功
```

### 演示输入

```text
我今天买入了某股票，买入价 18.6，仓位 30%，理由是最近三天涨得很强。我想知道现在能不能加仓。
```

### 演示输出

```text
系统判断：
当前不满足加仓训练规则。

原因：
1. 买入理由偏短期情绪驱动。
2. 未设置明确止损条件。
3. 仓位已超过当前能力等级建议训练范围。
4. 缺少交易失效条件。

训练任务：
请先补全交易计划，包括止损位置、最大亏损、退出规则和复盘时间。

合规提示：
本系统仅用于交易能力训练，不构成任何投资建议。
```

这个演示能很好地传达：

```text
不是给答案
而是评估能力、检查行为、生成训练任务、写入记忆
```

---

## 10. 数据结构设计

### 10.1 UserProfile

```json
{
  "user_id": "u_001",
  "trader_type": "经验型散户",
  "total_score": 58,
  "dimension_scores": {
    "market_understanding": 12,
    "analysis_framework": 13,
    "risk_control": 10,
    "execution_discipline": 8,
    "review_ability": 14
  },
  "risk_tags": ["追涨", "止损不执行", "仓位偏高"],
  "training_stage": "foundation",
  "updated_at": "2026-05-17"
}
```

### 10.2 TradeRecord

```json
{
  "trade_id": "t_001",
  "user_id": "u_001",
  "stock": "xxx",
  "buy_price": 18.6,
  "sell_price": null,
  "position": 30,
  "buy_reason": "短期上涨",
  "stop_loss_plan": "",
  "holding_period": "短线",
  "emotion": "兴奋/害怕踏空",
  "created_at": "2026-05-17"
}
```

### 10.3 TrainingTask

```json
{
  "task_id": "task_001",
  "user_id": "u_001",
  "source": "behavior_training",
  "task_type": "trade_plan_completion",
  "content": "未来3笔交易必须先填写止损、最大亏损和失效条件",
  "status": "pending",
  "deadline": "2026-05-20"
}
```

### 10.4 SessionMemory

```json
{
  "memory_id": "m_001",
  "user_id": "u_001",
  "session_type": "training",
  "summary": "用户因短期上涨买入并考虑加仓，但缺少止损与失效条件。",
  "decision_pattern": "追涨倾向，计划缺失",
  "tags": ["追涨", "加仓冲动", "止损缺失"],
  "created_at": "2026-05-17"
}
```

---

## 11. 前后端开发优先级

## P0：必须完成

```text
首页三入口
交易能力评估短版题单
行为训练表单
智能复盘表单
统一 Orchestrator
三大引擎 mock 或 LLM 调用
工具调用链展示
合规提示与输出过滤
session memory 写入展示
```

## P1：建议完成

```text
能力雷达图
历史记忆列表
训练任务列表
研报检索摘要
用户画像页面
演示模式页面
```

## P2：暂缓

```text
复杂 K 线图
实时行情
真实交易接口
完整研报 PDF 解析
深度回测系统
复杂会员体系
```

---

## 12. 技术实现建议

### 12.1 前端

可以使用：

```text
Next.js / React
Tailwind CSS
shadcn/ui
```

页面重点是清晰，不需要复杂视觉设计。

核心组件：

```text
EntryCard
AssessmentForm
TrainingForm
ReviewForm
ToolTracePanel
ReportCard
RiskTag
ScoreRadar
MemoryTimeline
ComplianceNotice
```

### 12.2 后端

可以使用：

```text
FastAPI / Node.js Express
SQLite / PostgreSQL
LLM API
MCP Server
```

### 12.3 数据库表

```text
users
user_profiles
trade_records
assessment_results
training_tasks
review_reports
session_memories
tool_call_logs
compliance_logs
research_reports
```

---

## 13. 合规设计

### 13.1 页面级合规提示

每个输出报告底部显示：

```text
本系统仅用于投资教育与交易能力训练，不构成任何投资建议、个股推荐或买卖信号。
```

### 13.2 输出限制

禁止输出：

```text
可以买
建议买入
建议卖出
加仓到多少
跌破多少卖出
目标价多少
稳赚
确定上涨
```

允许输出：

```text
当前交易计划不完整
当前行为存在追涨风险
当前不满足训练规则
建议补充风险控制条件
请明确最大可承受亏损
请记录本次决策依据
```

### 13.3 合规替代表达

| 风险表达      | 合规表达                     |
| --------- | ------------------------ |
| 建议你加仓     | 当前不满足/满足加仓训练规则           |
| 建议你卖出     | 当前计划缺少退出条件，请补全           |
| 跌破 17 元止损 | 请根据你的最大亏损额度设定止损条件        |
| 这只股票可以买   | 系统不判断个股是否可买，只评估你的交易计划完整度 |
| 目标价 20 元  | 请明确你的目标区域和失效条件           |

---

## 14. 验收标准

### 14.1 产品验收

```text
用户进入首页后，能清楚看到三个入口。
用户能完成一次能力评估，并获得能力画像。
用户能输入一笔交易计划，并获得行为训练反馈。
用户能提交一笔交易复盘，并获得错误归因。
系统能展示工具调用链。
系统能把本次结果写入 session memory。
系统输出不包含买卖建议。
```

### 14.2 答辩验收

```text
评委能在 3 分钟内理解产品不是荐股工具。
评委能看到三大 AI 引擎真实参与流程。
评委能看到 MCP / 工具调用轨迹。
评委能看到用户长期记忆沉淀。
评委能看到合规边界。
```

---

## 15. 推荐开发排期

### 第 1 阶段：产品骨架

```text
首页三入口
三个基础表单
输出报告卡片
合规提示
```

### 第 2 阶段：后端联调

```text
Orchestrator
三大引擎 mock
session memory
tool trace
```

### 第 3 阶段：增强演示效果

```text
能力雷达图
风险标签
研报摘要
历史记忆写入
答辩演示模式
```

### 第 4 阶段：打磨答辩故事

```text
准备标准输入案例
准备系统输出案例
准备工具调用截图
准备合规说明
```

---

## 16. 最终推荐版本

你们的 Hackathon V1 不要做成：

```text
股票问答机器人
```

也不要做成：

```text
三个割裂的小工具
```

而应该做成：

```text
AI 交易能力训练工作台
= 三入口前端
+ 统一智能调度后端
+ 三大 AI 引擎
+ MCP 工具调用
+ 长期记忆
+ 合规输出
```

最终产品一句话：

> **用户看到的是交易能力评估、行为训练、智能复盘三个清晰入口；评委看到的是一套能持续评估、训练、复盘并沉淀用户行为数据的 agent-native 交易能力训练系统。**
