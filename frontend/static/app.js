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

const stylePreviewText = document.getElementById("stylePreviewText");

const FONT_OPTIONS = [
  { value: "Lobster", label: "Lobster", family: "'Lobster', cursive", weight: "500" },
  { value: "Lobster-Bold", label: "Lobster-Bold", family: "'Lobster', cursive", weight: "800" },
  { value: "Baloo", label: "Baloo", family: "'Baloo 2', cursive", weight: "500" },
  { value: "Baloo-Bold", label: "Baloo-Bold", family: "'Baloo 2', cursive", weight: "800" },
  { value: "Fredoka", label: "Fredoka", family: "'Fredoka', sans-serif", weight: "500" },
  { value: "Fredoka-Bold", label: "Fredoka-Bold", family: "'Fredoka', sans-serif", weight: "800" },
  { value: "Bangers", label: "Bangers", family: "'Bangers', cursive", weight: "500" },
  { value: "Bangers-Bold", label: "Bangers-Bold", family: "'Bangers', cursive", weight: "800" },
  { value: "Luckiest Guy", label: "Luckiest Guy", family: "'Luckiest Guy', cursive", weight: "500" },
  { value: "Luckiest Guy-Bold", label: "Luckiest Guy-Bold", family: "'Luckiest Guy', cursive", weight: "800" },
  { value: "Anton", label: "Anton", family: "'Anton', sans-serif", weight: "500" },
  { value: "Anton-Bold", label: "Anton-Bold", family: "'Anton', sans-serif", weight: "800" },
  { value: "Montserrat", label: "Montserrat", family: "'Montserrat', sans-serif", weight: "500" },
  { value: "Montserrat-Bold", label: "Montserrat-Bold", family: "'Montserrat', sans-serif", weight: "800" },
  { value: "Oswald", label: "Oswald", family: "'Oswald', sans-serif", weight: "500" },
  { value: "Oswald-Bold", label: "Oswald-Bold", family: "'Oswald', sans-serif", weight: "800" },
  { value: "Poppins", label: "Poppins", family: "'Poppins', sans-serif", weight: "500" },
  { value: "Poppins-Bold", label: "Poppins-Bold", family: "'Poppins', sans-serif", weight: "800" },
  { value: "Inter", label: "Inter", family: "'Inter', sans-serif", weight: "500" },
  { value: "Inter-Bold", label: "Inter-Bold", family: "'Inter', sans-serif", weight: "800" },
  { value: "Nunito", label: "Nunito", family: "'Nunito', sans-serif", weight: "500" },
  { value: "Nunito-Bold", label: "Nunito-Bold", family: "'Nunito', sans-serif", weight: "800" },
];

const EFFECT_OPTIONS = [
  { value: "rebote", label: "rebote" },
  { value: "fade", label: "fade" },
  { value: "pop", label: "pop" },
];

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

function summaryText(selectedCount, totalCount, firstLabel) {
  if (selectedCount === 0) {
    return "Selecciona estilos";
  }
  if (selectedCount === totalCount) {
    return "Todas seleccionadas";
  }
  if (selectedCount === 1) {
    return firstLabel;
  }
  return `${selectedCount} seleccionadas`;
}

function createMultiSelect({
  rootId,
  triggerId,
  menuId,
  optionsId,
  selectAllId,
  clearId,
  closeId,
  options,
  useFontPreview = false,
  onChange,
}) {
  const root = document.getElementById(rootId);
  const trigger = document.getElementById(triggerId);
  const menu = document.getElementById(menuId);
  const optionsWrap = document.getElementById(optionsId);
  const selectAllBtn = document.getElementById(selectAllId);
  const clearBtn = document.getElementById(clearId);
  const closeBtn = document.getElementById(closeId);
  const label = root?.querySelector(".multi-select-label");

  const selected = new Set();

  function updateTrigger() {
    const firstSelected = options.find((item) => selected.has(item.value));
    trigger.textContent = summaryText(selected.size, options.length, firstSelected?.label || "Selecciona estilos");
  }

  function renderOptions() {
    optionsWrap.innerHTML = "";
    options.forEach((item) => {
      const label = document.createElement("label");
      label.className = "menu-option";

      const check = document.createElement("input");
      check.type = "checkbox";
      check.checked = selected.has(item.value);
      check.addEventListener("change", () => {
        if (check.checked) {
          selected.add(item.value);
        } else {
          selected.delete(item.value);
        }
        label.classList.toggle("selected", check.checked);
        updateTrigger();
        onChange(getSelectedValues());
      });

      const text = document.createElement("span");
      text.className = "option-text";
      text.textContent = item.label;
      if (useFontPreview) {
        text.style.fontFamily = item.family;
        text.style.fontWeight = item.weight || "700";
      }

      label.classList.toggle("selected", check.checked);
      label.appendChild(check);
      label.appendChild(text);
      optionsWrap.appendChild(label);
    });
  }

  function getSelectedValues() {
    return options.filter((item) => selected.has(item.value)).map((item) => item.value);
  }

  function openMenu() {
    document.querySelectorAll(".multi-select-menu").forEach((otherMenu) => {
      if (otherMenu !== menu) {
        otherMenu.hidden = true;
      }
    });
    document.querySelectorAll(".multi-select").forEach((otherRoot) => {
      if (otherRoot !== root) {
        otherRoot.classList.remove("open");
      }
    });
    document.querySelectorAll(".multi-select-trigger").forEach((otherTrigger) => {
      if (otherTrigger !== trigger) {
        otherTrigger.setAttribute("aria-expanded", "false");
      }
    });

    menu.hidden = false;
    root.classList.add("open");
    trigger.setAttribute("aria-expanded", "true");
    document.body.classList.add("modal-open");
  }

  function closeMenu() {
    menu.hidden = true;
    root.classList.remove("open");
    trigger.setAttribute("aria-expanded", "false");
    if (!document.querySelector(".multi-select.open")) {
      document.body.classList.remove("modal-open");
    }
  }

  trigger.addEventListener("click", (event) => {
    event.stopPropagation();
    if (menu.hidden) {
      openMenu();
    } else {
      closeMenu();
    }
  });

  trigger.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }
    event.preventDefault();
    if (menu.hidden) {
      openMenu();
    } else {
      closeMenu();
    }
  });

  if (label) {
    label.addEventListener("click", (event) => {
      event.stopPropagation();
      if (menu.hidden) {
        openMenu();
      } else {
        closeMenu();
      }
    });
  }

  selectAllBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    options.forEach((item) => selected.add(item.value));
    renderOptions();
    updateTrigger();
    onChange(getSelectedValues());
  });

  clearBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    selected.clear();
    renderOptions();
    updateTrigger();
    onChange(getSelectedValues());
  });

  if (closeBtn) {
    closeBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      closeMenu();
    });
  }

  menu.addEventListener("click", (event) => {
    if (event.target === menu) {
      closeMenu();
      return;
    }
    event.stopPropagation();
  });

  document.addEventListener("click", (event) => {
    if (!root.contains(event.target)) {
      closeMenu();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeMenu();
    }
  });

  updateTrigger();
  renderOptions();

  return {
    getSelectedValues,
    setValues(values) {
      selected.clear();
      values.forEach((value) => selected.add(value));
      renderOptions();
      updateTrigger();
      onChange(getSelectedValues());
    },
  };
}

let selectedFonts = [];
let selectedEffects = [];

function refreshPreview() {
  const fallbackFamily = "'Space Grotesk', sans-serif";
  const firstFont = FONT_OPTIONS.find((item) => item.value === selectedFonts[0]);
  stylePreviewText.style.fontFamily = firstFont?.family || fallbackFamily;
  stylePreviewText.style.fontWeight = firstFont?.weight || "800";
}

const fontSelect = createMultiSelect({
  rootId: "fontSelectRoot",
  triggerId: "fontTrigger",
  menuId: "fontMenu",
  optionsId: "fontOptions",
  selectAllId: "fontSelectAll",
  clearId: "fontClear",
  closeId: "fontClose",
  options: FONT_OPTIONS,
  useFontPreview: true,
  onChange(values) {
    selectedFonts = values;
    refreshPreview();
  },
});

const effectSelect = createMultiSelect({
  rootId: "effectSelectRoot",
  triggerId: "effectTrigger",
  menuId: "effectMenu",
  optionsId: "effectOptions",
  selectAllId: "effectSelectAll",
  clearId: "effectClear",
  closeId: "effectClose",
  options: EFFECT_OPTIONS,
  onChange(values) {
    selectedEffects = values;
  },
});

refreshPreview();

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

  selectedFonts = fontSelect.getSelectedValues();
  selectedEffects = effectSelect.getSelectedValues();
  if (selectedFonts.length === 0 || selectedEffects.length === 0) {
    setStatus("Debes seleccionar al menos 1 fuente y 1 efecto visual.");
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
  formData.append("text_bold", "true");
  selectedFonts.forEach((font) => formData.append("text_fonts", font));
  selectedEffects.forEach((effect) => formData.append("text_effects", effect));

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
