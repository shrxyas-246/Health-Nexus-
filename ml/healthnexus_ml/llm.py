"""Optional LLM narration over the wellness model's output.

What this is, and what it deliberately is not: the trained models decide
*everything clinical* — the plan archetype, the calorie and protein targets, the
dietary restrictions, the training intensity. This layer only rewrites the
**explanation** in the patient's own context, so the same plan reads as "because
your HbA1c is where it is and you walk to work already" rather than as a generic
paragraph.

That split is the whole point. Numbers and restrictions come from models that
were trained and measured; prose comes from the LLM. An LLM is not permitted to
invent a target here, and the caller keeps the structured payload regardless of
what comes back.

Off unless configured. If the `anthropic` package or a credential is missing, or
the call fails for any reason, ``narrate`` returns the input untouched and the
product serves the reviewed template copy — no user-visible failure.

Set ``HNX_LLM_NARRATION=1`` and provide ``ANTHROPIC_API_KEY`` to enable.

On fine-tuning: the product spec asks for a fine-tuned model here. Fine-tuning
is not available for Claude, and no local base model is shipped with this repo,
so the equivalent — and the standard approach for this shape of task — is a
grounded prompt over a structured, model-derived patient state. If a fine-tuned
open-weights model is added later, it slots in behind this same ``narrate``
interface without any change above it.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

MODEL = "claude-opus-5"
MAX_TOKENS = 1200  # deliberately short: three sentences per card, nothing more

SYSTEM_PROMPT = """You rewrite the one-line rationale on a patient's daily health plan card so it reads as personal rather than generic.

Hard rules:
- Never state, change or imply a calorie target, protein target, medicine, dose or diagnosis. Those come from a separate clinical model and are shown to the patient verbatim elsewhere.
- Never add a new restriction or remove one you are given.
- Ground every sentence in the patient facts provided. If a fact is not in the input, do not mention it.
- Two sentences maximum per card. Plain, warm, direct. No emoji, no exclamation marks, no "as an AI".
- British English spelling.

Output format: one line per card, in the order given, each prefixed with the card kind and a pipe, e.g.
diet|<rewritten rationale>
workout|<rewritten rationale>
lifestyle|<rewritten rationale>
Output nothing else."""


def is_enabled() -> bool:
    if os.getenv("HNX_LLM_NARRATION", "").lower() not in {"1", "true", "yes"}:
        return False
    if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def _patient_summary(record: dict[str, Any], prediction: dict[str, Any]) -> str:
    conditions = [
        c.get("name") if isinstance(c, dict) else str(c)
        for c in (record.get("conditions") or [])
    ]
    restrictions = [
        name for name, value in prediction.get("restrictions", {}).items() if value.get("flag")
    ]
    lines = [
        f"Age: {record.get('age', 'unknown')}",
        f"Active conditions: {', '.join(conditions) if conditions else 'none recorded'}",
        f"BMI: {record.get('bmi', 'not recorded')}",
        f"Typical sleep: {record.get('sleep_hours', 'not recorded')} hours",
        f"Activity level (0 sedentary – 3 very active): {record.get('activity_level', 'not recorded')}",
        f"Plan archetype chosen by the clinical model: {prediction.get('archetype')}",
        f"Training intensity chosen by the clinical model: {prediction.get('workout_intensity')}",
        f"Dietary restrictions in force: {', '.join(restrictions) if restrictions else 'none'}",
    ]
    return "\n".join(lines)


def narrate(cards: list[dict[str, Any]], record: dict[str, Any], prediction: dict[str, Any]) -> list[dict[str, Any]]:
    """Rewrite each card's `rationale` in the patient's context. Never raises."""
    if not is_enabled() or not cards:
        return cards

    try:
        import anthropic

        client = anthropic.Anthropic()
        current = "\n".join(f"{card['kind']}|{card['rationale']}" for card in cards)
        response = client.with_options(timeout=12.0, max_retries=1).messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Patient facts:\n{_patient_summary(record, prediction)}\n\n"
                        f"Current card rationales:\n{current}"
                    ),
                }
            ],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
    except Exception as error:  # noqa: BLE001 — narration must never break a plan
        logger.warning("LLM narration unavailable, serving template copy: %s", error)
        return cards

    rewritten = {}
    for line in text.splitlines():
        kind, separator, body = line.partition("|")
        if separator and body.strip():
            rewritten[kind.strip().lower()] = body.strip()

    out = []
    for card in cards:
        updated = dict(card)
        if card["kind"] in rewritten:
            updated["rationale"] = rewritten[card["kind"]]
            updated["narrated_by"] = MODEL
        out.append(updated)
    return out
