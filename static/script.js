const messagesEl = document.getElementById("messages");
const userInputEl = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");
const resetBtn = document.getElementById("resetBtn");
const uploadBtn = document.getElementById("uploadBtn");
const pdfInput = document.getElementById("pdfInput");
const uploadStatus = document.getElementById("uploadStatus");
const loadingOverlay = document.getElementById("loadingOverlay");
const themeSwitch = document.getElementById("themeSwitch");

let pdfReady = false;

function showLoading(show){
  loadingOverlay.style.display = show ? "flex" : "none";
}

function addMessage(role, text){
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  wrap.appendChild(bubble);
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function cleanText(s){
  return (s || "").trim();
}

// ---- Theme ----
themeSwitch.addEventListener("change", () => {
  document.body.classList.toggle("theme-dark", themeSwitch.checked);
  document.body.classList.toggle("theme-light", !themeSwitch.checked);
});

// ---- Upload ----
uploadBtn.addEventListener("click", () => pdfInput.click());

pdfInput.addEventListener("change", async () => {
  const file = pdfInput.files && pdfInput.files[0];
  if(!file){
    return;
  }
  uploadStatus.textContent = "Uploading...";
  showLoading(true);

  try{
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch("/upload", {
      method: "POST",
      body: formData
    });

    if(!res.ok){
      const t = await res.text();
      throw new Error(t || "Upload failed");
    }

    pdfReady = true;
    uploadStatus.textContent = "PDF analyzed. You can ask questions now.";
    addMessage("bot", "Thank you for providing your PDF document. I have analyzed it, so now you can ask me any questions regarding it!");
  }catch(err){
    pdfReady = false;
    uploadStatus.textContent = "Upload error.";
    addMessage("bot", "Sorry, I couldn't process that PDF. Please try again.");
    console.error(err);
  }finally{
    showLoading(false);
  }
});

// ---- Chat send ----
async function sendMessage(){
  const text = cleanText(userInputEl.value);
  if(!text) return;

  addMessage("user", text);
  userInputEl.value = "";

  if(!pdfReady){
    addMessage("bot", "Please upload a PDF first so I can answer based on it.");
    return;
  }

  showLoading(true);
  try{
    const res = await fetch("/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message: text})
    });

    const data = await res.json();
    addMessage("bot", data.response || "No response.");
  }catch(err){
    addMessage("bot", "Something went wrong while generating the answer.");
    console.error(err);
  }finally{
    showLoading(false);
  }
}

sendBtn.addEventListener("click", sendMessage);
userInputEl.addEventListener("keydown", (e) => {
  if(e.key === "Enter") sendMessage();
});

// ---- Reset ----
resetBtn.addEventListener("click", () => {
  // keep the first greeting message only
  messagesEl.innerHTML = `
    <div class="msg bot">
      <div class="bubble">
        Hello there! I'm your friendly data assistant, ready to answer any questions regarding your data.
        Could you please upload a PDF file for me to analyze?
        <div class="upload-row">
          <input id="pdfInput" type="file" accept="application/pdf" hidden />
          <button id="uploadBtn" class="btn btn-primary btn-sm">
            <i class="fa-solid fa-upload"></i> Upload File
          </button>
          <span id="uploadStatus" class="upload-status"></span>
        </div>
      </div>
    </div>
  `;

  // rebind after reset (because we replaced DOM)
  location.reload();
});
