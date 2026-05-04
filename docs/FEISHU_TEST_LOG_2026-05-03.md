# Feishu Test Log

Date: 2026-05-03

## What happened

This run showed two different things at once:

1. Feishu itself can be driven successfully on the main screen when the UIA fallback path is used well.
2. The later calendar failure was not simply a grounding instability. The agent followed its own planned recovery steps too rigidly after clicking `Today`, instead of re-evaluating that the UI had already moved into a useful schedule-creation state.

## Key evidence

- The run started with a main-model / grounding-model configuration that was effectively the same endpoint and same model.
- The captured screen size was `3520 x 1200`, while the runtime grounding image size was `1919 x 654`.
- Feishu chat entry clicks landed within bounds and worked.
- Message input grounding returned y-coordinates around `781` on a `654`-pixel image, which was out of range.
- The later successful message send happened because the UIA text fallback matched the input field placeholder and completed the paste/send path.
- In the calendar test, after the agent clicked `Today`, the UI state changed. The agent continued with its scripted recovery loop rather than adapting to the actual current state.

## Important log facts

- `MODEL_INTERFACE_INIT` showed:
  - `same_model: True`
  - `same_url: True`
  - `requested_grounding_size: (1920, 1080)`
  - `actual_grounding_size: (1919, 654)`
- `GROUNDING_RESPONSE` for the message input field returned points like:
  - `<point>257 781</point>`
  - `<point>228 782</point>`
- `GROUNDING_COORD_OUT_OF_RANGE` was recorded for the message input field.
- The successful task completion log showed the worker ending with `agent.done()`.

## Why it worked

- The Feishu chat entry click succeeded because the returned coordinates were in range.
- The message input step succeeded because the placeholder text was specific enough for UIA matching.
- The bad bottom-area coordinates were no longer the only route, so the UIA fallback carried the run.

## Why this still matters

- The generic agent capability is broader than Feishu.
- The Feishu-specific path is now split from the sandbox interface, but the grounding interface itself still looks unstable.
- The more important calendar issue is agent-level state adaptation: it can strictly follow a self-generated sequence even when the screen state has changed enough that the next action should be reconsidered.
- This log is useful as a reference point for deciding whether Feishu needs stronger state-aware verification between actions, not only better clicking.

## Correction After Review

The calendar failure should be interpreted as a planning/state issue first:

- Grounding may still have coordinate-contract issues in some places, especially around screen sizing, but that was not the only or primary explanation for the calendar behavior.
- The agent clicked `Today`, which changed the interface state.
- Instead of recognizing the new state and adjusting, it kept following the planned route for creating a schedule.
- The result was a loop: navigate/recover, open or approach creation, then continue from stale assumptions.

Working hypothesis: Feishu workflows need stronger per-step state verification and opportunistic replanning. The agent should ask, "Given the current screen, what useful state am I already in?" before continuing a previously planned sequence.

## Files touched in this round

- `gui_agents/s3/agents/grounding.py`
- `gui_agents/s3/memory/procedural_memory.py`
