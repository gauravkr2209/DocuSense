# DocuSense Demo Report (Demo Student)

> Written summary of the demo report, based on the project's documented facts. The live app generates its own summaries with the model; this one is written by the author for the public demo.

## Context
DocuSense is an AI-assisted tool that helps teachers review student project documentation. A teacher uploads a PDF report and receives a structured summary, then asks questions that are answered only from that document. The project targets final-semester reports, where reading every page before a viva takes time and checking a single fact is slow.

## Objectives
The main objectives of the project are to:
* Extract text from a PDF and keep the page number of each passage
* Produce a consistent summary with six fixed sections and five viva questions
* Answer questions only from the document, citing pages where possible
* Refuse with a fixed sentence when the document does not contain the answer
* Measure the system with a repeatable test set and report its limits honestly

## Methodology
The system has two parts that share one vector store. Ingestion reads the PDF page by page, cleans the text, splits it into chunks of 1000 characters with a 150-character overlap, and stores their embeddings in Chroma, one collection per document. The summary groups the chunks into at most ten parts, writes short notes for each part, and combines them into the final six-section summary. Question answering retrieves the six most similar chunks and gives only those to the model, with a strict instruction to answer from them alone. The chat model is chosen from a prioritised list of free Gemini models, so a busy or rate-limited model is replaced by the next one. A local option runs the same pipeline with Ollama on the user's computer.

## Results
Measured on the local Ollama version, using a 15-page research paper and 13 questions (9 answerable, 4 unanswerable):
* Evidence found in the top six retrieved passages: 9 of 9
* Correct answers on answerable questions (keyword check): 9 of 9
* Correct refusals on unanswerable questions: 4 of 4
* False refusals on answerable questions: 0 of 9
* Answers with unverified numbers: 0 of 9
* Average time per question: about 31 seconds

The Gemini version has not yet been formally evaluated, so no accuracy figures are claimed for it.

## Limitations
* The evaluation is small: one paper, 13 questions and keywords chosen by the author.
* The local model has 3 billion parameters and can make factual or formatting mistakes in summaries.
* Citations are approximate. Pages labelled "Possible sources" are the best-matching pages, not verified origins.
* The number check cannot catch numbers that exist in the document but answer a different question.
* Scanned PDFs are not supported, because there is no OCR.
* Gemini free-tier limits are daily and per minute, and they are shared by all users of the same key.
* In Gemini mode, document text is sent to Google, and the free tier may be used by Google to improve its products. Use only non-sensitive documents.

## Suggested Viva Questions
1. How does retrieval-augmented generation keep the answers tied to the uploaded document?
2. Why was a chunk size of 1000 characters with a 150-character overlap chosen, and what did the sweep show?
3. How does the summary's map-reduce step keep a long document within the model's limits?
4. What happens when the free Gemini quota is used up, and how does the model fallback respond?
5. Why does the project keep each document's embeddings tied to the provider that created them?