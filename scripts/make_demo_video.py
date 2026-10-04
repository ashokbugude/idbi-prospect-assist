#!/usr/bin/env python3
"""Build the 3-minute narrated demo in one command.

Records the live app (no caption bar), then lays a neural voice over it.

    python scripts/make_demo_video.py

Requires: a running app (or this script will start uvicorn), Playwright,
ffmpeg, and edge-tts (pip install edge-tts playwright && playwright install chromium).
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from add_narration import main as narrate_main  # noqa: E402
from demo_story import FINAL_SECONDS  # noqa: E402
from record_demo import record, to_mp4  # noqa: E402


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


def wait_http(url: str, seconds: float = 25.0) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.4)
    return False


def ensure_app(base: str) -> subprocess.Popen | None:
    login = base.rstrip("/") + "/login"
    if wait_http(login, seconds=2.0):
        print(f"  app already running at {base}")
        return None
    host, _, port_s = base.replace("http://", "").replace("https://", "").partition(":")
    host = host.split("/")[0] or "127.0.0.1"
    port = int(port_s or 8000)
    if port_open(host, port):
        print(f"  port {port} is open but /login did not answer — continuing anyway")
        return None
    print(f"  starting uvicorn on {host}:{port} …")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", host, "--port", str(port)],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if not wait_http(login, seconds=30.0):
        proc.terminate()
        sys.exit("Could not start the app. Start it yourself:\n"
                 "    uvicorn app.main:app --port 8000")
    return proc


def verify(path: Path) -> None:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,codec_name,width,height",
         "-of", "default=nk=1:nw=1", str(path)],
        capture_output=True, text=True,
    )
    print("\nVerify:")
    print(f"  file     {path}")
    print(f"  size     {path.stat().st_size / 1_048_576:.1f} MB")
    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nk=1:nw=1", str(path)],
        capture_output=True, text=True,
    ).stdout.strip()
    try:
        seconds = float(dur)
    except ValueError:
        seconds = 0.0
    print(f"  duration {seconds:.2f}s  (target {FINAL_SECONDS:.1f}s, cap 180)")
    has_audio = "aac" in probe.stdout or "audio" in probe.stdout
    print(f"  audio    {'yes' if has_audio else 'MISSING'}")
    if seconds < 170 or seconds > 181:
        print("  warning  duration is outside the 2:50–3:01 window")
    if not has_audio:
        sys.exit("Narrated video has no audio track.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Record + narrate the 3-minute demo.")
    ap.add_argument("--base-url", default=os.environ.get("DEMO_BASE_URL", "http://127.0.0.1:8000"))
    ap.add_argument("--pin", default=os.environ.get("RM_DEMO_PIN", "idbi2026"))
    ap.add_argument("--out", default=str(ROOT / "docs" / "demo-video"))
    ap.add_argument("--skip-record", action="store_true",
                    help="Mux narration onto the existing silent mp4.")
    ap.add_argument("--sapi", action="store_true", help="Use Windows SAPI instead of neural TTS.")
    ap.add_argument("--voice", default="", help="edge-tts voice override.")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    silent = out_dir / "IDBI_Prospect_Assist_Demo_v0.9.0.mp4"
    narrated = out_dir / "IDBI_Prospect_Assist_Demo_v0.9.0_narrated.mp4"

    server = None
    try:
        if not args.skip_record:
            server = ensure_app(args.base_url)
            print(f"Recording {args.base_url} -> {out_dir}")
            webm, lead_in = record(args.base_url.rstrip("/"), args.pin, out_dir, captions=False)
            if not to_mp4(webm, silent, lead_in):
                sys.exit("ffmpeg is required to finish the demo video.")
            print(f"  silent take: {silent}")

        argv = ["add_narration.py", "--tts", "--video", str(silent), "--out", str(narrated)]
        if args.sapi:
            argv.append("--sapi")
        if args.voice:
            argv += ["--voice", args.voice]
        sys.argv = argv
        narrate_main()
        verify(narrated)
        print(f"\nReady: {narrated}")
        return 0
    finally:
        if server is not None:
            server.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
