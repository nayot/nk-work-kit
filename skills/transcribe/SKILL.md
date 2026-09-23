---
name: transcribe
description: Transcribe an audio recording (meeting, interview, lecture) into a Markdown transcript with timestamps and speaker labels, in Thai, English, or mixed. Use `/transcribe <audio-path>` or activate automatically when the user asks to "transcribe", "ถอดเสียง", "ถอดความ", "ทำ transcript", "get a transcript / minutes / notes from this recording", or points at an audio file (.m4a, .mp3, .wav, .aac, .ogg, .flac) and wants text out of it.
argument-hint: <audio-path> [model-id]
allowed-tools: [Bash, Read]
version: 1.0.0
---

# transcribe — Audio → Markdown Transcript

Wraps `scripts/transcribe.py` (vendored from
[autoTranscribe](https://github.com/nayot/autoTranscribe) — see that repo for
the canonical source and README). It sends audio to an audio-capable LLM via
OpenRouter and returns Markdown: a short summary, then a verbatim
`[MM:SS]`-timestamped, `**Speaker N**`-labeled transcript, **in the original
language** — Thai stays Thai, English stays English, mixed stays mixed. It
never translates.

## Arguments

`$ARGUMENTS`

Parse as: `<audio-path> [model-id]`
- `audio-path`: required. Path to the audio file.
- `model-id`: optional OpenRouter model ID (see table below). If omitted,
  pick one yourself per the guidance below — **do not ask the user to choose
  from a menu**; the underlying script's menu is interactive and this skill
  always runs it non-interactively with `--model` and `--yes`.

## Requirements

- `uv` on PATH — the script is self-contained (PEP 723 inline deps), no
  `pip install` needed.
- `ffmpeg` + `ffprobe` on PATH.
- `OPENROUTER_API_KEY`. The script reads it from the environment or from a
  `.env` file: **`~/.config/nk-work-kit/.env`** first (the one config file for
  the whole plugin — copy `scripts/.env.example` into it), then next to
  `transcribe.py`, then upward from the working directory. Prefer `~/.config`:
  a plugin installs into a version-pinned directory, so a key left beside the
  script is lost on the next plugin upgrade. Do **not** rely on `export` in one
  Bash call being visible in the next — shell state does not persist between
  tool calls, but a `.env` file does.
- If the key is missing, `transcribe.py` exits with
  `Error: OPENROUTER_API_KEY not set` — tell the user to put their
  OpenRouter key (from <https://openrouter.ai/keys>) into
  `~/.config/nk-work-kit/.env` as `OPENROUTER_API_KEY=sk-or-...`, then retry.

## Running it

Always pass `--model` and `--yes` — there is no terminal for the script's
interactive prompts when Claude runs it.

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/transcribe.py" "<audio-path>" \
  --model <model-id> \
  --yes
```

Progress ("Transcribing in single call…", chunk counters, "Generating
summary…") goes to stderr; the final line is `Wrote <output-path>` (default
output: `<audio-path>` with its extension swapped for `.md`, next to the
source file — override with `-o <path>` if the user wants it elsewhere).

Useful flags:

| Flag | When to use |
|---|---|
| `-o, --output PATH` | User wants the transcript in a specific location. |
| `--no-summary` | User wants the raw transcript only, no summary block. |
| `--chunk-seconds N` | Only for very long recordings where the default 900s (15 min) chunking needs adjusting — see "Long files" below. |

## Picking a model

| Model ID | Use when | ~Cost/min |
|---|---|---|
| `google/gemini-2.5-flash-lite` | Short, clean, single-speaker recording; cost matters most | $0.0003 |
| `google/gemini-2.5-flash` | **Default.** Thai, English, or mixed; multiple speakers; general meetings | $0.0012 |
| `google/gemini-2.5-pro` | Noisy audio, heavy crosstalk, technical/legal jargon, or the flash pass came back garbled | $0.0048 |
| `openai/gpt-4o-mini-audio-preview` | English-only, budget option — Thai is noticeably weaker than Gemini | $0.015 |
| `openai/gpt-4o-audio-preview` | English-only, premium — avoid for any Thai content | $0.10 |

Default to **`google/gemini-2.5-flash`** unless the user's context points
elsewhere (e.g. they mention the recording is noisy → `gemini-2.5-pro`; they
say it's a quick clean English clip → `flash-lite`). Costs are rough
estimates (±50%); `transcribe.py` prints the file's duration and the
estimated cost before running — read that off stderr/stdout and mention it
to the user if it's non-trivial (say, over a dollar), but don't block on
confirmation for typical short-to-medium recordings — `--yes` already
signals the user wants this to just run.

## Long files

Files over 20 minutes are automatically split into 900s (15 min) chunks,
transcribed sequentially, and timestamp-realigned before concatenation —
no special handling needed on your end. Speaker labels can drift across
chunk boundaries (the model can't see prior chunks) — if the user needs
consistent speaker IDs across a long recording, prefer
`google/gemini-2.5-pro` or pass `--chunk-seconds 1800` to reduce the number
of boundaries, and mention the caveat in your reply.

## After it runs

1. Read the output Markdown file and show the user the summary block (and
   the participant list, if identified) in chat — don't dump the entire
   verbatim transcript into the conversation unless they ask for it.
2. Give the output file path.
3. If `transcribe.py` reports `No audio stream found`, the file is probably
   a video container — extract audio first:
   `ffmpeg -i input.mp4 -vn -c:a copy output.m4a`, then retry.
4. If the response comes back empty, the chosen model doesn't actually
   accept `input_audio` — retry with a `google/gemini-2.5-*` or
   `openai/gpt-4o*-audio-preview` model.

## What not to do

- Don't pass a bare `transcribe.py <audio>` with no `--model`/`--yes` — it
  will hang waiting for interactive input Claude cannot supply.
- Don't guess at Thai speech content if the model output looks wrong —
  re-run with a stronger model (`gemini-2.5-pro`) rather than editing the
  transcript by hand.
- Don't put a real `OPENROUTER_API_KEY` value in any file that gets
  committed — `~/.config/nk-work-kit/.env` sits outside the repo entirely, and
  the fallback `scripts/.env` is covered by the repo's `.gitignore` (`.env`).
  If you ever see a real key about to be staged (`git status`/`git diff` before
  committing), stop and flag it rather than committing it.
