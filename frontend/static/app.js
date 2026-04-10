const clipsInput = document.getElementById("clips");
const clipList = document.getElementById("clipList");
const musicPreset = document.getElementById("musicPreset");
const musicFile = document.getElementById("musicFile");
const versionsInput = document.getElementById("versions");
const styleInput = document.getElementById("style");
const promptContextInput = document.getElementById("promptContext");
const generateBtn = document.getElementById("generateBtn");
const statusText = document.getElementById("statusText");
const resultsEl = document.getElementById("results");

function setStatus(text) {
  statusText.textContent = text;
}

function renderClipList(files) {
  clipList.innerHTML = "";
  Array.from(files).forEach((file, idx) => {
    const li = document.createElement("li");
    li.textContent = `${idx + 1}. ${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)`;
    clipList.appendChild(li);
  });
}

async function loadPresets() {
  try {
    const res = await fetch("/api/music-presets");
    if (!res.ok) {
      return;
    }
    const presets = await res.json();
    presets.forEach((preset) => {
      const option = document.createElement("option");
      option.value = preset.filename;
      option.textContent = preset.name;
      musicPreset.appendChild(option);
    });
  } catch (_) {
    // No-op for local usage.
  }
}

async function getErrorMessage(res) {
  const contentType = (res.headers.get("content-type") || "").toLowerCase();

  if (contentType.includes("application/json")) {
    try {
      const payload = await res.json();
      return payload.detail || payload.message || "Error al generar";
    } catch (_) {
      return `Error ${res.status}`;
    }
  }

  try {
    const text = (await res.text()).trim();
    return text || `Error ${res.status}`;
  } catch (_) {
    return `Error ${res.status}`;
  }
}

function renderResults(payload) {
  resultsEl.innerHTML = "";
  payload.results.forEach((item) => {
    const wrapper = document.createElement("div");
    wrapper.className = "result-item";

    const title = document.createElement("strong");
    title.textContent = `Version ${item.variant_index}`;

    const caption = document.createElement("p");
    caption.textContent = item.caption;

    const overlay1 = document.createElement("p");
    overlay1.className = "overlay-preview";
    overlay1.textContent = `Texto en video 1: ${item.overlay_text_1}`;

    const overlay2 = document.createElement("p");
    overlay2.className = "overlay-preview";
    overlay2.textContent = `Texto en video 2: ${item.overlay_text_2}`;

    const copyButton = document.createElement("button");
    copyButton.className = "copy-btn";
    copyButton.textContent = "Copiar caption";
    copyButton.type = "button";
    copyButton.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(item.caption);
        copyButton.textContent = "Copiado";
        setTimeout(() => {
          copyButton.textContent = "Copiar caption";
        }, 1200);
      } catch (_) {
        copyButton.textContent = "No se pudo copiar";
      }
    });

    const link = document.createElement("a");
    link.href = item.download_url;
    link.textContent = "Descargar MP4";

    wrapper.appendChild(title);
    wrapper.appendChild(overlay1);
    wrapper.appendChild(overlay2);
    wrapper.appendChild(caption);
    wrapper.appendChild(copyButton);
    wrapper.appendChild(link);
    resultsEl.appendChild(wrapper);
  });
}

generateBtn.addEventListener("click", async () => {
  const files = Array.from(clipsInput.files || []);
  if (files.length === 0) {
    setStatus("Sube al menos un clip.");
    return;
  }
  if (files.length > 10) {
    setStatus("Solo se permiten hasta 10 clips.");
    return;
  }

  const versions = Number(versionsInput.value || 1);
  if (versions < 1 || versions > 10) {
    setStatus("La cantidad de versiones debe ser entre 1 y 10.");
    return;
  }

  generateBtn.disabled = true;
  setStatus("Procesando videos... puede tardar varios minutos.");
  resultsEl.innerHTML = "";

  const formData = new FormData();
  files.forEach((file) => formData.append("clips", file));
  formData.append("versions", String(versions));
  formData.append("style", styleInput.value);
  formData.append("prompt_context", promptContextInput.value || "");

  if (musicPreset.value) {
    formData.append("music_preset", musicPreset.value);
  }

  if (musicFile.files?.[0]) {
    formData.append("music_file", musicFile.files[0]);
  }

  try {
    const res = await fetch("/api/generate", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      throw new Error(await getErrorMessage(res));
    }

    const payload = await res.json();
    renderResults(payload);
    setStatus(`Listo: ${payload.generated_versions} videos generados.`);
  } catch (error) {
    setStatus(`Fallo: ${error.message}`);
  } finally {
    generateBtn.disabled = false;
  }
});

clipsInput.addEventListener("change", () => renderClipList(clipsInput.files || []));
loadPresets();
