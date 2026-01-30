import os
import uuid
import time
import hashlib
import logging
from flask import Flask, render_template, request, jsonify

from worker import init_llm, process_document, process_prompt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("server")

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024  # 30MB


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/upload", methods=["POST"])
def upload():
    req_id = str(uuid.uuid4())[:8]
    t0 = time.time()

    try:
        logger.info("[%s] /upload called from %s", req_id, request.remote_addr)

        if "file" not in request.files:
            logger.warning("[%s] Missing file", req_id)
            return jsonify({"error": "Upload failed. Please try again."}), 400

        f = request.files["file"]
        if not f or not f.filename:
            logger.warning("[%s] Empty file", req_id)
            return jsonify({"error": "Upload failed. Please try again."}), 400

        original_name = f.filename
        _, ext = os.path.splitext(original_name)

        if ext.lower() != ".pdf":
            logger.warning("[%s] Rejected non-PDF file: %s", req_id, original_name)
            return jsonify({"error": "Upload failed. Please try again."}), 400

        safe_name = f"{uuid.uuid4().hex}.pdf"
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
        f.save(save_path)

        file_size = os.path.getsize(save_path)
        logger.info("[%s] Saved PDF: %s (original=%s, bytes=%d)", req_id, save_path, original_name, file_size)

        #  fingerprint (this is the key for caching)
        t_hash = time.time()
        doc_id = sha256_file(save_path)
        logger.info("[%s] sha256 computed in %.2fs => %s", req_id, time.time() - t_hash, doc_id[:12])

        # Process doc (worker will skip if already indexed)
        logger.info("[%s] Starting process_document(doc_id=%s)", req_id, doc_id[:12])
        t_proc = time.time()
        status = process_document(save_path, doc_id=doc_id)  # returns "indexed" or "cached"
        logger.info("[%s] process_document finished in %.2fs (status=%s)", req_id, time.time() - t_proc, status)

        logger.info("[%s] Total /upload time: %.2fs", req_id, time.time() - t0)
        return jsonify({"message": "PDF processed successfully."}), 200

    except Exception:
        logger.exception("[%s] Upload/processing failed", req_id)
        return jsonify({"error": "Sorry, I couldn't process that PDF. Please try again."}), 500


@app.route("/chat", methods=["POST"])
def chat():
    req_id = str(uuid.uuid4())[:8]
    try:
        logger.info("[%s] /chat called from %s", req_id, request.remote_addr)

        data = request.get_json(force=True, silent=True) or {}
        prompt = (data.get("message") or "").strip()

        if not prompt:
            msg = "Please type a question."
            return jsonify({"answer": msg, "response": msg, "message": msg, "bot_response": msg}), 200

        logger.info("[%s] Processing prompt (len=%d)", req_id, len(prompt))
        answer = process_prompt(prompt) or ""
        logger.info("[%s] Prompt processed successfully", req_id)

        return jsonify({"answer": answer, "response": answer, "message": answer, "bot_response": answer}), 200

    except Exception:
        logger.exception("[%s] Chat failed", req_id)
        msg = "Sorry, something went wrong. Please try again."
        return jsonify({"answer": msg, "response": msg, "message": msg, "bot_response": msg}), 500


if __name__ == "__main__":
    logger.info("Initializing LLM...")
    init_llm()
    logger.info("Starting server on http://127.0.0.1:8000")
    app.run(host="127.0.0.1", port=8000, debug=False)
