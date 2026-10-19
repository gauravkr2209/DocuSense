"""Streamlit interface for DocuSense."""
import re
import urllib.request

import streamlit as st

import config
import store
import ui
from ingest import IngestionError, ingest_pdf
from qa import DocumentQA, QAError
from summarize import SummaryError, summarize_collection

st.set_page_config(page_title="DocuSense", page_icon="📄", layout="wide")

USER_AVATAR, BOT_AVATAR = "🧑‍🏫", "🤖"
VIEW_SUMMARY, VIEW_CHAT = "📋 Summary", "💬 Chat"


# ---------- helpers ----------

def ollama_running() -> bool:
    """Quick check that the local Ollama server answers."""
    try:
        with urllib.request.urlopen(config.OLLAMA_BASE_URL, timeout=1.5):
            return True
    except Exception:
        return False


def handle_upload(student: str, title: str, uploaded):
    """Save, ingest and register an uploaded PDF.
    Returns (record, already_indexed)."""
    data = uploaded.getvalue()
    digest = store.file_sha256(data)
    existing = store.find_by_hash(digest)
    if existing:
        return existing, True

    path = store.UPLOAD_DIR / f"{digest[:8]}_{store.safe_filename(uploaded.name)}"
    path.write_bytes(data)
    try:
        result = ingest_pdf(str(path))
    except IngestionError:
        path.unlink(missing_ok=True)
        raise
    record = store.make_record(student, title, uploaded.name, digest, result)
    store.add_record(record)
    return record, False


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

if "pending_select" in st.session_state:
    st.session_state["selected"] = st.session_state.pop("pending_select")

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
    st.sidebar.caption("No documents yet. Add one below.")

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
                    record, reused = handle_upload(student, title, uploaded)
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

st.sidebar.markdown(ui.sidebar_footer(), unsafe_allow_html=True)

# ---------- main area ----------

ollama_ok = ollama_running()
st.markdown(
    ui.topbar(
        "DocuSense",
        "AI-assisted review of student project documentation",
        ollama_ok,
    ),
    unsafe_allow_html=True,
)
if not ollama_ok:
    st.warning("Ollama is not running. Start it with: ollama serve")

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
        "⚠ AI-generated. Small local models can make mistakes, so verify "
        "important details against the original document."
    ),
    unsafe_allow_html=True,
)

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
        with st.expander("Regenerate summary"):
            st.caption("This takes about 10 minutes and replaces the saved summary.")
            if st.button("Regenerate"):
                run_summary(record)
    else:
        st.info(
            "No summary yet. Generating one takes roughly 10 minutes on this "
            "computer. Keep this tab open and do not click anything else "
            "until it finishes. It is saved afterwards, so you only wait once."
        )
        if st.button("Generate summary", type="primary"):
            run_summary(record)
else:
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
                }
            slot.empty()
            render_body(reply)
        messages.append(reply)

    if messages and st.button("Clear chat"):
        st.session_state[msg_key] = []
        qa.history = []
        st.rerun()