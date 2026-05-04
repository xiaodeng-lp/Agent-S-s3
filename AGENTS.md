# AGENTS

## Purpose

This repo is `Agent-S` secondary development for a Feishu desktop GUI agent.

Current baseline:

- `launcher.py` is the product shell
- `gui_agents/s3/` is the generic GUI kernel
- `sop_executor.py` and `sops/` are the lightweight scripted path

Feishu capability should be added as a domain layer, not by continuously polluting `gui_agents/s3/`.
Current mainline is `Windows + 飞书桌面端 + GUI-first`, not Feishu CLI, bot, or open-platform-first integration.

## Source Of Truth

Read in this order before changing architecture or module boundaries:

1. `docs/项目需求.md`
2. `docs/feishu_gui_agent_master_plan.md`
3. `docs/product/feishu_gui_agent_prd.md`
4. `docs/spec/feishu_gui_agent_technical_spec.md`
5. `docs/interfaces/feishu_gui_agent_interfaces.md`
6. `CONTRIBUTE.md`

## Collaboration Rules

1. Use multiple coding agents only when module ownership is clear and write scopes are disjoint.
2. Every module change must follow `analysis -> manual plan -> coding -> review`.
3. Do not code before the manual plan is understood by both the model and the human.
4. If an interface changes, update `docs/interfaces/` before or together with implementation.
5. After coding, run minimal verification first; use a different agent for review when practical.
6. Do not assume Feishu open-platform capability exists unless the task explicitly targets that mode.
7. Prefer separate git worktrees for `main` and active feature branches when parallel work is ongoing.

## Ownership Boundaries

Prefer parallel work in these areas:

- `gui_agents/feishu/testcases/`
- `gui_agents/feishu/planner/`
- `gui_agents/feishu/pages/`
- `gui_agents/feishu/detectors/`
- `gui_agents/feishu/locators/`
- `gui_agents/feishu/workflows/`
- `gui_agents/feishu/verifiers/`
- `gui_agents/feishu/reports/`
- `gui_agents/feishu/maintenance/`

Default parallel rollout:

- first wave: `testcases/planner` + `pages/detectors/locators` + `workflows/verifiers`
- second wave: `reports/maintenance`
- final serial integration: `feishu_worker` and `s3` high-coupling files

Treat these as high-coupling and change them serially:

- `gui_agents/s3/agents/worker.py`
- `gui_agents/s3/agents/grounding.py`
- `gui_agents/s3/cli_app.py`
- `gui_agents/s3/memory/procedural_memory.py`
- future `gui_agents/feishu/agents/feishu_worker.py`

## Architecture Constraints

1. Keep `s3` as the generic GUI kernel.
2. Add Feishu logic under `gui_agents/feishu/`.
3. Prefer explicit `TestCase -> Planner -> Workflow -> Verifier -> Report` contracts.
4. Do not use unconstrained free-form agent execution as the main path.
5. Do not treat memory as the primary solution; stabilize actions, state detection, locators, verifier gates, and fallback first.
6. Any future API adapter must remain optional and isolated from the GUI-first path.

## Planning Standard

Before coding any module, write a short manual plan with:

- target files and ownership
- interface changes
- direct dependencies
- verification path
- risk or rollback notes

If the change touches a high-coupling module, finish plan review before any edit.

## Branch And Worktree

1. Keep `main` as the integration branch, not the active feature workspace.
2. Do feature work on dedicated branches and dedicated worktrees.
3. Sync by updating `main` first, then rebasing feature branches onto `main`.
4. Do not develop the same branch from multiple worktrees at the same time.

## Delivery Standard

Each completed module should include:

- explicit module boundary
- success criteria or verifier
- fallback or failure handling
- minimal regression evidence
- short review summary with risks and follow-ups
