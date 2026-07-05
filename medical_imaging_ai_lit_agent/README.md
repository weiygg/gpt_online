# 医学影像 AI 每日文献与项目热点工作流

这个文件夹是一个轻量、真实可落地的科研 Agent 原型。它参考了培训文档里的“四位 AI 研究员”思路，但按你现在已经具备的条件重做了一版：Codex / ChatGPT 做执行和解释，Claude Code 做复核，远端 Hermes 做记忆沉淀，飞书做每日推送入口。

## 1. 先用人话理解：这套系统到底在干什么

不要把 Agent 理解成一个“万能机器人”。更准确地说，它是一组固定岗位：

| 岗位 | 你现在的工具 | 负责什么 | 不应该负责什么 |
|---|---|---|---|
| 检索员 | Python 脚本 + PubMed，arXiv/Crossref 可选 | 每天按主题检索新文献，去重，生成候选清单 | 判断论文一定有价值 |
| 读书秘书 | Codex / ChatGPT | 把候选论文转成文献卡片，解释为什么值得读 | 代替你做最终学术判断 |
| 复核员 | Claude Code | 检查代码、逻辑、证据边界、夸大表述 | 自动相信检索结果 |
| 记忆员 | Hermes / Obsidian / 本地 Markdown | 保存每次卡片、项目判断、可复用命令 | 把未经核验的结论当成事实 |
| 通知员 | 飞书机器人或用户身份 | 每天把“最该读的几篇”推送到飞书 | 在未经配置时乱发消息 |

核心原则是：AI 负责重复劳动，人负责判断；每次输出都要能追溯来源、检索式、时间和人工复核状态。

## 2. 你现在可以实现的版本

### 今天就能跑通

1. 从 PubMed 检索医学影像/临床 AI 文献。
2. 必要时从 arXiv 检索医学影像 AI 方法、预印本、基础模型、分割/检测类论文；arXiv 有频率限制，所以默认不阻塞每日任务。
3. 必要时从 Crossref 补充 DOI 和非 PubMed 工程类期刊信息；当前网络下它偏慢，所以默认不阻塞每日任务。
4. 自动去重并输出：
   - `literature_hits.json`
   - `daily_card.md`
5. 通过 `lark-cli im +messages-send` 推送 Markdown 到飞书。
6. 把每天的卡片存到 `outputs/YYYY-MM-DD/`，作为 Hermes/Obsidian 可吸收的项目记忆。

### 需要后续加强

1. 全文 PDF 自动下载和图表抽取：需要 DOI、开放访问权限、PDF 下载规则。
2. 公众号/小红书/抖音线索自动采集：技术和平台规则更复杂，建议先做“人工转发到飞书，再自动归档”。
3. 用大模型自动深读全文：可以做，但必须保留人工复核点，尤其是样本量、数据集、指标、外部验证、代码开放性。
4. Hermes 远端长期记忆：需要你那台服务器开放一个稳定的写入方式，例如 API、Git 同步、Obsidian Sync 或共享目录。

## 3. 推荐目录结构

```text
medical_imaging_ai_lit_agent/
  README.md
  config/
    topics.example.json
  scripts/
    daily_literature_scan.py
    run_daily_scan.ps1
  prompts/
    hotspot_feasibility_review.md
  skills/
    medical-imaging-literature-card/
      SKILL.md
    hotspot-feasibility-analyst/
      SKILL.md
  outputs/
    YYYY-MM-DD/
      literature_hits.json
      daily_card.md
```

## 4. 每日工作流

### Step 1：配置你关心的方向

复制配置文件：

```powershell
Copy-Item .\medical_imaging_ai_lit_agent\config\topics.example.json .\medical_imaging_ai_lit_agent\config\topics.local.json
```

然后改里面的主题，例如：

- 肝转移影像组学
- 乳腺 MRI 基础模型
- 甲状腺 CT 风险预测
- 胰腺癌 CT 深度学习
- 医学影像 foundation model
- radiomics reproducibility

### Step 2：本地生成每日文献卡

```powershell
python .\medical_imaging_ai_lit_agent\scripts\daily_literature_scan.py `
  --topics .\medical_imaging_ai_lit_agent\config\topics.example.json `
  --outdir .\medical_imaging_ai_lit_agent\outputs
```

默认只检索 PubMed，最稳定。想补充 arXiv 和 Crossref 时，可以加：

```powershell
--sources pubmed,arxiv,crossref
```

如果只想加 arXiv：

```powershell
--sources pubmed,arxiv
```

结果会写入今天日期的文件夹。

### Step 3：确认飞书接收对象

先查你要推送的群：

```powershell
lark-cli im +chat-search --query "科研" --as user
```

拿到 `oc_xxx` 形式的 `chat_id` 后，先 dry-run：

```powershell
.\medical_imaging_ai_lit_agent\scripts\run_daily_scan.ps1 `
  -Topics .\medical_imaging_ai_lit_agent\config\topics.example.json `
  -ChatId "oc_xxx" `
  -DryRun
```

确认没问题后再真的发送：

```powershell
.\medical_imaging_ai_lit_agent\scripts\run_daily_scan.ps1 `
  -Topics .\medical_imaging_ai_lit_agent\config\topics.example.json `
  -ChatId "oc_xxx" `
  -Send
```

## 5. 每张每日文献卡应该长什么样

建议每天不要推太多。新手常见错误是“把所有文献都推送”，最后等于没人读。更好的结构：

```text
医学影像 AI 每日文献卡 - 2026-06-23

今日优先读
1. 论文 A
   为什么重要：外部验证 / 多中心 / 新任务 / 新数据集 / 临床转化强
   落地判断：高 / 中 / 低
   需要人工复核：样本量、数据来源、是否有独立测试集

2. 论文 B

热点观察
- 本周高频主题：foundation model、MRI segmentation、radiomics reproducibility
- 可能机会：把公开基础模型迁移到你自己的病种任务
- 风险：很多论文只有内部测试，没有真实外部验证

下一步
- 下载 2 篇 PDF 深读
- 建立数据集/任务/指标表
- 让 Claude Code 复核证据边界
```

## 6. 项目热点如何判断“能不能落地”

医学影像 AI 的“热”不等于“能做”。建议每个热点都按 6 个维度打分：

| 维度 | 问题 | 判断标准 |
|---|---|---|
| 临床需求 | 这个问题临床上真的痛吗 | 是否影响诊断、分层、治疗、随访或工作效率 |
| 数据可得性 | 你能不能拿到足够数据 | 模态、病种、标签、随访、外部验证是否可得 |
| 技术成熟度 | 方法是不是可复现 | 是否有代码、公开模型、公开数据、明确指标 |
| 竞争强度 | 会不会已经太卷 | 是否已有大队列、多中心、高影响力论文 |
| 发表空间 | 还能不能讲出新意 | 是否能补充外部验证、亚组、真实世界、可解释性 |
| 转化可能 | 能否进入临床路径 | 是否能减少工作量、提高准确性、改变决策 |

建议输出四档：

- A 类：立刻值得立项，已有数据或容易拿到数据。
- B 类：值得观察，先做 1 周快速证据评估。
- C 类：概念热但落地难，适合作为综述或背景材料。
- D 类：暂不投入，证据弱、数据难、竞争过强或临床价值不清。

## 7. 四 Agent 分工建议

### Codex

负责本地执行：

- 写检索脚本。
- 生成 Markdown 文献卡。
- 保存 JSON/CSV/Excel。
- 调用飞书 CLI。
- 后续写 PDF 提取、图表抽取、统计分析脚本。

### ChatGPT

负责解释和教学：

- 把每日卡片讲给新手听。
- 把复杂论文转成“研究问题-数据-方法-结果-局限-能否复用”。
- 帮你准备组会讲稿、培训材料。

### Claude Code

负责复核：

- 检查脚本是否漏检、重复、日期过滤错误。
- 检查论文卡片是否夸大。
- 检查“落地可能性”是否有证据支撑。
- 检查是否把预印本当成已发表证据。

### Hermes

负责长期记忆：

- 每天保存卡片。
- 记录你对项目方向的判断。
- 记录“哪些主题已经被放弃，为什么”。
- 记录可复用检索式、纳排标准、复核清单。

## 8. 新手最容易误解的地方

1. Agent 不是自动替你科研，而是自动把“材料准备”做到可复核。
2. 每日推送不是越多越好，3-5 篇优先读比 50 篇标题更有用。
3. 大模型总结一定要带原文链接、DOI、PMID 或 arXiv ID。
4. 医学影像 AI 项目不能只看 AUC，要看数据来源、外部验证、标签质量、真实临床流程。
5. 热点分析不能只说“foundation model 很火”，必须回答“我的数据、病种、任务能不能接上”。
6. 所有自动化都要有人工复核点，尤其是临床、伦理、数据许可和论文结论。

## 9. 建议的迭代路线

### 第 1 周：跑通每日卡片

- 固定 5-8 个主题。
- 每天自动检索。
- 推送到飞书。
- 人工标记“值得深读 / 忽略 / 后续观察”。

### 第 2 周：加入 PDF 深读

- 对每天 1-2 篇优先论文下载 PDF。
- 提取样本量、数据集、模型、验证方式、指标、局限。
- 建立 `paper_evidence_table.xlsx`。

### 第 3 周：加入项目热点雷达

- 每周统计高频主题。
- 输出“本周最值得做的 3 个方向”。
- 每个方向给 A/B/C/D 落地等级。

### 第 4 周：加入 Hermes/Obsidian

- 每日卡片同步到知识库。
- 每个项目形成独立专题页。
- 保存已验证结论和放弃理由。

## 10. 最小可用原则

先不要急着做“全自动科研系统”。最小可用版本只需要做到：

1. 每天帮你发现新论文。
2. 不重复。
3. 有链接和来源。
4. 能推到飞书。
5. 能保存下来。
6. 每篇都有“为什么值得读”和“落地可能性初判”。

只要这 6 件事稳定，后面再加 PDF、图表、Meta 分析、项目申报、论文写作，都会自然接上。
