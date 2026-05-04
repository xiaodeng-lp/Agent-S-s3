# 飞书 GUI Agent 文档索引

## 1. 阅读顺序

1. [项目需求](./项目需求.md)
2. [主方案](./feishu_gui_agent_master_plan.md)
3. [PRD](./product/feishu_gui_agent_prd.md)
4. [Technical Spec](./spec/feishu_gui_agent_technical_spec.md)
5. [Interface Doc](./interfaces/feishu_gui_agent_interfaces.md)
6. [并行开发执行规范](./process/feishu_gui_agent_parallel_dev_playbook.md)
7. [参考文档](#5-参考文档)
8. [Archive](./archive/)

## 2. 文档职责

- `项目需求.md`：外部输入，定义竞赛题目和原始要求。
- `feishu_gui_agent_master_plan.md`：唯一主设计文档，回答“整体怎么做”。
- `product/feishu_gui_agent_prd.md`：产品范围、阶段目标、验收口径，回答“做什么、做到什么程度”。
- `spec/feishu_gui_agent_technical_spec.md`：模块拆分、数据模型、并行开发边界，回答“工程上怎么落地”。
- `interfaces/feishu_gui_agent_interfaces.md`：内部模块契约，回答“模块之间如何对接”。
- `process/feishu_gui_agent_parallel_dev_playbook.md`：团队和多 agent 协作执行规范，回答“并行开发怎么做而不打架”。
- `../CONTRIBUTE.md`：仓库级贡献规范，回答“提交前要检查什么、PR 怎么提、并行开发怎么守规则”。
- `archive/`：历史草案归档，不再作为主维护入口。

## 3. 推荐协作流程

1. 先看 `项目需求.md` 和 `master plan`，确认目标与架构边界。
2. 针对单个模块，先写手动 plan，再对照 `spec` 和 `interfaces` 校准边界。
3. 并行开发前，再看 `process/feishu_gui_agent_parallel_dev_playbook.md` 确认拆分方式和联调顺序。
4. plan 审阅通过后再 coding。
5. coding 后先做最小验证，再做 review。
6. 若改动影响跨模块契约，必须同步更新 `interfaces`。

## 4. 变更规则

- 产品范围或里程碑调整：更新 `PRD`。
- 架构、模块职责或并行开发边界调整：更新 `master plan` 和 `spec`。
- 输入输出、数据结构、调用方式调整：更新 `interfaces`。
- 过时设计稿移入 `archive/`，不要继续在旧稿上增量维护。

## 5. 参考文档

- [openai_api_parameters.md](./openai_api_parameters.md)：模型参数与推理配置参考。属于通用参考资料，不是当前飞书 GUI Agent 架构的 source of truth。
