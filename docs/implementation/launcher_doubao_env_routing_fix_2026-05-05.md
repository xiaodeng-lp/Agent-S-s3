# Launcher Doubao Env Routing Fix (2026-05-05)

## Goal

修复 `launcher.py` 中 Doubao / ARK 主模型与定位模型的环境变量路由，避免主模型错误继承定位模型的 `ARK_API_KEY`，导致主模型 `ep-id` 连通性测试返回 `403 AccessDenied`。

## Problem Summary

当前 `env.txt` 同时存在两组 ARK 凭据：

- 主模型：`ep-id` + `api-key`
- 定位模型：`ARK_API_KEY` + 固定视觉模型名

但 `launcher.py` 的 `_apply_env_defaults()` 先取：

```python
ark_key = env.get("ARK_API_KEY") or env.get("api-key", "")
```

然后把这个值同时灌给：

- `main_providers["volcano"]["model_api_key"]`
- `ground_providers["doubao_ark"]["api_key"]`

这会导致：

1. `env.txt` 中如果同时提供 `ARK_API_KEY` 和 `api-key`，主模型优先吃到 `ARK_API_KEY`
2. 主模型实际请求参数变成：`model=ep-id` + `api_key=ARK_API_KEY`
3. 当 `ARK_API_KEY` 只对视觉定位 endpoint 有权限时，主模型连通性测试返回 `403`

## Source Of Truth

1. `AGENTS.md`
2. `launcher.py`
3. `env.txt.example`
4. `docs/openai_api_parameters.md`

## Module Boundary

本次只修：

- `launcher.py` 的 `env.txt` 读取与默认路由
- `env.txt.example` 的字段说明
- 必要的文档说明与自动化测试

本次不修：

- `cli_app.py` 的运行链路
- Doubao grounding 解析逻辑
- 真实联网鉴权结果本身

## Target Files

- `launcher.py`
- `env.txt.example`
- `docs/openai_api_parameters.md`
- `tests/test_launcher_env_config.py`

## Implementation Plan

1. 将主模型与定位模型的 env 路由拆开：
   - 主模型优先用 `api-key`
   - 定位模型优先用 `ARK_API_KEY`
2. 为主模型补充更清晰的兼容别名，减少 `api-key` / `ARK_API_KEY` 歧义。
3. 对旧 fallback 污染做最小兼容修复：
   - 当主模型当前 key 等于定位 key，且 `env.txt` 明确提供了 `api-key` 时，自动回切主模型到 `api-key`
4. 更新示例文档，明确：
   - 主模型在 ARK 路由下走 `Endpoint ID`
   - 定位模型走固定视觉模型名
5. 增加 focused tests，覆盖主模型 / 定位模型 key 分流行为。

## Verification

自动化验证：

1. `env.txt` 同时提供 `api-key` 与 `ARK_API_KEY` 时：
   - 主模型取 `api-key`
   - 定位模型取 `ARK_API_KEY`
2. 仅提供 `ARK_API_KEY` 时：
   - 主模型和定位模型都允许 fallback 到该 key
3. 旧污染场景：
   - 若主模型 key 被旧逻辑写成 `ARK_API_KEY`，且 env 中存在 `api-key`，应自动修正为 `api-key`

命令验证：

- `python -m unittest tests.test_launcher_env_config -v`
- `python -m compileall launcher.py tests/test_launcher_env_config.py`

## Risks

1. 若用户刻意希望主模型与定位模型共用同一个 ARK key，本次修复不应破坏该场景。
2. 若现有本地 `config.json` 已保存手工配置，需要避免被 env 默认值粗暴覆盖。
3. 文档若仍写“主模型直接填 doubao-seed-2.0-pro”，会继续造成使用歧义。

## Rollback

若本次修复引入新的配置兼容问题：

1. 保留测试文件
2. 回滚 `launcher.py` 的迁移逻辑
3. 保留文档中对主模型 / 定位模型凭据分离的说明
