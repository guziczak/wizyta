import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "frontend" / "src"
OUT_FILE = ROOT / "index.html"

CSS_TOKEN = "<!-- INLINE_CSS -->"
JS_TOKEN = "<!-- INLINE_JS -->"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def minify_css(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*([:;{},])\s*", r"\1", text)
    return text.strip()


def minify_js(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    lines = [line.rstrip() for line in text.splitlines()]
    lines = [line for line in lines if line.strip()]
    return "\n".join(lines).strip()


def minify_html(text: str) -> str:
    text = re.sub(r"<!--(?!\[if).*?-->", "", text, flags=re.S)
    text = re.sub(r">\s+<", "><", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def build(minify: bool) -> None:
    html = _read(SRC_DIR / "index.html")
    css = _read(SRC_DIR / "styles.css")
    js = _read(SRC_DIR / "app.js")

    if minify:
        css_out = minify_css(css)
        js_out = minify_js(js)
    else:
        css_out = css.strip()
        js_out = js.strip()

    html = html.replace(CSS_TOKEN, f"<style>{css_out}</style>")
    html = html.replace(JS_TOKEN, f"<script>{js_out}</script>")

    if minify:
        html = minify_html(html)

    OUT_FILE.write_text(html + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build and minify frontend into index.html")
    parser.add_argument("--no-minify", action="store_true", help="Skip minification")
    args = parser.parse_args()
    build(not args.no_minify)
    print(f"Wrote {OUT_FILE}")
