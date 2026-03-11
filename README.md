<div align="center">

# KangaBase 🦘

**轻如 SQLite、易如 Supabase、为 Agent 而生**

*Agent-Native Database — 让 AI Agent 安全、高效地操作数据*

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-brightgreen.svg)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-68%20passed-success.svg)](tests/)

</div>

---

## 为什么需要 KangaBase？

当 AI Agent 需要操作数据时，传统方案要么让 Agent 直接写 SQL（危险），要么套一层 ORM（不是为 Agent 设计的）。

KangaBase 换了一种思路：**Agent 不进厨房做菜，而是从菜单点菜。**

```
YAML Schema（语义层）→ YAML Contract（操作契约层）→ SQLite（存储层）
```

Agent 选择预定义的操作、填入参数，KangaBase 负责安全执行。就这么简单。

> 命名由来：**Kanga**(roo) + **Base**。袋鼠🦘 — 容纳、保护、轻便携带。

---

## ✨ 特性亮点

| | 特性 | 描述 |
|---|---|---|
| 📐 | **YAML 声明式 Schema** | 用人类可读的 YAML 定义数据模型，自带语义信息（同义词、指标、约束） |
| 📜 | **操作契约（Contract）** | 预定义操作白名单，Agent 只能执行已声明的操作，从根源杜绝越权 |
| 🧭 | **意图路由（Intent Registry）** | 架构枢纽——自然语言或结构化调用统一路由到正确的操作 |
| 🛡️ | **沙箱预执行（Sandbox）** | 每个操作先在沙箱 dry-run，确认安全后才真正执行 |
| 🔐 | **细粒度权限（Policy）** | 基于角色的权限控制 + 风险等级阈值，不同 Agent 不同权限 |
| 📋 | **全链路审计（Audit）** | 每一次操作都有迹可循——谁、什么时候、做了什么、结果如何 |
| 🎯 | **Agent SDK** | 一行代码创建 Agent，结构化调用或自然语言调用随你选 |
| ⚡ | **零配置嵌入式** | 单文件 SQLite 存储，无需安装数据库服务，pip install 即用 |

---

## 🚀 快速开始

### 第一步：安装

```bash
pip install kangabase
```

### 第二步：定义 Schema + Contract

```yaml
# schemas/coupon.yaml
version: "1.0"
namespace: coupon_system
entities:
  - name: Coupon
    description: "优惠券，企业用于激励消费者消费的营销工具"
    storage: { table: coupons }
    fields:
      id: { type: string, auto: uuid, description: "唯一标识" }
      amount: { type: decimal, description: "面额（元）", constraints: { positive: true, max: 100 }, synonyms: ["面额", "金额"] }
      min_order: { type: decimal, description: "最低消费门槛" }
      status: { type: enum, values: [created, issued, used, expired], description: "状态" }
      user_id: { type: string, description: "持券用户" }
      campaign_id: { type: string, description: "所属活动" }
      created_at: { type: datetime, auto: now }
  - name: Campaign
    description: "营销活动"
    storage: { table: campaigns }
    fields:
      id: { type: string, auto: uuid }
      name: { type: string, description: "活动名称" }
      budget: { type: decimal, description: "预算（元）", constraints: { positive: true } }
      status: { type: enum, values: [draft, active, paused, ended] }
```

```yaml
# contracts/coupon_ops.yaml
version: "1.0"
namespace: coupon_system
operations:
  issue_coupon:
    description: "向用户发放优惠券"
    intent_patterns: ["发券给{user_id}", "issue coupon"]
    params:
      user_id: { type: string, required: true }
      amount: { type: decimal, required: true, max: 100, min: 1 }
      min_order: { type: decimal, required: true, min: 0 }
      campaign_id: { type: string, required: true }
    preconditions:
      - sql: "SELECT budget FROM campaigns WHERE id = :campaign_id AND status = 'active'"
        check: "result.budget >= :amount"
        error: "活动预算不足或未激活"
    steps:
      - sql: "INSERT INTO coupons (id, amount, min_order, status, user_id, campaign_id, created_at) VALUES (:id, :amount, :min_order, 'issued', :user_id, :campaign_id, datetime('now'))"
        generate: { id: "uuid" }
      - sql: "UPDATE campaigns SET budget = budget - :amount WHERE id = :campaign_id"
    compensation:
      - sql: "DELETE FROM coupons WHERE id = :id"
      - sql: "UPDATE campaigns SET budget = budget + :amount WHERE id = :campaign_id"
    risk_level: medium
```

### 第三步：创建 Agent 并执行

```python
import kangabase as kb

# 打开数据库（不存在则自动创建）
db = kb.open("shop.db")
db.load_schema("schemas/coupon.yaml")
db.load_contract("contracts/coupon_ops.yaml")

# 创建 Agent
agent = db.agent("coupon_bot", role="asB")

# 结构化调用
result = agent.execute("issue_coupon",
    user_id="12345",
    amount=10,
    campaign_id="spring"
)
print(result)
# ✅ ExecutionResult(success=True, affected_rows=1, operation="issue_coupon")

# 自然语言调用
result = agent.ask("给用户12345发一张10元优惠券")
print(result)
# ✅ 同上
```

就这么简单。三步上手，Agent 安全操作数据。

---

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────┐
│                    Agent Layer                       │
│         agent.execute() / agent.ask()                │
├─────────────────────────────────────────────────────┤
│               ┌──────────────┐                       │
│  语义层       │  YAML Schema │  实体、字段、约束、    │
│  (Semantic)   │              │  同义词、指标          │
│               └──────┬───────┘                       │
│                      ▼                               │
│               ┌──────────────┐                       │
│  契约层       │YAML Contract │  操作白名单、前置条件、│
│  (Contract)   │              │  步骤、补偿、风险等级  │
│               └──────┬───────┘                       │
│                      ▼                               │
│  ┌────────┐  ┌──────────────┐  ┌─────────┐          │
│  │ Policy │→ │Intent Registry│→ │ Sandbox │          │
│  │ 权限    │  │  意图路由     │  │ 沙箱    │          │
│  └────────┘  └──────┬───────┘  └─────────┘          │
│                      ▼                               │
│               ┌──────────────┐  ┌─────────┐          │
│  存储层       │   SQLite     │→ │  Audit  │          │
│  (Storage)    │   数据库     │  │  审计    │          │
│               └──────────────┘  └─────────┘          │
└─────────────────────────────────────────────────────┘
```

**三层架构的核心思想：**

- **语义层**：用 YAML Schema 描述数据"是什么"——不只是字段类型，还有业务含义、同义词、指标
- **契约层**：用 YAML Contract 描述"能做什么"——操作白名单，Agent 只能从菜单点菜
- **存储层**：SQLite 负责"怎么存"——轻量、可靠、零配置

中间的 **Intent Registry** 是架构枢纽，连接语义理解和操作执行。

---

## 📚 核心概念

| 概念 | 说明 |
|---|---|
| **Schema** | YAML 定义的数据模型。描述实体、字段、约束，并携带语义信息（同义词、指标）供 Agent 理解 |
| **Contract** | YAML 定义的操作契约。每个操作有名称、参数、前置条件、执行步骤、补偿逻辑和风险等级 |
| **Intent** | Agent 的操作意图。结构化调用直接匹配，自然语言调用经 NL Parser 解析后匹配 |
| **Policy** | 权限策略。定义角色能执行哪些操作，参数约束是什么，风险阈值是多少 |
| **Agent** | Agent 身份。每个 Agent 有名称和角色，通过 Policy 控制权限边界 |
| **Sandbox** | 沙箱预执行。操作先在内存沙箱 dry-run，验证通过才真正执行，防止破坏性操作 |
| **Audit** | 审计日志。完整记录每次操作的 Agent、时间、操作、参数、结果，支持追溯和统计 |

---

## 📊 与传统方案对比

| 维度 | KangaBase 🦘 | 传统 RDBMS | ORM | 文件系统 |
|---|---|---|---|---|
| **面向对象** | Agent | 开发者 | 开发者 | 任何人 |
| **数据定义** | YAML（语义化） | SQL DDL | 代码类定义 | 无 |
| **操作方式** | 契约白名单 | 任意 SQL | 方法调用 | 读/写文件 |
| **安全模型** | 白名单+沙箱+审计 | 权限+视图 | 应用层控制 | 文件权限 |
| **意图理解** | ✅ 原生支持 | ❌ | ❌ | ❌ |
| **部署复杂度** | pip install | 安装服务 | 依赖 DB | 无 |
| **事务支持** | ✅（SQLite） | ✅ | ✅ | ❌ |
| **审计追踪** | ✅ 内建 | 需额外配置 | 需手动实现 | ❌ |
| **适合场景** | Agent 数据操作 | 通用数据存储 | Web 应用 | 配置/文档 |

---

## 🎯 使用场景

### ✅ 适合

- **Agent 驱动的业务系统**：优惠券发放、订单管理、用户积分——Agent 需要安全地增删改查
- **Multi-Agent 协作**：多个 Agent 共享数据库，通过 Policy 隔离权限
- **Agentic Commerce**：asC/asB/A2A 场景下，Agent 自主完成商业交易
- **快速原型**：零配置、单文件，5 分钟搭建一个 Agent 可操作的数据系统
- **嵌入式 Agent 数据层**：嵌入到 Agent 框架中，作为数据操作的安全中间层

### ❌ 不适合

- **高并发 OLTP**：SQLite 单写，不适合数千 TPS 的场景（未来可通过 libSQL/Turso 扩展）
- **大数据分析**：不是 OLAP 工具，请用 DuckDB / ClickHouse
- **纯人类使用的 Web 应用**：没有 Agent，不需要 Contract 和 Intent 这些概念
- **文件/配置管理**：纯配置用 YAML/JSON 文件即可，不需要数据库

---

## 🗺️ Roadmap

| 阶段 | 目标 | 状态 |
|---|---|---|
| v0.1 | 核心架构：Schema + Contract + Intent + Policy + Sandbox + Audit | ✅ 已完成 |
| v0.2 | Agent SDK + NL Parser + CLI 工具 | ✅ 已完成 |
| v0.3 | Events 事件系统 + Schema 迁移 | ✅ 已完成 |
| v0.4 | 性能优化 + PRAGMA 调优 + 批量操作 | 🚧 进行中 |
| v0.5 | libSQL 适配 + 远程存储支持 | 📋 计划中 |
| v0.6 | Turso 云端部署 + Multi-Agent 分布式协作 | 📋 计划中 |
| v1.0 | 生产就绪版本 | 🎯 目标 |

---

## 📁 项目结构

```
kangabase/
├── __init__.py           # KangaBase 主类，open() 入口
├── core/
│   ├── database.py       # SQLite 封装 + Storage Adapter
│   ├── schema.py         # YAML Schema 解析
│   ├── contract.py       # 操作契约执行器
│   ├── intent.py         # Intent Registry（架构枢纽）
│   ├── policy.py         # 权限引擎
│   ├── sandbox.py        # 沙箱预执行
│   ├── audit.py          # 审计日志
│   └── events.py         # 事件系统
├── agent.py              # Agent SDK
├── nl/parser.py          # NL 意图解析
├── cli/main.py           # CLI 工具
├── examples/coupon/      # 优惠券 Demo
└── tests/                # 测试套件（68个用例）
```

---

## 📜 许可证

[Apache License 2.0](LICENSE) — 自由使用、修改和分发。

---

## 🙏 致谢

KangaBase 站在巨人的肩膀上：

- **[SQLite](https://sqlite.org/)** — 世界上部署最广泛的数据库引擎，我们的存储基石
- **[Supabase](https://supabase.com/)** — "开发者友好"的标杆，启发了我们的 DX 设计
- **[Stripe Docs](https://stripe.com/docs)** — 技术文档的天花板，我们追求同等的清晰度
- **[libSQL](https://github.com/tursodatabase/libsql) / [Turso](https://turso.tech/)** — SQLite 的未来演进方向
- **3A 范式 & Agentic Commerce** — Agent 时代的商业理论体系，KangaBase 的设计原点

---

<div align="center">

**KangaBase 🦘 — 给 Agent 一个安全的家**

[快速开始](docs/GUIDE.md) · [设计理念](docs/DESIGN.md) · [API 文档](docs/API.md) · [示例](examples/)

</div>
