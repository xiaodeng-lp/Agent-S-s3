# Plan: OSCAR-Inspired Per-Step State Verification

Status: implemented  
Date: 2026-05-03

## Problem

Agent S follows a pre-formed plan mechanically even when the UI has already moved into a more advanced state. After clicking "Today" in the Feishu calendar, the UI entered a schedule-creation-adjacent state, but the agent continued its scripted recovery loop instead of recognising the new state and adapting.

Root cause: the reflection system only detects cycles (stuck / on-track / done). Neither the reflection agent nor the generator is asked "am I already ahead of where I expected to be?"

## Solution

Adapt OSCAR's Observe → Verify(expected vs actual) → Act → Expect loop into Agent S's existing two-file structure. No new LLM calls. Reflection system untouched.

---

## Change 1: `gui_agents/s3/memory/procedural_memory.py` lines 80–112

Replace the four-section generator format:

```
(Previous action verification)
(Screenshot Analysis)
(Next Action)
(Grounded Action)
```

with five sections:

```
(Observe)
(State Verification)
(Next Action)
(Expected Next State)
(Grounded Action)
```

### New section text

**(Observe)** — replaces both "Previous action verification" and "Screenshot Analysis":

```
(Observe)
Look only at the current screenshot. Describe what view or mode the application is currently in and what controls are visible. Do not reference your plan history here — only describe what you see right now.
```

**(State Verification)** — new section after Observe:

```
(State Verification)
Compare the current screen to the Expected Next State from your last step (shown in this message as "Expected state from last action: ...").
Classify the current state as one of:
- As expected: the last action worked as planned, continue
- Behind: the screen has not changed or the last action had no effect, consider a retry or alternative
- Ahead: the UI has already reached a state you planned to reach in a future step; explicitly identify which planned steps are now unnecessary and skip them
If this is the first step, write: "First step — no expected state."
```

**(Next Action)** — small wording change:

```
(Next Action)
Based on the current screen state (from Observe and State Verification above) and what still needs to be done to complete the task, decide the single next action.
```

**(Expected Next State)** — new section before Grounded Action:

```
(Expected Next State)
In one sentence, describe what the screen should look like immediately after the next action succeeds. Be specific: name the UI view, dialog, or element that should appear or change.
```

**(Grounded Action)** — keep ALL existing text and notes 1–13 unchanged.

---

## Change 2: `gui_agents/s3/agents/worker.py`

### 2a. Add to `reset()` (around line 77)

```python
self.last_expected_state: str = ""
```

### 2b. Add helper function at top of file (after imports)

```python
import re as _re

def _parse_expected_next_state(plan: str) -> str:
    match = _re.search(
        r'\(Expected Next State\)[^\n]*\n(.*?)(?=\n\s*\(|\n\s*```|$)',
        plan,
        _re.DOTALL | _re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    return ""
```

### 2c. Inject last step's expected state into generator message (in `generate_next_action()`, around line 195, before `self.generator_agent.add_message(...)`)

```python
if self.turn_count > 0 and self.last_expected_state:
    generator_message = (
        f"Expected state from last action: {self.last_expected_state}\n\n"
        + generator_message
    )
```

### 2d. Extract and store expected state after getting the plan (in `generate_next_action()`, around line 353, after `call_llm_formatted(...)`)

```python
self.last_expected_state = _parse_expected_next_state(plan)
```

---

## What is NOT changed

| Component | Reason |
|---|---|
| `REFLECTION_ON_TRAJECTORY` prompt | No new cases added; reflection naturally gets richer `worker_history[-1]` (now contains Expected Next State) |
| `SINGLE_ACTION_FORMATTER` | Only checks code block — unaffected by new sections |
| `CODE_VALID_FORMATTER` | Only checks code validity — unaffected |
| `grounding.py` | Not touched |
| `cli_app.py` | Not touched |

---

## Fallback behaviour

- If the model omits `(Expected Next State)`: `_parse_expected_next_state` returns `""`, nothing is injected next step, behaviour degrades gracefully to current state.
- If `(State Verification)` is ignored by model: `(Observe)` still forces screen-first description, partial improvement preserved.

---

## Verification after implementation

Run the Feishu calendar task. In `logs/normal-*.log`, look for:
- `(Observe)` sections that describe a calendar creation view
- `(State Verification)` sections that say "Ahead" and skip planned steps
- Fewer redundant navigation actions after a state has already been reached
