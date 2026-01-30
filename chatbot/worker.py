import os
import io
import base64
import logging
from typing import List, Optional

import fitz  # PyMuPDF
from dotenv import load_dotenv

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

import json
from PIL import Image


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Globals
llm_hub = None
embeddings = None
conversation_retrieval_chain = None
chat_history = []

# Vectorstore root (for caching)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VECTOR_DB_DIR = os.path.join(BASE_DIR, "vector_db")
os.makedirs(VECTOR_DB_DIR, exist_ok=True)


def init_llm():
    """Initialize OpenAI chat model + embeddings (reads OPENAI_API_KEY from .env)."""
    global llm_hub, embeddings
    load_dotenv()

    llm_hub = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.1,
        max_tokens=512,
    )

     
    embeddings = OpenAIEmbeddings()

    logger.info("OpenAI LLM and embeddings initialized.")


def _extract_selectable_text_documents(pdf_path: str) -> List[Document]:
    """Extract selectable text from PDF via PyMuPDF (fast)."""
    docs: List[Document] = []
    with fitz.open(pdf_path) as pdf:
        for i, page in enumerate(pdf):
            text = (page.get_text("text") or "").strip()
            if text:
                docs.append(Document(page_content=text, metadata={"page": i + 1, "source": pdf_path}))
    logger.info("Selectable-text pages extracted: %d", len(docs))
    return docs


def _vision_ocr_pdf(pdf_path: str, max_pages: int = 20, dpi: int = 140, batch_size: int = 3) -> List[Document]:
    """
    OCR fallback using OpenAI Vision (NO Tesseract / NO Poppler).
    Faster version:
      - Render pages at moderate DPI
      - Convert to JPEG (smaller)
      - Send images in batches to reduce API calls
    """
    if llm_hub is None:
        raise RuntimeError("LLM not initialized. Call init_llm() first.")

    logger.info("Running Vision OCR fallback on PDF: %s", pdf_path)

    docs: List[Document] = []

    with fitz.open(pdf_path) as pdf:
        total_pages = len(pdf)
        pages_to_process = min(total_pages, max_pages)

        logger.info("Vision OCR: total_pages=%d, processing=%d, dpi=%d, batch_size=%d",
                    total_pages, pages_to_process, dpi, batch_size)

        def page_to_jpeg_data_url(page_index: int) -> str:
            page = pdf[page_index]
            # render at DPI (smaller than huge zoom PNG)
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # pix -> PIL -> JPEG bytes
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=60, optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return f"data:image/jpeg;base64,{b64}"

        # batch pages
        batch_start = 0
        while batch_start < pages_to_process:
            batch_end = min(batch_start + batch_size, pages_to_process)
            batch_indices = list(range(batch_start, batch_end))

            logger.info("Vision OCR batch: pages %s", [i + 1 for i in batch_indices])

            # Ask model to return JSON mapping page_number->text
            prompt = (
                "You will receive multiple page images from a PDF. "
                "Extract all readable text from EACH page faithfully, keeping the original language (Arabic/English). "
                "Return STRICT JSON ONLY in this format:\n"
                "{\n"
                '  "pages": [\n'
                '    {"page": 1, "text": "..."},\n'
                '    {"page": 2, "text": "..."}\n'
                "  ]\n"
                "}\n"
                "If a page has no text, use empty string."
            )

            content = [{"type": "text", "text": prompt}]
            for idx in batch_indices:
                content.append({"type": "image_url", "image_url": {"url": page_to_jpeg_data_url(idx)}})

            resp = llm_hub.invoke([{"role": "user", "content": content}])
            raw = (resp.content or "").strip()

            # Parse JSON safely
            try:
                data = json.loads(raw)
                for item, idx in zip(data.get("pages", []), batch_indices):
                    text = (item.get("text") or "").strip()
                    if text:
                        docs.append(Document(
                            page_content=text,
                            metadata={"page": idx + 1, "source": pdf_path, "ocr": "vision"}
                        ))
            except Exception:
                # Fallback: if model returned non-JSON, store it as one chunk
                logger.warning("Vision OCR returned non-JSON; storing raw text for batch %s", batch_indices)
                if raw:
                    docs.append(Document(
                        page_content=raw,
                        metadata={"page_range": f"{batch_start+1}-{batch_end}", "source": pdf_path, "ocr": "vision_raw"}
                    ))

            batch_start = batch_end

    logger.info("Vision OCR extracted text docs: %d", len(docs))
    return docs



def process_document(document_path: str, doc_id: Optional[str] = None) -> str:
    """
    Build or load vectorstore + RetrievalQA chain.
    Returns: "indexed" or "cached"
    """
    global conversation_retrieval_chain, chat_history

    if embeddings is None or llm_hub is None:
        raise RuntimeError("LLM/Embeddings not initialized. Call init_llm() first.")

    logger.info("process_document called (path=%s, doc_id=%s)", document_path, doc_id)

    # reset chat history per new document
    chat_history = []

    persist_dir = None
    if doc_id:
        persist_dir = os.path.join(VECTOR_DB_DIR, doc_id)

        # If cached vectorstore exists, load it (FAST)
        if os.path.isdir(persist_dir) and os.listdir(persist_dir):
            logger.info("Loading cached Chroma DB from: %s", persist_dir)
            db = Chroma(persist_directory=persist_dir, embedding_function=embeddings)

            conversation_retrieval_chain = RetrievalQA.from_chain_type(
                llm=llm_hub,
                chain_type="stuff",
                retriever=db.as_retriever(search_type="mmr", search_kwargs={"k": 6, "lambda_mult": 0.25}),
                return_source_documents=False,
                input_key="question"
            )
            logger.info("RetrievalQA chain ready (cached).")
            return "cached"

    # 1) Try selectable text first (FAST)
    docs = _extract_selectable_text_documents(document_path)

    # 2) If no text → Vision OCR fallback (NO INSTALL)
    if len(docs) == 0:
        docs = _vision_ocr_pdf(document_path, max_pages=12, zoom=1.4)

    if len(docs) == 0:
        raise ValueError("No extractable text found (even after Vision OCR).")

    # Split into chunks
    splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120)
    chunks = splitter.split_documents(docs)
    chunks = [c for c in chunks if (c.page_content or "").strip()]
    logger.info("Total non-empty text chunks: %d", len(chunks))

    # Build Chroma
    logger.info("Creating Chroma vector store...")
    if persist_dir:
        os.makedirs(persist_dir, exist_ok=True)
        db = Chroma.from_documents(chunks, embedding=embeddings, persist_directory=persist_dir)
        db.persist()
        logger.info("Chroma persisted to: %s", persist_dir)
    else:
        db = Chroma.from_documents(chunks, embedding=embeddings)

    logger.info("Building RetrievalQA chain...")
    conversation_retrieval_chain = RetrievalQA.from_chain_type(
        llm=llm_hub,
        chain_type="stuff",
        retriever=db.as_retriever(search_type="mmr", search_kwargs={"k": 6, "lambda_mult": 0.25}),
        return_source_documents=False,
        input_key="question"
    )

    logger.info("RetrievalQA chain ready (indexed).")
    return "indexed"


def process_prompt(prompt: str) -> str:
    global conversation_retrieval_chain, chat_history

    if conversation_retrieval_chain is None:
        return "Please upload a PDF first so I can answer based on it."

    prompt = (prompt or "").strip()
    if not prompt:
        return "Please type a question."

    logger.info("Processing prompt: %s", prompt)

    out = conversation_retrieval_chain.invoke({"question": prompt})
    answer = (out.get("result") or "").strip()

    chat_history.append((prompt, answer))
    return answer or "No response."
