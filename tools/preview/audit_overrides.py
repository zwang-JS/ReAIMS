"""Audit that our overrides actually beat AIMS's colours — and prove the audit can fail.

What this checks
----------------
The extension's entire premise is "every colour AIMS hardcodes is overridden". This
script tests that claim across the *whole* class inventory at once, instead of the
handful of pages we happen to have markup for.

Method: parse every literal colour AIMS's stylesheet declares, then render the
preview fixtures in DARK mode and walk every visible classified element, reporting
any whose computed `color` or `background-color` is still one of AIMS's literals.

Why the dark-mode restriction makes this sound: in dark mode every one of our own
values is dark, while every one of AIMS's is light (it was a 2002 light-only design).
So an overlap cannot be a coincidence — it is a missed override. The one exception is
pure white, which we deliberately use twice (button text, and the app-store badge
chip in `07-widgets`/`03-chrome`); those specific values are excluded explicitly
below, and that exclusion is the only "trust me" in the whole check.

Verifying the verifier
----------------------
A check that cannot fail proves nothing, so this script ships with a self-test:
`--selftest` deliberately breaks one override, confirms the audit then FAILS, and
restores the file. Run it if you ever change the audit and want to know it still
detects anything.

Usage
-----
    python tools/preview/audit_overrides.py            # run the audit
    python tools/preview/audit_overrides.py --selftest # prove the audit can fail

Requires: `python tools/preview/fetch_vendor.py` to have been run (needs AIMS's
stylesheet), and Chrome. Exits non-zero on FAIL.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
BANNER_CSS = os.path.join(HERE, "vendor", "css", "web_defaultapp.css")
PREVIEW = os.path.join(HERE, "preview.html")
OUT_DIR = os.path.join(HERE, "out")

# 我方深色令牌值。必须排除 —— 否则会把正确的设计取值误报成覆盖失败。
# 这里唯一需要"相信我"的地方，已在模块 docstring 里说明理由。
OURS = {
    (0x13, 0x12, 0x16), (0x1A, 0x19, 0x1F), (0x21, 0x1F, 0x27), (0x26, 0x24, 0x2D),
    (0x1F, 0x1D, 0x25), (0x2A, 0x28, 0x31), (0xED, 0xEB, 0xF1), (0xA0, 0x9E, 0xAC),
    (0x7D, 0x7B, 0x88), (0xC0, 0x33, 0x7A), (0xD6, 0x45, 0x8C), (0x3D, 0x0A, 0x26),
    (0xF0, 0x6C, 0xA8), (0xFF, 0x8F, 0xC0), (0xD9, 0x9A, 0xE0), (0xFF, 0xFF, 0xFF),
    (0xFF, 0x9B, 0x95), (0xFF, 0xC4, 0x6B), (0x6E, 0xE7, 0xA0), (0x86, 0xBD, 0xF5),
    (0xFF, 0xB2, 0x7A), (0x2C, 0x2A, 0x34), (0x3A, 0x37, 0x43),
}

CHROME_CANDIDATES = [
    os.environ.get("CHROME"),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome", "chromium", "chrome",
]


def find_chrome() -> str | None:
    for c in CHROME_CANDIDATES:
        if not c:
            continue
        if os.path.sep in c or c.endswith(".exe"):
            if os.path.exists(c):
                return c
        else:
            found = shutil.which(c)
            if found:
                return found
    return None


def banner_literals(path: str) -> set[tuple[int, int, int]]:
    """Every literal colour AIMS declares on a colour-ish property."""
    css = open(path, encoding="utf-8", errors="replace").read()
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out: set[tuple[int, int, int]] = set()
    for block in re.findall(r"\{([^{}]*)\}", css):
        for decl in block.split(";"):
            prop, _, value = decl.partition(":")
            prop = prop.strip().lower()
            if prop not in ("color", "background-color", "background",
                            "border-color", "border-top-color"):
                continue
            for m in re.finditer(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b", value):
                h = m.group(1)
                if len(h) == 3:
                    h = "".join(ch * 2 for ch in h)
                out.add(tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)))
            for name, rgb in (("white", (255, 255, 255)), ("black", (0, 0, 0))):
                if re.search(r"\b%s\b" % name, value, re.I):
                    out.add(rgb)
    return out


AUDIT_JS = """
<script>
(() => {
  const DANGER = new Set([%s]);
  function rgbOf(el, prop) {
    const v = getComputedStyle(el).getPropertyValue(prop);
    const m = v.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)(?:,\\s*([\\d.]+))?\\)/);
    if (!m) return null;
    if (m[4] !== undefined && parseFloat(m[4]) === 0) return null;
    return m[1] + "," + m[2] + "," + m[3];
  }
  const offenses = [];
  let inspected = 0, hidden = 0;
  for (const el of document.querySelectorAll('[class]')) {
    const cls = (el.getAttribute('class') || '').trim().split(/\\s+/);
    if (!cls.length) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') { hidden++; continue; }
    inspected++;
    for (const prop of ['color', 'background-color']) {
      const v = rgbOf(el, prop);
      if (v && DANGER.has(v)) {
        const anc = el.closest('.body,.cityu_noprint,.footer_outer,.pagetitlediv,.cityubar_outer');
        offenses.push(prop + '=' + v + '  .' + cls.join('.') +
                      '  <' + el.tagName.toLowerCase() + '>' +
                      '  ctx=' + (anc ? '.' + anc.className.split(/\\s+/)[0] : '(none)'));
      }
    }
  }
  const lines = [
    'audited (visible, classified) elements: ' + inspected + '   |   hidden skipped: ' + hidden,
    'AIMS literals that are not one of our own values: ' + DANGER.size,
    '',
  ];
  if (!offenses.length) {
    lines.push('PASS - no element still computes to an AIMS literal colour in dark mode.');
  } else {
    const uniq = [...new Set(offenses)];
    lines.push('FAIL - ' + uniq.length + ' distinct place(s) still computing to an AIMS literal:');
    lines.push('');
    for (const o of uniq) lines.push('  ' + o);
  }
  const pre = document.createElement('pre');
  pre.id = 'reaims-audit-out';
  pre.textContent = lines.join('\\n');
  document.body.insertBefore(pre, document.body.firstChild);
})();
</script>
"""


def build_audit_page(danger: set[tuple[int, int, int]]) -> str:
    html = open(PREVIEW, encoding="utf-8").read()
    js = AUDIT_JS % ",\n    ".join('"%d,%d,%d"' % c for c in sorted(danger))

    # 生成物放在 out/ 下，所以里面的相对路径都要多退一级
    for a, b in (('href="../../src/', 'href="../../../src/'),
                 ('href="vendor/', 'href="../vendor/'),
                 ('src="vendor/', 'src="../vendor/')):
        html = html.replace(a, b)

    idx = html.rfind("</body>")
    html = html[:idx] + js + html[idx:]

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "preview-audit.html")
    open(path, "w", encoding="utf-8").write(html)
    return path


def run_audit(chrome: str, page: str) -> str:
    url = "file:///" + page.replace("\\", "/").lstrip("/") + "?theme=dark"
    proc = subprocess.run(
        [chrome, "--headless=new", "--disable-gpu", "--virtual-time-budget=5000",
         "--dump-dom", url],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    m = re.search(r'<pre id="reaims-audit-out">(.*?)</pre>', proc.stdout, re.S)
    if not m:
        return "AUDIT DID NOT RUN — could not find its output in the rendered DOM."
    text = m.group(1)
    for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"')):
        text = text.replace(a, b)
    return text.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true",
                    help="故意破坏一条覆盖规则，确认审计会 FAIL，然后还原")
    args = ap.parse_args()

    if not os.path.exists(BANNER_CSS):
        print("缺少 vendor/css/web_defaultapp.css —— 先跑 python tools/preview/fetch_vendor.py",
              file=sys.stderr)
        return 2
    if not os.path.exists(PREVIEW):
        print("缺少 tools/preview/preview.html —— 先跑 python tools/preview/build_preview.py",
              file=sys.stderr)
        return 2

    chrome = find_chrome()
    if not chrome:
        print("找不到 Chrome —— 用 CHROME 环境变量指定可执行文件路径。", file=sys.stderr)
        return 2

    danger = banner_literals(BANNER_CSS) - OURS

    target = os.path.join(REPO, "src", "styles", "03-chrome.css")
    original = None
    if args.selftest:
        # 挑一条【没有后备规则】的：td.bg3 的底色（AIMS 的 #cccc00）。
        # 别挑 a:link 之类的 —— 02-base 的全局规则会兜住，破坏它不会改变实际取值，
        # 于是审计"正确地"仍然 PASS，看起来像审计失灵。
        original = open(target, encoding="utf-8").read()
        needle = "  background-color: var(--reaims-line) !important;\n  background-image: none !important;\n}"
        if needle not in original:
            print("自检锚点未找到，03-chrome.css 的 td.bg3 规则可能已改动。", file=sys.stderr)
            return 2
        open(target, "w", encoding="utf-8").write(
            original.replace(needle, "  /* selftest: override removed */\n"
                                     "  background-image: none !important;\n}"))
        print("自检：已临时移除 td.bg3 的底色覆盖，期望审计报告 FAIL\n")

    try:
        page = build_audit_page(danger)
        result = run_audit(chrome, page)
        print(result)
    finally:
        if original is not None:
            open(target, "w", encoding="utf-8").write(original)
            print("\n自检：已还原 03-chrome.css")

    # 注意：不能判断 result.startswith("FAIL") —— 结果前几行是统计摘要，
    # FAIL 出现在中间。必须查子串。
    failed = ("FAIL - " in result) or result.startswith("AUDIT DID NOT RUN")
    if args.selftest:
        if "FAIL - " in result:
            print("\n自检通过：审计确实能发现问题。")
            return 0
        print("\n自检失败：故意破坏后审计仍然 PASS —— 这个检查是不可信的。")
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
