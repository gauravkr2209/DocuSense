# Doc demo (Gaurav)

## Context
DocuSense is a web application designed to help teachers review student project documents. It uses a retrieval-augmented generation (RAG) technique with LangChain, Chroma vector database, and Ollama model runner to extract text from PDFs and produce structured summaries.

## Objectives
The main objectives of the project are to:
* Extract text from PDFs and keep page numbers
* Produce structured summaries with 6 fixed sections
* Answer questions from uploaded documents and cite pages
* Run offline on ordinary laptops with 8 GB RAM
* Measure accuracy with a repeatable test set

## Methodology
The system uses a two-pipeline approach, with ingestion, summary, and question-answering pipelines sharing one vector store. The ingestion pipeline reads PDFs page by page with the pypdf library, while the summary pipeline groups chunks into up to 10 parts using a map-reduce method. The question-answering pipeline retrieves six most similar chunks and answers only from those chunks. The system is implemented in Python, with code divided into 6 files, and uses tools such as LangChain, Chroma, Ollama, and Streamlit.

## Results
The main results of the project are:
* 9/13 questions answered correctly
* 4 refused
* 9/9 evidence found
* 9/9 answer correctness
* 4/4 correct refusals
* 0/9 false refusals
* 7/9 model named a page itself
* 31 seconds average time per question
* Full summary took 11 minutes to generate

## Limitations
The limitations of the project are:
* Slow summary generation
* Small language model limitations
* Limited memory forcing small model
* Citation handling issues
* Source paper inconsistencies

## Suggested Viva Questions
1. How does the system handle citation handling, and what are the implications for accuracy?
2. What is the best chunk size for interpretation, and how does it affect the system's performance?
3. How does the system's hybrid search combining keyword and meaning-based matching improve its accuracy?
4. What are the limitations of the system's language model, and how can they be addressed in future work?
5. How does the system's offline capability affect its usability, and what are the implications for teacher efficiency?