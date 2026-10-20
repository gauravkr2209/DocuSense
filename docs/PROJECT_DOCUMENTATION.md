# DocuSense: Project Documentation

## Chapter 1: Introduction

DocuSense is a web application that helps teachers review a student's final-semester project report. A teacher uploads a PDF and receives a structured summary with six sections (Context, Objectives, Methodology, Results, Limitations and Suggested Viva Questions). The teacher can also ask questions about the document in a chat. Every answer is drawn only from the uploaded document, and when the document does not contain the answer, the system replies with a fixed sentence.

DocuSense supports the teacher. It does not replace the teacher's judgement, and every screen says that AI-generated content must be checked against the original document.

## Chapter 2: Objectives

- Extract text from a PDF and keep the page number of each passage.
- Produce a consistent six-part summary with five viva questions.
- Answer questions only from the document, with page references.
- Refuse, with an exact sentence, when the document does not support an answer.
- Measure the system with a repeatable test set, and report its limits honestly.
- Support two model providers: Google Gemini on the free tier (default) and Ollama on the user's own computer.

## Chapter 3: Background

**Retrieval-augmented generation (RAG).** The document is split into chunks. For each question, the most similar chunks are retrieved, and only those chunks are given to the language model. This reduces invented answers.

**Embeddings and vector database.** An embedding is a list of numbers that represents the meaning of a text. Chroma stores the embeddings for each document in its own collection.

**Models.** The Ollama version uses llama3.2:3b with nomic-embed-text embeddings, on a CPU. The Gemini version uses a free-tier Gemini chat model with Gemini embeddings.

**Frameworks.** LangChain provides the text splitter, vector store and model connections. Streamlit provides the web interface. pypdf reads the PDF.

## Chapter 4: System Design

The system has two parts that share one vector store. The ingestion part prepares a document once: it reads each page, cleans the text, splits it into 1000-character chunks with a 150-character overlap, embeds the chunks and stores them. The question-answering and summary parts read from that store.

**Summary.** The chunks are grouped into at most 10 parts. The model writes short notes for each part (map step), then combines the notes into the final six-section summary (reduce step). The result is saved, so it is generated once per document.

**Question answering.** The question is embedded and the six most similar chunks are retrieved. A strict prompt tells the model to answer only from them, and to reply with the fixed sentence if the answer is missing. The program removes the model's own page citations and shows only pages it has checked against the retrieved chunks. Numbers in the answer that do not appear in the retrieved text trigger a warning.

**Model fallback.** The chat model is tried from a prioritised list. If one model is busy or over its quota, the next one answers, and the interface shows which model answered.

**Provider separation.** Only `providers.py` talks to the model libraries. Each indexed document records which provider created its embeddings, because embeddings from different providers cannot be searched together.

## Chapter 5: Implementation

| File | Purpose |
|---|---|
| config.py | Provider choice, model names, chunk and summary settings |
| providers.py | Creates chat and embedding models; model fallback; readable error messages |
| ingest.py | PDF to cleaned, split, embedded chunks in Chroma |
| qa.py | Retrieval, grounded answer, citation cleanup, number check |
| summarize.py | Map-reduce summary with six fixed sections |
| store.py | Document registry, summary cache, safe file names |
| ui.py | Light and dark styling, cards, chips and helper text |
| app.py | Streamlit interface, including demo mode |
| evaluate.py | Retrieval, full question-answering and chunk-size evaluation |
| test_*.py | Unit tests (77) that run without any model or API key |

The interface has a sidebar for choosing and uploading documents, a status bar, a Summary view with colour-coded cards, and a Chat view with the input pinned at the bottom and an animated search indicator.

## Chapter 6: Evaluation

The evaluation was run on the local Ollama version, using one 15-page research paper (49 chunks) and 13 questions: 9 answerable and 4 unanswerable, including two traps. The keywords were chosen by the author after reading the paper.

| Metric | Result |
|---|---|
| Evidence in top-6 retrieved chunks | 9/9 |
| Answer correct (keyword check) | 9/9 |
| Correct refusals | 4/4 |
| False refusals | 0/9 |
| Shown pages contain the evidence | 9/9 |
| Answers with unverified numbers | 0/9 |
| Model named a page itself | 7/9 |

A chunk-size sweep (500, 800, 1000 and 1500 characters) found 1000 characters best, though the difference is one question and not a proven trend.

The Gemini version has not been formally evaluated. No accuracy figures are claimed for it.

## Chapter 7: Limitations

- The evaluation is small: one paper, 13 questions, author-chosen keywords.
- The local model is 3B parameters and can make factual or formatting mistakes in summaries.
- Citations are approximate. Pages labelled "Possible sources" are the best-matching pages, not verified origins.
- The number check cannot detect a number that exists in the document but answers a different question, or contradictions inside the document.
- Scanned PDFs are not supported (no OCR).
- Gemini free-tier limits are daily and per minute, shared by all users of the same key.
- In Gemini mode, document text is sent to Google. The free tier may be used by Google to improve its products, so only non-sensitive documents should be used.
- There is no login, no delete button and no protection against prompt injection.

## Chapter 8: Challenges Faced and Solutions

| No. | Problem | Cause | Solution |
|---|---|---|---|
| 1 | The no-code workflow never ran | The free trial expired | Rebuilt the project in Python with LangChain, Chroma and Ollama |
| 2 | Slow processing on the laptop | 8 GB RAM, no usable GPU | Used a 3B model and capped the number of summary parts |
| 3 | Everything had to stay in one folder | Default install locations on C: | Virtual environment, pip cache and model folder all set to D: |
| 4 | `ollama` not recognised in new terminals | PATH not refreshed | Used the full path, then a session alias, then a clean PATH fix |
| 5 | A PATH command copied session entries into the user PATH | Command copied the whole session PATH | Provided a cleanup script |
| 6 | Ollama reported zero model files after restart | Models were looked up in the new folder | Pulled the embedding model again so it landed on D: |
| 7 | Shared Phase 1 code was broken | Code was flattened and partly missing | Rewrote the complete files |
| 8 | Deprecation warning, and a package name that does not exist | Mistaken suggestion | Read PDFs with pypdf directly |
| 9 | No test PDF | Sample generator file was never created | Used a real 15-page research paper |
| 10 | Repeated ingestion created duplicate collections | Each run creates a new collection | Kept per-document isolation and added duplicate detection by file fingerprint |
| 11 | Wrong or invented page citations (for example "page 20") | The model wrote its own page numbers | Stripped model citations; show only verified pages; label the rest "Possible sources" |
| 12 | Summary took 8 to 11 minutes and had missing spaces | Model output formatting, slow CPU | Progress display, saved summaries and a spacing fix |
| 13 | Summary skipped part of the paper | Greedy grouping made more groups than the cap | Group size grows until the whole document fits |
| 14 | Summary factual and formatting slips | Small model | Tighter prompts, visible AI notice; not fully solved |
| 15 | Test file imported itself; evaluate.py was missing | Copy-paste mistakes | Corrected the import and created the file |
| 16 | A pasted edit broke a dictionary | Partial paste | Replaced the whole function |
| 17 | One evaluation answer was marked wrong | The paper contains 41.0 and 41.8 | Verified in the PDF and accepted both values; limitation recorded |
| 18 | App reachable on the Wi-Fi network | Default server address | Bound the app to 127.0.0.1 |
| 19 | Interface looked plain | Default Streamlit styling | Redesign with cards, a status bar, chips and a search animation |
| 20 | Dark mode text boxes and dropdown were unreadable | Streamlit paints widgets with its own theme; element names vary by version | Layered CSS overrides, checked in the browser over several iterations |
| 21 | Test counts and time estimates were wrong | Manual counting and guessing | Used the real test output and measured times |
| 22 | Diagnosis of a citation problem was wrong | Assumed the page without checking | Checked the output and corrected the diagnosis |
| 23 | Gemini summary was cut off after Context | Gemini 3 "thinking" tokens use the same output budget as the answer | Set a minimum output budget of 8192 tokens and regenerated the summary |
| 24 | Gemini daily quota exhausted | The free limit for one model was used up | Compared limits on the rate-limit page; added a fallback list of models |
| 25 | "503 high demand" error in chat | Temporary load on Google's servers | Readable message and automatic fallback to the next model |
| 26 | API key pasted into chat | Copy-paste during testing | Advised revoking keys; keys kept only in `secrets.toml`, which Git ignores |
| 27 | Edits pasted as fragments broke code | Partial edits | Provided complete files for changed modules |
| 28 | `requirements.txt` contained command text and a hidden character | PowerShell here-string written into the file | Rewrote the file cleanly |
| 29 | Documents indexed by one provider failed with the other | Embeddings differ between providers | Each document records its provider; the app asks for re-indexing |
| 30 | Port 8501 still in use | Old app still running | Used the next free port, 8502 |

**Lessons learned**

- Measure, do not assume. Several early conclusions were corrected by checking the real output.
- Keep secrets out of chat and out of Git from the start.
- Replace whole files when a change touches many lines, rather than pasting fragments.
- Free models have limits that change; read the current figures on the provider's page.

## Chapter 9: Conclusion and Future Work

DocuSense shows that a useful document-review assistant can be built with free tools. The local version runs entirely on an ordinary laptop. The Gemini version runs on a free tier and needs no local model. On the test set, the local version answered all nine answerable questions correctly and refused all four unanswerable ones.

Future work:

- Formal evaluation of the Gemini version, and a comparison with the local model
- Prompt-injection tests and hardening
- Delete-document button and a warning for pages with no text
- OCR for scanned PDFs
- Hybrid keyword and embedding search with re-ranking
- A public demo with uploads disabled
- Teacher login
- A larger evaluation set built from real student reports

## Appendix: Setup

See the README in the repository for installation, the Gemini key setup and the Ollama option.