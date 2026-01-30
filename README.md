# 📄 Personal Data Assistant (PDF Chatbot)

**Personal Data Assistant** is an AI-powered web application that allows users to upload PDF documents and interact with them conversationally. The assistant understands the content of the uploaded document and answers user questions using Retrieval-Augmented Generation (RAG).

---

## ✨ Features

- 📂 Upload PDF files (English & Arabic supported)
- 🤖 Ask natural language questions about the document
- 🧠 Uses RAG (Retrieval + LLM) for accurate answers
- 🖼️ OCR fallback for image-based/scanned PDFs
- ⚡ Optimized for speed with smart chunking and caching
- 🔐 Secure handling of API keys via environment variables
- 🌐 Simple web interface (Flask + HTML/CSS/JS)

---

## 🧠 How It Works (High Level)

1. **PDF Upload**
   - User uploads a PDF file through the web interface.

2. **Document Processing**
   - If the PDF contains selectable text → text is extracted directly.
   - If the PDF is image-based → OCR is applied.
   - Text is split into chunks and converted into embeddings.

3. **Vector Store**
   - Embeddings are stored in a Chroma vector database.

4. **Question Answering**
   - User questions are embedded and matched against the vector store.
   - Relevant chunks are retrieved and passed to the LLM.
   - The LLM generates a contextual answer.

---

## 🛠️ Tech Stack

- **Backend**: Python, Flask
- **LLM**: OpenAI GPT-4 (via `ChatOpenAI`)
- **Embeddings**: OpenAI Embeddings
- **Vector Database**: Chroma
- **PDF Parsing**: PyMuPDF
- **OCR**: Tesseract OCR (with Poppler)
- **Frontend**: HTML, CSS, JavaScript
- **Environment Management**: python-dotenv

---

## 📁 Project Structure

```text
chatbot/
├── server.py              # Flask server (API routes)
├── worker.py              # LLM, OCR, embeddings, RAG logic
├── requirements.txt       # Python dependencies
├── README.md              # Project documentation
├── .gitignore             # Ignored files & folders
├── .env.example           # Environment variables template
│
├── templates/
│   └── index.html         # Frontend UI
│
├── static/
│   ├── style.css          # UI styling
│   └── script.js          # Frontend logic
│
├── uploads/               # Uploaded PDFs (runtime)
├── cache/                 # Vector cache (runtime)
````

---

## 🚀 Getting Started

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
```

---

### 2️⃣ Create & Activate Virtual Environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 4️⃣ Environment Variables

Create a `.env` file (do NOT upload it to GitHub):

```env
OPENAI_API_KEY=your_openai_api_key_here
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
OCR_LANG=eng
```

> For reference, see `.env.example`.

---

### 5️⃣ Run the Application

```bash
python server.py
```

Then open your browser at:

```
http://127.0.0.1:8000
```

---

## ⚡ Performance Optimizations

* Skips OCR if selectable text exists
* Filters empty chunks before embedding
* Uses Max Marginal Relevance (MMR) retriever
* Chunk size optimized for fast indexing
* Avoids reprocessing identical PDFs

---

## 🧪 Supported PDF Types

| PDF Type        | Supported                            |
| --------------- | ------------------------------------ |
| Text-based PDFs | ✅ Yes                                |
| Scanned PDFs    | ✅ Yes (OCR)                          |
| Image-only PDFs | ✅ Yes (OCR)                          |
| Arabic PDFs     | ✅ Yes (with OCR_LANG=ara or eng+ara) |

---

## 🔐 Security Notes

* `.env` is ignored via `.gitignore`
* API keys are never exposed to frontend
* Only `.env.example` is committed

---

## 🧩 Future Improvements

* Async/background PDF processing
* Streaming responses
* Multi-document chat
* Persistent vector database
* User authentication
* Deployment with Docker

---

## 👩‍💻 Author

**Asten Beta**
*My name: Aya Alhamwi*

---

## 📄 License

This project is provided for educational and personal use.
You are free to modify and extend it.

---
