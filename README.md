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
