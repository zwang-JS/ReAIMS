#!/usr/bin/env python3
"""Regenerate tools/preview/preview.html and tools/preview/preview-bare.html.

The preview harness is the visual verification rig for the ReAIMS restyle: it
renders real (and realistically-shaped) Banner 8.x Self-Service markup so the
theme can be checked without logging into AIMS. Both pages are plain static
files -- no build step, no server, no extension required; just open them in
Chrome.

preview.html is a *generated* artifact. This script is the source of truth for:

  1. Fixture 1, lifted verbatim from ``source code.html`` at the repo root
     (a real captured AIMS main-menu page),
  2. the harness-only ``<style>`` / ``<script>`` chrome, which must survive
     regeneration and stay byte-identical, and
  3. the two rewrites applied to every fixture below (see REWRITES).


TWO THINGS IN HERE LOOK WRONG AND ARE NOT. READ BEFORE EDITING.

1. THE CASCADE ORDER IS INVERTED.
   The 8 extension stylesheets are linked FIRST and Banner's own stylesheet
   (``vendor/css/web_defaultapp.css``) is linked LAST. That is the opposite of
   the conventional "reset first, theme last" order, and it is deliberate: in
   the real browser our CSS arrives via ``content_scripts[].css``, which Chrome
   applies BEFORE the page's own ``<link>`` elements. Banner therefore wins
   every equal-specificity source-order tie on the live site -- which is the
   entire reason every rule in ``src/styles/`` carries ``!important``. Link
   Banner's stylesheet first and our rules will appear to win when they do not,
   and the harness silently stops reproducing the real cascade.

2. ASSET PATHS ARE REWRITTEN TO THE VENDORED COPIES.
   The captured markup uses root-absolute paths (``/cityu2/gifs/...``) that
   cannot resolve over ``file://``. ``vendorise()`` repoints them at
   ``tools/preview/vendor/`` so the brand band, tab corners and menu bullets
   actually render. Without this the fixture is full of broken-image icons and
   hides exactly what needs looking at.


ONE PREREQUISITE.

   Run ``python tools/preview/fetch_vendor.py`` once after cloning, before
   building or opening anything.

   ``tools/preview/vendor/`` holds third-party material -- AIMS's real
   stylesheet and CityU/Apple/Google brand images -- that this public repo
   deliberately does not redistribute, so it is gitignored and fetched on
   demand. Point 1 above is the reason that matters: with the stylesheet
   missing, the pages still open and still look plausible while testing
   nothing at all. Silent degradation is the worst possible failure here, so
   this script warns loudly on stderr and the generated pages raise a visible
   banner.


Usage:

    python tools/preview/build_preview.py           # write both pages
    python tools/preview/build_preview.py --check   # exit 1 if either is stale

Paths are resolved relative to this script's own location, so it works from
any working directory.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
SOURCE_PAGE = REPO_ROOT / "source code.html"

OUT_PREVIEW = HERE / "preview.html"
OUT_BARE = HERE / "preview-bare.html"

#: The extension's own stylesheets, in their exact cascade order (a later file
#: wins ties). Hrefs are relative to the generated pages so they resolve over
#: file://.  NOTE: these are linked BEFORE Banner's stylesheet -- see the
#: module docstring before changing anything here.
STYLESHEETS = (
    "../../src/styles/01-tokens.css",
    "../../src/styles/02-base.css",
    "../../src/styles/03-chrome.css",
    "../../src/styles/04-tables.css",
    "../../src/styles/05-forms.css",
    "../../src/styles/06-messages.css",
    "../../src/styles/07-widgets.css",
    "../../src/styles/custom.css",
)

#: Banner's real page stylesheet, vendored byte-identical to the live one.
#: It MUST stay last -- see the module docstring.
BANNER_STYLESHEET = "vendor/css/web_defaultapp.css"

#: Vendored files referenced by the generated pages: ``src="vendor/..."`` or
#: ``href="vendor/..."``. Deliberately anchored on the attribute form so the
#: prose mentions of these paths inside comments do not register as references.
VENDOR_REF = re.compile(r'(?:src|href)="(vendor/[^"]+)"')

#: Stderr warning frame. Wide enough to be unmissable in a scrolled terminal.
_BANG = "!" * 78


# --------------------------------------------------------------------------
# Vendored-asset preflight
# --------------------------------------------------------------------------

def find_missing_vendor_assets(*pages: str) -> list[str]:
    """Return vendored paths the pages reference but which are absent on disk."""
    refs: set[str] = set()
    for page in pages:
        refs.update(VENDOR_REF.findall(page))
    return sorted(ref for ref in refs if not (HERE / ref).exists())


def warn_missing_vendor(missing: list[str]) -> None:
    """Print a loud stderr warning about missing vendored assets.

    Two severities. Without Banner's stylesheet the harness is not testing the
    cascade at all and a green-looking preview means nothing, so that case gets
    the alarming wording. Missing brand images only degrade fidelity.
    """
    missing_banner_css = BANNER_STYLESHEET in missing
    decorative = [m for m in missing if m != BANNER_STYLESHEET]

    if missing_banner_css:
        headline = "PREVIEW HARNESS IS NOT TESTING THE CASCADE -- READ THIS"
    else:
        headline = "PREVIEW HARNESS IS MISSING VENDORED ASSETS"

    lines = [
        "",
        _BANG,
        "!!",
        f"!!  {headline}",
        "!!",
        _BANG,
        "",
        "  Missing from tools/preview/vendor/:",
    ]
    if missing_banner_css:
        lines.append(f"    - {BANNER_STYLESHEET}   <-- the cascade check depends on this")
    lines.extend(f"    - {path}" for path in decorative)
    lines.append("")

    if missing_banner_css:
        lines += [
            "  The pages were still written and WILL still open, and they will still",
            "  look plausible. That is exactly the problem. Banner's real stylesheet is",
            "  not being loaded, so the inverted cascade is not reproduced and nothing",
            "  in this preview proves that our !important rules actually beat Banner's.",
            "  A preview that looks fine right now proves nothing at all.",
        ]
        if decorative:
            lines += [
                "",
                f"  ({len(decorative)} decorative file(s) are missing too -- brand images and",
                "  GIFs, which only affect how the header and bullets look.)",
            ]
    else:
        lines += [
            "  Banner's stylesheet is present, so the cascade check IS active. Only",
            "  decorative assets -- brand images and Banner's GIFs -- are missing, so",
            "  the header and menu bullets will show broken-image icons.",
        ]

    lines += [
        "",
        "  Fix it, then re-run this script:",
        "",
        "      python tools/preview/fetch_vendor.py",
        "",
        "  vendor/ holds third-party material this public repo does not redistribute,",
        "  so it is gitignored and fetched on demand. The preview will open either",
        "  way -- it just will not be validating anything.",
        "",
        _BANG,
        "",
    ]
    print("\n".join(lines), file=sys.stderr)


# --------------------------------------------------------------------------
# Asset rewriting
# --------------------------------------------------------------------------

#: The CityU logo is fetched from an absolute https URL in the capture.
_TEMPLATE_LOGO = re.compile(
    r"https?://template\.cityu\.edu\.hk/template/img/logos/cityu_deptpage\.png",
    re.IGNORECASE,
)

#: ``src="/foo/bar.png"`` -> ``src="vendor/foo/bar.png"``.
#: Only src= is touched: href= values are page navigations (/pls/PROD/...),
#: not assets, and prefixing them with vendor/ would be a lie. The (?!/)
#: lookahead leaves protocol-relative //host/... URLs alone.
_ABSOLUTE_SRC = re.compile(
    r"""(\ssrc\s*=\s*)(["'])/(?!/)([^"']*)\2""",
    re.IGNORECASE,
)


def vendorise(markup: str) -> str:
    """Repoint root-absolute asset paths at the vendored copies.

    Applied to the copied capture and to the fixture templates alike, so a
    regeneration stays correct.
    """
    markup = _TEMPLATE_LOGO.sub("vendor/cityu_deptpage.png", markup)
    return _ABSOLUTE_SRC.sub(
        lambda m: f"{m.group(1)}{m.group(2)}vendor/{m.group(3)}{m.group(2)}",
        markup,
    )


# --------------------------------------------------------------------------
# Fixture 1 -- lifted verbatim from source code.html
# --------------------------------------------------------------------------

def load_fixture_1() -> str:
    """Return the captured AIMS page body, verbatim apart from <script> removal.

    The capture is a ``<body>...</body>`` fragment. We drop the outer body tags
    (the harness has its own <body>) and strip every ``<script>`` block: the
    session-timeout block would run and error offline, and the Google tag block
    would make a real network request to googletagmanager.com. Nothing else is
    touched -- the markup is byte-accurate and deliberately left unformatted.
    """
    text = SOURCE_PAGE.read_text(encoding="utf-8")
    # Normalise CRLF so the generated file is LF-only and deterministic.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    opening = re.search(r"<body[^>]*>", text, re.IGNORECASE)
    if opening is None:
        raise SystemExit(f"{SOURCE_PAGE}: no <body> tag found")
    body = text[opening.end():]

    body = re.sub(r"</body\s*>\s*$", "", body, flags=re.IGNORECASE)
    body = re.sub(
        r"<script\b[^>]*>.*?</script\s*>",
        "",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return body.strip()


# --------------------------------------------------------------------------
# Fixture 2 -- real data-entry form, captured live from the catalog page
# --------------------------------------------------------------------------

FIXTURE_2 = """\
<div class="infotextdiv"><table CLASS="infotexttable"><tr><td CLASS="indefault"><img src="/wtlgifs/web_info_cascade.png" alt="Information" CLASS="headerImg" HEIGHT=12 WIDTH=14 /></td><td CLASS="indefault"><SPAN class="infotext"> Please select a Catalog term and choose Submit to proceed to the Course Search page.</SPAN></td></tr></table></DIV>
<form action="#" method="post">
<input type="hidden" name="call_proc_in" value="" />
<table CLASS="dataentrytable" WIDTH="100%"><caption class="captiontext">Search by Term: </caption>
<tr><TD CLASS="dedefault"><LABEL for=term_input_id><SPAN class="fieldlabeltextinvisible">Term</SPAN></LABEL>
<select name="cat_term_in" size="1" ID="term_input_id">
<OPTION VALUE="None">None</OPTION>
<OPTION VALUE="202609">Semester A 2026/27</OPTION>
</select>
</TD></tr>
</table>
<br /><br />
<input type="submit" value="Submit" />
</form>"""


# --------------------------------------------------------------------------
# Fixture 3 -- synthesised data tables
# Only real Banner class vocabulary is used anywhere below: datadisplaytable /
# captiontext / ddheader / dddefault / ddlabel / ddseparator / dataentrytable /
# dedefault / bordertable / dbheader / dbdefault / ntdefault / ntlabel, plus
# Banner's bare colour utility classes.
# --------------------------------------------------------------------------

FIXTURE_3 = """\
<table class="datadisplaytable" summary="This table lists the courses and grades for the selected term.">
<caption class="captiontext">Semester A 2026/27 Course and Grade List</caption>
<tr>
<th class="ddheader" scope="col">Course</th>
<th class="ddheader" scope="col">Title</th>
<th class="ddheader" scope="col">Units</th>
<th class="ddheader" scope="col">Grade</th>
<th class="ddheader" scope="col">Quality Points</th>
<th class="ddheader" scope="col">Status</th>
</tr>
<tr>
<td class="ddlabel">CS1102</td>
<td class="dddefault">Introduction to Computer Studies</td>
<td class="dddefault">3</td>
<td class="dddefault"><span class="green">A-</span></td>
<td class="dddefault">11.10</td>
<td class="dddefault">Registered</td>
</tr>
<tr>
<td class="ddlabel">CS2204</td>
<td class="dddefault">Fundamentals of Internet Applications
<table class="datadisplaytable" summary="This table lists the meeting times for CS2204.">
<caption class="captiontext">Scheduled Meeting Times</caption>
<tr>
<th class="ddheader" scope="col">Type</th>
<th class="ddheader" scope="col">Time</th>
<th class="ddheader" scope="col">Days</th>
<th class="ddheader" scope="col">Where</th>
<th class="ddheader" scope="col">Date Range</th>
</tr>
<tr>
<td class="dddefault">Lecture</td>
<td class="dddefault">9:00 am - 10:50 am</td>
<td class="dddefault">M W</td>
<td class="dddefault">YEUNG-B6605</td>
<td class="dddefault">31-AUG-2026 - 05-DEC-2026</td>
</tr>
<tr>
<td class="dddefault">Tutorial</td>
<td class="dddefault">11:00 am - 11:50 am</td>
<td class="dddefault">F</td>
<td class="dddefault">YEUNG-B5309</td>
<td class="dddefault">07-SEP-2026 - 04-DEC-2026</td>
</tr>
</table>
</td>
<td class="dddefault">3</td>
<td class="dddefault"><span class="blue">B+</span></td>
<td class="dddefault">9.90</td>
<td class="dddefault">Registered</td>
</tr>
<tr>
<td class="ddlabel">MA1200</td>
<td class="dddefault">Calculus and Basic Linear Algebra I</td>
<td class="dddefault">3</td>
<td class="dddefault"><span class="orange">C</span></td>
<td class="dddefault">6.00</td>
<td class="dddefault">Registered</td>
</tr>
<tr>
<td class="ddlabel">GE1401</td>
<td class="dddefault">University English</td>
<td class="dddefault">3</td>
<td class="dddefault"><span class="red">F</span></td>
<td class="dddefault">0.00</td>
<td class="dddefault">Repeat Required</td>
</tr>
<tr>
<td class="ddseparator" colspan="6"><hr /></td>
</tr>
<tr>
<td class="dddefault" colspan="6"><span class="red">red</span> <span class="blue">blue</span> <span class="green">green</span> <span class="orange">orange</span> <span class="magenta">magenta</span> <span class="yellow">yellow</span></td>
</tr>
</table>

<table class="bordertable" summary="This table lists service indicators held on the student record.">
<caption class="captiontext">Service Indicators</caption>
<tr>
<th class="dbheader" scope="col">Hold</th>
<th class="dbheader" scope="col">Originator</th>
<th class="dbheader" scope="col">From</th>
<th class="dbheader" scope="col">To</th>
<th class="dbheader" scope="col">Amount</th>
</tr>
<tr>
<td class="dbdefault">Library Fine</td>
<td class="dbdefault">Library</td>
<td class="dbdefault">12-JAN-2026</td>
<td class="dbdefault">&nbsp;</td>
<td class="dbdefault">120.00</td>
</tr>
<tr>
<td class="dbdefault">Outstanding Tuition Fee</td>
<td class="dbdefault">Finance Office</td>
<td class="dbdefault">03-SEP-2026</td>
<td class="dbdefault">&nbsp;</td>
<td class="dbdefault">17,500.00</td>
</tr>
</table>

<table class="ntdefault" summary="This layout table displays the student's programme record.">
<tr>
<td class="ntlabel">Student Name</td>
<td class="ntdefault">CHAN Tai Man</td>
</tr>
<tr>
<td class="ntlabel">Programme</td>
<td class="ntdefault">BSc Computer Science</td>
</tr>
<tr>
<td class="ntlabel">Term</td>
<td class="ntdefault">Semester A 2026/27</td>
</tr>
<tr>
<td class="ntlabel">Level</td>
<td class="ntdefault">Bachelor</td>
</tr>
<tr>
<td class="ntlabel">College</td>
<td class="ntdefault">College of Computing</td>
</tr>
</table>

<p><input type="submit" value="Submit" /></p>
<p><input type="submit" value="View Degree Progress Report" /></p>
<p><input type="submit" class="cityu_button_100" value="View Detail" /></p>
<p><input type="text" class="search_textbox" name="search_textbox" size="30" />
<input type="submit" class="search_button" value="Search" /></p>

<p>AIMS really uses <code>cityu_button_100</code> for short, equal-width labels only:
Banner hard-codes <code>width: 100px</code> on it and the theme deliberately keeps that
width, so a long label such as the one on the unclassed button above would clip
there. Both the fixed-width and auto-width cases are shown.</p>"""


# --------------------------------------------------------------------------
# Fixture 4 -- message / notice styles
#
# AIMS uses message styles in two distinct shapes and the harness must cover
# both, because they land in different places in the cascade:
#   (a) wrapped in an info callout -- div.infotextdiv > table.infotexttable >
#       td.indefault > span, and
#   (b) bare, as a direct child of div.body sitting between two <p> elements.
# Showing every message inside a callout makes an error look like an info box
# and hides whether the bare case is styled at all.
# --------------------------------------------------------------------------

FIXTURE_4 = """\
<p>Shape (a) -- messages inside the real info callout wrapper:</p>

<div class="infotextdiv">
<table class="infotexttable">
<tr>
<td class="indefault"><span class="infotext"> Please review the notices below before you continue. Fields marked with an asterisk are mandatory.</span></td>
</tr>
</table>
</div>

<div class="infotextdiv">
<table class="infotexttable">
<tr>
<td class="indefault"><span class="errortext">Error: Invalid ID number entered.</span></td>
</tr>
</table>
</div>

<div class="infotextdiv">
<table class="infotexttable">
<tr>
<td class="indefault"><span class="warningtext">Warning: Your registration appointment has not yet opened.</span></td>
</tr>
</table>
</div>

<p>Shape (b) -- bare, as direct children of div.body between paragraphs:</p>

<p>Your registration appointment begins on 12-AUG-2026 at 09:30.</p>
<span class="errortext">Error: You are not permitted to register for this course at this time.</span>
<p>Please return to the main menu and try again later.</p>
<span class="warningtext">Warning: Your mailing address has not been verified since 2024.</span>
<p>Programme and term information shown on this page is current as of today.</p>

<p><span class="fielderrortext">Invalid value: expected a term code of the form YYYYTT.</span></p>
<p><span class="fieldrequiredtext">This field is required and must be completed.</span></p>
<p><span class="requiredmsgtext">* Denotes a required field.</span></p>
<p class="multipagemsgtext">This is page 1 of 3. Use the navigation buttons below to move between pages.</p>

<table class="hwgksphb_privacy" summary="This table displays the personal information collection statement.">
<tr>
<td>Personal Information Collection Statement: the personal data provided by you will be used by the University for the purposes stated in the Personal Information Collection Statement available at the AIMS login page, and may be disclosed to the parties described therein. You have the right to request access to and correction of your personal data by contacting the IT Service Desk.</td>
</tr>
</table>

<p><span class="releasetext">Release: 8.11</span></p>"""


# --------------------------------------------------------------------------
# Fixture 5 -- legacy popup styling, shown inside a normal AIMS page shell
#
# NOTE: the real /cityu/pics.htm has NO .cityubar_outer and no div.body, which
# is precisely the case the extension's `body:not(:has(.cityubar_outer))` rule
# targets -- and that rule can never fire here, because fixture 1 in this page
# legitimately has .cityubar_outer. The bare, faithful version of this page
# lives in preview-bare.html, which is generated alongside this one.
# --------------------------------------------------------------------------

FIXTURE_5 = """\
<div class="harness-legacy-popup" style="background: #FFFAE8; color: #006666; padding: 16px 20px;">
<font face="Arial, Helvetica">
<center>
<p>City University of Hong Kong</p>
<p>Personal Information Collection Statements (PICS)</p>
</center>
<p>Your personal data are collected for the purposes directly related to the
admission, registration and administration of your studies at the University.</p>
<p>
<a href="#pics-purpose" style="color: #006666;">Purpose of Collection</a> |
<a href="#pics-use" style="color: #006666;">Use of Personal Data</a> |
<a href="#pics-access" style="color: #006666;">Access and Correction</a>
</p>
<p>Enquiries: IT Service Desk, +852 3442-8340.</p>
</font>
</div>"""


# --------------------------------------------------------------------------
# The AIMS page shell that every content fixture must sit inside
#
# div.body is the single criterion that separates AIMS page CONTENT from page
# CHROME (tab strip, title block, footer). The extension scopes its whole
# data-sheet treatment to `div.body`, so a fixture without this wrapper never
# exercises the design at all.
# --------------------------------------------------------------------------

PAGE_SHELL = """\
<div class="pagetitlediv">
<table class="plaintable" summary="This table displays title and static header displays." width="100%">
<tbody><tr>
<td class="pldefault">
<h2>@@TITLE@@</h2>
</td>
<td class="pldefault">
&nbsp;
</td>
<td class="pldefault">
<div class="staticheaders">@@STATIC@@</div>
</td>
</tr>
<tr>
<td class="bg3" width="100%" colspan="3"><img src="vendor/wtlgifs/web_transparent.gif" alt="Transparent Image" class="headerImg" title="Transparent Image" name="web_transparent" hspace="0" vspace="0" border="0" height="3" width="10"></td>
</tr>
</tbody></table>
<a name="main_content"></a>
</div>
<div class="body">
@@CONTENT@@
</div>"""


def aims_page(title: str, static_header: str, content: str) -> str:
    """Wrap fixture content in the real AIMS title block + ``div.body``."""
    return (
        PAGE_SHELL
        .replace("@@TITLE@@", title)
        .replace("@@STATIC@@", static_header)
        .replace("@@CONTENT@@", content)
    )


# --------------------------------------------------------------------------
# Harness chrome -- not part of the extension
# --------------------------------------------------------------------------

#: Local custom properties for the harness chrome. Named --harness-* so they
#: can never collide with the extension's tokens.
CHROME_TOKENS_CSS = """\
:root {
  --harness-bg: #F6F5F7;
  --harness-ink: #17161A;
  --harness-muted: #6C6A75;
  --harness-hairline: #D9D6DF;
  --harness-accent: #A50B5E;
}
html[data-reaims-theme="dark"] {
  --harness-bg: #131216;
  --harness-ink: #EDEBF1;
  --harness-muted: #9A97A6;
  --harness-hairline: #2C2A34;
  --harness-accent: #C0337A;
}
/* "follow OS" is the state with no data-reaims-theme attribute at all, so the
   dark chrome must key off the media query unless light was explicitly forced. */
@media (prefers-color-scheme: dark) {
  html:not([data-reaims-theme="light"]) {
    --harness-bg: #131216;
    --harness-ink: #EDEBF1;
    --harness-muted: #9A97A6;
    --harness-hairline: #2C2A34;
    --harness-accent: #C0337A;
  }
}
"""


READOUT_CSS = """\
#harness-theme-readout {
  position: fixed;
  right: 12px;
  bottom: 12px;
  z-index: 2147483000;
  padding: 6px 10px;
  border-radius: 6px;
  background: rgba(23, 22, 26, 0.88);
  color: #FFFFFF;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
  line-height: 1.4;
  white-space: nowrap;
  pointer-events: none;
}
html[data-reaims-theme="dark"] #harness-theme-readout {
  background: rgba(237, 235, 241, 0.92);
  color: #17161A;
}
@media (prefers-color-scheme: dark) {
  html:not([data-reaims-theme="light"]) #harness-theme-readout {
    background: rgba(237, 235, 241, 0.92);
    color: #17161A;
  }
}
"""


#: Shown only when the vendor preflight fails. Fixed to the top so it cannot be
#: scrolled past, and so it costs the bare page no layout fidelity.
VENDOR_BANNER_CSS = """\
.harness-vendor-warning {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 2147483001;
  margin: 0;
  padding: 10px 20px;
  background: #B3261E;
  color: #FFFFFF;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.5;
}
.harness-vendor-warning[hidden] {
  display: none;
}
"""


#: Only preview.html gets the page framing -- preview-bare.html must keep its
#: faithful <body bgcolor=...> presentation.
PAGE_FRAMING_CSS = """\
body.harness-body {
  margin: 0;
  padding: 0 0 80px;
  background: var(--harness-bg);
  color: var(--harness-ink);
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-size: 14px;
  line-height: 1.45;
}

.harness-page-header {
  padding: 20px 24px 14px;
  border-bottom: 1px solid var(--harness-hairline);
}
.harness-page-header h1 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.01em;
}
.harness-page-header p {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--harness-muted);
}
.harness-page-header code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
}

.harness-section {
  margin-top: 26px;
  padding-top: 4px;
  border-top: 1px dashed var(--harness-hairline);
}
.harness-section:first-of-type {
  margin-top: 0;
  border-top: 0;
}

/* The section label lives OUTSIDE the AIMS page shell on purpose, so it can
   never be mistaken for AIMS page content. */
.harness-label {
  margin: 0;
  padding: 8px 24px 8px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--harness-accent);
}
.harness-label small {
  display: block;
  margin-top: 3px;
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 0.01em;
  text-transform: none;
  color: var(--harness-muted);
}

.harness-fixture {
  margin: 0 24px 26px;
  outline: 1px dashed var(--harness-hairline);
}
"""


HARNESS_SCRIPT = """\
/* preview harness chrome -- not part of the extension.
   Reads ?theme= from the URL and mirrors the extension's real semantics:
   "light" / "dark" set html[data-reaims-theme]; anything else (absent or
   invalid) sets NO attribute at all, because "follow the OS" must be a real,
   independently testable state rather than a third attribute value. */
(function () {
  "use strict";

  var root = document.documentElement;
  var requested = (new URLSearchParams(window.location.search).get("theme") || "").toLowerCase();
  var forced = (requested === "light" || requested === "dark") ? requested : null;

  if (forced) {
    root.dataset.reaimsTheme = forced;
  }
  /* Read by screenshot tooling. "auto" == no data-reaims-theme attribute. */
  root.dataset.themeState = forced || "auto";

  function paint() {
    var out = document.getElementById("harness-theme-readout");
    if (!out) { return; }
    var resolved = forced;
    if (!resolved) {
      resolved = window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark (from OS)"
        : "light (from OS)";
    }
    out.textContent =
      "?theme=" + (requested || "(none)") +
      "  data-reaims-theme=" + (forced || "(absent)") +
      "  resolved: " + resolved;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", paint);
  } else {
    paint();
  }

  var scheme = window.matchMedia("(prefers-color-scheme: dark)");
  if (scheme.addEventListener) { scheme.addEventListener("change", paint); }

  /* ---------------------------------------------------------------------
     Fail loud when Banner's stylesheet did not load.

     vendor/ is gitignored, fetched by tools/preview/fetch_vendor.py. If it is
     missing this page still renders and still looks plausible -- while testing
     nothing, because the inverted cascade is not being reproduced. A silent,
     plausible-looking preview is the worst outcome here, so raise a banner.

     HOW WE DETECT IT, and why this script sits BEFORE the <link> tags.

     CSSOM is useless for this over file://. Measured in this repo: a <link>
     pointing at a file that does not exist still gets a non-null .sheet, still
     appears in document.styleSheets, and reading .cssRules throws
     SecurityError for missing and present sheets alike (a file:// page has an
     opaque origin). So the obvious "scan document.styleSheets for the href"
     check cannot tell them apart -- it reports the sheet is there either way.

     Events are the only signal that discriminates, and they are asymmetric:
     measured, a failed <link> fires "error" which DOES reach a capture-phase
     listener on window, while a successful link's "load" does NOT. So we key
     on the failure signal: no error means it loaded.

     That listener has to be registered before the <link> tags are parsed or
     the error can be missed, which is why this whole script is emitted ahead
     of the stylesheet links rather than after them. Do not move it down.
     --------------------------------------------------------------------- */
  var VENDOR_CSS = "web_defaultapp.css";
  var vendorLoadFailed = false;

  window.addEventListener("error", function (e) {
    var t = e.target;
    if (t && t.tagName === "LINK" && (t.href || "").slice(-VENDOR_CSS.length) === VENDOR_CSS) {
      vendorLoadFailed = true;
    }
  }, true);

  function checkVendor() {
    /* Two ways to be broken: the stylesheet failed to load, or the <link> is
       not in the document at all (someone deleted it). */
    var linkPresent = !!document.querySelector('link[href$="' + VENDOR_CSS + '"]');
    var missing = vendorLoadFailed || !linkPresent;
    root.dataset.vendorState = missing ? "missing" : "ok";
    if (!missing) { return; }

    var el = document.getElementById("harness-vendor-warning");
    if (!el) { return; }
    el.textContent =
      "CASCADE CHECK INACTIVE — vendor/css/web_defaultapp.css did not load. " +
      "This preview is NOT validating that our rules beat Banner's. " +
      "Run: python tools/preview/fetch_vendor.py";
    el.hidden = false;
  }

  function scheduleVendorCheck() {
    window.setTimeout(checkVendor, 400);
  }
  if (document.readyState === "complete") { scheduleVendorCheck(); }
  else { window.addEventListener("load", scheduleVendorCheck); }
})();
"""


# --------------------------------------------------------------------------
# Stylesheet block
# --------------------------------------------------------------------------

CASCADE_WARNING = """\
<!--
  ============================================================================
  THE CASCADE ORDER BELOW IS DELIBERATELY INVERTED -- DO NOT "FIX" IT.
  ============================================================================

  The extension's 8 stylesheets are linked FIRST. Banner's own page stylesheet
  (vendor/css/web_defaultapp.css) is linked LAST.

  This looks backwards, but it is the entire point of the harness. On the live
  site our CSS is injected via content_scripts[].css, and Chrome applies
  injected content-script CSS BEFORE the page's own <link> elements. Banner's
  stylesheet therefore wins every equal-specificity source-order tie -- which
  is exactly why every rule in src/styles/ carries !important.

  Link Banner's stylesheet first and our rules will appear to win when on the
  real site they do not. The harness would keep rendering, keep looking fine,
  and quietly stop testing anything. That is the failure mode to avoid.
-->"""


def stylesheet_block() -> str:
    """Return the full <link> block, extension CSS first, Banner CSS last."""
    lines = [CASCADE_WARNING]
    lines.append("<!-- The extension's 8 stylesheets, in their exact cascade order. -->")
    for href in STYLESHEETS:
        lines.append(f'<link rel="stylesheet" href="{href}" />')
    lines.append("")
    lines.append(
        "<!-- Banner's real page stylesheet. It MUST stay last: it stands in "
        "for the page's own CSS, which\n"
        "     lands after our injected content-script CSS in the real browser. "
        "See the warning above. -->"
    )
    lines.append(f'<link rel="stylesheet" href="{BANNER_STYLESHEET}" />')
    return "\n".join(lines)


# --------------------------------------------------------------------------
# preview.html
# --------------------------------------------------------------------------

PREVIEW_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>ReAIMS preview harness — Banner 8.x Self-Service fixtures</title>
<!--
  GENERATED FILE -- do not edit by hand.
  Source of truth: tools/preview/build_preview.py
  Regenerate with: python tools/preview/build_preview.py
-->
<!--
  The harness script is emitted BEFORE the stylesheet links on purpose: it
  installs a capture-phase error listener that cannot be registered late.
  See the comment inside it. Do not move it below the <link> tags.
-->
<script>
@@SCRIPT@@
</script>
@@LINKS@@
<!--
  preview harness chrome -- not part of the extension.

  PREREQUISITE: run `python tools/preview/fetch_vendor.py` before opening this
  page. tools/preview/vendor/ holds third-party material (AIMS's real
  stylesheet, CityU/Apple/Google brand images) that this public repo does not
  redistribute, so it is gitignored and fetched on demand.

  Without it this page still opens and still looks plausible -- but the cascade
  check is dead, which is the one thing the harness exists to do. So rather
  than degrading quietly, the script below probes whether Banner's stylesheet
  actually loaded and raises a red banner across the top of the page if it did
  not. tools/preview/build_preview.py prints the same warning to stderr at
  build time.
-->
<style>
@@STYLE@@
</style>
</head>
<body class="harness-body">

<div id="harness-vendor-warning" class="harness-vendor-warning" role="alert" hidden></div>

<header class="harness-page-header">
<h1>ReAIMS preview harness</h1>
<p>Static stand-in for CityU AIMS (Ellucian/SunGard Banner 8.x Self-Service). Open over <code>file://</code> with no server and no extension. Append <code>?theme=light</code> or <code>?theme=dark</code>; with no valid parameter <code>data-reaims-theme</code> is absent, which is the "follow the OS" state.</p>
<p>Cascade order is deliberately inverted: our 8 stylesheets load <strong>before</strong> Banner's <code>web_defaultapp.css</code>, reproducing how Chrome applies injected content-script CSS ahead of the page's own <code>&lt;link&gt;</code> elements. Do not "correct" it.</p>
<p>Requires <code>python tools/preview/fetch_vendor.py</code> to have been run: <code>vendor/</code> is third-party material and is gitignored. If Banner's stylesheet is missing, a red banner appears at the top of this page &mdash; without it the cascade check is not happening.</p>
</header>

<main class="harness-stack">

<section class="harness-section" id="fixture-1">
<h2 class="harness-label">Fixture 1 &mdash; real main menu page<small>Verbatim body of a captured AIMS page (<code>source code.html</code>). Only its &lt;script&gt; blocks were removed; the Google analytics tag and the session-timeout poller must not run in this harness. Asset paths are repointed at <code>tools/preview/vendor/</code> so the brand band and bullets render.</small></h2>
<div class="harness-fixture">
@@FIXTURE_1@@
</div>
</section>

<section class="harness-section" id="fixture-2">
<h2 class="harness-label">Fixture 2 &mdash; real data-entry form<small>Captured live from the catalog page, verbatim, inside a real AIMS title block and <code>div.body</code>.</small></h2>
<div class="harness-fixture">
@@FIXTURE_2@@
</div>
</section>

<section class="harness-section" id="fixture-3">
<h2 class="harness-label">Fixture 3 &mdash; data tables<small>Datadisplay, bordered and nested-table patterns, the ntdefault family, buttons and search controls, plus Banner's bare colour utility classes.</small></h2>
<div class="harness-fixture">
@@FIXTURE_3@@
</div>
</section>

<section class="harness-section" id="fixture-4">
<h2 class="harness-label">Fixture 4 &mdash; message and notice styles<small>Shown in both real shapes: inside the info callout wrapper, and bare as direct children of <code>div.body</code>. Error, warning, field error, required and release text, multi-page text, and the yellow PICS privacy table.</small></h2>
<div class="harness-fixture">
@@FIXTURE_4@@
</div>
</section>

<section class="harness-section" id="fixture-5">
<h2 class="harness-label">Fixture 5 &mdash; legacy popup styling inside an AIMS page<small>Stands in for <code>/cityu/pics.htm</code>, which links no stylesheet at all and paints itself with HTML presentational attributes. Its <code>link</code>, <code>vlink</code> and <code>alink</code> were all <code>#006666</code>. The <em>bare</em> version of that page &mdash; no <code>.cityubar_outer</code>, so the extension's bare-page rule can actually fire &mdash; is <code>preview-bare.html</code>.</small></h2>
<div class="harness-fixture">
@@FIXTURE_5@@
</div>
</section>

</main>

<div id="harness-theme-readout" aria-hidden="true"></div>

</body>
</html>
"""


# --------------------------------------------------------------------------
# preview-bare.html
# --------------------------------------------------------------------------

BARE_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>ReAIMS preview harness — bare legacy popup (/cityu/pics.htm)</title>
<!--
  GENERATED FILE -- do not edit by hand.
  Source of truth: tools/preview/build_preview.py
  Regenerate with: python tools/preview/build_preview.py
-->
<!--
  The harness script is emitted BEFORE the stylesheet links on purpose: it
  installs a capture-phase error listener that cannot be registered late.
  See the comment inside it. Do not move it below the <link> tags.
-->
<script>
@@SCRIPT@@
</script>
@@LINKS@@
<!--
  preview harness chrome -- not part of the extension.

  PREREQUISITE: run `python tools/preview/fetch_vendor.py` before opening this
  page. tools/preview/vendor/ holds third-party material (AIMS's real
  stylesheet, CityU/Apple/Google brand images) that this public repo does not
  redistribute, so it is gitignored and fetched on demand.

  Without it this page still opens and still looks plausible -- but the cascade
  check is dead, which is the one thing the harness exists to do. So rather
  than degrading quietly, the script below probes whether Banner's stylesheet
  actually loaded and raises a red banner across the top of the page if it did
  not. tools/preview/build_preview.py prints the same warning to stderr at
  build time.
-->
<style>
@@STYLE@@
</style>
</head>
<!--
  Faithful reproduction of CityU's stylesheet-less legacy popup /cityu/pics.htm:
  presentational attributes on <body> instead of any CSS.

  This page exists separately from preview.html for one reason. The extension
  carries a rule keyed on `body:not(:has(.cityubar_outer))` that gives
  stylesheet-less legacy popups their own reading measure. In preview.html that
  rule can never fire, because fixture 1 legitimately contains the CityU bar.
  Here it can, because the page has no CityU bar wrapper at all.

  The class name above appears ONLY inside this comment -- a grep for
  cityubar_outer in this file returns comment text, not markup. No element on
  this page carries that class. Verify with:

      chrome --headless=new --dump-dom preview-bare.html | grep cityubar_outer

  which should print nothing at all.

  The <body> keeps its real bgcolor/text/link attributes and deliberately does
  NOT carry the harness's body class, so the page's own presentation is not
  overridden by harness chrome.
-->
<body text="#006666" bgcolor="#FFFAE8" link="#006666" vlink="#006666" alink="#006666">
<div id="harness-vendor-warning" class="harness-vendor-warning" role="alert" hidden></div>
<font face="Arial, Helvetica">
<center>
<p>City University of Hong Kong
<p>Personal Information Collection Statements (PICS)
</center>

<p>The personal data provided by you will be used by the University for the
purposes directly related to the admission, registration, teaching and
administration of your studies, and for the provision of student services.</p>

<p>Your personal data may be transferred to and accessed by other offices and
departments of the University, and to external bodies where such transfer is
required or permitted by law. The University will not disclose your personal
data to any third party for direct marketing purposes without your consent.</p>

<p>You have the right to request access to and correction of your personal data
held by the University. Requests should be made in writing to the IT Service
Desk. A fee may be charged for the processing of a data access request.</p>

<p>
<a href="#purpose">Purpose of Collection</a> |
<a href="#use">Use of Personal Data</a> |
<a href="#access">Access and Correction</a>
</p>

<p>Enquiries: IT Service Desk, +852 3442-8340<br>
Email: <a href="mailto:it.servicedesk@cityu.edu.hk">it.servicedesk@cityu.edu.hk</a></p>
</font>

<div id="harness-theme-readout" aria-hidden="true"></div>
</body>
</html>
"""


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------

def render_preview() -> str:
    """Build preview.html."""
    fixtures = {
        "@@FIXTURE_1@@": vendorise(load_fixture_1()),
        # Fixtures 2-5 get the real AIMS title block + div.body wrapper: the
        # extension scopes its tabular treatment to div.body, so without this
        # they would not exercise the design at all.
        "@@FIXTURE_2@@": aims_page(
            "Search by Term",
            "Term: 2026/27 Semester A",
            vendorise(FIXTURE_2),
        ),
        "@@FIXTURE_3@@": aims_page(
            "Student Records",
            "Term: 2026/27 Semester A",
            vendorise(FIXTURE_3),
        ),
        "@@FIXTURE_4@@": aims_page(
            "Notices and Messages",
            "Term: 2026/27 Semester A",
            vendorise(FIXTURE_4),
        ),
        "@@FIXTURE_5@@": aims_page(
            "Personal Information Collection Statement",
            "CityU AIMS",
            vendorise(FIXTURE_5),
        ),
    }

    page = PREVIEW_TEMPLATE
    substitutions = {
        "@@LINKS@@": stylesheet_block(),
        "@@STYLE@@": (
            CHROME_TOKENS_CSS + "\n" + PAGE_FRAMING_CSS + "\n"
            + READOUT_CSS + "\n" + VENDOR_BANNER_CSS
        ).rstrip("\n"),
        "@@SCRIPT@@": HARNESS_SCRIPT.rstrip("\n"),
    }
    substitutions.update(fixtures)
    for token, value in substitutions.items():
        page = page.replace(token, value)
    return _check(page)


def render_bare() -> str:
    """Build preview-bare.html."""
    page = BARE_TEMPLATE
    for token, value in (
        ("@@LINKS@@", stylesheet_block()),
        ("@@STYLE@@", (
            CHROME_TOKENS_CSS + "\n" + READOUT_CSS + "\n" + VENDOR_BANNER_CSS
        ).rstrip("\n")),
        ("@@SCRIPT@@", HARNESS_SCRIPT.rstrip("\n")),
    ):
        page = page.replace(token, value)
    return _check(page)


def _check(page: str) -> str:
    if "@@" in page:
        leftover = sorted(set(re.findall(r"@@[A-Z_0-9]+@@", page)))
        raise SystemExit(f"unsubstituted template tokens: {leftover}")
    return page


def _write(path: Path, page: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # newline="" keeps our LF line endings from being rewritten to CRLF on
    # Windows, which is what makes the output byte-identical across runs.
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(page)
    print(f"wrote {path} ({len(page.encode('utf-8')):,} bytes, {page.count(chr(10))} lines)")


def main(argv: list[str]) -> int:
    pages = ((OUT_PREVIEW, render_preview()), (OUT_BARE, render_bare()))

    # Preflight before anything else: with the vendored stylesheet missing, the
    # pages still build and still look fine while testing nothing. Say so loudly.
    missing = find_missing_vendor_assets(*(page for _, page in pages))
    if missing:
        warn_missing_vendor(missing)

    if "--check" in argv:
        stale = []
        for path, page in pages:
            current = path.read_text(encoding="utf-8") if path.exists() else None
            if current != page:
                stale.append(path)
                print(f"STALE: {path} differs from the templates", file=sys.stderr)
        if stale:
            return 1
        print("up to date: both pages match the templates")
        return 0

    for path, page in pages:
        _write(path, page)

    print(f"  fixture 1 sourced from {SOURCE_PAGE}")
    print(f"  {len(STYLESHEETS)} extension stylesheets + Banner's, in inverted cascade order")
    if missing:
        print("  vendor preflight FAILED -- cascade check inactive (see warning above)")
    else:
        print("  vendor preflight ok -- cascade check active")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
