"""Download the third-party assets the preview harness needs.

Why this is a script and not committed files
--------------------------------------------
The preview harness needs two kinds of third-party material to be faithful:

  1. AIMS's real stylesheet (`web_defaultapp.css`). Without it the harness cannot
     test the one thing that matters most — whether our `!important` rules actually
     beat AIMS's rules in the real cascade order. With it, the harness reproduces
     the live browser exactly.
  2. A handful of CityU brand assets (logo, header banner, app-store badges) and
     Banner's decorative GIFs, so the header and menu bullets render instead of
     showing broken-image icons.

None of that belongs to this project — it is CityU's, Ellucian/SunGard's and
Apple/Google's. This repository is public, so rather than redistribute their
material we download it on demand, straight from the same public URLs the browser
uses. `tools/preview/vendor/` is gitignored.

Usage
-----
    python tools/preview/fetch_vendor.py            # fetch anything missing
    python tools/preview/fetch_vendor.py --force    # re-fetch everything

Run it once after cloning, before opening the preview.
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request

BANWEB = "https://banweb.cityu.edu.hk"
TEMPLATE = "https://template.cityu.edu.hk"

# (url, path under vendor/)
ASSETS: list[tuple[str, str]] = [
    # AIMS 的真实样式表 —— 层叠验证的核心，缺了它预览台就失去意义
    (f"{BANWEB}/cityu2/css/web_defaultapp.css", "css/web_defaultapp.css"),
    # 品牌资源（用于页头色带、CityU 标识、页脚应用商店徽章）
    (f"{BANWEB}/cityu2/gifs/web_header.png", "cityu2/gifs/web_header.png"),
    (f"{TEMPLATE}/template/img/logos/cityu_deptpage.png", "cityu_deptpage.png"),
    (f"{BANWEB}/cityu2/gifs/button_ios_apps.png", "cityu2/gifs/button_ios_apps.png"),
    (f"{BANWEB}/cityu2/gifs/button_android_apps.png", "cityu2/gifs/button_android_apps.png"),
    (f"{BANWEB}/cityu2/gifs/button_cityu_apps.png", "cityu2/gifs/button_cityu_apps.png"),
    # Banner 的装饰性位图（透明占位、标签圆角、蓝球项目符号、信息图标）
    (f"{BANWEB}/wtlgifs/web_transparent.gif", "wtlgifs/web_transparent.gif"),
    (f"{BANWEB}/wtlgifs/web_tab_corner_right.gif", "wtlgifs/web_tab_corner_right.gif"),
    (f"{BANWEB}/wtlgifs/web_info_cascade.png", "wtlgifs/web_info_cascade.png"),
    (f"{BANWEB}/gengifs/hwggbbal.gif", "gengifs/hwggbbal.gif"),
    # 按钮上的渐变底图（Banner 把颜色写在图里，扩展必须覆盖它们）
    (f"{BANWEB}/cityu2/gifs/web_tab_corner.gif", "cityu2/gifs/web_tab_corner.gif"),
    (f"{BANWEB}/cityu2/gifs/web_bg_button.png", "cityu2/gifs/web_bg_button.png"),
    (f"{BANWEB}/cityu2/gifs/web_bg_button_100x27.png", "cityu2/gifs/web_bg_button_100x27.png"),
    (f"{BANWEB}/cityu2/gifs/web_bg_button_28x22.png", "cityu2/gifs/web_bg_button_28x22.png"),
]

VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
UA = "ReAIMS-preview-fetch/1.0 (+local development fixture; not an extension component)"


def fetch(url: str, dest: str, force: bool) -> str:
    """Returns 'skip' | 'ok' | 'fail'."""
    if os.path.exists(dest) and not force:
        return "skip"

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        print(f"  FAIL  {url}\n        {exc}")
        return "fail"

    if not data:
        print(f"  FAIL  {url}\n        服务器返回空内容")
        return "fail"

    with open(dest, "wb") as handle:
        handle.write(data)
    print(f"  ok    {os.path.relpath(dest, VENDOR)}  ({len(data):,} bytes)")
    return "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="重新下载已存在的文件")
    args = parser.parse_args()

    print(f"下载预览台所需的第三方资源到 {os.path.relpath(VENDOR)}/\n")
    counts = {"ok": 0, "skip": 0, "fail": 0}
    for url, rel in ASSETS:
        counts[fetch(url, os.path.join(VENDOR, rel), args.force)] += 1

    print(
        f"\n完成：新下载 {counts['ok']}，已存在跳过 {counts['skip']}，失败 {counts['fail']}"
    )

    if counts["fail"]:
        print(
            "\n有资源下载失败。缺 web_defaultapp.css 的话，预览台仍然能打开，\n"
            "但它就【无法验证层叠覆盖】了 —— 那是这个预览台存在的主要理由，\n"
            "所以务必在网络可达时重跑一次。"
        )
        return 1

    print("\n现在可以打开 tools/preview/preview.html 了。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
