"""Check background hygiene on the rendered page — both directions.

Why this exists (and why it is not part of audit_overrides.py)
-------------------------------------------------------------
`audit_overrides.py` answers one question: "is any element still computing to a
literal colour that AIMS declared?" That gate is structurally unable to see the
two failure modes this script covers:

  * It iterates `document.querySelectorAll('[class]')`, so `html`/`body` — which
    have no class — are never inspected, and neither is any classless element
    carrying an inline style.
  * A background that has been *erased* computes to `transparent`, which is not
    an AIMS literal, so removal reads as "nothing to report".
  * Pure white is deliberately excluded from its danger set (we use it on
    purpose for button text and the badge chip), so a white background can never
    be reported.

So the two checks below are a separate concern — background hygiene rather than
literal colours — and live in their own tool rather than bloating that one.

CHECK 1 — nothing light should be painted in dark mode.
  Walks every *visible* element (no `[class]` filter) and flags any computed
  `background-color` that is opaque and bright. This is the check that would
  have caught the reported bug: a CityU notice carrying `bgcolor="#FFFFFF"` on a
  container rendered as white with our pink link colour on top of it. Deliberate
  light surfaces are allow-listed explicitly (the app-store badge chip exists to
  be white in dark mode), and the allow-list is printed so it cannot hide
  anything silently.

CHECK 2 — the surfaces we paint on purpose must still be there.
  Asserts a list of key surfaces equals the token it is supposed to use, in BOTH
  themes. This is the guard for the global background neutraliser added to
  `02-base.css`: that rule clears every background that is not ours, and if its
  specificity were wrong it would clear ours too — silently, and invisibly to
  the literal-colour audit. The `html`/`body` assertion is the canary: if the
  page background ever goes transparent, this fails loudly.

Usage
-----
    python tools/preview/check_surfaces.py
    python tools/preview/check_surfaces.py --selftest   # prove the check can fail

Requires: `fetch_vendor.py` run once, and `build_preview.py` (needs
preview.html). Exits non-zero on failure.
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
PREVIEW = os.path.join(HERE, "preview.html")
OUT_DIR = os.path.join(HERE, "out")
BANNER_CSS = os.path.join(HERE, "vendor", "css", "web_defaultapp.css")

CHROME_CANDIDATES = [
    os.environ.get("CHROME"),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome", "chromium", "chrome",
]

#: Surfaces we paint deliberately, and the token each must resolve to.
#: Compared against the token *resolved in the same theme*, so retuning the
#: palette does not break this check — only losing a surface does.
SURFACES: list[tuple[str, str, str]] = [
    # (label, css selector, token it must equal)
    ("page background (canary)", "html", "--reaims-bg"),
    ("body background (canary)", "body", "--reaims-bg"),
    ("identity bar", ".cityubar_outer", "--reaims-surface"),
    ("brand band", ".header_outer", "--reaims-brand-band"),
    ("sticky nav", ".cityu_noprint", "--reaims-surface"),
    ("active tab pill", ".pageheaderlinks2 td.tabon", "--reaims-brand"),
    ("inactive tab pill", ".pageheaderlinks2 td.taboff", "--reaims-surface-3"),
    ("title rule (bg3)", "div.pagetitlediv td.bg3", "--reaims-line"),
    ("table sheet", "div.body table.datadisplaytable", "--reaims-surface"),
    ("table header cell", "div.body table.datadisplaytable :is(td,th).ddheader", "--reaims-surface-3"),
    ("info callout", "div.infotextdiv table.infotexttable", "--reaims-info-bg"),
    ("warning callout", "table.hwgksphb_privacy", "--reaims-warning-bg"),
    ("badge chip (dark: white on purpose)", ".poweredbydiv img", "--reaims-badge-bg"),
]

#: Light surfaces that are intentional in dark mode. Anything here is reported
#: as "expected" rather than silently skipped.
LIGHT_ALLOWED = [".poweredbydiv img"]

#: Opaque backgrounds brighter than this (relative luminance) are "light".
#: Our lightest dark-mode surface is ~0.02; AIMS's light ones are all >= 0.5.
LUMINANCE_THRESHOLD = 0.35


PROBE_JS = """
<script>
(() => {
  const lines = [];
  const dark = (document.documentElement.getAttribute('data-reaims-theme') || '') === 'dark'
            || (!document.documentElement.hasAttribute('data-reaims-theme')
                && matchMedia('(prefers-color-scheme: dark)').matches);
  const theme = dark ? 'dark' : 'light';

  /* ---- 解析颜色 ----
     Chrome 把 color-mix(in oklab, …) 的计算值序列化成 "oklab(L a b)"，而不是
     rgb()。只认 rgb() 的话，凡是走 color-mix 的令牌（info/warning/danger 的底、
     brand-soft）都会被判成"解析不出来" —— 那是量错了，比不量更糟。
     所以这里把两种写法都归一化成 sRGB 字节。 */
  const clamp01 = (x) => Math.min(1, Math.max(0, x));
  function parseColor(str) {
    if (!str) return null;
    const nums = (str.match(/-?[\\d.]+(?:e-?\\d+)?/g) || []).map(Number);
    if (str.startsWith('oklab') && nums.length >= 3) {
      const [L, a, b] = nums;
      const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
      const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
      const s_ = L - 0.0894841775 * a - 1.2914855480 * b;
      const l = l_ ** 3, m = m_ ** 3, s = s_ ** 3;
      const g1 = (v) => { v = clamp01(v); return 255 * (v <= 0.0031308 ? 12.92 * v : 1.055 * Math.pow(v, 1 / 2.4) - 0.055); };
      return {
        r: Math.round(g1(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s)),
        g: Math.round(g1(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s)),
        b: Math.round(g1(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)),
        a: nums.length > 3 ? nums[3] : 1,
      };
    }
    if (str.startsWith('rgb') && nums.length >= 3) {
      return { r: nums[0], g: nums[1], b: nums[2], a: nums.length > 3 ? nums[3] : 1 };
    }
    return null;
  }

  const probeEl = document.createElement('span');
  document.body.appendChild(probeEl);
  function token(name) {
    probeEl.style.color = 'var(' + name + ')';
    return parseColor(getComputedStyle(probeEl).color);
  }
  function rgbOf(el) {
    return parseColor(getComputedStyle(el).backgroundColor);
  }
  const key = (c) => c ? c.r + ',' + c.g + ',' + c.b : 'none';

  /* 两条路径（令牌 vs 元素计算值）可能差 1 个单位，允许 ±2 的容差 */
  const near = (x, y) => !!x && !!y &&
    Math.abs(x.r - y.r) <= 2 && Math.abs(x.g - y.g) <= 2 &&
    Math.abs(x.b - y.b) <= 2 && Math.abs((x.a || 1) - (y.a || 1)) < 0.02;

  /* WCAG relative luminance from an sRGB triple. */
  function lum(c) {
    const f = (x) => { x /= 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  }

  lines.push('THEME: ' + theme);

  /* ---- CHECK 1: 深色模式下不该有浅色底 ---- */
  lines.push('');
  lines.push('CHECK 1 - light backgrounds in dark mode');
  if (theme !== 'dark') {
    lines.push('  skipped (only meaningful in dark mode)');
  } else {
    const allowed = %s;
    const isAllowed = (el) => allowed.some((sel) => { try { return el.matches(sel); } catch (e) { return false; } });
    let flagged = 0, expected = 0, visible = 0;
    for (const el of document.querySelectorAll('*')) {
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) continue;
      visible++;
      const c = rgbOf(el);
      if (!c || c.a === 0) continue;
      if (lum(c) <= %s) continue;
      if (isAllowed(el)) { expected++; continue; }
      const cls = (el.getAttribute('class') || '').trim().split(/\\s+/).filter(Boolean);
      flagged++;
      if (flagged <= 25) {
        lines.push('  LIGHT  rgb(' + key(c) + ')  lum=' + lum(c).toFixed(2) +
                   '  <' + el.tagName.toLowerCase() + '>' +
                   (cls.length ? '  .' + cls.join('.') : '') +
                   (el.getAttribute('style') ? '  [style]' : '') +
                   (el.hasAttribute('bgcolor') ? '  [bgcolor=' + el.getAttribute('bgcolor') + ']' : ''));
      }
    }
    lines.push('  visible elements scanned: ' + visible);
    lines.push('  deliberate light surfaces (allow-listed): ' + expected +
               '  -> ' + allowed.join(', '));
    lines.push(flagged === 0
      ? '  PASS - no unexpected light background'
      : '  FAIL - ' + flagged + ' element(s) painting a light background');
  }

  /* ---- CHECK 2: 我们自己画的底必须还在 ---- */
  lines.push('');
  lines.push('CHECK 2 - deliberate surfaces still painted');
  const SURFACES = %s;
  let bad = 0, checkedCount = 0;
  for (const [label, sel, tok] of SURFACES) {
    const el = document.querySelector(sel);
    if (!el) { lines.push('  skip   ' + label + '  (' + sel + ' not in this page)'); continue; }
    const want = token(tok);
    const got = rgbOf(el);
    if (!want) { lines.push('  ERR    ' + label + '  token ' + tok + ' did not resolve'); bad++; continue; }
    checkedCount++;
    const same = near(got, want);
    if (!same) bad++;
    lines.push((same ? '  ok     ' : '  FAIL   ') + label.padEnd(38) + ' ' + tok.padEnd(24) +
               'want rgb(' + key(want) + ')' +
               (same ? '' : '  got ' + (got ? 'rgb(' + key(got) + ') alpha=' + got.a : 'none')));
  }
  lines.push(bad === 0
    ? '  PASS - all ' + checkedCount + ' surfaces intact'
    : '  FAIL - ' + bad + ' surface(s) wrong or missing');

  probeEl.remove();

  const pre = document.createElement('pre');
  pre.id = 'reaims-surfaces-out';
  pre.textContent = lines.join('\\n');
  (document.body || document.documentElement).insertBefore(pre, document.body.firstChild);
})();
</script>
"""


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


def build_probe_page() -> str:
    html = open(PREVIEW, encoding="utf-8").read()
    js = PROBE_JS % (
        "[" + ", ".join('"%s"' % s for s in LIGHT_ALLOWED) + "]",
        LUMINANCE_THRESHOLD,
        "[" + ", ".join('["%s", "%s", "%s"]' % s for s in SURFACES) + "]",
    )
    # 生成物放在 out/ 下，链接要多退一级
    for a, b in (('href="../../src/', 'href="../../../src/'),
                 ('href="vendor/', 'href="../vendor/'),
                 ('src="vendor/', 'src="../vendor/')):
        html = html.replace(a, b)
    idx = html.rfind("</body>")
    html = html[:idx] + js + html[idx:]
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "preview-surfaces.html")
    open(path, "w", encoding="utf-8").write(html)
    return path


def run_probe(chrome: str, page: str, theme: str) -> str:
    url = "file:///" + page.replace("\\", "/").lstrip("/") + "?theme=" + theme
    profile = tempfile.mkdtemp(prefix="reaims-surfaces-chrome-")
    try:
        proc = subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--user-data-dir=" + profile,
             "--virtual-time-budget=5000", "--dump-dom", url],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
        )
    finally:
        shutil.rmtree(profile, ignore_errors=True)

    m = re.search(r'<pre id="reaims-surfaces-out">(.*?)</pre>', proc.stdout, re.S)
    if not m:
        err = [ln for ln in (proc.stderr or "").splitlines() if ln.strip()]
        return ("PROBE DID NOT RUN -- no output in the rendered DOM.\n"
                "  chrome exit code : %s\n  dom bytes        : %s\n  chrome stderr    : %s"
                % (proc.returncode, len(proc.stdout), err[0] if err else "(empty)"))
    text = m.group(1)
    for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"')):
        text = text.replace(a, b)
    return text.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true",
                    help="故意弄坏一个面，确认检查会 FAIL，然后还原")
    args = ap.parse_args()

    missing = [p for p in (PREVIEW, BANNER_CSS) if not os.path.exists(p)]
    if missing:
        print("缺少 %s —— 先跑 fetch_vendor.py 与 build_preview.py" % ", ".join(missing),
              file=sys.stderr)
        return 2
    chrome = find_chrome()
    if not chrome:
        print("找不到 Chrome —— 用 CHROME 环境变量指定路径。", file=sys.stderr)
        return 2

    target = os.path.join(REPO, "src", "styles", "03-chrome.css")
    original = None
    if args.selftest:
        # 把徽章白片的 !important 去掉 —— 那正是"被中和规则吃掉"的典型症状：
        # 背景变成透明，深色下黑色徽章就看不见了。
        raw = open(target, "rb").read()
        style = "\r\n" if b"\r\n" in raw else "\n"
        body = raw.decode("utf-8").replace("\r\n", "\n")
        needle = "  background: var(--reaims-badge-bg) !important;"
        if needle not in body:
            print("自检锚点未找到（03-chrome.css 的徽章规则可能已改动）。", file=sys.stderr)
            return 2
        original = (body, style)
        broken = body.replace(needle, "  background: var(--reaims-badge-bg);  /* selftest */")
        open(target, "wb").write((broken if style == "\n" else broken.replace("\n", style)).encode("utf-8"))
        print("自检：已临时去掉徽章白片的 !important，期望 CHECK 2 报 FAIL\n")

    results = {}
    try:
        page = build_probe_page()
        for theme in ("dark", "light"):
            out = run_probe(chrome, page, theme)
            results[theme] = out
            print("=" * 78)
            print(out)
            print()
    finally:
        if original is not None:
            body, style = original
            open(target, "wb").write((body if style == "\n" else body.replace("\n", style)).encode("utf-8"))
            print("自检：已还原 03-chrome.css\n")

    failed = any(("FAIL" in r) or r.startswith("PROBE DID NOT RUN") for r in results.values())
    if args.selftest:
        if failed:
            print("自检通过：检查确实能发现问题。")
            return 0
        print("自检失败：故意弄坏后仍然全绿 —— 这个检查不可信。")
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
