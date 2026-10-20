"""Streamlit interface for DocuSense (Ollama locally, Gemini when hosted)."""
import os
import re
import urllib.request

import streamlit as st

import config
import providers
import store
import ui
from ingest import IngestionError, ingest_pdf
from qa import DocumentQA, QAError
from summarize import SummaryError, summarize_collection

st.set_page_config(page_title="DocuSense", page_icon="📄", layout="wide")

USER_AVATAR, BOT_AVATAR = "🧑‍🏫", "🤖"
VIEW_SUMMARY, VIEW_CHAT = "📋 Summary", "💬 Chat"
DEMO_NAME = "DocuSense_Demo_Report.pdf"
DEMO_PDF = config.BASE_DIR / "docs" / DEMO_NAME
DEMO_SUMMARY = config.BASE_DIR / "docs" / "demo_summary.md"


# ---------- setup helpers ----------

def load_secrets_into_env() -> None:
    """Copy the key from Streamlit secrets into the environment, where
    providers.py reads it. The key is never displayed."""
    try:
        key = st.secrets.get(providers.KEY_ENV)
    except Exception:
        key = None
    if key and not os.environ.get(providers.KEY_ENV):
        os.environ[providers.KEY_ENV] = str(key)


load_secrets_into_env()


def ollama_running() -> bool:
    """Quick check that the local Ollama server answers."""
    try:
        with urllib.request.urlopen(config.OLLAMA_BASE_URL, timeout=1.5):
            return True
    except Exception:
        return False


def is_ready() -> bool:
    return ollama_running() if providers.is_local() else providers.provider_ready()


def status_label(ok: bool) -> str:
    if providers.is_local():
        return "Ollama running" if ok else "Ollama not running"
    return "Gemini ready" if ok else "Gemini key missing"


def find_indexed(digest: str):
    """A record with the same file fingerprint, indexed by the active provider."""
    for record in store.load_registry():
        if (
            record.get("file_hash") == digest
            and record.get("provider", "ollama") == config.PROVIDER
        ):
            return record
    return None


def ingest_bytes(student: str, title: str, name: str, data: bytes):
    """Save, index and register a PDF. Returns (record, already_indexed)."""
    digest = store.file_sha256(data)
    existing = find_indexed(digest)
    if existing:
        return existing, True

    path = store.UPLOAD_DIR / f"{digest[:8]}_{store.safe_filename(name)}"
    path.write_bytes(data)
    try:
        result = ingest_pdf(str(path))
    except IngestionError:
        path.unlink(missing_ok=True)
        raise
    record = store.make_record(
        student, title, name, digest, result, provider=config.PROVIDER
    )
    store.add_record(record)
    return record, False


def ensure_demo() -> None:
    """Demo mode: index the sample report with the active provider once,
    so visitors can use it without uploading anything."""
    if not config.DEMO_MODE or not providers.provider_ready() or not DEMO_PDF.exists():
        return
    for record in store.load_registry():
        if (
            record.get("source_file") == DEMO_NAME
            and record.get("provider", "ollama") == config.PROVIDER
        ):
            return
    with st.spinner("Preparing the demo document..."):
        try:
            record, _ = ingest_bytes(
                "Demo Student", "DocuSense Demo Report", DEMO_NAME, DEMO_PDF.read_bytes()
            )
        except IngestionError as err:
            st.error(f"The demo could not be prepared: {err}")
            return
        if DEMO_SUMMARY.exists():
            store.save_summary(
                str(record["collection_name"]),
                DEMO_SUMMARY.read_text(encoding="utf-8"),
            )
    st.rerun()


def run_summary(record: dict) -> None:
    """Generate the summary with a progress bar, save it, reload."""
    collection = str(record["collection_name"])
    bar = st.progress(0.0, text="Starting...")

    def on_progress(message: str) -> None:
        match = re.match(r"Reading part (\d+) of (\d+)", message)
        if match:
            done, total = int(match.group(1)) - 1, int(match.group(2))
            bar.progress(done / (total + 1), text=message)
        else:
            bar.progress(0.95, text=message)

    title = str(record.get("project_title") or collection)
    student = str(record.get("student_name") or "")
    heading = f"{title} ({student})" if student else title

    try:
        out = summarize_collection(collection, title=heading, progress=on_progress)
    except SummaryError as err:
        bar.empty()
        st.error(f"Summary failed: {err}")
        return

    markdown = str(out["markdown"])
    if out["groups_used"] < out["groups_total"]:
        markdown += (
            f"\n\n_Note: long document. Only {out['groups_used']} of "
            f"{out['groups_total']} parts were read (evenly spaced)._"
        )
    store.save_summary(collection, markdown)
    st.session_state["flash"] = f"Summary ready (took {out['seconds']} seconds)."
    st.rerun()


def render_body(msg: dict) -> None:
    """Content of one chat message (call inside a chat_message block)."""
    st.markdown(msg["content"])
    if msg.get("pages"):
        label = "Sources" if msg.get("cited") else "Possible sources"
        st.markdown(ui.page_chips(msg["pages"], label), unsafe_allow_html=True)
    if msg.get("unverified"):
        st.warning(
            "Check these figures in the document, they were not found "
            f"in the retrieved text: {', '.join(msg['unverified'])}"
        )
    if msg.get("model"):
        st.caption(f"Answered by {msg['model']}")


def render_message(msg: dict) -> None:
    avatar = USER_AVATAR if msg["role"] == "user" else BOT_AVATAR
    with st.chat_message(msg["role"], avatar=avatar):
        render_body(msg)


def render_summary(markdown: str) -> None:
    """Show the six sections as cards, or plain Markdown as a fallback."""
    _, sections, note = ui.split_summary(markdown)
    if not sections:
        st.markdown(markdown)
        return
    st.markdown(ui.summary_html(sections), unsafe_allow_html=True)
    if note:
        st.caption(note)


# ---------- theme and sidebar ----------

st.session_state.setdefault("dark", False)
st.sidebar.markdown(ui.sidebar_brand(), unsafe_allow_html=True)
st.sidebar.markdown(ui.sidebar_label("Appearance"), unsafe_allow_html=True)
dark = st.sidebar.toggle("🌙 Dark mode", key="dark")
st.markdown(ui.build_css(dark), unsafe_allow_html=True)

ensure_demo()

if "pending_select" in st.session_state:
    st.session_state["selected"] = st.session_state.pop("pending_select")

if providers.is_local():
    st.sidebar.caption("Everything runs locally on this computer.")
else:
    st.sidebar.caption(
        "Answers use Google Gemini (free tier). Use only non-sensitive documents."
    )

records = sorted(
    store.load_registry(), key=lambda r: str(r.get("created", "")), reverse=True
)
by_name = {str(r["collection_name"]): r for r in records}

st.sidebar.markdown(
    ui.sidebar_label("Documents", len(records)), unsafe_allow_html=True
)
if records:
    st.sidebar.selectbox(
        "Document",
        options=list(by_name),
        format_func=lambda name: store.label(by_name[name]),
        key="selected",
        label_visibility="collapsed",
    )
else:
    st.sidebar.caption(
        "No documents yet." + ("" if config.DEMO_MODE else " Add one below.")
    )

submitted = False
if not config.DEMO_MODE:
    st.sidebar.markdown(ui.sidebar_label("Add a document"), unsafe_allow_html=True)
    with st.sidebar.form("upload_form"):
        student = st.text_input("Student name", placeholder="e.g. Asha Rao")
        title = st.text_input("Project title", placeholder="e.g. Smart Attendance System")
        uploaded = st.file_uploader("Project documentation (PDF)", type=["pdf"])
        submitted = st.form_submit_button("Upload and index", type="primary")

    if submitted:
        if not student.strip() or not title.strip() or uploaded is None:
            st.sidebar.error("Please fill in the name, the title and choose a PDF.")
        else:
            try:
                with st.sidebar:
                    with st.spinner("Reading and indexing the PDF..."):
                        record, reused = ingest_bytes(
                            student, title, uploaded.name, uploaded.getvalue()
                        )
            except IngestionError as err:
                st.sidebar.error(f"Ingestion failed: {err}")
            else:
                st.session_state["pending_select"] = record["collection_name"]
                st.session_state["flash"] = (
                    "This PDF was already indexed, so it was reused."
                    if reused
                    else "Document indexed."
                )
                st.rerun()

    st.sidebar.markdown(ui.sidebar_label("Maintenance"), unsafe_allow_html=True)
    with st.sidebar.expander("Import earlier test collections"):
        st.caption("Adds collections made before the app existed.")
        if st.button("Import"):
            try:
                added = store.import_existing()
                st.session_state["flash"] = f"Imported {added} collection(s)."
                st.rerun()
            except Exception as err:
                st.error(f"Import failed: {err}")
else:
    st.sidebar.info(
        "Demo version: uploads are turned off. Explore the sample report."
    )

st.sidebar.markdown(
    ui.sidebar_footer(local=providers.is_local()), unsafe_allow_html=True
)

# ---------- main area ----------

ready = is_ready()
st.markdown(
    ui.topbar(
        "DocuSense",
        "AI-assisted review of student project documentation",
        ready,
        label=status_label(ready),
    ),
    unsafe_allow_html=True,
)
if config.DEMO_MODE:
    st.info(
        "Public demo. The sample report is ready to explore. Uploads are "
        "turned off here, because real student work should stay on the "
        "teacher's own computer."
    )
if not ready:
    if providers.is_local():
        st.warning("Ollama is not running. Start it with: ollama serve")
    else:
        st.warning(providers.missing_key_message())

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

selected = st.session_state.get("selected")
if not records or selected not in by_name:
    st.markdown(
        ui.steps_html(
            [
                ("1", "Upload", "Add a student's project PDF in the sidebar."),
                ("2", "Summarize", "Get a structured summary with viva questions."),
                ("3", "Ask", "Chat with the document. Answers show their pages."),
            ]
        ),
        unsafe_allow_html=True,
    )
    st.stop()

record = by_name[selected]
collection = str(record["collection_name"])
record_provider = record.get("provider", "ollama")

st.markdown(
    ui.docbar(
        str(record.get("project_title") or collection),
        [
            ("Student", record.get("student_name") or "Unknown"),
            ("Pages", record.get("pages") or "-"),
            ("Chunks", record.get("chunks") or "-"),
            ("File", ui.truncate(record.get("source_file") or "-")),
        ],
    ),
    unsafe_allow_html=True,
)
st.markdown(
    ui.notice(
        "⚠ AI-generated. Small models can make mistakes, so verify "
        "important details against the original document."
    ),
    unsafe_allow_html=True,
)

if record_provider != config.PROVIDER:
    st.warning(
        f"This document was indexed with {record_provider}, but DocuSense is "
        f"now set to {config.PROVIDER}. Index it again with the current "
        "setting to use it."
    )
    st.stop()

if st.checkbox("ℹ️ Processing info", key="show_info"):
    st.markdown(ui.info_note(), unsafe_allow_html=True)

view = st.radio(
    "View",
    [VIEW_SUMMARY, VIEW_CHAT],
    horizontal=True,
    key="view",
    label_visibility="collapsed",
)

if view == VIEW_SUMMARY:
    cached = store.load_summary(collection)
    if cached:
        render_summary(cached)
        st.download_button(
            "Download summary (.md)",
            data=cached,
            file_name=f"summary_{collection}.md",
            mime="text/markdown",
        )
        if not config.DEMO_MODE:
            with st.expander("Regenerate summary"):
                st.caption("This replaces the saved summary and uses the model again.")
                if st.button("Regenerate", disabled=not ready):
                    run_summary(record)
    elif config.DEMO_MODE:
        st.info("The demo summary is being prepared. Refresh the page in a moment.")
    else:
        wait = (
            "about 10 minutes on this computer"
            if providers.is_local()
            else "a few minutes"
        )
        st.info(
            f"No summary yet. Generating one takes {wait}. Keep this tab open "
            "until it finishes. It is saved afterwards, so you only wait once."
        )
        if st.button("Generate summary", type="primary", disabled=not ready):
            run_summary(record)
else:
    if not ready:
        st.error("The model is not ready yet. See the warning at the top.")
        st.stop()

    qa_key, msg_key = f"qa_{collection}", f"msgs_{collection}"
    if qa_key not in st.session_state:
        try:
            st.session_state[qa_key] = DocumentQA(collection)
        except QAError as err:
            st.error(str(err))
            st.stop()
    qa: DocumentQA = st.session_state[qa_key]
    messages = st.session_state.setdefault(msg_key, [])

    if not messages:
        st.caption(
            "Ask about methods, results, numbers or anything in the document. "
            "If it is not in the document, DocuSense will say so."
        )
    for msg in messages:
        render_message(msg)

    question = st.chat_input("🔍 Ask a question about this document")
    if question:
        user_msg = {"role": "user", "content": question}
        messages.append(user_msg)
        render_message(user_msg)

        with st.chat_message("assistant", avatar=BOT_AVATAR):
            slot = st.empty()

            def on_stage(stage: str) -> None:
                slot.markdown(ui.thinking(stage), unsafe_allow_html=True)

            try:
                result = qa.ask(question, on_stage=on_stage)
            except QAError as err:
                reply = {"role": "assistant", "content": f"Error: {err}"}
            else:
                reply = {
                    "role": "assistant",
                    "content": result["answer"],
                    "pages": result["pages"],
                    "cited": result["cited"],
                    "unverified": result["unverified"],
                    "model": result.get("model", ""),
                }
            slot.empty()
            render_body(reply)
        messages.append(reply)

    if messages and st.button("Clear chat"):
        st.session_state[msg_key] = []
        qa.history = []
        st.rerun()