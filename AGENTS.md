# Agent S S3 Working Notes

This repository is being actively adapted for a Windows Feishu/Lark workflow.

## How to resume work

1. Read `docs/PROJECT_STATE.md` first.
2. Read `docs/DECISIONS.md` for the reasons behind the current patches.
3. Inspect `gui_agents/s3/agents/grounding_feishu.py` (Windows/Feishu actions), `gui_agents/s3/agents/_feishu_exec.py` (exec code builders), `gui_agents/s3/cli_app.py`, and `gui_agents/s3/memory/procedural_memory.py` before changing behavior.
   - `gui_agents/s3/agents/grounding.py` is kept identical to upstream — do not add Windows-specific code there.
4. Keep Feishu-specific changes aligned with the local helper scripts in `integrations/ui_tars_sandbox/`.
5. Make one behavior change per turn, then verify it from logs.

## Current operating assumptions

- Windows is the target platform.
- Feishu/Lark is the primary app under test.
- Main model and grounding model are configured through `config.json` and the launcher UI.
- The working goal is reliable desktop interaction, not a new UI.

## Notes for future edits

- Prefer focused patches over broad refactors.
- Preserve the current launcher workflow unless a change is clearly needed.
- When a click seems wrong, inspect `logs/execution-trace.log` before changing anything else.
