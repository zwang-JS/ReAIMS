"""Build the release ZIP that users drag into chrome://extensions.

Why the file list is not derived from manifest.json
--------------------------------------------------
The obvious approach — collect the paths `manifest.json` references and zip those —
ships a **broken extension**. `manifest.json` never mentions `src/popup/popup.css`;
`popup.html` does (`<link href="popup.css">`). A manifest-derived list would therefore
omit the popup's entire stylesheet and the popup would render unstyled, with nothing
in the build output looking wrong.

So this script includes the whole `src/` and `icons/` trees, and then *verifies* the
result by resolving references in both the manifest AND the nested HTML — which is the
check that actually catches that class of mistake.

Layout requirement
------------------
`manifest.json` must sit at the **root** of the ZIP, not inside a folder. Chrome looks
for the manifest at the root of whatever it unpacks — whether the user drops the ZIP
onto chrome://extensions or extracts it and picks the folder. A nested folder gives
"Manifest file is missing or unreadable". The self-check asserts this.

Usage
-----
    python tools/package_release.py
    python tools/package_release.py --out dist        # default output dir

Writes `dist/ReAIMS-v<version>.zip` and prints every file it packed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
MANIFEST = os.path.join(REPO, "manifest.json")

#: Trees that make up the extension. Everything under these goes in, verbatim.
INCLUDE_DIRS = ["icons", "src"]

#: Individual files at the repo root worth shipping for the reader.
INCLUDE_FILES = ["manifest.json", "README.md", "LICENSE"]

#: Defensive excludes. None of these should appear inside INCLUDE_DIRS today; they are
#: listed so a stray build artifact can never sneak into a release.
EXCLUDE_NAMES = {"__pycache__", ".DS_Store", "Thumbs.db"}
EXCLUDE_SUFFIXES = (".pyc", ".pyo", ".zip", ".crx", ".pem")

#: Fixed timestamp so repeated builds of the same tree are byte-identical.
FIXED_DT = (2026, 1, 1, 0, 0, 0)


def collect() -> list[str]:
    """Repo-relative paths to pack, sorted for determinism."""
    out: list[str] = []
    for name in INCLUDE_FILES:
        path = os.path.join(REPO, name)
        if os.path.exists(path):
            out.append(name)
    for d in INCLUDE_DIRS:
        base = os.path.join(REPO, d)
        for root, dirs, files in os.walk(base):
            dirs[:] = [x for x in dirs if x not in EXCLUDE_NAMES]
            for f in files:
                if f in EXCLUDE_NAMES or f.endswith(EXCLUDE_SUFFIXES):
                    continue
                full = os.path.join(root, f)
                out.append(os.path.relpath(full, REPO).replace("\\", "/"))
    return sorted(set(out))


def referenced_paths() -> set[str]:
    """Every extension-internal path referenced by the manifest or a packed HTML file.

    This is the verification side of the coin: it resolves the nested references the
    manifest does not contain, so a missing stylesheet cannot pass unnoticed.
    """
    refs: set[str] = set()
    manifest = json.load(open(MANIFEST, encoding="utf-8"))

    for v in manifest.get("icons", {}).values():
        refs.add(v)
    action = manifest.get("action", {})
    if "default_popup" in action:
        refs.add(action["default_popup"])
    for v in action.get("default_icon", {}).values():
        refs.add(v)
    for cs in manifest.get("content_scripts", []):
        refs.update(cs.get("css", []))
        refs.update(cs.get("js", []))

    # 再解析每个被引用的 HTML 里 <link href> / <script src> 指向的本地文件
    htmls = [r for r in list(refs) if r.endswith(".html")]
    seen: set[str] = set()
    while htmls:
        rel = htmls.pop()
        if rel in seen:
            continue
        seen.add(rel)
        path = os.path.join(REPO, rel.replace("/", os.sep))
        if not os.path.exists(path):
            continue
        text = open(path, encoding="utf-8", errors="replace").read()
        for attr in re.findall(r'(?:href|src)="([^"]+)"', text):
            if attr.startswith(("http://", "https://", "data:", "#", "mailto:")):
                continue
            target = os.path.normpath(os.path.join(os.path.dirname(rel), attr))
            target = target.replace("\\", "/")
            refs.add(target)
            if target.endswith(".html"):
                htmls.append(target)

    return {r for r in refs if not r.startswith(("http", "data:"))}


def build(out_dir: str) -> tuple[str, list[str]]:
    version = json.load(open(MANIFEST, encoding="utf-8"))["version"]
    os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(out_dir, "ReAIMS-v%s.zip" % version)

    files = collect()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            full = os.path.join(REPO, rel.replace("/", os.sep))
            info = zipfile.ZipInfo(rel, date_time=FIXED_DT)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(full, "rb") as fh:
                zf.writestr(info, fh.read())
    return zip_path, files


def verify(zip_path: str) -> list[str]:
    """Return a list of problems. Empty means the package is sound."""
    problems: list[str] = []
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())

        if "manifest.json" not in names:
            problems.append("manifest.json 不在 zip 根目录 —— Chrome 会报 "
                            "Manifest file is missing or unreadable")
        # 任何文件被套进一层目录都说明打包姿势错了
        if any(n.startswith(("ReAIMS/", "ReAIMS\\")) for n in names):
            problems.append("zip 里出现了多余的一层目录 —— 清单就不在根上了")

        if "manifest.json" in names:
            try:
                data = json.loads(zf.read("manifest.json").decode("utf-8"))
                if not data.get("version"):
                    problems.append("manifest.json 里没有 version")
            except Exception as exc:                       # noqa: BLE001
                problems.append("manifest.json 不是合法 JSON: %s" % exc)

        for rel in sorted(referenced_paths()):
            if rel not in names:
                problems.append("被引用但没打进包里: %s" % rel)

        for n in sorted(names):
            if n.startswith(("tools/", "docs/")) or n == "source code.html":
                problems.append("不该出现在发布包里: %s" % n)

    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(REPO, "dist"),
                    help="输出目录（默认 dist/）")
    args = ap.parse_args()

    zip_path, files = build(args.out)
    size = os.path.getsize(zip_path)
    print("打包完成：%s  （%d 个文件，%s 字节）\n" % (
        os.path.relpath(zip_path, REPO), len(files), format(size, ",")))
    for rel in files:
        print("   " + rel)

    problems = verify(zip_path)
    print()
    if problems:
        print("自检失败：")
        for p in problems:
            print("  - " + p)
        return 1

    print("自检通过：")
    print("  - manifest.json 在 zip 根目录")
    print("  - manifest 与嵌套 HTML 引用的每个文件都在包内")
    print("  - manifest.json 是合法 JSON")
    print("  - 包内不含 tools/ 、docs/ 、source code.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
