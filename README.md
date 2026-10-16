# 电商经营分析助手

面向电商经营场景的自然语言数据分析应用。用户直接提问，助手自动完成 SQL 规划、数据库查询和结果分析，以文字、表格及图表展示经营数据。

**技术栈：Dify · Python · MySQL · DeepSeek · ECharts**

## 功能特性

- **自然语言查询**：分析销售额、订单数、客单价、商品销量、客户贡献及退款情况。
- **多维经营分析**：关联客户、商品、订单和明细，按时间、品类、地区或渠道进行统计。
- **自动可视化**：根据问题和数据选择柱状图、折线图或饼图，支持仅返回文字和表格。
- **查询约束与异常处理**：校验 SQL、限制可访问表和函数，配合只读账号；对模糊问题、无记录和不支持的需求给出明确说明。

## 使用效果

提问「查看9月各品类销售额」，助手返回统计结论、明细表格和品类对比图。

![品类销售额分析](docs/screenshots/category-analysis.png)

![品类销售额柱状图](docs/screenshots/category-chart.png)

演示使用模拟数据：**240 位客户、32 件商品、1,200 笔订单、3,043 条订单明细**，覆盖 2026-04-01 至 2026-10-15。相对时间统一以 2026-10-16 为基准，便于重复验证。

## 技术架构

```mermaid
flowchart LR
    A[用户提问] --> B[LLM 查询规划]
    B --> C[Python 解析与 SQL 检查]
    C -->|需要澄清或不支持| D[返回说明]
    C -->|通过检查| E[MySQL 只读查询]
    E --> F[LLM 基于实际结果分析]
    F --> G[正文与图表参数校验]
    G --> H[分析结论与表格]
    G --> I[ECharts 图表]
```

查询默认生成 1 条 SQL，必要时最多 3 条；单次最多返回 100 行。每条查询的标题、SQL、指标口径和实际结果一起传入汇总节点，避免丢失数据来源。

| 数据表 | 内容 | 关联关系 |
|---|---|---|
| `customers` | 客户、地区、注册日期 | 一位客户对应多笔订单 |
| `products` | 商品、品类、目录价格 | 一件商品对应多条订单明细 |
| `orders` | 下单时间、状态、渠道、实付及退款金额 | 一笔订单对应多条明细 |
| `order_items` | 购买数量、历史价格与成本、明细实付 | 关联订单和商品 |

销售额仅统计 `paid`、`completed` 状态，按下单日期归属；商品和品类销售额使用明细实付汇总，避免关联后重复累加订单金额。完整定义见[指标口径](docs/指标口径.md)。

## 快速开始

### 1. 准备环境

需要 Python 3.10+、MySQL 和 Dify，并在 Dify 中配置 DeepSeek、database、ECharts 插件。项目脚本只使用 Python 标准库，无需安装额外 pip 依赖。

```bash
git clone https://github.com/Carti111/commerce-analysis-assistant.git
cd commerce-analysis-assistant
```

### 2. 初始化数据库

```bash
python scripts/import_database.py
```

按终端提示输入本机 MySQL 管理账号密码。脚本创建独立数据库 `commerce_ai_demo`、导入模拟数据，并生成仅有查询权限的账号。若发现已有项目表，会停止导入，避免覆盖数据。

初始化后，专用只读账号的连接串保存在项目根目录 `.local-db-uri.txt`，该文件已被 Git 忽略。

也可手动依次执行 `database/01_schema.sql`、`database/02_seed.sql`，然后替换 `database/03_readonly_user.template.sql` 的密码占位符并创建只读账号。

### 3. 配置并运行 Dify

1. 在 Dify 工作室导入 [`workflow/电商经营分析助手.yml`](workflow/电商经营分析助手.yml)。
2. 确认两个 LLM 节点使用已配置的可用模型。
3. 点击顶部 **ENV**，将 `.local-db-uri.txt` 中的完整连接串填入 **Secret** 类型的 `DB_URI`。
4. 确认「执行只读SQL」节点的 DB URI 引用 `env.DB_URI`，输出格式为 JSON，然后预览运行。

手工配置连接时，格式如下：

```text
mysql+pymysql://commerce_reader:YOUR_PASSWORD@host.docker.internal:3306/commerce_ai_demo?charset=utf8mb4
```

`YOUR_PASSWORD` 为只读账号密码。Windows 上通过 Docker 运行的 Dify 插件可用 `host.docker.internal` 访问宿主机；其他部署方式应填写实际可达的 MySQL 地址。账号连接信息只在本地配置，不提交到仓库。

可以从这些问题开始：

- 查看9月各品类销售额
- 查看近7天销售额趋势
- 查看9月渠道销售占比
- 查看近30天客户排行
- 查看9月销售额与订单数

## 开发与验证

```text
config/       插件版本配置
database/     建表、模拟数据与只读账号模板
workflow/     可导入的 Dify 工作流
prompts/      查询规划与结果分析提示词
nodes/        Python 节点代码
scripts/      初始化、构建与验证脚本
evaluation/   验收用例、参考 SQL 与验证记录
docs/         指标定义与演示截图
```

修改提示词或节点代码后，重新生成工作流，再导入 Dify：

```bash
python scripts/build_workflow.py
python scripts/check_project.py
```

项目包含 **23 条验收用例**。已通过 11 组本地检查、16 条 MySQL 参考查询和 3 项权限拒绝检查；参考查询结果不等同于模型问答准确率。用例与期望结果见[验收数据](evaluation/cases.json)，实际运行记录见[手工验收记录](evaluation/手工验收记录.md)。

当前支持受约束的单层 SELECT、显式 JOIN 和基础聚合；SQL 检查采用词法与规则校验，数据库只读权限负责限制实际访问。演示数据不包含库存、广告或访问流量，也不提供未来销售预测。
