#!/usr/bin/env python3
"""Record a ~2–3 minute Prospect Assist AI demo video with Playwright."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "https://idbi-prospect-assist-474562381457.asia-south1.run.app"
DEFAULT_PIN = "idbi2026"
OUTPUT_DIR = ROOT / "docs" / "demo-video"


def pause(seconds: float) -> None:
    time.sleep(seconds)


def scroll_page(page, amount: int = 500) -> None:
    page.evaluate(f"window.scrollBy({{ top: {amount}, behavior: 'smooth' }})")


def login(page, base_url: str, pin: str) -> None:
    page.goto(f"{base_url}/login", wait_until="networkidle")
    pause(1.2)
    page.fill('input[name="pin"]', pin)
    pause(0.4)
    page.click('button[type="submit"]')
    page.wait_for_url(f"{base_url}/**", wait_until="networkidle")
    pause(1.5)


def record_demo(base_url: str, pin: str, output_dir: Path) -> Path:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "Playwright not installed. Run:\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        ) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    for old in output_dir.glob("*.webm"):
        old.unlink(missing_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=str(output_dir),
            record_video_size={"width": 1280, "height": 720},
            locale="en-IN",
        )
        page = context.new_page()

        # 1. Login
        login(page, base_url, pin)

        # 2. Dashboard overview
        page.wait_for_selector("h1", timeout=15000)
        pause(2.0)
        scroll_page(page, 350)
        pause(1.5)
        scroll_page(page, 350)
        pause(1.5)

        # 3. Before / After toggle
        page.click('button.demo-btn[data-mode="before"]')
        pause(2.5)
        page.click('button.demo-btn[data-mode="after"]')
        pause(2.0)

        # 4. Quality Lead detail
        page.click('a.rm-card[href*="/customer/IDBI-L10010"]')
        page.wait_for_load_state("networkidle")
        pause(2.0)
        scroll_page(page, 450)
        pause(2.0)
        scroll_page(page, 450)
        pause(2.0)

        # 5. Window shopper — deprioritization brief
        page.goto(f"{base_url}/customer/IDBI-L10121", wait_until="networkidle")
        pause(2.0)
        scroll_page(page, 400)
        pause(2.5)

        # 6. Multi-bank AA flow
        page.goto(f"{base_url}/multi-bank", wait_until="networkidle")
        pause(1.5)
        page.select_option('#aa-form select[name="customer_id"]', "IDBI-L10055")
        pause(0.8)
        page.click('#aa-form button[type="submit"]')
        page.wait_for_selector("#aa-result h3", timeout=20000)
        pause(3.0)
        scroll_page(page, 500)
        pause(2.5)

        # 7. Impact page
        page.goto(f"{base_url}/impact", wait_until="networkidle")
        pause(2.0)
        scroll_page(page, 500)
        pause(2.0)

        # 8. Architecture (quick)
        page.goto(f"{base_url}/architecture", wait_until="networkidle")
        pause(2.5)
        scroll_page(page, 400)
        pause(2.0)

        # Close to finalize video file
        video_path = page.video.path() if page.video else None
        context.close()
        browser.close()

    if not video_path:
        raise SystemExit("Playwright did not produce a video file.")

    src = Path(video_path)
    webm_out = output_dir / "IDBI_Prospect_Assist_Demo.webm"
    if src != webm_out:
        shutil.move(str(src), webm_out)

    return webm_out


def convert_to_mp4(webm_path: Path) -> Path | None:
    mp4_path = webm_path.with_suffix(".mp4")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(webm_path),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        str(mp4_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return mp4_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Record Prospect Assist AI demo video")
    parser.add_argument("--base-url", default=DEFAULT_URL, help="App base URL")
    parser.add_argument("--pin", default=DEFAULT_PIN, help="RM demo PIN")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    print(f"Recording demo from {args.base_url} ...")
    webm = record_demo(args.base_url.rstrip("/"), args.pin, args.output_dir)
    print(f"Saved WebM: {webm}")

    mp4 = convert_to_mp4(webm)
    if mp4:
        print(f"Saved MP4:  {mp4}")
    else:
        print("ffmpeg not found — upload the .webm or convert to MP4 manually.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
