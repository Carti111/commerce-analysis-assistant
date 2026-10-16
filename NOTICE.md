# 项目来源与组件说明

本项目是基于Dify教学工作流进行场景改造的个人学习项目，改造方向为电商经营分析。项目复用了教学流程中的自然语言生成SQL、数据库查询和图表展示思路，新增了四表电商数据模型、模拟数据生成、指标口径、查询约束、异常分支和可重复验证材料。

使用的第三方组件：

- [Dify](https://github.com/langgenius/dify)：工作流编排和应用运行环境。
- [DeepSeek模型插件](https://marketplace.dify.ai/plugins/langgenius/deepseek)：模型调用；需要使用者自行配置账号。
- [hjlarry/database](https://github.com/hjlarry/dify-plugin-database)：数据库工具。
- [ECharts](https://echarts.apache.org/)及Dify ECharts插件：图表配置与渲染。

这些第三方组件没有被复制进本仓库，使用时应遵守各组件自己的许可与服务条款。本项目不声称自行研发这些底层组件，也不附带模型API密钥、数据库密码或真实客户数据。
