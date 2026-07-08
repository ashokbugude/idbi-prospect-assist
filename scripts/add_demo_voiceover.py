#!/usr/bin/env python3
"""Add timed English voiceover to the Prospect Assist AI demo video."""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VIDEO = ROOT / "docs" / "demo-video" / "IDBI_Prospect_Assist_Demo.mp4"
DEFAULT_OUTPUT = ROOT / "docs" / "demo-video" / "IDBI_Prospect_Assist_Demo_with_voiceover.mp4"

DEFAULT_VOICE = "en-IN-PrabhatNeural"
SPEECH_RATE = "+8%"

# (cue_seconds, narration) — cues aligned to on-screen actions in record_demo_video.py
NARRATION_SEGMENTS: list[tuple[float, str]] = [
    (0.0, "Welcome to Prospect Assist AI — IDBI Innovate Track 02. Signing in now."),
    (
        5.0,
        "The dashboard scores leads on repayment capacity, purchase intent, and discipline.",
    ),
    (
        12.5,
        "Toggle Before and After to compare spray-and-pray with an RM priority queue.",
    ),
    (
        19.0,
        "Quality lead L ten zero ten — GenAI call brief, income inference, and transaction timeline.",
    ),
    (
        31.0,
        "Window shopper L ten one two one — deprioritize, no RM sales call.",
    ),
    (
        38.5,
        "Account Aggregator on L ten zero fifty-five — holistic income moves the tier to Serious.",
    ),
    (52.0, "Impact quantifies conversion uplift and the four-week pilot KPIs."),
    (
        57.0,
        "Cloud Run POC today, IDBI AWS sandbox next. Thank you — Srishti GenAI.",
    ),
]

GAP_BETWEEN_LINES = 0.35


async def _synthesize_segment(text: str, voice: str, out_path: Path) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=SPEECH_RATE)
    await communicate.save(str(out_path))


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def _to_wav(src: Path, dst: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-ar", "44100", "-ac", "2", str(dst)],
        check=True,
        capture_output=True,
    )


def _make_silence(seconds: float, dst: Path) -> None:
    if seconds <= 0.01:
        return
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=stereo",
            "-t",
            f"{seconds:.3f}",
            str(dst),
        ],
        check=True,
        capture_output=True,
    )


def _build_sequential_audio(
    segment_files: list[tuple[float, Path]],
    video_duration: float,
    work_dir: Path,
) -> Path:
    """Place narration lines sequentially — never overlapping."""
    mixed = work_dir / "narration_mix.wav"
    concat_list = work_dir / "concat.txt"
    parts: list[Path] = []
    cursor = 0.0

    for i, (cue, src) in enumerate(segment_files):
        wav = work_dir / f"seg_{i:02d}.wav"
        _to_wav(src, wav)
        duration = _probe_duration(wav)

        start = max(cue, cursor)
        silence_len = start - cursor
        if silence_len > 0.01:
            silence = work_dir / f"silence_{i:02d}.wav"
            _make_silence(silence_len, silence)
            parts.append(silence)

        parts.append(wav)
        cursor = start + duration + GAP_BETWEEN_LINES

    tail = max(0.0, video_duration - cursor)
    if tail > 0.01:
        tail_silence = work_dir / "silence_tail.wav"
        _make_silence(tail, tail_silence)
        parts.append(tail_silence)

    with concat_list.open("w", encoding="utf-8") as fh:
        for part in parts:
            fh.write(f"file '{part.as_posix()}'\n")

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c:a",
            "pcm_s16le",
            str(mixed),
        ],
        check=True,
        capture_output=True,
    )
    return mixed


def add_voiceover(
    video_path: Path,
    output_path: Path,
    *,
    voice: str = DEFAULT_VOICE,
) -> Path:
    try:
        import edge_tts  # noqa: F401
    except ImportError as exc:
        raise SystemExit("edge-tts not installed. Run: pip install edge-tts") from exc

    if not video_path.exists():
        raise SystemExit(f"Video not found: {video_path}")

    video_duration = _probe_duration(video_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        segment_files: list[tuple[float, Path]] = []

        for i, (cue, text) in enumerate(NARRATION_SEGMENTS):
            seg_path = work / f"seg_{i:02d}.mp3"
            asyncio.run(_synthesize_segment(text, voice, seg_path))
            segment_files.append((cue, seg_path))

        narration = _build_sequential_audio(segment_files, video_duration, work)

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(narration),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(output_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Add voiceover to demo video")
    parser.add_argument("--video", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--voice",
        default=DEFAULT_VOICE,
        help="edge-tts voice id (e.g. en-IN-PrabhatNeural, en-IN-NeerjaNeural)",
    )
    args = parser.parse_args()

    print(f"Voice: {args.voice}")
    print(f"Input: {args.video}")
    out = add_voiceover(args.video, args.output, voice=args.voice)
    print(f"Saved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
