"""Capture evidence screenshots for each problem and collect them in screenshots/SCREENSHOTS.md.

    python scripts/screenshot.py 1 --file AI_prompts.md --caption "AI_prompts.md log created"
    python scripts/screenshot.py 3 --url http://localhost:5173 --caption "Product grid"
    python scripts/screenshot.py 4 --url http://localhost:5173 --full-page --caption "..."
    python scripts/screenshot.py 3 --url http://localhost:5173 --chat "Do you have hoodies?" --caption "Chat"

--file renders a Markdown/text/code file as a page; --url screenshots a running site.
Several shots per problem are numbered problem3.png, problem3b.png, ...
"""

from __future__ import annotations

import argparse
import html
import re
from datetime import datetime
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SHOT_DIR = ROOT / "screenshots"
GALLERY = SHOT_DIR / "SCREENSHOTS.md"

PAGE_CSS = """
body { font-family: Segoe UI, Arial, sans-serif; max-width: 1000px; margin: 24px auto; padding: 0 24px;
       color: #1d2733; background: #fff; line-height: 1.5; }
.bar { background: #00356b; color: #fff; padding: 8px 14px; border-radius: 6px; font-family: Consolas, monospace;
       font-size: 14px; margin-bottom: 16px; }
blockquote { border-left: 4px solid #00356b; margin: 8px 0; padding: 4px 12px; background: #f3f6fa; }
code, pre { font-family: Consolas, monospace; background: #f3f6fa; }
pre { padding: 12px; overflow-x: auto; border-radius: 6px; font-size: 13px; }
table { border-collapse: collapse; } td, th { border: 1px solid #ccd; padding: 4px 8px; }
"""


def render_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".md":
        body = markdown.markdown(text, extensions=["tables", "fenced_code"])
    else:
        body = f"<pre>{html.escape(text)}</pre>"
    rel = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name
    return f"<html><head><style>{PAGE_CSS}</style></head><body><div class='bar'>{rel}</div>{body}</body></html>"


def next_name(problem: str) -> str:
    base = f"problem{problem}"
    existing = {p.stem for p in SHOT_DIR.glob(f"{base}*.png")}
    if base not in existing:
        return base
    for letter in "bcdefghijklmnopqrstuvwxyz":
        if base + letter not in existing:
            return base + letter
    raise RuntimeError("too many screenshots for one problem")


def add_to_gallery(problem: str, name: str, caption: str, source: str) -> None:
    if not GALLERY.exists():
        GALLERY.write_text("# Screenshots: evidence by problem\n", encoding="utf-8")
    text = GALLERY.read_text(encoding="utf-8")
    heading = f"## Problem {problem}"
    entry = (f"\n**{caption}** ({source}, {datetime.now():%Y-%m-%d %H:%M})\n\n"
             f"![{caption}]({name}.png)\n")
    if heading in text:
        # insert after the last entry of this problem (before the next heading, or at the end)
        start = text.index(heading)
        nxt = re.search(r"\n## Problem ", text[start + len(heading):])
        cut = start + len(heading) + nxt.start() if nxt else len(text)
        text = text[:cut].rstrip("\n") + "\n" + entry + text[cut:]
    else:
        text = text.rstrip("\n") + f"\n\n{heading}\n" + entry
    GALLERY.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("problem", help="problem number, e.g. 3")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="page of the running site to capture")
    src.add_argument("--file", type=Path, help="Markdown/text/code file to render and capture")
    parser.add_argument("--caption", required=True)
    parser.add_argument("--chat", help="open the chat widget, send this message, and wait for the reply")
    parser.add_argument("--full-page", action="store_true", help="capture the whole scrollable page")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=800)
    parser.add_argument("--wait", type=int, default=800, help="ms to wait after load (images, data)")
    args = parser.parse_args()

    SHOT_DIR.mkdir(exist_ok=True)
    name = next_name(args.problem)
    out = SHOT_DIR / f"{name}.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": args.width, "height": args.height})
        if args.url:
            page.goto(args.url, wait_until="networkidle")
            source = args.url
            if args.chat:
                page.click(".chat-fab")
                # count real (non-typing) assistant messages, then wait for one more with no typing indicator
                before = page.locator(".chat-msg.assistant:not(.typing)").count()
                page.fill(".chat-input input", args.chat)
                page.click(".chat-input button")
                page.wait_for_function(
                    "n => document.querySelectorAll('.chat-msg.assistant:not(.typing)').length > n"
                    " && !document.querySelector('.chat-msg.typing')",
                    arg=before,
                    timeout=120_000,
                )
                page.wait_for_timeout(800)
        else:
            path = (ROOT / args.file) if not args.file.is_absolute() else args.file
            page.set_content(render_file(path))
            source = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name
        page.wait_for_timeout(args.wait)
        page.screenshot(path=str(out), full_page=args.full_page or bool(args.file))
        browser.close()
    add_to_gallery(args.problem, name, args.caption, source)
    print(f"Saved {out.relative_to(ROOT).as_posix()} and added it to {GALLERY.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
