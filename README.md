# Card Review Toolkit

One Codex plugin containing card-proofreader, card-text-repair, and card-symbol-repair with 175 candidate icon assets.

## Install

Run with the Codex CLI installed:

```sh
codex plugin marketplace add raakshassh/card-review-toolkit
codex plugin add card-review-toolkit@card-review
```

Start a new task after installation.

## Use

Attach the original and enhanced card images and identify their roles.

- Ask: "Use card-proofreader to compare these cards and report confirmed errors with the collector number. Do not repair yet."
- After reviewing findings: "Use card-text-repair to fix the approved text errors, preserving font, alignment, background texture, and previous fixes."
- For symbols: "Use card-symbol-repair to prepare source-matched previews of the approved symbol repairs."

## Requirements and limits

Python with Pillow and NumPy for local edits and pixel checks; OpenCV when alignment or inpainting is needed. The bundled scripts require no separate API key. Codex account usage limits still apply.

These are agent-assisted skills, not a standalone automatic detector. Card Review Studio is not included. Icons require source matching; source blur can prevent exact font or symbol recovery.

The marketplace is at `.agents/plugins/marketplace.json`, and all plugin resources are under `plugins/card-review-toolkit/`. Keep hidden directories when copying.

See the plugin README for details and the [official packaging documentation](https://developers.openai.com/plugins/build/plugins) for marketplace installation.

## Version 1.1: consistent, faster preparation

The proofreader now uses one bundled engine with fixed overlapping card-relative crops, saved geometry, ordered contact sheets, native-pixel details on demand, hash-verified caching, and a coverage completion check. Start with the default grid; all templates cover the full card. Automatic boundary proposals require visual confirmation.

Install the Python dependencies once: `python -m pip install -r requirements.txt`. The engine lives in `plugins/card-review-toolkit/skills/card-proofreader/scripts/audit_engine.py`; its [workflow guide](plugins/card-review-toolkit/skills/card-proofreader/references/engine.md) explains commands and evidence records.

The routine-audit target is two minutes, not a cutoff or guarantee. A local Zorua fixture prepared in about two seconds and a cached repeat in under 0.1 seconds; those timings exclude AI review, tool latency, geometry correction and reporting. Blurry details can require longer inspection. The bundled tests verify deterministic crops, coverage, cache invalidation, native pixel preservation and completion gates, not model recognition accuracy.

To update an existing installation:

```sh
codex plugin marketplace upgrade card-review
codex plugin add card-review-toolkit@card-review
```

Start a new task to pick up the new skill instructions.
