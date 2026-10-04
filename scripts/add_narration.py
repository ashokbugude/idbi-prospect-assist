#!/usr/bin/env python3
"""Add narration to the recorded demo video.

    python scripts/add_narration.py --tts          # neural voice (edge-tts), SAPI fallback
    python scripts/add_narration.py --audio FILE   # your own continuous recording

Cue times and lines come from scripts/demo_story.py, so recording and narration
share one clock.
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from demo_story import FINAL_SECONDS, cues as story_cues  # noqa: E402

DEFAULT_VIDEO = ROOT / "docs" / "demo-video" / "IDBI_Prospect_Assist_Demo_v0.9.0.mp4"

# Documentary Indian-English first; fall back if a voice is missing on this box.
VOICE_CHAIN = (
    "en-IN-NeerjaExpressiveNeural",
    "en-IN-NeerjaNeural",
    "en-IN-PrabhatNeural",
    "en-US-JennyNeural",
)

PAUSE = 0.45
RUSHED = 1.35


def require(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        sys.exit(f"{tool} is not on PATH. Install it and try again "
                 f"(ffmpeg: winget install Gyan.FFmpeg)")
    return path


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nk=1:nw=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit("ffmpeg failed:\n" + "\n".join(proc.stderr.strip().splitlines()[-12:]))


def speak_windows(text: str, out_wav: Path, rate: int) -> None:
    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.Rate = {rate}; "
        f"$s.SetOutputToWaveFile('{out_wav}'); "
        f"$s.Speak([Console]::In.ReadToEnd()); "
        "$s.Dispose()"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        input=text, text=True, capture_output=True,
    )
    if proc.returncode != 0 or not out_wav.exists():
        sys.exit("Windows speech synthesis failed.\n" + (proc.stderr or "").strip())


async def _edge_save(text: str, out: Path, voice: str, rate: str) -> None:
    import edge_tts
    comm = edge_tts.Communicate(text, voice=voice, rate=rate)
    await comm.save(str(out))


_working_voice: str | None = None


def speak_neural(text: str, out: Path, voice: str, rate: str) -> None:
    global _working_voice
    order: list[str] = []
    if _working_voice:
        order.append(_working_voice)
    order += [voice, *VOICE_CHAIN]
    seen: set[str] = set()
    last: Exception | None = None
    for candidate in order:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            asyncio.run(_edge_save(text, out, candidate, rate))
            if _working_voice != candidate:
                print(f"    voice: {candidate}")
                _working_voice = candidate
            return
        except Exception as exc:
            last = exc
    raise RuntimeError(f"All neural voices failed: {last}")


def pick_voice(preferred: str | None) -> str:
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        return ""
    if preferred:
        return preferred
    return VOICE_CHAIN[0]


def fit_to_slot(media: Path, work: Path, idx: int, slot: float) -> tuple[Path, float]:
    allowed = max(1.0, slot - PAUSE)
    length = probe_duration(media)
    if length <= allowed or length == 0.0:
        return media, 1.0
    tempo = length / allowed
    chain, remaining = [], tempo
    while remaining > 2.0:
        chain.append("atempo=2.0")
        remaining /= 2.0
    chain.append(f"atempo={remaining:.4f}")
    fitted = work / f"fit_{idx:02d}.wav"
    run([require("ffmpeg"), "-v", "error", "-y", "-i", str(media),
         "-filter:a", ",".join(chain), str(fitted)])
    return fitted, tempo


def build_tts_track(cues, work: Path, total: float, *,
                    neural: bool, voice: str, neural_rate: str, sapi_rate: int) -> list[Path]:
    clips, rushed = [], []
    for i, (at, line) in enumerate(cues, 1):
        nxt = cues[i][0] if i < len(cues) else total
        slot = nxt - at
        raw = work / (f"line_{i:02d}.mp3" if neural else f"line_{i:02d}.wav")
        if neural:
            speak_neural(line, raw, voice, neural_rate)
        else:
            speak_windows(line, raw, sapi_rate)
        fitted, tempo = fit_to_slot(raw, work, i, slot)
        mark = f"{int(at)//60}:{int(at)%60:02d}"
        note = "fits" if tempo == 1.0 else f"squeezed {tempo:.2f}x to fit {slot:.0f}s"
        if tempo > RUSHED:
            rushed.append((mark, tempo))
            note += "  <-- will sound hurried"
        print(f"  {mark}  {note}  ({probe_duration(fitted):.1f}s)")
        clips.append(fitted)
    if rushed:
        print("\n  These lines needed heavy compression:")
        for mark, tempo in rushed:
            print(f"    {mark} at {tempo:.2f}x — shorten it in scripts/demo_story.py")
    return clips


def mux_timed(video: Path, clips: list[Path], cues, out: Path, music_db: float) -> None:
    ffmpeg = require("ffmpeg")
    fade_out_at = max(0.5, FINAL_SECONDS - 1.2)
    cmd = [ffmpeg, "-y", "-i", str(video)]
    for c in clips:
        cmd += ["-i", str(c)]
    parts, labels = [], []
    for i, (at, _line) in enumerate(cues):
        ms = int(round(at * 1000))
        vol = f",volume={music_db}dB" if music_db else ""
        parts.append(f"[{i+1}:a]adelay={ms}|{ms}{vol}[n{i}]")
        labels.append(f"[n{i}]")
    parts.append(
        "".join(labels)
        + f"amix=inputs={len(clips)}:normalize=0:dropout_transition=0,"
          f"loudnorm=I=-16:TP=-1.5:LRA=11,"
          f"afade=t=in:st=0:d=0.25,afade=t=out:st={fade_out_at:.2f}:d=1.0,apad[aout]"
    )
    cmd += ["-filter_complex", ";".join(parts),
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-shortest", "-movflags", "+faststart", str(out)]
    run(cmd)


def mux_single(video: Path, audio: Path, out: Path, offset: float) -> None:
    ffmpeg = require("ffmpeg")
    cmd = [ffmpeg, "-y", "-i", str(video)]
    if offset >= 0:
        cmd += ["-itsoffset", f"{offset}", "-i", str(audio)]
    else:
        cmd += ["-ss", f"{abs(offset)}", "-i", str(audio)]
    cmd += ["-map", "0:v", "-map", "1:a",
            "-filter:a", "loudnorm=I=-16:TP=-1.5:LRA=11,apad",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-shortest", "-movflags", "+faststart", str(out)]
    run(cmd)


def main() -> int:
    ap = argparse.ArgumentParser(description="Add narration to the demo video.")
    ap.add_argument("--video", default=str(DEFAULT_VIDEO))
    ap.add_argument("--audio", help="Your own continuous narration recording (wav/mp3/m4a).")
    ap.add_argument("--tts", action="store_true", help="Synthesize the scripted lines.")
    ap.add_argument("--sapi", action="store_true",
                    help="Force the Windows built-in voice instead of neural TTS.")
    ap.add_argument("--voice", default="", help="edge-tts voice name.")
    ap.add_argument("--neural-rate", default="-5%",
                    help="Neural TTS rate, e.g. -5% or +10%.")
    ap.add_argument("--offset", type=float, default=0.0,
                    help="Shift --audio in seconds; positive delays it, negative trims its start.")
    ap.add_argument("--rate", type=int, default=1,
                    help="SAPI speed, -10 (slow) to 10 (fast).")
    ap.add_argument("--gain", type=float, default=0.0, help="TTS gain in dB.")
    ap.add_argument("--out", help="Output path. Defaults to <video>_narrated.mp4")
    args = ap.parse_args()

    if bool(args.audio) == bool(args.tts):
        sys.exit("Choose exactly one: --audio FILE  or  --tts")

    video = Path(args.video)
    if not video.exists():
        sys.exit(f"Video not found: {video}\nRecord it first: python scripts/record_demo.py")
    out = Path(args.out) if args.out else video.with_name(video.stem + "_narrated.mp4")

    if args.audio:
        audio = Path(args.audio)
        if not audio.exists():
            sys.exit(f"Audio not found: {audio}")
        print(f"Muxing {audio.name} into {video.name} (offset {args.offset:+.2f}s)")
        mux_single(video, audio, out, args.offset)
        print(f"\nDone: {out}")
        return 0

    cues = story_cues()
    neural = not args.sapi
    voice = pick_voice(args.voice or None) if neural else ""
    if neural and not voice:
        print("edge-tts is not installed — falling back to the Windows voice.")
        print("    pip install edge-tts")
        neural = False
    elif neural:
        print(f"Speaking {len(cues)} lines with {voice} ({args.neural_rate}):")
    else:
        if sys.platform != "win32":
            sys.exit("SAPI is Windows-only. Install edge-tts, or pass --audio.")
        print(f"Speaking {len(cues)} lines with Windows SAPI:")

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        try:
            clips = build_tts_track(
                cues, work, probe_duration(video) or FINAL_SECONDS,
                neural=neural, voice=voice,
                neural_rate=args.neural_rate, sapi_rate=args.rate,
            )
        except Exception as exc:
            if neural:
                print(f"Neural TTS failed ({exc}). Falling back to Windows SAPI.")
                if sys.platform != "win32":
                    raise
                clips = build_tts_track(
                    cues, work, probe_duration(video) or FINAL_SECONDS,
                    neural=False, voice="",
                    neural_rate=args.neural_rate, sapi_rate=args.rate,
                )
            else:
                raise
        mux_timed(video, clips, cues, out, args.gain)

    print(f"\nDone: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
