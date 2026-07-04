"""
The ULTRON agent loop.

A portable ReAct controller: it shows the LLM the tool catalogue and asks it
to reply with strict JSON — either a tool call or a final answer. It runs the
tool, feeds back the observation, and loops until the model is done (or a step
cap is hit). This works identically for every provider, including mock.

Emits a stream of structured events so the UI can show ULTRON "thinking",
calling tools, and answering in real time.
"""
from __future__ import annotations

import json
import re
from typing import Iterator

from . import memory
from .config import SYSTEM_PROMPT, settings
from .llm import complete, vision_complete
from .profile import profile_prompt
from .tools import dispatch, tool_catalog

MAX_STEPS = 6

_PROTOCOL = """You operate as a step-by-step agent. On each turn reply with a \
SINGLE JSON object and nothing else.

To use a tool:
{{"thought": "<brief reasoning>", "action": "<tool_name>", "action_input": {{<args>}}}}

To give your final answer to the user:
{{"thought": "<brief reasoning>", "final": "<your reply>"}}

Available tools:
{tools}

Rules:
- Prefer tools for anything requiring current info or an action.
- After you receive an OBSERVATION, either call another tool or give "final".
- Never invent tool output. Keep "final" answers natural and in character.
"""


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model reply, tolerantly."""
    text = text.strip()
    # strip ``` fences if present
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, flags=re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    # Model gave prose — treat it as a final answer.
    return {"final": text}


_MODE_HINTS = {
    "brief": "\n\n# Length for THIS reply\nBe brief and to the point — a few "
             "sentences at most. No preamble.",
    "deep": "\n\n# Length for THIS reply\nGo deep: give a thorough, well-"
            "structured answer with reasoning, examples, and code where useful.",
}


def run(session: str, user_message: str, image: str | None = None,
        mode: str | None = None) -> Iterator[dict]:
    """Yield events: {type: thought|tool|observation|final|error, ...}.

    If `image` (a data URL) is supplied, ULTRON looks at it with a vision
    model and answers about it directly. `mode` ('brief'|'deep'|'auto')
    tunes answer length for this turn.
    """
    logged = user_message + (" [image attached]" if image else "")
    memory.add_message(session, "user", logged)

    mode_hint = _MODE_HINTS.get(mode or "", "")

    # --- vision branch: an image was attached ---
    if image:
        yield {"type": "thought", "text": "Analysing the attached image."}
        vsystem = SYSTEM_PROMPT + "\n\n" + profile_prompt() + mode_hint
        answer = vision_complete(vsystem, user_message, image)
        memory.add_message(session, "assistant", answer)
        yield {"type": "final", "text": answer}
        return

    system = (SYSTEM_PROMPT + "\n\n" + profile_prompt() + mode_hint + "\n\n"
              + _PROTOCOL.format(tools=tool_catalog()))
    convo = [{"role": "system", "content": system}]
    convo += memory.get_history(session, limit=20)

    for step in range(MAX_STEPS):
        raw = complete(convo)
        data = _extract_json(raw)

        thought = data.get("thought", "")
        if thought:
            yield {"type": "thought", "text": thought}

        if "final" in data:
            answer = data["final"]
            memory.add_message(session, "assistant", answer)
            yield {"type": "final", "text": answer}
            return

        action = data.get("action")
        action_input = data.get("action_input", {}) or {}
        if not action:
            answer = raw
            memory.add_message(session, "assistant", answer)
            yield {"type": "final", "text": answer}
            return

        yield {"type": "tool", "name": action, "input": action_input}
        observation = dispatch(action, action_input)
        yield {"type": "observation", "name": action, "text": observation}

        # Record the exchange for the model's next turn.
        convo.append({"role": "assistant", "content": json.dumps(data)})
        convo.append({"role": "user", "content": f"OBSERVATION: {observation}"})

    # Ran out of steps — force a wrap-up.
    yield {"type": "final",
           "text": "I've hit my step limit for this request, sir. "
                   "Here's what I gathered above."}
