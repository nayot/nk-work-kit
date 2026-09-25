---
name: transcribe
description: Transcribe an audio recording (meeting, interview, lecture) into a Markdown transcript with timestamps and speaker labels, in Thai, English, or mixed. Use `/transcribe <audio-path>` or activate automatically when the user asks to "transcribe", "ถอดเสียง", "ถอดความ", "ทำ transcript", "get a transcript / minutes / notes from this recording", or points at an audio file (.m4a, .mp3, .wav, .aac, .ogg, .flac) and wants text out of it.
argument-hint: <audio-path> [model-id]
allowed-tools: [Bash, Read, Edit, Write]
version: 1.2.0
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
- `ffmpeg` + `ffprobe` — on PATH, or in a standard package-manager location
  (Homebrew on macOS; winget, Scoop or Chocolatey on Windows). If missing, the
  script exits with a per-OS install hint (`brew install ffmpeg`,
  `winget install Gyan.FFmpeg`, `sudo apt install ffmpeg`) — relay it.
- `OPENROUTER_API_KEY`. The script reads it from the environment or from a
  `.env` file: **`~/.config/nk-work-kit/.env`** first (the one config file for
  the whole plugin — copy `scripts/.env.example` into it; on Windows
  `%APPDATA%\nk-work-kit\.env` is also checked), then next to
  `transcribe.py`, then upward from the working directory. Prefer `~/.config`:
  a plugin installs into a version-pinned directory, so a key left beside the
  script is lost on the next plugin upgrade. Do **not** rely on `export` in one
  Bash call being visible in the next — shell state does not persist between
  tool calls, but a `.env` file does.
- If the key is missing, `transcribe.py` exits with
  `Error: OPENROUTER_API_KEY not set` — tell the user to put their
  OpenRouter key (from <https://openrouter.ai/keys>) into
  `~/.config/nk-work-kit/.env` as `OPENROUTER_API_KEY=sk-or-...`, then retry.
- `rclone` with a configured Google Drive remote, for filing the recording
  and its transcript afterwards (see below). Without it the transcription
  still runs; only the move is skipped.

## First run: setup

After transcribing, the skill **moves the audio file and its transcript
`.md`** to a Google Drive folder with `rclone`, so the two stay together. The
folder comes from
`TRANSCRIBE_RCLONE_DEST` in the `.env`, as an rclone `remote:path` such as
`GDrive:Recordings`. `transcribe.py` does not read this variable. You resolve
it yourself, in the scripts' lookup order: a real env var first, then the first
`.env` that sets it.

```bash
dest="${TRANSCRIBE_RCLONE_DEST:-}"
for f in "${XDG_CONFIG_HOME:-$HOME/.config}/nk-work-kit/.env" "$HOME/.config/nk-work-kit/.env" "${CLAUDE_PLUGIN_ROOT}/scripts/.env"; do
  [ -z "$dest" ] && [ -f "$f" ] && dest=$(grep -m1 '^TRANSCRIBE_RCLONE_DEST=' "$f" | cut -d= -f2-)
done
echo "${dest:-<unset>}"
```

(On Windows, also check `%APPDATA%\nk-work-kit\.env`.)

Do this check **before** running the transcription, so setup questions come
up front and don't interrupt the result:

- **A `remote:path` value:** use it. There is nothing to ask.
- **`none`:** the user has opted out. Leave both files where they are and do not ask.
- **Empty or unset:** this is the setup phase. Ask once:
  1. Run `rclone listremotes` and ask which remote and folder to use. Several
     remotes may point at different Google accounts, so don't guess. If rclone
     is missing or has no remotes, say so (`rclone config` creates one) and
     offer `none` for now.
  2. Check the folder with `rclone lsf "<remote:path>" --max-depth 1`. If it
     doesn't exist, offer `rclone mkdir "<remote:path>"`.
  3. Write `TRANSCRIBE_RCLONE_DEST=<remote:path>` into
     `~/.config/nk-work-kit/.env`: replace an existing empty line, or append
     one. Create the file with `chmod 600` if it doesn't exist. If the user
     declines, write `TRANSCRIBE_RCLONE_DEST=none` so they aren't asked again.

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
3. **Move the audio and the transcript to Drive.** Do this only when the
   destination is set (see setup) **and** the transcript is non-empty and
   looks sane. `rclone move` deletes the local files, and the retries below
   (video container, empty output, re-run with `gemini-2.5-pro`) all need the
   audio. So an empty or garbled transcript means no move. Do steps 1–2
   (reading and summarising the `.md`) before this, because the local copy
   is gone afterwards. The transcript is the `Wrote <output-path>` file, which
   is not next to the audio when `-o` was used.

   First check both names for a clash, because rclone would silently
   overwrite a different file with the same name:

   ```bash
   rclone lsf "<dest>/<audio-filename>" 2>/dev/null
   rclone lsf "<dest>/<transcript-filename>" 2>/dev/null
   ```

   A printed filename means that file already exists. Nothing printed means
   the name is free (rclone reports `directory not found` on stderr with exit
   3 for a missing path, which is not a clash).

   If either name already exists, ask the user before moving anything: rename
   the clashing upload (`rclone moveto "<local-path>" "<dest>/<new-name>"`;
   keep the audio and `.md` basenames matching, e.g. both get a `-2` suffix),
   or keep both files local. Otherwise move the audio, then the transcript:

   ```bash
   rclone move "<audio-path>" "<dest>/" --no-traverse
   rclone move "<transcript-path>" "<dest>/" --no-traverse
   ```

   rclone verifies each upload before it deletes the source. Report both
   Drive locations (`<dest>/<audio-filename>`, `<dest>/<transcript-filename>`).
   If rclone fails (not installed, expired token, unreachable folder), say
   that the transcript is fine, say which files are still local, and give the
   error. This is not a transcription failure. If the audio move fails, don't
   move the `.md` either, so the pair isn't split. If the user later wants a
   re-run or to edit the transcript, get the files back first with
   `rclone copy "<dest>/<filename>" <local-dir>/`. When you extracted audio
   from a video (next step), move the file you transcribed and leave the
   original video alone.
4. If `transcribe.py` reports `No audio stream found`, the file is probably
   a video container — extract audio first:
   `ffmpeg -i input.mp4 -vn -c:a copy output.m4a`, then retry.
5. If the response comes back empty, the chosen model doesn't actually
   accept `input_audio` — retry with a `google/gemini-2.5-*` or
   `openai/gpt-4o*-audio-preview` model.

## What not to do

- Don't pass a bare `transcribe.py <audio>` with no `--model`/`--yes` — it
  will hang waiting for interactive input Claude cannot supply.
- Don't move anything before the transcript has been checked and its
  summary shown, and don't move one file of the pair without the other
  unless the user chose that.
- Don't guess at Thai speech content if the model output looks wrong —
  re-run with a stronger model (`gemini-2.5-pro`) rather than editing the
  transcript by hand.
- Don't put a real `OPENROUTER_API_KEY` value in any file that gets
  committed — `~/.config/nk-work-kit/.env` sits outside the repo entirely, and
  the fallback `scripts/.env` is covered by the repo's `.gitignore` (`.env`).
  If you ever see a real key about to be staged (`git status`/`git diff` before
  committing), stop and flag it rather than committing it.
