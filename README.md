# 商析助手：电商经营分析

把原有的学生成绩查询工作流改造成电商经营分析个人项目。保留Dify + MySQL + Python + ECharts链路，重新设计业务数据、指标口径、查询约束和验收方式。

这是基于Dify教学工作流进行业务改造的个人学习项目。销售额、订单数和客单价已在本机Dify预览中人工核对；完整23条端到端验收尚未完成。所有数据均为模拟数据，没有真实客户信息。

运行环境：Python 3.10+、MySQL、Dify，以及已配置的DeepSeek、database和ECharts插件。Python脚本只用标准库，无需安装pip依赖。项目来源与组件说明见[NOTICE.md](NOTICE.md)。

## 实际演示

2026年9月有效销售额为53,247.35元，有效订单数209，客单价254.77元。以下为本机Dify预览截图，均使用模拟数据：

| 销售额查询 | 订单数与客单价查询 |
|---|---|
| ![销售额查询](docs/screenshots/sales-summary.png) | ![订单数与客单价](docs/screenshots/order-metrics.png) |

## 能做什么

- 用自然语言查询销售额、有效订单数、客单价、商品销量、地区/渠道表现、客户贡献及全额退款订单率。
- 从四张表进行必要的关联查询，并将实际执行结果汇总成Markdown表格。
- 按用户需求选择柱状图、线性图、饼图，或仅输出文字和表格。
- 对模糊问题先澄清；对库存、广告、转化率、未来预测和数据写入请求明确说明不支持。

数据规模：240位模拟客户、32件商品、1,200笔订单、3,043条订单明细。

时间范围：2026-04-01至2026-10-15。演示“今天”固定为2026-10-16；最近30天固定为2026-09-16至2026-10-15。之后更换真实数据时，需同步更新日期规则。

## 与原工作流的区别

| 项目点 | 原成绩查询流程 | 当前电商版本 |
|---|---|---|
| 数据模型 | 学生成绩单表 | 客户、商品、订单、明细四表 |
| 查询范围 | 一个问题扩展最多10条SQL | 通常1条，必要时最多3条，问题不明确时澄清 |
| 指标定义 | 主要靠提示词描述 | 明确销售额、销量、客单价、退款率及估算毛利口径 |
| SQL约束 | JSON解析后直接执行 | 词法/规则检查、表和函数允许列表、最多100行、5秒SELECT提示，配合只读账号 |
| 结果传递 | 拼接Python字符串，可能失去查询关系 | 每个结果保留标题、SQL、口径、行数和实际记录 |
| 错误处理 | 可能静默忽略查询失败、返回空白默认值 | 查询失败终止；空结果与异常区分；非法图表参数明确报错 |
| 用户输出 | 多个技术进度消息 | 正文和图表，或可理解的澄清/不支持提示 |
| 验收 | 临时提问 | 23条问题、16条参考SQL、独立期望结果和验证报告 |

## 数据和流程

```mermaid
erDiagram
  customers ||--o{ orders : places
  orders ||--|{ order_items : contains
  products ||--o{ order_items : referenced_by
```

```mermaid
flowchart LR
  A[用户问题] --> B[模型规划SQL与口径]
  B --> C[Python解析与SQL规则检查]
  C --> D{是否可执行}
  D -->|否| E[澄清或不支持说明]
  D -->|是| F[顺序查询只读数据库]
  F --> G[保留每条查询与实际结果]
  G --> H[模型基于结果汇总]
  H --> I[正文和图表参数检查]
  I --> J[输出分析正文]
  J --> K{图表类型}
  K --> L[ECharts图表]
```

## 第一步：导入新数据库

已存在的成绩库不会被修改。数据库名为`commerce_ai_demo`，应使用一个尚未创建同名表的新库。

在本项目目录打开终端，执行：

```powershell
python scripts/import_database.py
```

脚本会在本机终端询问MySQL管理账号密码；不用把密码发送到聊天中。它只会创建新项目库及专用只读账号，不会删除或重置已有数据。若发现已有项目表或重名账号，会停止而不是覆盖。

默认连接本机127.0.0.1:3306，自动查找mysql.exe，也支持显式指定：

```powershell
python scripts/import_database.py --mysql "D:/MySQL/Server/bin/mysql.exe" --port 3306 --user root
```

成功后在项目根目录生成`.local-db-uri.txt`，内容是专用只读账号的连接串。该文件已列入`.gitignore`，不要分享或提交。不要把root连接串填给工作流。

如果希望手工导入，依次执行`database/01_schema.sql`、`database/02_seed.sql`，再修改并执行`database/03_readonly_user.template.sql`中的密码占位符。不要在运行初始化脚本之后再重复执行这些文件。

只读账号仅获四张演示表的SELECT权限。数据库插件本身能执行任意SQL，因此账号权限是必要边界；不能把提示词或本项目的规则检查当成完整隔离机制。[数据库插件说明](https://github.com/hjlarry/dify-plugin-database)、[MySQL GRANT文档](https://dev.mysql.com/doc/refman/8.0/en/grant.html)。

## 第二步：导入Dify工作流

1. 在Dify工作室选择“导入DSL文件”，导入`workflow/商析助手-电商经营分析.yml`，作为一个新应用。
2. 保留已有成绩查询应用，方便对照和回退。
3. 根据导入提示安装DeepSeek、database、ECharts插件。文件沿用原工作流中已使用的插件标识，不强制升级。
4. 在两个LLM节点中确认你当前可用的DeepSeek模型。默认沿用原流程的`deepseek-v4-flash`名称；若账号或插件里没有此型号，选择你已配置并能正常调用的模型。
5. 在环境变量中找到秘密变量`DB_URI`，把`.local-db-uri.txt`内容填入。导出文件的值为空是正常的，交付包不包含凭证。
6. 打开“执行只读SQL”节点，确认输出格式为JSON，DB URI引用`env.DB_URI`。若插件要求授权，使用同一个专用只读连接配置，不要沿用成绩库的管理账号。
7. 先在预览中测试，不需要先发布。

连接串应类似：

```text
mysql+pymysql://commerce_reader:你的随机密码@host.docker.internal:3306/commerce_ai_demo?charset=utf8mb4
```

Windows上Dify插件在Docker中运行时，`host.docker.internal`通常用于访问宿主机MySQL；插件中的`localhost`指容器自身，不能直接等同于宿主机。[插件连接说明](https://github.com/hjlarry/dify-plugin-database)。若Dify部署在其他机器，改为MySQL服务器实际可达地址。

两个模型节点设置了`reasoning_format: separated`，同时代码仍兼容纯JSON、Markdown代码块及完整的`<think>`前缀。Dify提供思考标签分离能力；旧版本界面不支持该开关时，保留代码兼容处理即可。[Dify LLM文档](https://docs.dify.ai/en/cloud/use-dify/nodes/llm)。本版使用明确JSON契约和代码校验，未依赖原生结构化输出开关。

DSL文件采用JSON语法的YAML子集，扩展名为`.yml`，可以按DSL文件导入；项目生成脚本不需要额外安装YAML库。

## 第三步：先跑这四个问题

1. 查询2026年9月各品类销售额，用柱状图展示。
2. 最近7天每天的有效销售额是多少？用线性图展示。
3. 统计2026年9月各渠道销售额占比，用饼图展示。
4. 查询2026年9月销售额、有效订单数、客单价和购买客户数，不要图表。

第4题的参考结果是：

| 指标 | 参考值 |
|---|---:|
| 有效销售额 | 53,247.35元 |
| 有效订单数 | 209 |
| 客单价 | 254.77元 |
| 购买客户数 | 123 |

结果对上后，再完成`evaluation/手工验收记录.md`中的全部23条问题。`evaluation/cases.json`包含参考SQL和期望记录，可在MySQL中独立核对。模型SQL的文本不必和参考SQL完全相同，应检查指标口径和实际结果。

## 本地验证和已完成的检查

```powershell
python scripts/check_project.py
```

当前11组本地检查通过，覆盖参考SQL可接受性、越权/写入拦截、批次原子拒绝、JSON格式、空结果区分、图表点位、外键/金额一致性和DSL引用。

如果需要重新验证真实MySQL语法和只读权限：

```powershell
python scripts/verify_mysql.py --mysql-bin "D:/MySQL/Server/bin"
```

该命令创建全新的临时数据目录和仅绑定127.0.0.1的临时实例，在操作完成后关闭并清理；不会连接你现有的3306实例。当前已用本机MySQL 26.7.0验证16条参考查询及3项权限拒绝检查，详情见`evaluation/mysql_validation_report.json`。

这些是数据库、代码和数据口径验证，不是大模型问答正确率。用户已在Dify中人工核对9月销售额53,247.35元、有效订单数209及客单价254.77元，柱状图也已生成。完整23条端到端验收、模型耗时、Token成本和SQL生成准确率仍待实测；未验证项不视为通过。窄屏预览中可能发生图表轴标签裁切，当前保留插件原始图表配置。

## 代码组织

| 路径 | 内容 |
|---|---|
| `workflow/` | 可导入DSL |
| `config/` | 构建时使用的插件版本标识 |
| `database/` | 建表、模拟数据、只读账号模板、数据快照及清单 |
| `prompts/` | SQL规划与结果汇总提示词 |
| `nodes/` | 可单独编辑的Dify Python节点代码 |
| `scripts/` | 数据生成、DSL构建、导入及本地验证 |
| `evaluation/` | 验收问题、参考SQL、期望结果、真实验证报告 |
| `docs/` | 指标口径和简历/面试说明 |

修改节点代码或提示词后执行`python scripts/build_workflow.py`，再导入生成的新DSL；文件修改不会自动同步已导入的Dify应用。修改模拟数据时重新运行`generate_data.py`与`build_evaluation.py`；生成文件并不会自动更新已导入的数据库。

所有构建输入均保存在本仓库中，不依赖原教学目录。上传GitHub的步骤见[GitHub上传步骤](docs/GitHub上传步骤.md)。

## 当前边界

只支持受约束的单层SELECT、显式JOIN和基础聚合，不支持CTE、子查询、UNION和窗口函数。检查器是词法/规则检查，不是完整SQL AST解析器，也不证明所有可接受SQL都语义正确。MySQL只读权限、行数上限、函数允许列表和执行时间提示共同降低风险；MAX_EXECUTION_TIME是服务器处理的SELECT提示，不能当作所有资源消耗的绝对保证。

没有实现RAG、模型微调、缓存、自动SQL修复、预测模型、自研前端或高并发服务。需要在简历中展示的是你理解并实际完成的数据建模、工作流编排、指标定义、异常处理和验证工作。
