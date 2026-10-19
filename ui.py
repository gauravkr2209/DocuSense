"""Styling and display helpers for the DocuSense interface."""
import html
import re
from typing import Dict, List, Sequence, Tuple

from summarize import SECTIONS

SECTION_META = {
    "Context": ("🧭", "context"),
    "Objectives": ("🎯", "objectives"),
    "Methodology": ("🛠️", "methodology"),
    "Results": ("📊", "results"),
    "Limitations": ("⚠️", "limitations"),
    "Suggested Viva Questions": ("🎓", "viva"),
}
WIDE_SECTIONS = {"Limitations", "Suggested Viva Questions"}

STAGES = {
    "search": ("🔍", "Searching the document"),
    "write": ("✍️", "Writing the answer"),
}

LIGHT = {
    "bg": "#F4F5FB",
    "surface": "#FFFFFF",
    "surface2": "#F0F2F9",
    "text": "#1F2937",
    "muted": "#6B7280",
    "border": "rgba(15, 23, 42, 0.10)",
    "primary": "#4F46E5",
    "primary_soft": "rgba(79, 70, 229, 0.12)",
    "shadow": "0 4px 18px rgba(15, 23, 42, 0.06)",
    "hero_a": "#4F46E5",
    "hero_b": "#7C3AED",
}
DARK = {
    "bg": "#0E1117",
    "surface": "#171B26",
    "surface2": "#1F2433",
    "text": "#E6E8EF",
    "muted": "#9AA3B5",
    "border": "rgba(255, 255, 255, 0.10)",
    "primary": "#8B7CFF",
    "primary_soft": "rgba(139, 124, 255, 0.18)",
    "shadow": "0 4px 18px rgba(0, 0, 0, 0.35)",
    "hero_a": "#3730A3",
    "hero_b": "#6D28D9",
}

BASE_CSS = """
#MainMenu, footer, .stDeployButton, .stAppDeployButton {visibility: hidden;}
[data-testid="stHeader"] {background: transparent;}
.stApp {background: var(--ds-bg); color: var(--ds-text);}
.block-container {padding-top: 1.2rem; padding-bottom: 6rem; max-width: 1080px;}
[data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {background: var(--ds-surface);}
[data-testid="stSidebar"] {border-right: 1px solid var(--ds-border);}
.stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4, [data-testid="stWidgetLabel"] p {color: var(--ds-text);}
[data-testid="stCaptionContainer"] {color: var(--ds-muted);}
[data-baseweb="input"] > div, [data-baseweb="base-input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] {background: var(--ds-surface2) !important; border-color: var(--ds-border) !important;}
input, textarea {color: var(--ds-text) !important; -webkit-text-fill-color: var(--ds-text);}
[data-baseweb="select"] * {color: var(--ds-text);}
[data-baseweb="popover"] [data-baseweb="menu"], [data-baseweb="popover"] ul {background: var(--ds-surface) !important;}
[data-baseweb="popover"] li {color: var(--ds-text) !important;}
[data-testid="stFileUploaderDropzone"] {background: var(--ds-surface2); border: 1px dashed var(--ds-border);}
[data-testid="stFileUploaderDropzone"] small, [data-testid="stFileUploaderDropzone"] span {color: var(--ds-muted) !important;}
[data-testid="stForm"] {border: 1px solid var(--ds-border); border-radius: 14px; background: transparent;}
[data-testid="stExpander"] {background: var(--ds-surface); border: 1px solid var(--ds-border); border-radius: 12px;}
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * {color: var(--ds-text) !important;}
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {border-radius: 10px; font-weight: 600; background: var(--ds-surface); color: var(--ds-text); border: 1px solid var(--ds-border);}
button[kind="primary"], button[kind="primaryFormSubmit"], [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {background: var(--ds-primary) !important; border-color: var(--ds-primary) !important; color: #fff !important;}
button[kind="primary"] p, button[kind="primaryFormSubmit"] p, [data-testid="stBaseButton-primary"] p, [data-testid="stBaseButton-primaryFormSubmit"] p {color: #fff !important;}
.ds-topbar {display: flex; align-items: center; justify-content: space-between; gap: 16px; background: linear-gradient(135deg, var(--ds-hero-a), var(--ds-hero-b)); border-radius: 16px; padding: 14px 22px; box-shadow: var(--ds-shadow); margin-bottom: 14px;}
.ds-brand {color: #fff; font-size: 1.35rem; font-weight: 800; letter-spacing: -0.01em;}
.ds-tag {color: rgba(255, 255, 255, 0.85); font-size: 0.85rem; margin-top: 2px;}
.ds-pill {display: inline-flex; align-items: center; gap: 7px; padding: 5px 13px; border-radius: 999px; font-size: 0.8rem; font-weight: 600; background: rgba(255, 255, 255, 0.18); color: #fff; white-space: nowrap;}
.ds-dot {width: 8px; height: 8px; border-radius: 50%; display: inline-block;}
.ds-ok .ds-dot {background: #34D399; box-shadow: 0 0 0 3px rgba(52, 211, 153, 0.3);}
.ds-bad .ds-dot {background: #F87171; box-shadow: 0 0 0 3px rgba(248, 113, 113, 0.3);}
.ds-docbar {margin: 2px 0 4px 0;}
.ds-doc-title {font-size: 1.3rem; font-weight: 700; color: var(--ds-text); margin-bottom: 6px;}
.ds-meta {display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;}
.ds-meta-item {background: var(--ds-surface); border: 1px solid var(--ds-border); border-radius: 999px; padding: 4px 12px; font-size: 0.8rem; color: var(--ds-muted); white-space: nowrap; max-width: 100%; overflow: hidden; text-overflow: ellipsis;}
.ds-meta-item b {color: var(--ds-text); font-weight: 600; margin-left: 6px;}
.ds-notice {background: rgba(245, 158, 11, 0.12); border-left: 3px solid #F59E0B; border-radius: 8px; padding: 6px 12px; font-size: 0.8rem; color: var(--ds-text); margin: 6px 0 12px 0;}
div[role="radiogroup"] {gap: 8px;}
label[data-baseweb="radio"] {background: var(--ds-surface); border: 1px solid var(--ds-border); border-radius: 999px; padding: 6px 18px; margin-right: 0 !important;}
label[data-baseweb="radio"] > div:first-child {display: none;}
label[data-baseweb="radio"]:has(input:checked) {background: var(--ds-primary); border-color: var(--ds-primary);}
label[data-baseweb="radio"]:has(input:checked) * {color: #fff !important;}
.ds-grid {display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; align-items: stretch; margin-top: 6px;}
.ds-card {background: var(--ds-surface); border: 1px solid var(--ds-border); border-top: 3px solid var(--ds-accent); border-radius: 14px; padding: 16px 18px; box-shadow: var(--ds-shadow);}
.ds-card.wide {grid-column: 1 / -1;}
.ds-card-head {display: flex; align-items: center; gap: 10px; margin-bottom: 8px;}
.ds-badge {width: 30px; height: 30px; border-radius: 9px; display: flex; align-items: center; justify-content: center; background: var(--ds-accent-soft); font-size: 1rem;}
.ds-card-title {font-weight: 700; font-size: 1rem; color: var(--ds-text);}
.ds-card-body {font-size: 0.93rem; line-height: 1.55; color: var(--ds-text);}
.ds-card-body p {margin: 0 0 8px 0;}
.ds-card-body ol, .ds-card-body ul {margin: 0; padding-left: 1.3rem;}
.ds-card-body li {margin-bottom: 6px;}
.ds-empty {color: var(--ds-muted); font-style: italic;}
.ds-c-context {--ds-accent: #3B82F6; --ds-accent-soft: rgba(59, 130, 246, 0.15);}
.ds-c-objectives {--ds-accent: #8B5CF6; --ds-accent-soft: rgba(139, 92, 246, 0.15);}
.ds-c-methodology {--ds-accent: #14B8A6; --ds-accent-soft: rgba(20, 184, 166, 0.15);}
.ds-c-results {--ds-accent: #22C55E; --ds-accent-soft: rgba(34, 197, 94, 0.15);}
.ds-c-limitations {--ds-accent: #F59E0B; --ds-accent-soft: rgba(245, 158, 11, 0.15);}
.ds-c-viva {--ds-accent: #EC4899; --ds-accent-soft: rgba(236, 72, 153, 0.15);}
.ds-steps {display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-top: 10px;}
.ds-step {background: var(--ds-surface); border: 1px solid var(--ds-border); border-radius: 14px; padding: 18px; box-shadow: var(--ds-shadow);}
.ds-step-n {width: 32px; height: 32px; border-radius: 50%; background: var(--ds-primary-soft); color: var(--ds-primary); font-weight: 800; display: flex; align-items: center; justify-content: center; margin-bottom: 8px;}
.ds-step-t {font-weight: 700; color: var(--ds-text); margin-bottom: 4px;}
.ds-step-d {color: var(--ds-muted); font-size: 0.9rem;}
[data-testid="stChatMessage"] {background: var(--ds-surface); border: 1px solid var(--ds-border); border-radius: 14px; padding: 12px 16px; margin-bottom: 10px; box-shadow: var(--ds-shadow);}
[data-testid="stBottom"], [data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] {background: var(--ds-bg);}
[data-testid="stChatInput"], [data-testid="stChatInput"] > div {background: var(--ds-surface); border-radius: 14px;}
[data-testid="stChatInput"] {border: 1px solid var(--ds-border);}
[data-testid="stChatInput"] textarea {color: var(--ds-text) !important;}
.ds-chip {display: inline-block; padding: 2px 10px; margin: 2px 4px 2px 0; border-radius: 999px; font-size: 0.78rem; background: var(--ds-primary-soft); color: var(--ds-primary);}
.ds-chip-label {font-size: 0.78rem; color: var(--ds-muted); margin-right: 6px;}
.ds-think {display: flex; align-items: center; gap: 10px; color: var(--ds-muted); font-size: 0.92rem;}
.ds-lens {display: inline-block; font-size: 1.2rem; animation: ds-swing 1.2s ease-in-out infinite;}
.ds-dots span {display: inline-block; width: 5px; height: 5px; margin-left: 3px; border-radius: 50%; background: var(--ds-primary); animation: ds-bounce 1.2s infinite ease-in-out;}
.ds-dots span:nth-child(2) {animation-delay: 0.15s;}
.ds-dots span:nth-child(3) {animation-delay: 0.3s;}
@keyframes ds-swing {0%, 100% {transform: rotate(-14deg) scale(1);} 50% {transform: rotate(14deg) scale(1.15);}}
@keyframes ds-bounce {0%, 80%, 100% {opacity: 0.25; transform: translateY(0);} 40% {opacity: 1; transform: translateY(-3px);}}
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"], [data-baseweb="textarea"] > div {background-color: var(--ds-surface2) !important; border-color: var(--ds-border) !important;}
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea, [data-baseweb="input"] input, [data-baseweb="base-input"] input {background-color: transparent !important; color: var(--ds-text) !important; -webkit-text-fill-color: var(--ds-text) !important; caret-color: var(--ds-text);}
input::placeholder, textarea::placeholder {color: var(--ds-muted) !important; -webkit-text-fill-color: var(--ds-muted) !important; opacity: 1;}
input:-webkit-autofill {-webkit-box-shadow: 0 0 0 1000px var(--ds-surface2) inset !important; -webkit-text-fill-color: var(--ds-text) !important;}
[data-testid="stChatInput"] [data-baseweb="textarea"], [data-testid="stChatInput"] [data-baseweb="base-input"], [data-testid="stChatInput"] textarea {background-color: transparent !important;}
[data-testid="stTextInputRootElement"], [data-testid="stTextInputRootElement"] > div, [data-testid="stSidebar"] [data-baseweb="input"], [data-testid="stSidebar"] [data-baseweb="base-input"] {background: var(--ds-surface2) !important; border: 1px solid var(--ds-border) !important;}
[data-testid="stTextInputRootElement"] input, [data-testid="stSidebar"] input {background: transparent !important; color: var(--ds-text) !important; -webkit-text-fill-color: var(--ds-text) !important;}
[data-testid="stSelectbox"], [data-testid="stSelectbox"] div, [data-testid="stSelectbox"] [data-baseweb="select"], [data-testid="stSelectbox"] [data-baseweb="select"] > div, [data-testid="stSelectbox"] [data-baseweb="select"] > div > div, [data-testid="stSidebar"] [data-baseweb="select"], [data-testid="stSidebar"] [data-baseweb="select"] div {background-color: var(--ds-surface2) !important; color: var(--ds-text) !important; -webkit-text-fill-color: var(--ds-text) !important;}
[data-testid="stSelectbox"] [data-baseweb="select"] > div, [data-testid="stSidebar"] [data-baseweb="select"] > div {border: 1px solid var(--ds-border) !important; border-radius: 10px;}
[data-testid="stSelectbox"] input, [data-testid="stSelectbox"] span, [data-testid="stSelectbox"] p {color: var(--ds-text) !important; -webkit-text-fill-color: var(--ds-text) !important; background-color: transparent !important;}
[data-testid="stSelectbox"] svg {fill: var(--ds-text) !important; color: var(--ds-text) !important;}
div[data-baseweb="popover"], div[data-baseweb="popover"] > div, div[data-baseweb="popover"] ul, div[data-baseweb="popover"] li, div[data-baseweb="popover"] [role="listbox"], div[data-baseweb="popover"] [role="option"], [data-baseweb="menu"], [data-baseweb="menu"] li {background-color: var(--ds-surface) !important; color: var(--ds-text) !important; -webkit-text-fill-color: var(--ds-text) !important;}
div[data-baseweb="popover"] li:hover, div[data-baseweb="popover"] [role="option"]:hover, div[data-baseweb="popover"] [aria-selected="true"], [data-baseweb="menu"] li:hover {background-color: var(--ds-primary-soft) !important;}
[data-testid="stFileUploaderDropzone"] button {background: var(--ds-surface) !important; border: 1px solid var(--ds-border) !important;}
[data-testid="stFileUploaderDropzone"] button, [data-testid="stFileUploaderDropzone"] button * {color: var(--ds-text) !important;}
[data-testid="stProgress"] [role="progressbar"] > div {background-color: var(--ds-surface2) !important;}
[data-testid="stProgress"] [role="progressbar"] > div > div {background-color: var(--ds-primary) !important;}
[data-testid="stRadio"] label > span:first-child, [data-testid="stRadio"] label > div:first-child:not(:last-child), label[data-baseweb="radio"] > span:first-child {display: none !important;}
[data-testid="stRadio"] label {background: var(--ds-surface); border: 1px solid var(--ds-border); border-radius: 999px; padding: 6px 18px !important;}
[data-testid="stRadio"] label:has(input:checked) {background: var(--ds-primary); border-color: var(--ds-primary);}
[data-testid="stRadio"] label:has(input:checked) * {color: #fff !important;}
[data-testid="stRadio"] label p {margin: 0;}
[data-testid="stSelectbox"], [data-testid="stSelectbox"] > div, [data-testid="stSelectbox"] label, [data-testid="stSelectbox"] [data-testid="stWidgetLabel"], [data-testid="stSelectbox"] [data-testid="stWidgetLabel"] * {background-color: transparent !important;}
[data-testid="stSelectbox"] [data-baseweb="select"] > div {padding-left: 4px;}
.ds-info {background: var(--ds-primary-soft); border: 1px solid var(--ds-border); border-left: 4px solid var(--ds-primary); border-radius: 12px; padding: 14px 18px; margin: 4px 0 14px 0; color: var(--ds-text);}
.ds-info-title {font-weight: 700; font-size: 1rem; color: var(--ds-primary); margin-bottom: 8px;}
.ds-info ul {margin: 0; padding-left: 1.2rem;}
.ds-info li {font-size: 0.92rem; line-height: 1.55; margin-bottom: 5px; color: var(--ds-text);}
.ds-info-foot {font-size: 0.82rem; color: var(--ds-muted); margin-top: 8px; font-style: italic;}
[data-testid="stCheckbox"] p, [data-testid="stCheckbox"] label {color: var(--ds-text) !important;}
[data-testid="stSidebar"] {min-width: 310px !important;}
[data-testid="stSidebarHeader"] {height: 2.2rem; padding: 0.4rem 0.8rem 0 0.8rem;}
[data-testid="stSidebarCollapseButton"] button, [data-testid="stSidebarCollapseButton"] svg, [data-testid="stSidebarCollapseButton"] span {color: var(--ds-muted) !important; opacity: 1 !important;}
.ds-sb-brand {display: flex; align-items: center; gap: 12px; padding: 4px 2px 14px 2px; border-bottom: 1px solid var(--ds-border);}
.ds-sb-logo {width: 42px; height: 42px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 1.3rem; background: linear-gradient(135deg, var(--ds-hero-a), var(--ds-hero-b)); box-shadow: var(--ds-shadow);}
.ds-sb-name {font-weight: 800; font-size: 1.15rem; color: var(--ds-text); line-height: 1.1;}
.ds-sb-sub {font-size: 0.75rem; color: var(--ds-muted); margin-top: 2px;}
.ds-sb-label {display: flex; align-items: center; justify-content: space-between; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase; color: var(--ds-muted); margin: 18px 0 6px 2px;}
.ds-sb-count {background: var(--ds-primary-soft); color: var(--ds-primary); border-radius: 999px; padding: 1px 9px; font-size: 0.7rem; letter-spacing: 0;}
.ds-sb-foot {margin-top: 18px; padding-top: 12px; border-top: 1px solid var(--ds-border); font-size: 0.75rem; color: var(--ds-muted); line-height: 1.4;}
[data-testid="stSidebar"] [data-testid="stToggle"] {background: var(--ds-surface2); border: 1px solid var(--ds-border); border-radius: 10px; padding: 8px 12px;}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {font-size: 0.82rem; font-weight: 600;}
[data-testid="stSidebar"] [data-baseweb="input"], [data-testid="stSidebar"] [data-baseweb="base-input"], [data-testid="stSidebar"] [data-baseweb="select"] > div, [data-testid="stSidebar"] [data-testid="stTextInputRootElement"] {border: 1px solid color-mix(in srgb, var(--ds-text) 22%, transparent) !important; border-radius: 10px !important;}
[data-testid="stSidebar"] [data-baseweb="input"]:focus-within, [data-testid="stSidebar"] [data-testid="stTextInputRootElement"]:focus-within, [data-testid="stSidebar"] [data-baseweb="select"]:focus-within > div {border-color: var(--ds-primary) !important; box-shadow: 0 0 0 2px var(--ds-primary-soft) !important; outline: none !important;}
[data-testid="stSidebar"] [data-testid="stForm"] {border: 1px solid var(--ds-border); border-radius: 14px; padding: 14px 14px 10px 14px; background: transparent;}
[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] > button {width: 100%; padding: 0.55rem 0;}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {font-size: 0.85rem;}
@media (max-width: 760px) {.ds-grid, .ds-steps {grid-template-columns: 1fr;}}
"""


def build_css(dark: bool = False) -> str:
    """Return the <style> block for the light or dark theme."""
    t = DARK if dark else LIGHT
    variables = (
        ":root {"
        f"--ds-bg: {t['bg']}; --ds-surface: {t['surface']}; "
        f"--ds-surface2: {t['surface2']}; --ds-text: {t['text']}; "
        f"--ds-muted: {t['muted']}; --ds-border: {t['border']}; "
        f"--ds-primary: {t['primary']}; --ds-primary-soft: {t['primary_soft']}; "
        f"--ds-shadow: {t['shadow']}; --ds-hero-a: {t['hero_a']}; "
        f"--ds-hero-b: {t['hero_b']}; "
        f"color-scheme: {'dark' if dark else 'light'};"
        "}"
    )
    return f"<style>{variables}{BASE_CSS}</style>"


def esc(value: object) -> str:
    """Escape text for HTML. The dollar sign is escaped too, because
    Streamlit's Markdown can mistake pairs of $ for maths."""
    return html.escape(str(value), quote=True).replace("$", "&#36;")


def _inline(text: str) -> str:
    """Escape, then turn **bold** into <strong>."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(text))


def truncate(text: object, limit: int = 34) -> str:
    value = str(text)
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def status_pill(ok: bool) -> str:
    if ok:
        return (
            '<span class="ds-pill ds-ok"><span class="ds-dot"></span>'
            "Ollama running</span>"
        )
    return (
        '<span class="ds-pill ds-bad"><span class="ds-dot"></span>'
        "Ollama not running</span>"
    )


def topbar(title: str, tagline: str, ollama_ok: bool) -> str:
    return (
        '<div class="ds-topbar"><div>'
        f'<div class="ds-brand">📄 {esc(title)}</div>'
        f'<div class="ds-tag">{esc(tagline)}</div></div>'
        f"{status_pill(ollama_ok)}</div>"
    )


def meta_chips(items: Sequence[Tuple[str, object]]) -> str:
    chips = "".join(
        f'<span class="ds-meta-item">{esc(label)}<b>{esc(value)}</b></span>'
        for label, value in items
    )
    return f'<div class="ds-meta">{chips}</div>'


def docbar(title: str, items: Sequence[Tuple[str, object]]) -> str:
    return (
        f'<div class="ds-docbar"><div class="ds-doc-title">{esc(title)}</div>'
        f"{meta_chips(items)}</div>"
    )

INFO_TITLE = "ℹ️ Processing note"
INFO_POINTS = [
    "Best for documents of up to about 10 pages. Longer documents are "
    "summarised from up to 10 evenly spaced parts, so some pages may be "
    "skipped (the summary says so).",
    "A summary takes about 10 minutes, because DocuSense runs a free, "
    "local AI model on this computer. It is saved afterwards, so you "
    "only wait once.",
    "Chat answers take about 30 seconds each and search the whole document.",
]
INFO_FOOT = "We are working on making this faster."


def info_note() -> str:
    """Theme-aware information card shown when the info box is ticked."""
    items = "".join(f"<li>{esc(point)}</li>" for point in INFO_POINTS)
    return (
        '<div class="ds-info">'
        f'<div class="ds-info-title">{esc(INFO_TITLE)}</div>'
        f"<ul>{items}</ul>"
        f'<div class="ds-info-foot">{esc(INFO_FOOT)}</div></div>'
    )
def sidebar_brand() -> str:
    return (
        '<div class="ds-sb-brand"><div class="ds-sb-logo">📄</div><div>'
        '<div class="ds-sb-name">DocuSense</div>'
        '<div class="ds-sb-sub">Document review assistant</div>'
        "</div></div>"
    )


def sidebar_label(text: str, count: object = None) -> str:
    badge = ""
    if count is not None and count != "":
        badge = f'<span class="ds-sb-count">{esc(count)}</span>'
    return f'<div class="ds-sb-label"><span>{esc(text)}</span>{badge}</div>'


def sidebar_footer() -> str:
    return (
        '<div class="ds-sb-foot">🔒 Runs locally. No document leaves '
        "this computer.</div>"
    )

def notice(text: str) -> str:
    return f'<div class="ds-notice">{esc(text)}</div>'


def steps_html(steps: Sequence[Tuple[str, str, str]]) -> str:
    cards = "".join(
        f'<div class="ds-step"><div class="ds-step-n">{esc(number)}</div>'
        f'<div class="ds-step-t">{esc(title)}</div>'
        f'<div class="ds-step-d">{esc(text)}</div></div>'
        for number, title, text in steps
    )
    return f'<div class="ds-steps">{cards}</div>'


def page_chips(pages: Sequence[int], label: str) -> str:
    chips = "".join(f'<span class="ds-chip">p. {esc(p)}</span>' for p in pages)
    return f'<span class="ds-chip-label">{esc(label)}</span>{chips}'


def thinking(stage: str) -> str:
    """Animated 'working' line shown while the answer is being made."""
    icon, text = STAGES.get(stage, ("⏳", "Working"))
    return (
        f'<div class="ds-think"><span class="ds-lens">{icon}</span>'
        f"<span>{esc(text)}</span>"
        '<span class="ds-dots"><span></span><span></span><span></span></span>'
        "</div>"
    )


def is_empty_section(text: str) -> bool:
    """True for the model's 'nothing here' answers."""
    lowered = text.strip().lower()
    return not lowered or lowered.startswith(("not stated", "none stated"))


def body_html(text: str) -> str:
    """Turn plain model text into safe HTML: paragraphs, bullets and
    numbered lists. Everything is escaped first."""
    parts: List[str] = []
    open_tag = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        ordered = re.match(r"^\d+[.)]\s+(.*)$", line)
        bullet = re.match(r"^[-*\u2022]\s+(.*)$", line)
        tag = "ol" if ordered else "ul" if bullet else ""
        if tag != open_tag:
            if open_tag:
                parts.append(f"</{open_tag}>")
            if tag:
                parts.append(f"<{tag}>")
            open_tag = tag
        if tag:
            item = (ordered or bullet).group(1)  # type: ignore[union-attr]
            parts.append(f"<li>{_inline(item)}</li>")
        else:
            parts.append(f"<p>{_inline(line)}</p>")
    if open_tag:
        parts.append(f"</{open_tag}>")
    return "".join(parts)


def card_html(name: str, body: str) -> str:
    icon, slug = SECTION_META[name]
    if is_empty_section(body):
        inner = '<div class="ds-empty">Not stated in the document.</div>'
    else:
        inner = body_html(body)
    wide = " wide" if name in WIDE_SECTIONS else ""
    return (
        f'<div class="ds-card ds-c-{slug}{wide}">'
        f'<div class="ds-card-head"><div class="ds-badge">{icon}</div>'
        f'<div class="ds-card-title">{esc(name)}</div></div>'
        f'<div class="ds-card-body">{inner}</div></div>'
    )


def summary_html(sections: Dict[str, str]) -> str:
    """All summary cards in the fixed section order."""
    cards = "".join(
        card_html(name, sections[name]) for name in SECTIONS if name in sections
    )
    return f'<div class="ds-grid">{cards}</div>'


def split_summary(markdown: str) -> Tuple[str, Dict[str, str], str]:
    """Split a saved summary into (title, sections, note).

    Only the six known headings are treated as sections. Returns an
    empty sections dict if none are found, so the caller can fall back
    to plain Markdown."""
    title, note = "", ""
    current = None
    found: Dict[str, List[str]] = {}
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title = stripped[2:].strip()
            continue
        match = re.match(r"^##\s+(.+?)\s*$", stripped)
        if match and match.group(1) in SECTIONS:
            current = match.group(1)
            found.setdefault(current, [])
            continue
        if stripped.startswith("_Note:") and stripped.endswith("_"):
            note = stripped.strip("_").strip()
            continue
        if current:
            found[current].append(line)
    sections = {
        name: "\n".join(found[name]).strip() for name in SECTIONS if name in found
    }
    return title, sections, note