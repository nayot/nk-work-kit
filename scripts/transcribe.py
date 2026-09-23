#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "openai>=1.40",
#   "python-dotenv>=1.0",
# ]
# ///
"""
autoTranscribe — transcribe audio to Markdown via OpenRouter.

Vendored from https://github.com/nayot/autoTranscribe (transcribe.py) for the
`transcribe` skill in this plugin, so the plugin is self-contained. Source of
truth for the CLI itself is the autoTranscribe repo — port fixes/features back
there and re-sync this copy rather than diverging.

Usage:
    uv run transcribe.py path/to/audio.m4a
    uv run transcribe.py audio.wav --model google/gemini-2.5-pro --yes
    uv run transcribe.py audio.mp3 -o out.md --no-summary

Requires OPENROUTER_API_KEY in the environment or in ~/.config/nk-work-kit/.env
(then beside this script, then upward from the CWD — see scripts/.env.example).
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# LOCAL CHANGE (not in upstream autoTranscribe): look in the shared plugin
# config dir first, so one file serves every nk-work-kit skill and survives a
# plugin upgrade — a plugin installs into a version-pinned directory, so a
# .env beside this script is orphaned by the next version. Re-apply this on
# the next re-sync from upstream.
_xdg = os.environ.get("XDG_CONFIG_HOME")
load_dotenv((Path(_xdg) if _xdg else Path.home() / ".config") / "nk-work-kit" / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env")
load_dotenv()  # upstream behaviour: search from the CWD upward

# LOCAL CHANGE (not in upstream autoTranscribe): Windows hands a legacy code
# page to a redirected stream, so a Thai filename or model id printed to a
# piped stdout raises UnicodeEncodeError. Harmless everywhere else.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# --- Model catalog ----------------------------------------------------------
# cost_per_min_usd is an approximation based on:
#   - audio input tokens billed at the model's prompt rate (Gemini uses
#     ~32 tokens/sec of audio = 1,920 tokens/min)
#   - ~200 output tokens/min for a typical transcript (~150 words/min speech)
# Real costs vary ±50% depending on speech density, silence, and routing.

MODELS = [
    {
        "id": "google/gemini-2.5-flash-lite",
        "label": "Gemini 2.5 Flash Lite",
        "precision": "Good for clean recordings; weaker on Thai accents & overlap",
        "cost_per_min_usd": 0.0003,
    },
    {
        "id": "google/gemini-2.5-flash",
        "label": "Gemini 2.5 Flash  (recommended)",
        "precision": "Strong Thai + English, decent speaker labels, fast",
        "cost_per_min_usd": 0.0012,
    },
    {
        "id": "google/gemini-2.5-pro",
        "label": "Gemini 2.5 Pro",
        "precision": "Highest precision; best for noisy audio or jargon; ~4× cost",
        "cost_per_min_usd": 0.0048,
    },
    {
        "id": "openai/gpt-4o-mini-audio-preview",
        "label": "GPT-4o mini audio",
        "precision": "Good English; Thai support noticeably weaker than Gemini",
        "cost_per_min_usd": 0.015,
    },
    {
        "id": "openai/gpt-4o-audio-preview",
        "label": "GPT-4o audio",
        "precision": "Premium English; not recommended for Thai-heavy content",
        "cost_per_min_usd": 0.10,
    },
]
DEFAULT_MODEL_INDEX = 1  # Gemini 2.5 Flash

DEFAULT_CHUNK_SECONDS = 900       # 15 min per chunk when splitting
SINGLE_CALL_MAX_SECONDS = 1200    # transcribe in one call if <= 20 min

TRANSCRIBE_PROMPT = """Transcribe this audio file completely and accurately.

Requirements:
- The audio may be in Thai, English, or a mix of both. Transcribe each utterance in its original language — do not translate.
- Detect distinct speakers and label them as **Speaker 1**, **Speaker 2**, etc. Be consistent throughout.
- Insert a timestamp `[MM:SS]` at the start of each speaker turn and roughly every 30 seconds of continuous speech.
- Use Markdown formatting. Put each speaker turn on its own paragraph.
- Do not summarize, omit, or paraphrase — produce a verbatim transcript.

Output ONLY the transcript content, no preamble."""

SUMMARY_PROMPT = """Given the following transcript, write a concise Markdown block with:
- A 2-3 sentence overview
- A bulleted list of key points (3-7 bullets)
- A list of named participants if any are identifiable

Use the same language(s) as the transcript (Thai stays Thai, English stays English). Output only the block, no preamble or heading."""


# --- Audio inspection -------------------------------------------------------

@dataclass
class AudioInfo:
    path: Path
    duration_s: float
    size_bytes: int
    codec: str
    sample_rate: int
    channels: int
    bitrate_kbps: int

    @property
    def duration_min(self) -> float:
        return self.duration_s / 60.0

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)


def run_capture(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout


def inspect_audio(path: Path) -> AudioInfo:
    raw = run_capture([
        "ffprobe", "-v", "error",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(path),
    ])
    data = json.loads(raw)
    fmt = data.get("format", {})
    audio_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "audio"),
        None,
    )
    if audio_stream is None:
        sys.exit(f"No audio stream found in {path}")
    return AudioInfo(
        path=path,
        duration_s=float(fmt.get("duration", 0.0)),
        size_bytes=int(fmt.get("size", 0)),
        codec=str(audio_stream.get("codec_name", "?")),
        sample_rate=int(audio_stream.get("sample_rate", 0) or 0),
        channels=int(audio_stream.get("channels", 0) or 0),
        bitrate_kbps=int(fmt.get("bit_rate", 0) or 0) // 1000,
    )


def format_duration(seconds: float) -> str:
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:d}:{s:02d}"


def print_audio_info(info: AudioInfo) -> None:
    print()
    print(f"  File:        {info.path.name}")
    print(f"  Duration:    {format_duration(info.duration_s)}  ({info.duration_min:.1f} min)")
    print(f"  Size:        {info.size_mb:.1f} MB")
    print(f"  Codec:       {info.codec}")
    print(f"  Sample rate: {info.sample_rate} Hz")
    print(f"  Channels:    {info.channels}")
    if info.bitrate_kbps:
        print(f"  Bitrate:     {info.bitrate_kbps} kbps")
    print()


# --- Model selection --------------------------------------------------------

def estimate_cost(model: dict, duration_min: float) -> float:
    return duration_min * model["cost_per_min_usd"]


def select_model(duration_min: float) -> dict:
    print("Available models  (cost estimates are approximate ±50%):")
    print()
    for i, m in enumerate(MODELS, 1):
        est = estimate_cost(m, duration_min)
        marker = " *" if (i - 1) == DEFAULT_MODEL_INDEX else "  "
        print(f"{marker}{i}. {m['label']}")
        print(f"     {m['precision']}")
        print(f"     Est. ${est:.4f}  ({m['id']})")
        print()
    print(f"  {len(MODELS) + 1}. Custom OpenRouter model ID")
    print(f"  0. Cancel")
    print()
    while True:
        try:
            raw = input(f"Choice [1-{len(MODELS) + 1}, default={DEFAULT_MODEL_INDEX + 1}]: ").strip()
        except EOFError:
            sys.exit("\nCancelled (no input).")
        if raw == "":
            return MODELS[DEFAULT_MODEL_INDEX]
        try:
            n = int(raw)
        except ValueError:
            print("Please enter a number.")
            continue
        if n == 0:
            sys.exit("Cancelled.")
        if 1 <= n <= len(MODELS):
            return MODELS[n - 1]
        if n == len(MODELS) + 1:
            cid = input("Model ID (e.g. anthropic/claude-3.5-sonnet): ").strip()
            if cid:
                return {
                    "id": cid,
                    "label": cid,
                    "precision": "(custom)",
                    "cost_per_min_usd": 0.0,
                }
        print("Invalid choice.")


def find_model(model_id: str) -> dict:
    for m in MODELS:
        if m["id"] == model_id:
            return m
    return {
        "id": model_id,
        "label": model_id,
        "precision": "(custom)",
        "cost_per_min_usd": 0.0,
    }


def confirm(message: str) -> bool:
    try:
        return input(f"{message} [y/N]: ").strip().lower() in {"y", "yes"}
    except EOFError:
        return False


# --- Transcription ----------------------------------------------------------

def normalize_to_mp3(src: Path, dst: Path, start: float | None = None, length: float | None = None) -> None:
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src)]
    if start is not None:
        cmd += ["-ss", str(start)]
    if length is not None:
        cmd += ["-t", str(length)]
    cmd += ["-ac", "1", "-ar", "16000", "-b:a", "64k", str(dst)]
    subprocess.run(cmd, check=True)


def chunk_audio(src: Path, duration_s: float, chunk_seconds: int, workdir: Path) -> list[tuple[Path, float]]:
    n = max(1, int(duration_s // chunk_seconds) + (1 if duration_s % chunk_seconds else 0))
    chunks: list[tuple[Path, float]] = []
    for i in range(n):
        offset = i * chunk_seconds
        out = workdir / f"chunk_{i:03d}.mp3"
        normalize_to_mp3(src, out, start=offset, length=chunk_seconds)
        chunks.append((out, float(offset)))
    return chunks


def transcribe_audio(client: OpenAI, model_id: str, path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    response = client.chat.completions.create(
        model=model_id,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": TRANSCRIBE_PROMPT},
                {"type": "input_audio", "input_audio": {"data": data, "format": "mp3"}},
            ],
        }],
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError(f"Empty response from model for {path.name}")
    return content.strip()


def shift_timestamps(text: str, offset_seconds: float) -> str:
    def repl(m: re.Match[str]) -> str:
        parts = [int(p) for p in m.group(1).split(":")]
        if len(parts) == 2:
            total = parts[0] * 60 + parts[1]
        elif len(parts) == 3:
            total = parts[0] * 3600 + parts[1] * 60 + parts[2]
        else:
            return m.group(0)
        total += int(offset_seconds)
        h, rem = divmod(total, 3600)
        mm, ss = divmod(rem, 60)
        return f"[{h:02d}:{mm:02d}:{ss:02d}]" if h else f"[{mm:02d}:{ss:02d}]"

    return re.sub(r"\[(\d{1,2}(?::\d{2}){1,2})\]", repl, text)


def summarize(client: OpenAI, model_id: str, transcript: str) -> str:
    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": SUMMARY_PROMPT},
            {"role": "user", "content": transcript},
        ],
    )
    return (response.choices[0].message.content or "").strip()


# --- Main -------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe audio to Markdown via OpenRouter.")
    parser.add_argument("audio", type=Path, help="Path to audio file (mp3, m4a, wav, etc.)")
    parser.add_argument("-o", "--output", type=Path, help="Output .md path (default: <audio>.md)")
    parser.add_argument("--model", help="OpenRouter model ID — skips the interactive menu")
    parser.add_argument("--chunk-seconds", type=int, default=DEFAULT_CHUNK_SECONDS,
                        help=f"Chunk length for long files (default: {DEFAULT_CHUNK_SECONDS})")
    parser.add_argument("--no-summary", action="store_true", help="Skip the summary header")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        sys.exit("Error: OPENROUTER_API_KEY not set (export it or put it in .env)")
    if not args.audio.exists():
        sys.exit(f"File not found: {args.audio}")

    info = inspect_audio(args.audio)
    print_audio_info(info)

    if args.model:
        model = find_model(args.model)
        est = estimate_cost(model, info.duration_min)
        print(f"Model: {model['label']}  —  est. ${est:.4f}")
    else:
        model = select_model(info.duration_min)
        est = estimate_cost(model, info.duration_min)
        print()
        print(f"Selected: {model['label']}  —  est. ${est:.4f} for {info.duration_min:.1f} min")

    if not args.yes:
        if not confirm("Proceed?"):
            sys.exit("Cancelled.")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "https://github.com/nayot/autoTranscribe",
            "X-Title": "autoTranscribe",
        },
    )

    out_path = args.output or args.audio.with_suffix(".md")

    with tempfile.TemporaryDirectory() as td:
        workdir = Path(td)

        if info.duration_s <= SINGLE_CALL_MAX_SECONDS:
            print("Transcribing in single call…", file=sys.stderr)
            normalized = workdir / "audio.mp3"
            normalize_to_mp3(args.audio, normalized)
            transcript = transcribe_audio(client, model["id"], normalized)
        else:
            print(f"Chunking into {args.chunk_seconds}s segments…", file=sys.stderr)
            chunks = chunk_audio(args.audio, info.duration_s, args.chunk_seconds, workdir)
            parts: list[str] = []
            for i, (chunk_path, offset) in enumerate(chunks, 1):
                mm = int(offset // 60)
                print(f"  [{i}/{len(chunks)}] transcribing chunk starting at {mm:02d}:00…", file=sys.stderr)
                text = transcribe_audio(client, model["id"], chunk_path)
                parts.append(shift_timestamps(text, offset))
            transcript = "\n\n".join(parts)

    sections = [f"# Transcript: {args.audio.stem}"]
    if not args.no_summary:
        print("Generating summary…", file=sys.stderr)
        sections.append("## Summary\n\n" + summarize(client, model["id"], transcript))
    sections.append("## Transcript\n\n" + transcript)
    sections.append(
        f"---\n\n*Transcribed with `{model['id']}` via OpenRouter. "
        f"Source: `{args.audio.name}` ({format_duration(info.duration_s)}).*"
    )

    out_path.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
