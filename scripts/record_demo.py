#!/usr/bin/env python3
"""Record the 3-minute demo by driving the running app with Playwright.

A real recording of the real app — the AA consent actually re-scores the lead,
the what-if sliders actually move the tier. Nothing is faked or stitched.

Scene marks live in scripts/demo_story.py (shared with the narrator), so the
voice and the picture stay on the same clock.

    python scripts/record_demo.py
    python scripts/make_demo_video.py          # record + neural voice in one go

The app must already be running (uvicorn app.main:app --port 8000), unless you
use make_demo_video.py, which will start it.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit(
        "Playwright is not installed. Run:\n"
        "    pip install playwright\n"
        "    python -m playwright install chromium"
    )

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from demo_story import FINAL_SECONDS, SCENES, WARM_PATHS  # noqa: E402

# Hide the in-app loading overlay for the take — we still wait for the page,
# we just don't spend the spoken downbeat on a spinner.
STEALTH_CSS = """
(() => {
  if (window.__demoStealth) return;
  window.__demoStealth = true;
  const s = document.createElement('style');
  s.textContent = `
    .page-loader,
    html.nav-loading .page-loader,
    body.is-navigating .page-loader { display: none !important; }
    html.nav-loading .page-main,
    body.is-navigating .page-main {
      opacity: 1 !important;
      filter: none !important;
      pointer-events: auto !important;
    }
  `;
  document.documentElement.appendChild(s);
})();
"""

CURSOR_JS = """
(() => {
  if (window.__cursorInit) return;
  window.__cursorInit = true;
  const mount = () => {
    if (document.getElementById('__demo_cursor')) return;
    const c = document.createElement('div');
    c.id = '__demo_cursor';
    c.style.cssText = [
      'position:fixed', 'z-index:2147483646', 'width:22px', 'height:22px',
      'border:2.5px solid #004d40', 'background:rgba(255,255,255,.92)',
      'border-radius:50% 50% 50% 8%', 'pointer-events:none',
      'left:72%', 'top:28%',
      'transform:translate(-18%,-12%)',
      'box-shadow:0 3px 10px rgba(0,0,0,.28)',
      'transition:left .55s cubic-bezier(.22,1,.36,1), top .55s cubic-bezier(.22,1,.36,1), transform .12s ease',
    ].join(';');
    (document.body || document.documentElement).appendChild(c);
  };
  window.__cursorTo = (x, y) => {
    mount();
    const c = document.getElementById('__demo_cursor');
    if (!c) return;
    c.style.left = x + 'px';
    c.style.top = y + 'px';
  };
  window.__cursorClick = () => {
    const c = document.getElementById('__demo_cursor');
    if (!c) return;
    c.style.transform = 'translate(-18%,-12%) scale(.78)';
    setTimeout(() => { c.style.transform = 'translate(-18%,-12%) scale(1)'; }, 140);
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
"""

CAPTION_JS = """
(() => {
  if (window.__capInit) return;
  window.__capInit = true;
  const mount = () => {
    if (document.getElementById('__demo_caption')) return;
    const d = document.createElement('div');
    d.id = '__demo_caption';
    d.style.cssText = [
      'position:fixed', 'left:0', 'right:0', 'bottom:0', 'z-index:2147483647',
      'background:rgba(0,77,64,.94)', 'color:#fff',
      'font:600 27px/1.4 Calibri,"Segoe UI",system-ui,sans-serif',
      'padding:20px 48px', 'opacity:0', 'transition:opacity .4s ease',
      'box-shadow:0 -3px 22px rgba(0,0,0,.28)', 'pointer-events:none',
    ].join(';');
    (document.body || document.documentElement).appendChild(d);
  };
  window.__cap = (t) => {
    mount();
    const d = document.getElementById('__demo_caption');
    if (!d) return;
    d.textContent = t || '';
    d.style.opacity = t ? '1' : '0';
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
"""

SMOOTH_SCROLL_JS = """([to, ms]) => new Promise(resolve => {
  const start = window.scrollY;
  const delta = to - start;
  const t0 = performance.now();
  function ease(p) { return p < 0.5 ? 2*p*p : 1 - Math.pow(-2*p + 2, 2) / 2; }
  function step(t) {
    const p = Math.min(1, (t - t0) / ms);
    window.scrollTo(0, start + delta * ease(p));
    if (p < 1) requestAnimationFrame(step); else resolve();
  }
  requestAnimationFrame(step);
})"""


class Director:
    """Holds each scene until its mark, so the cut matches the spoken script."""

    def __init__(self, page, captions: bool):
        self.page = page
        self.captions = captions
        self.t0 = time.monotonic()
        self.base = ""

    def elapsed(self) -> float:
        return time.monotonic() - self.t0

    def start_clock(self) -> None:
        self.t0 = time.monotonic()

    def caption(self, text: str) -> None:
        if not self.captions:
            return
        try:
            self.page.evaluate("t => window.__cap && window.__cap(t)", text)
        except Exception:
            pass

    def hold_until(self, mark: float) -> None:
        remaining = mark - self.elapsed()
        if remaining > 0.05:
            self.page.wait_for_timeout(remaining * 1000)
        elif remaining < -0.4:
            print(f"    (behind by {-remaining:.1f}s at mark {mark:.0f}s)")

    def scroll_to(self, y: int, ms: int = 900) -> None:
        try:
            self.page.evaluate(SMOOTH_SCROLL_JS, [y, ms])
        except Exception:
            pass

    def scroll_to_text(self, text: str, offset: int = -120, ms: int = 900) -> None:
        try:
            box = self.page.get_by_text(text, exact=False).first.bounding_box()
            if box:
                y = max(0, int(box["y"] + self.page.evaluate("window.scrollY") + offset))
                self.scroll_to(y, ms)
        except Exception:
            pass

    def go(self, path: str) -> None:
        self.page.goto(self.base + path, wait_until="domcontentloaded")
        self.page.wait_for_load_state("networkidle")

    def wait_ready(self, selector: str, timeout: int = 8000) -> None:
        try:
            self.page.wait_for_selector(selector, state="visible", timeout=timeout)
        except Exception:
            pass
        self.page.wait_for_timeout(280)

    def point_at(self, locator, settle_ms: int = 480) -> None:
        try:
            box = locator.bounding_box()
        except Exception:
            box = None
        if not box:
            return
        x = box["x"] + box["width"] * 0.22
        y = box["y"] + box["height"] * 0.62
        try:
            self.page.evaluate("([x,y]) => window.__cursorTo && window.__cursorTo(x,y)", [x, y])
        except Exception:
            pass
        self.page.wait_for_timeout(settle_ms)

    def click_el(self, locator, timeout: int = 4000) -> bool:
        self.point_at(locator)
        try:
            self.page.evaluate("() => window.__cursorClick && window.__cursorClick()")
        except Exception:
            pass
        try:
            locator.click(timeout=timeout)
            return True
        except Exception:
            return False

    def hide_loader(self) -> None:
        try:
            self.page.evaluate(
                """() => {
                  document.documentElement.classList.remove('nav-loading');
                  document.body.classList.remove('is-navigating');
                  const l = document.getElementById('page-loader');
                  if (l) { l.style.setProperty('display','none','important'); }
                }"""
            )
        except Exception:
            pass

    def click_nav(self, href: str) -> None:
        loc = self.page.locator(f'nav.idbi-nav a[href="{href}"]').first
        self.point_at(loc, settle_ms=380)
        try:
            self.page.evaluate("() => window.__cursorClick && window.__cursorClick()")
        except Exception:
            pass
        # Direct goto so nav.js never paints the Loading overlay on the spoken downbeat.
        self.go(href)
        self.hide_loader()

    def set_range(self, name: str, value: int) -> None:
        slider = self.page.locator(f'#whatif-form input[type=range][name="{name}"]').first
        self.point_at(slider, settle_ms=280)
        try:
            slider.evaluate(
                "(el, v) => { el.value = v;"
                " el.dispatchEvent(new Event('input', {bubbles:true}));"
                " el.dispatchEvent(new Event('change', {bubbles:true})); }",
                value,
            )
        except Exception:
            pass


def _play_scene(d: Director, scene_id: str) -> None:
    page = d.page
    if scene_id == "hook":
        d.caption(SCENES[0].line)
        try:
            d.point_at(page.locator(".stat-card").nth(0), settle_ms=700)
        except Exception:
            pass
        return

    if scene_id == "tiers":
        d.caption(SCENES[1].line)
        try:
            d.point_at(page.locator(".stat-card.highlight-green").first, settle_ms=600)
            d.point_at(page.locator(".stat-card.highlight-red").first, settle_ms=700)
        except Exception:
            pass
        d.scroll_to_text("Today's RM Priority Queue", ms=1100)
        return

    if scene_id == "lead":
        loc = page.locator('a.rm-card[href^="/customer/"]').first
        d.point_at(loc)
        href = None
        try:
            href = loc.get_attribute("href")
        except Exception:
            href = None
        d.go(href or "/customer/IDBI-L10010")
        d.wait_ready(".detail-header h1")
        d.hide_loader()
        d.caption(SCENES[2].line)
        try:
            d.point_at(page.locator(".score.large").first, settle_ms=650)
        except Exception:
            pass
        d.scroll_to_text("Why this tier", ms=1200)
        return

    if scene_id == "actions":
        d.click_nav("/actions")
        d.wait_ready("h1")
        d.caption(SCENES[3].line)
        page.wait_for_timeout(1600)
        d.scroll_to(380, 1200)
        return

    if scene_id == "uplift":
        d.go("/customer/IDBI-L10010")
        d.wait_ready(".detail-header h1")
        d.scroll_to_text("Lead Uplift Simulator", ms=1100)
        d.caption(SCENES[4].line)
        page.wait_for_timeout(1800)
        d.scroll_to_text("What-if", ms=1000)
        d.set_range("luxury_spend_ratio", 40)
        page.wait_for_timeout(650)
        d.set_range("luxury_spend_ratio", 22)
        page.wait_for_timeout(650)
        d.set_range("luxury_spend_ratio", 8)
        page.wait_for_timeout(800)
        d.scroll_to_text("Call script in the customer", ms=900)
        for code in ("hi", "mr", "ta"):
            btn = page.locator(f'button[data-lang="{code}"]').first
            d.click_el(btn, timeout=1500)
            page.wait_for_timeout(850)
        return

    if scene_id == "aa":
        d.click_nav("/multi-bank")
        d.wait_ready("#aa-form")
        d.caption(SCENES[5].line)
        page.wait_for_timeout(900)
        btn = page.locator('#aa-form button[type=submit]').first
        d.click_el(btn)
        try:
            page.wait_for_selector("#aa-result:not([hidden])", timeout=8000)
        except Exception:
            page.wait_for_timeout(2800)
        d.scroll_to(480, 1100)
        return

    if scene_id == "governance":
        d.click_nav("/governance")
        d.wait_ready("h1")
        d.caption(SCENES[6].line)
        page.wait_for_timeout(2200)
        d.scroll_to(300, 800)
        page.wait_for_timeout(1200)
        for href in (
            "/governance?tab=model-risk",
            "/governance?tab=data-quality",
        ):
            tab = page.locator(f'nav.tabs a[href="{href}"]').first
            if not d.click_el(tab):
                d.go(href)
            else:
                page.wait_for_load_state("networkidle")
            d.wait_ready("h1")
            page.wait_for_timeout(1100)
            d.scroll_to(280, 700)
        return

    if scene_id == "outcomes":
        d.click_nav("/outcomes")
        d.wait_ready("h1")
        d.caption(SCENES[7].line)
        page.wait_for_timeout(1400)
        d.scroll_to_text("Calibration", ms=1100)
        return

    if scene_id == "model":
        d.click_nav("/ml")
        d.wait_ready("h1")
        d.caption(SCENES[8].line)
        try:
            d.point_at(page.locator(".stat-card").first, settle_ms=700)
        except Exception:
            pass
        return

    if scene_id == "architecture":
        d.click_nav("/architecture")
        d.wait_ready("h1")
        d.caption(SCENES[9].line)
        d.scroll_to_text("Data Flow", ms=900)
        return

    if scene_id == "differentiators":
        d.click_nav("/differentiators")
        d.wait_ready("h1")
        d.caption(SCENES[10].line)
        page.wait_for_timeout(900)
        d.scroll_to(280, 1100)
        return

    if scene_id == "impact":
        d.click_nav("/impact")
        d.wait_ready("h1")
        d.caption(SCENES[11].line)
        try:
            d.point_at(page.locator(".stat-card, .kpi").nth(1), settle_ms=800)
        except Exception:
            pass
        return

    raise KeyError(scene_id)


def record(base: str, pin: str, out_dir: Path, captions: bool):
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for stale in raw_dir.glob("*.webm"):
        stale.unlink()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--force-device-scale-factor=1"])
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(raw_dir),
            record_video_size={"width": 1920, "height": 1080},
        )
        context.add_init_script(STEALTH_CSS)
        context.add_init_script(CURSOR_JS)
        if captions:
            context.add_init_script(CAPTION_JS)
        page = context.new_page()
        video_started = time.monotonic()
        d = Director(page, captions)
        d.base = base

        page.goto(f"{base}/login", wait_until="networkidle")
        page.fill("input[name=pin]", pin)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        if "/login" in page.url:
            browser.close()
            sys.exit(f"Sign-in failed — is the PIN correct? (tried {pin!r})")

        print("  warming pages so the take has no cold loads…")
        for path in WARM_PATHS:
            try:
                page.goto(base + path, wait_until="domcontentloaded", timeout=20000)
            except Exception as exc:
                print(f"    warn: {path} ({exc})")
        page.goto(base + "/", wait_until="networkidle")
        page.wait_for_timeout(600)

        d.start_clock()
        lead_in = d.t0 - video_started
        print(f"  recording… (trimming {lead_in:.1f}s of sign-in/warmup off the front)")

        for scene in SCENES:
            d.hold_until(max(0.0, scene.at - scene.prep))
            print(f"    {int(scene.at)//60}:{int(scene.at)%60:02d}  {scene.title}")
            _play_scene(d, scene.title)
        d.hold_until(FINAL_SECONDS)

        print(f"  scene clock finished at {d.elapsed():.1f}s")
        page.close()
        context.close()
        browser.close()

    webm = next(iter(sorted(raw_dir.glob("*.webm"))), None)
    if webm is None:
        sys.exit("Playwright produced no video file.")
    return webm, lead_in


def to_mp4(webm: Path, mp4: Path, lead_in: float = 0.0) -> bool:
    if not shutil.which("ffmpeg"):
        print("\n  ffmpeg not found — keeping the .webm.")
        print("  Install it (winget install Gyan.FFmpeg) and re-run — without it the file\n"
              "  keeps the sign-in on the front and runs over three minutes.")
        return False
    subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{max(0.0, lead_in):.2f}", "-i", str(webm),
         "-t", f"{FINAL_SECONDS:.2f}", "-c:v", "libx264", "-crf", "20",
         "-preset", "medium", "-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart",
         str(mp4)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Record the demo video from the running app.")
    ap.add_argument("--base-url", default=os.environ.get("DEMO_BASE_URL", "http://localhost:8000"))
    ap.add_argument("--pin", default=os.environ.get("RM_DEMO_PIN", "idbi2026"))
    ap.add_argument("--out", default=str(ROOT / "docs" / "demo-video"))
    ap.add_argument("--captions", action="store_true",
                    help="Burn a caption bar into the picture (do not use if you will narrate).")
    args = ap.parse_args()

    out_dir = Path(args.out)
    print(f"Recording {args.base_url} -> {out_dir}")
    webm, lead_in = record(args.base_url.rstrip("/"), args.pin, out_dir, captions=args.captions)

    mp4 = out_dir / "IDBI_Prospect_Assist_Demo_v0.9.0.mp4"
    if to_mp4(webm, mp4, lead_in):
        print(f"\nDone: {mp4}")
    else:
        print(f"\nDone: {webm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
