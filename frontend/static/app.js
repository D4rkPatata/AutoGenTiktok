// ── Constants ─────────────────────────────────────────────────────────────────
const ALLOWED_VIDEO_EXTS = new Set([".mp4", ".mov"]);
const MAX_CLIPS = 10;
const MAX_SIZE_MB = 150;

const FONT_OPTIONS = [
  { value: "Lobster", label: "Lobster", family: "'Lobster', cursive", weight: "500" },
  { value: "Lobster-Bold", label: "Lobster Bold", family: "'Lobster', cursive", weight: "800" },
  { value: "Baloo", label: "Baloo", family: "'Baloo 2', cursive", weight: "500" },
  { value: "Baloo-Bold", label: "Baloo Bold", family: "'Baloo 2', cursive", weight: "800" },
  { value: "Fredoka", label: "Fredoka", family: "'Fredoka', sans-serif", weight: "500" },
  { value: "Fredoka-Bold", label: "Fredoka Bold", family: "'Fredoka', sans-serif", weight: "800" },
  { value: "Bangers", label: "Bangers", family: "'Bangers', cursive", weight: "500" },
  { value: "Bangers-Bold", label: "Bangers Bold", family: "'Bangers', cursive", weight: "800" },
  { value: "Luckiest Guy", label: "Luckiest Guy", family: "'Luckiest Guy', cursive", weight: "500" },
  { value: "Luckiest Guy-Bold", label: "Luckiest Guy Bold", family: "'Luckiest Guy', cursive", weight: "800" },
  { value: "Anton", label: "Anton", family: "'Anton', sans-serif", weight: "500" },
  { value: "Anton-Bold", label: "Anton Bold", family: "'Anton', sans-serif", weight: "800" },
  { value: "Montserrat", label: "Montserrat", family: "'Montserrat', sans-serif", weight: "500" },
  { value: "Montserrat-Bold", label: "Montserrat Bold", family: "'Montserrat', sans-serif", weight: "800" },
  { value: "Oswald", label: "Oswald", family: "'Oswald', sans-serif", weight: "500" },
  { value: "Oswald-Bold", label: "Oswald Bold", family: "'Oswald', sans-serif", weight: "800" },
  { value: "Poppins", label: "Poppins", family: "'Poppins', sans-serif", weight: "500" },
  { value: "Poppins-Bold", label: "Poppins Bold", family: "'Poppins', sans-serif", weight: "800" },
  { value: "Inter", label: "Inter", family: "'Inter', sans-serif", weight: "500" },
  { value: "Inter-Bold", label: "Inter Bold", family: "'Inter', sans-serif", weight: "800" },
  { value: "Nunito", label: "Nunito", family: "'Nunito', sans-serif", weight: "500" },
  { value: "Nunito-Bold", label: "Nunito Bold", family: "'Nunito', sans-serif", weight: "800" },
];

const EFFECT_OPTIONS = [
  { value: "none", label: "Sin efecto — texto estático" },
  { value: "fade", label: "Fade — aparece con fundido" },
  { value: "pop", label: "Pop — aparece con rebote de escala" },
  { value: "rebote", label: "Rebote — cae desde arriba" },
];

// ── DOM refs ──────────────────────────────────────────────────────────────────
const authArea = document.getElementById("authArea");
const tiktokAuthArea = document.getElementById("tiktokAuthArea");
const localModal = document.getElementById("localModal");
const driveModal = document.getElementById("driveModal");
const openLocalBtn = document.getElementById("openLocalBtn");
const openDriveBtn = document.getElementById("openDriveBtn");
const closeLocalModal = document.getElementById("closeLocalModal");
const closeDriveModal = document.getElementById("closeDriveModal");
const localModalBackdrop = document.getElementById("localModalBackdrop");
const driveModalBackdrop = document.getElementById("driveModalBackdrop");
const dropZone = document.getElementById("dropZone");
const browseFilesBtn = document.getElementById("browseFilesBtn");
const clipsInput = document.getElementById("clips");
const localFilesList = document.getElementById("localFilesList");
const localFilesCount = document.getElementById("localFilesCount");
const confirmLocalBtn = document.getElementById("confirmLocalBtn");
const driveLoginPrompt = document.getElementById("driveLoginPrompt");
const driveBrowserContent = document.getElementById("driveBrowserContent");
const driveBreadcrumb = document.getElementById("driveBreadcrumb");
const driveContentsList = document.getElementById("driveContentsList");
const driveSelectedCount = document.getElementById("driveSelectedCount");
const confirmDriveBtn = document.getElementById("confirmDriveBtn");
const selectedFilesArea = document.getElementById("selectedFilesArea");
const selectedFilesLabel = document.getElementById("selectedFilesLabel");
const selectedFilesList = document.getElementById("selectedFilesList");
const changeFilesBtn = document.getElementById("changeFilesBtn");
const fileErrorBanner = document.getElementById("fileErrorBanner");
const musicPreset = document.getElementById("musicPreset");
const musicFile = document.getElementById("musicFile");
const versionsInput = document.getElementById("versions");
const styleInput = document.getElementById("style");
const promptContextInput = document.getElementById("promptContext");
const generateBtn = document.getElementById("generateBtn");
const downloadZipBtn = document.getElementById("downloadZipBtn");
const sendTiktokBtn = document.getElementById("sendTiktokBtn");
const tiktokStatusEl = document.getElementById("tiktokStatus");
const statusText = document.getElementById("statusText");
const progressSection = document.getElementById("progressSection");
const progressStep = document.getElementById("progressStep");
const progressPct = document.getElementById("progressPct");
const progressFill = document.getElementById("progressFill");
const driveUserBar = document.getElementById("driveUserBar");
const resultsEl = document.getElementById("results");
const stylePreviewText = document.getElementById("stylePreviewText");
const narratorToggle = document.getElementById("narratorToggle");
const textModeControl = document.getElementById("textModeControl");
const textModeHint = document.getElementById("textModeHint");

// ── State ─────────────────────────────────────────────────────────────────────
let currentUser = null;
let currentTiktokUser = null;
let uploadMode = null; // "local" | "drive"
let localPendingFiles = []; // File[] — en el modal, antes de confirmar
let confirmedLocalFiles = []; // File[] — confirmados
let driveSelectedFiles = {}; // { id: {id, name, size} } — seleccionados en Drive
let confirmedDriveFileIds = []; // string[] — IDs confirmados
let driveBreadcrumbState = [{ id: "root", name: "Mi unidad" }];

let selectedFonts = [];
let selectedEffects = [];
let currentTextMode = "two_lines";
let currentJobId = "";
let currentResults = [];
const removedVideos = new Set();

// ── Auth ──────────────────────────────────────────────────────────────────────
async function loadAuthStatus() {
  try {
    const [googleRes, tiktokRes] = await Promise.all([
      fetch("/api/auth/me"),
      fetch("/api/auth/tiktok/me"),
    ]);
    currentUser = googleRes.ok ? await googleRes.json() : null;
    currentTiktokUser = tiktokRes.ok ? await tiktokRes.json() : null;
  } catch (_) {
    currentUser = null;
    currentTiktokUser = null;
  }
  renderAuthHeader();
  renderTiktokAuth();
}

function renderAuthHeader() {
  const existing = authArea.querySelector(".google-auth-slot");
  if (existing) existing.remove();

  const slot = document.createElement("div");
  slot.className = "google-auth-slot";
  slot.style.display = "flex";
  slot.style.alignItems = "center";

  if (!currentUser) {
    const a = document.createElement("a");
    a.href = "/api/auth/login";
    a.className = "btn-login";
    a.textContent = "Iniciar sesión con Google";
    slot.appendChild(a);
  } else {
    const chip = document.createElement("div");
    chip.className = "user-chip";
    if (currentUser.picture) {
      const img = document.createElement("img");
      img.src = currentUser.picture;
      img.alt = currentUser.name || "Usuario";
      img.className = "user-avatar";
      chip.appendChild(img);
    }
    const name = document.createElement("span");
    name.className = "user-name";
    name.textContent = currentUser.name || currentUser.email || "Usuario";
    chip.appendChild(name);
    const logout = document.createElement("a");
    logout.href = "/api/auth/logout";
    logout.className = "btn-logout";
    logout.textContent = "Salir";
    chip.appendChild(logout);
    slot.appendChild(chip);
  }
  authArea.insertBefore(slot, tiktokAuthArea);
}

function renderTiktokAuth() {
  tiktokAuthArea.innerHTML = "";
  if (!currentTiktokUser) {
    const a = document.createElement("a");
    a.href = "/api/auth/tiktok/login";
    a.className = "btn-tiktok";
    a.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1V9.01a6.32 6.32 0 00-.79-.05 6.34 6.34 0 00-6.34 6.34 6.34 6.34 0 006.34 6.34 6.34 6.34 0 006.33-6.34V8.69a8.18 8.18 0 004.78 1.52V6.76a4.85 4.85 0 01-1.01-.07z"/></svg> Conectar TikTok`;
    tiktokAuthArea.appendChild(a);
  } else {
    const chip = document.createElement("div");
    chip.className = "tiktok-chip";
    const icon = document.createElement("span");
    icon.className = "tiktok-chip-icon";
    icon.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1V9.01a6.32 6.32 0 00-.79-.05 6.34 6.34 0 00-6.34 6.34 6.34 6.34 0 006.34 6.34 6.34 6.34 0 006.33-6.34V8.69a8.18 8.18 0 004.78 1.52V6.76a4.85 4.85 0 01-1.01-.07z"/></svg>`;
    const name = document.createElement("span");
    name.className = "user-name";
    name.textContent = currentTiktokUser.display_name || "TikTok";
    const logout = document.createElement("a");
    logout.href = "/api/auth/tiktok/logout";
    logout.className = "btn-logout";
    logout.textContent = "Desconectar";
    chip.appendChild(icon);
    chip.appendChild(name);
    chip.appendChild(logout);
    tiktokAuthArea.appendChild(chip);
  }
}

// ── Error helper ──────────────────────────────────────────────────────────────
function showFileError(msg) {
  fileErrorBanner.textContent = msg;
  fileErrorBanner.hidden = false;
  setTimeout(() => { fileErrorBanner.hidden = true; }, 5000);
}

function hideFileError() {
  fileErrorBanner.hidden = true;
}

// ── Modal helpers ─────────────────────────────────────────────────────────────
function openModal(modal) {
  modal.hidden = false;
  document.body.classList.add("modal-open");
}

function closeModal(modal) {
  modal.hidden = true;
  document.body.classList.remove("modal-open");
}

// ── Local upload modal ────────────────────────────────────────────────────────
function isVideoFile(file) {
  const ext = "." + file.name.split(".").pop().toLowerCase();
  return ALLOWED_VIDEO_EXTS.has(ext);
}

function formatSize(bytes) {
  return bytes > 0 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : "tamaño desconocido";
}

function addLocalFiles(files) {
  const newFiles = Array.from(files);
  const errors = [];
  const valid = [];

  newFiles.forEach((f) => {
    if (!isVideoFile(f)) {
      errors.push(`"${f.name}" no es un video (solo MP4/MOV)`);
    } else if (f.size / 1024 / 1024 > MAX_SIZE_MB) {
      errors.push(`"${f.name}" supera el límite de ${MAX_SIZE_MB} MB`);
    } else {
      valid.push(f);
    }
  });

  const combined = [...localPendingFiles, ...valid];
  if (combined.length > MAX_CLIPS) {
    errors.push(`Solo se permiten hasta ${MAX_CLIPS} clips. Se ignoraron los extras.`);
    localPendingFiles = combined.slice(0, MAX_CLIPS);
  } else {
    localPendingFiles = combined;
  }

  if (errors.length > 0) {
    renderLocalModalError(errors);
  }

  renderLocalFilesList();
}

function renderLocalModalError(errors) {
  const existing = localFilesList.querySelector(".modal-error");
  if (existing) existing.remove();
  const div = document.createElement("div");
  div.className = "modal-error";
  div.innerHTML = errors.map((e) => `<span>⚠️ ${e}</span>`).join("");
  localFilesList.prepend(div);
  setTimeout(() => div.remove(), 6000);
}

function renderLocalFilesList() {
  // Remove existing items (keep error if present)
  localFilesList.querySelectorAll(".modal-file-item").forEach((el) => el.remove());

  localPendingFiles.forEach((file, idx) => {
    const item = document.createElement("div");
    item.className = "modal-file-item";

    const icon = document.createElement("span");
    icon.className = "file-item-icon";
    icon.textContent = "🎬";

    const info = document.createElement("div");
    info.className = "file-item-info";
    const nameEl = document.createElement("span");
    nameEl.className = "file-item-name";
    nameEl.textContent = file.name;
    const sizeEl = document.createElement("span");
    sizeEl.className = "file-item-size";
    sizeEl.textContent = formatSize(file.size);
    info.appendChild(nameEl);
    info.appendChild(sizeEl);

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "file-item-remove";
    removeBtn.textContent = "✕";
    removeBtn.title = "Quitar";
    removeBtn.addEventListener("click", () => {
      localPendingFiles.splice(idx, 1);
      renderLocalFilesList();
    });

    item.appendChild(icon);
    item.appendChild(info);
    item.appendChild(removeBtn);
    localFilesList.appendChild(item);
  });

  const count = localPendingFiles.length;
  localFilesCount.textContent = count === 0 ? "Sin archivos seleccionados" : `${count} video${count > 1 ? "s" : ""} listo${count > 1 ? "s" : ""}`;
  confirmLocalBtn.disabled = count === 0;
}

function openLocalModal() {
  localPendingFiles = [...confirmedLocalFiles];
  localFilesList.innerHTML = "";
  renderLocalFilesList();
  openModal(localModal);
}

clipsInput.addEventListener("change", () => {
  if (clipsInput.files && clipsInput.files.length > 0) {
    addLocalFiles(clipsInput.files);
    clipsInput.value = "";
  }
});

browseFilesBtn.addEventListener("click", () => clipsInput.click());
openLocalBtn.addEventListener("click", openLocalModal);
closeLocalModal.addEventListener("click", () => closeModal(localModal));
localModalBackdrop.addEventListener("click", () => closeModal(localModal));

dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("dragging");
});
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragging"));
dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragging");
  if (e.dataTransfer.files.length > 0) addLocalFiles(e.dataTransfer.files);
});

confirmLocalBtn.addEventListener("click", () => {
  confirmedLocalFiles = [...localPendingFiles];
  confirmedDriveFileIds = [];
  uploadMode = "local";
  closeModal(localModal);
  renderSelectedFiles();
});

// ── Drive browser modal ───────────────────────────────────────────────────────
function _showDriveSection(section) {
  driveLoginPrompt.hidden = section !== "login";
  driveBrowserContent.hidden = section !== "browser";
  driveUserBar.hidden = section !== "browser";
}

async function openDriveModal() {
  openModal(driveModal);
  driveSelectedFiles = {};
  updateDriveSelectedCount();
  _showDriveSection("none");
  driveContentsList.innerHTML = `<div class="drive-loading"><span class="spinner"></span> Verificando sesión...</div>`;

  try {
    const res = await fetch("/api/auth/me");
    currentUser = res.ok ? await res.json() : null;
  } catch (_) { currentUser = null; }

  renderAuthHeader();

  if (!currentUser) {
    _showDriveSection("login");
  } else {
    // Render user bar inside modal
    driveUserBar.innerHTML = "";
    if (currentUser.picture) {
      const img = document.createElement("img");
      img.src = currentUser.picture;
      img.alt = currentUser.name || "";
      driveUserBar.appendChild(img);
    }
    const nameSpan = document.createElement("span");
    nameSpan.textContent = `Conectado como ${currentUser.name || currentUser.email}`;
    driveUserBar.appendChild(nameSpan);
    const logoutLink = document.createElement("a");
    logoutLink.href = "/api/auth/logout";
    logoutLink.className = "btn-logout";
    logoutLink.style.marginLeft = "auto";
    logoutLink.textContent = "Salir";
    driveUserBar.appendChild(logoutLink);

    _showDriveSection("browser");
    driveBreadcrumbState = [{ id: "root", name: "Mi unidad" }];
    renderDriveBreadcrumb();
    loadDriveContents("root");
  }
}

openDriveBtn.addEventListener("click", openDriveModal);
closeDriveModal.addEventListener("click", () => closeModal(driveModal));
driveModalBackdrop.addEventListener("click", () => closeModal(driveModal));

function renderDriveBreadcrumb() {
  driveBreadcrumb.innerHTML = "";
  driveBreadcrumbState.forEach((crumb, idx) => {
    if (idx > 0) {
      const sep = document.createElement("span");
      sep.className = "crumb-sep";
      sep.textContent = "/";
      driveBreadcrumb.appendChild(sep);
    }
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "crumb-btn" + (idx === driveBreadcrumbState.length - 1 ? " crumb-active" : "");
    btn.textContent = crumb.name;
    if (idx < driveBreadcrumbState.length - 1) {
      btn.addEventListener("click", () => {
        driveBreadcrumbState = driveBreadcrumbState.slice(0, idx + 1);
        renderDriveBreadcrumb();
        loadDriveContents(crumb.id);
      });
    }
    driveBreadcrumb.appendChild(btn);
  });
}

async function loadDriveContents(parentId) {
  driveContentsList.innerHTML = `<div class="drive-loading"><span class="spinner"></span> Cargando...</div>`;
  try {
    const res = await fetch(`/api/drive/contents?parent=${encodeURIComponent(parentId)}`);
    if (!res.ok) {
      const err = await getErrorMessage(res);
      driveContentsList.innerHTML = `<div class="drive-error">❌ ${err}</div>`;
      return;
    }
    const payload = await res.json();
    const folders = Array.isArray(payload.folders) ? payload.folders : [];
    const files = Array.isArray(payload.files) ? payload.files : [];
    renderDriveContents(folders, files);
  } catch (err) {
    driveContentsList.innerHTML = `<div class="drive-error">❌ Error: ${err.message}</div>`;
  }
}

function renderDriveContents(folders, files) {
  driveContentsList.innerHTML = "";

  if (folders.length === 0 && files.length === 0) {
    driveContentsList.innerHTML = `<div class="drive-empty">Carpeta vacía — no hay carpetas ni videos aquí.</div>`;
    return;
  }

  // Carpetas
  folders.forEach((folder) => {
    const item = document.createElement("div");
    item.className = "drive-item drive-folder";

    const icon = document.createElement("span");
    icon.className = "drive-item-icon";
    icon.textContent = "📁";

    const label = document.createElement("span");
    label.className = "drive-item-name";
    label.textContent = folder.name;

    const arrow = document.createElement("span");
    arrow.className = "drive-item-arrow";
    arrow.textContent = "›";

    item.appendChild(icon);
    item.appendChild(label);
    item.appendChild(arrow);
    item.addEventListener("click", () => {
      driveBreadcrumbState.push({ id: folder.id, name: folder.name });
      renderDriveBreadcrumb();
      loadDriveContents(folder.id);
    });
    driveContentsList.appendChild(item);
  });

  // Archivos de video
  files.forEach((file) => {
    const item = document.createElement("label");
    item.className = "drive-item drive-file";
    if (driveSelectedFiles[file.id]) item.classList.add("drive-file-selected");

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "drive-file-check";
    checkbox.checked = Boolean(driveSelectedFiles[file.id]);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) {
        driveSelectedFiles[file.id] = file;
        item.classList.add("drive-file-selected");
      } else {
        delete driveSelectedFiles[file.id];
        item.classList.remove("drive-file-selected");
      }
      updateDriveSelectedCount();
    });

    const icon = document.createElement("span");
    icon.className = "drive-item-icon";
    icon.textContent = "🎬";

    const info = document.createElement("div");
    info.className = "drive-item-info";

    const name = document.createElement("span");
    name.className = "drive-item-name";
    name.textContent = file.name;

    const size = document.createElement("span");
    size.className = "drive-item-size";
    const sizeMb = Number(file.size || 0);
    size.textContent = sizeMb > 0 ? formatSize(sizeMb) : "";

    info.appendChild(name);
    info.appendChild(size);

    item.appendChild(checkbox);
    item.appendChild(icon);
    item.appendChild(info);
    driveContentsList.appendChild(item);
  });
}

function updateDriveSelectedCount() {
  const count = Object.keys(driveSelectedFiles).length;
  driveSelectedCount.textContent = count === 0 ? "0 videos seleccionados" : `${count} video${count > 1 ? "s" : ""} seleccionado${count > 1 ? "s" : ""}`;
  confirmDriveBtn.disabled = count === 0;
}

confirmDriveBtn.addEventListener("click", () => {
  confirmedDriveFileIds = Object.keys(driveSelectedFiles);
  confirmedLocalFiles = [];
  uploadMode = "drive";
  closeModal(driveModal);
  renderSelectedFiles();
});

// ── Selected files display ────────────────────────────────────────────────────
function renderSelectedFiles() {
  hideFileError();
  if (uploadMode === "local" && confirmedLocalFiles.length > 0) {
    selectedFilesArea.hidden = false;
    selectedFilesLabel.textContent = `${confirmedLocalFiles.length} video${confirmedLocalFiles.length > 1 ? "s" : ""} desde tu PC`;
    selectedFilesList.innerHTML = "";
    confirmedLocalFiles.forEach((file) => {
      const li = document.createElement("li");
      li.className = "sel-file-item";
      li.innerHTML = `<span class="sel-file-icon">🎬</span><span class="sel-file-name">${file.name}</span><span class="sel-file-size">${formatSize(file.size)}</span>`;
      selectedFilesList.appendChild(li);
    });
    changeFilesBtn.onclick = openLocalModal;
  } else if (uploadMode === "drive" && confirmedDriveFileIds.length > 0) {
    selectedFilesArea.hidden = false;
    const count = confirmedDriveFileIds.length;
    selectedFilesLabel.textContent = `${count} video${count > 1 ? "s" : ""} desde Google Drive`;
    selectedFilesList.innerHTML = "";
    confirmedDriveFileIds.forEach((id) => {
      const file = driveSelectedFiles[id];
      const li = document.createElement("li");
      li.className = "sel-file-item";
      li.innerHTML = `<span class="sel-file-icon">☁️</span><span class="sel-file-name">${file?.name || id}</span><span class="sel-file-size">${file ? formatSize(Number(file.size || 0)) : ""}</span>`;
      selectedFilesList.appendChild(li);
    });
    changeFilesBtn.onclick = openDriveModal;
  } else {
    selectedFilesArea.hidden = true;
  }
}

// ── Text mode ─────────────────────────────────────────────────────────────────
const TEXT_MODE_HINTS = {
  two_lines: "Dos frases en distintas posiciones del video",
  one_big: "Una sola frase grande centrada verticalmente",
};

textModeControl.querySelectorAll(".seg-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    textModeControl.querySelectorAll(".seg-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentTextMode = btn.dataset.value;
    textModeHint.textContent = TEXT_MODE_HINTS[currentTextMode] || "";
  });
});

// ── Multi-select ──────────────────────────────────────────────────────────────
function summaryText(selectedCount, totalCount, firstLabel) {
  if (selectedCount === 0) return "Haz clic para elegir";
  if (selectedCount === totalCount) return "Todos seleccionados";
  if (selectedCount === 1) return firstLabel;
  return `${selectedCount} seleccionados`;
}

function createMultiSelect({ rootId, triggerId, menuId, optionsId, selectAllId, clearId, closeId, options, useFontPreview = false, onChange }) {
  const root = document.getElementById(rootId);
  const trigger = document.getElementById(triggerId);
  const menu = document.getElementById(menuId);
  const optionsWrap = document.getElementById(optionsId);
  const selectAllBtn = document.getElementById(selectAllId);
  const clearBtn = document.getElementById(clearId);
  const closeBtn = document.getElementById(closeId);
  const labelEl = root?.querySelector(".multi-select-label");
  const selected = new Set();

  function updateTrigger() {
    const firstSelected = options.find((item) => selected.has(item.value));
    trigger.textContent = summaryText(selected.size, options.length, firstSelected?.label || "");
  }

  function renderOptions() {
    optionsWrap.innerHTML = "";
    options.forEach((item) => {
      const lbl = document.createElement("label");
      lbl.className = "menu-option";
      const check = document.createElement("input");
      check.type = "checkbox";
      check.checked = selected.has(item.value);
      check.addEventListener("change", () => {
        if (check.checked) selected.add(item.value);
        else selected.delete(item.value);
        lbl.classList.toggle("selected", check.checked);
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
      lbl.classList.toggle("selected", check.checked);
      lbl.appendChild(check);
      lbl.appendChild(text);
      optionsWrap.appendChild(lbl);
    });
  }

  function getSelectedValues() {
    return options.filter((item) => selected.has(item.value)).map((item) => item.value);
  }

  function openMenu() {
    document.querySelectorAll(".multi-select-menu").forEach((m) => { if (m !== menu) m.hidden = true; });
    document.querySelectorAll(".multi-select").forEach((r) => { if (r !== root) r.classList.remove("open"); });
    document.querySelectorAll(".multi-select-trigger").forEach((t) => { if (t !== trigger) t.setAttribute("aria-expanded", "false"); });
    menu.hidden = false;
    root.classList.add("open");
    trigger.setAttribute("aria-expanded", "true");
    document.body.classList.add("modal-open");
  }

  function closeMenu() {
    menu.hidden = true;
    root.classList.remove("open");
    trigger.setAttribute("aria-expanded", "false");
    if (!document.querySelector(".multi-select.open")) document.body.classList.remove("modal-open");
  }

  trigger.addEventListener("click", (e) => { e.stopPropagation(); menu.hidden ? openMenu() : closeMenu(); });
  trigger.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); menu.hidden ? openMenu() : closeMenu(); } });
  if (labelEl) labelEl.addEventListener("click", (e) => { e.stopPropagation(); menu.hidden ? openMenu() : closeMenu(); });
  selectAllBtn.addEventListener("click", (e) => { e.stopPropagation(); options.forEach((item) => selected.add(item.value)); renderOptions(); updateTrigger(); onChange(getSelectedValues()); });
  clearBtn.addEventListener("click", (e) => { e.stopPropagation(); selected.clear(); renderOptions(); updateTrigger(); onChange(getSelectedValues()); });
  if (closeBtn) closeBtn.addEventListener("click", (e) => { e.stopPropagation(); closeMenu(); });
  menu.addEventListener("click", (e) => { if (e.target === menu) { closeMenu(); return; } e.stopPropagation(); });
  document.addEventListener("click", (e) => { if (!root.contains(e.target)) closeMenu(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeMenu(); });

  updateTrigger();
  renderOptions();

  return {
    getSelectedValues,
    setValues(values) {
      selected.clear();
      values.forEach((v) => selected.add(v));
      renderOptions(); updateTrigger(); onChange(getSelectedValues());
    },
  };
}

const fontSelect = createMultiSelect({
  rootId: "fontSelectRoot", triggerId: "fontTrigger", menuId: "fontMenu",
  optionsId: "fontOptions", selectAllId: "fontSelectAll", clearId: "fontClear", closeId: "fontClose",
  options: FONT_OPTIONS, useFontPreview: true,
  onChange(values) { selectedFonts = values; refreshPreview(); },
});

const effectSelect = createMultiSelect({
  rootId: "effectSelectRoot", triggerId: "effectTrigger", menuId: "effectMenu",
  optionsId: "effectOptions", selectAllId: "effectSelectAll", clearId: "effectClear", closeId: "effectClose",
  options: EFFECT_OPTIONS,
  onChange(values) { selectedEffects = values; },
});

function refreshPreview() {
  const first = FONT_OPTIONS.find((item) => item.value === selectedFonts[0]);
  stylePreviewText.style.fontFamily = first?.family || "'Space Grotesk', sans-serif";
  stylePreviewText.style.fontWeight = first?.weight || "800";
}
refreshPreview();

// ── Presets & TikTok ──────────────────────────────────────────────────────────
async function loadPresets() {
  try {
    const res = await fetch("/api/music-presets");
    if (!res.ok) return;
    const presets = await res.json();
    presets.forEach((preset) => {
      const option = document.createElement("option");
      option.value = preset.filename;
      option.textContent = preset.name;
      musicPreset.appendChild(option);
    });
  } catch (_) {}
}

async function getErrorMessage(res) {
  const ct = (res.headers.get("content-type") || "").toLowerCase();
  if (ct.includes("application/json")) {
    try { const p = await res.json(); return p.detail || p.message || `Error ${res.status}`; } catch (_) { return `Error ${res.status}`; }
  }
  try { const t = (await res.text()).trim(); return t || `Error ${res.status}`; } catch (_) { return `Error ${res.status}`; }
}

async function loadTiktokStatus() {
  try {
    const res = await fetch("/api/tiktok/status");
    if (!res.ok) { tiktokStatusEl.textContent = ""; return; }
    const payload = await res.json();
    if (payload.connected) {
      tiktokStatusEl.textContent = `Cuenta conectada: ${currentTiktokUser?.display_name || "TikTok"}`;
      sendTiktokBtn.disabled = false;
    } else {
      tiktokStatusEl.textContent = "Conecta tu cuenta TikTok desde el header para enviar drafts.";
      sendTiktokBtn.disabled = true;
    }
  } catch (_) { tiktokStatusEl.textContent = ""; }
}

// ── Results ───────────────────────────────────────────────────────────────────
function setStatus(text) { statusText.textContent = text; }

function getSelectedResultFilenames() {
  return currentResults.map((item) => item.filename).filter((f) => !removedVideos.has(f));
}

function setActionButtonsEnabled(enabled) {
  downloadZipBtn.disabled = !enabled;
  sendTiktokBtn.disabled = !enabled;
}

function gridColumnsForCount(count) {
  if (count <= 2) return "1fr";
  if (count <= 4) return "repeat(2, 1fr)";
  return "repeat(3, 1fr)";
}

function renderResults(payload) {
  currentJobId = payload.job_id;
  currentResults = payload.results || [];
  removedVideos.clear();
  resultsEl.innerHTML = "";
  resultsEl.style.gridTemplateColumns = gridColumnsForCount(currentResults.length);

  payload.results.forEach((item) => {
    const card = document.createElement("div");
    card.className = "result-card";
    card.dataset.filename = item.filename;

    const titleRow = document.createElement("div");
    titleRow.className = "result-card-title";
    titleRow.textContent = `Versión ${item.variant_index}`;

    const preview = document.createElement("video");
    preview.className = "result-preview";
    preview.src = item.download_url;
    preview.controls = true;
    preview.preload = "metadata";

    const textInfo = document.createElement("div");
    textInfo.className = "result-text-info";
    if (item.overlay_text_1) {
      const p = document.createElement("p");
      p.className = "overlay-preview";
      p.textContent = `Texto 1: ${item.overlay_text_1}`;
      textInfo.appendChild(p);
    }
    if (item.overlay_text_2) {
      const p = document.createElement("p");
      p.className = "overlay-preview";
      p.textContent = `Texto 2: ${item.overlay_text_2}`;
      textInfo.appendChild(p);
    }
    if (item.centered_text) {
      const p = document.createElement("p");
      p.className = "overlay-preview";
      p.textContent = `Centrado: ${item.centered_text}`;
      textInfo.appendChild(p);
    }

    const actionsRow = document.createElement("div");
    actionsRow.className = "result-card-actions";

    const copyBtn = document.createElement("button");
    copyBtn.className = "copy-btn";
    copyBtn.textContent = "Copiar caption";
    copyBtn.type = "button";
    copyBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(item.caption);
        copyBtn.textContent = "¡Copiado!";
        setTimeout(() => { copyBtn.textContent = "Copiar caption"; }, 1400);
      } catch (_) { copyBtn.textContent = "No se pudo copiar"; }
    });

    const dlLink = document.createElement("a");
    dlLink.href = item.download_url;
    dlLink.className = "btn-download-single";
    dlLink.textContent = "Descargar";
    dlLink.download = item.filename;

    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "delete-btn";
    delBtn.textContent = "Eliminar";
    delBtn.addEventListener("click", async () => {
      delBtn.disabled = true;
      try {
        await fetch(`/api/videos/${currentJobId}/${item.filename}`, { method: "DELETE" });
        card.remove();
        removedVideos.add(item.filename);
        currentResults = currentResults.filter((r) => r.filename !== item.filename);
        resultsEl.style.gridTemplateColumns = gridColumnsForCount(currentResults.length);
        setActionButtonsEnabled(getSelectedResultFilenames().length > 0);
      } catch (err) {
        delBtn.disabled = false;
        setStatus(`Error eliminando: ${err.message}`);
      }
    });

    actionsRow.appendChild(copyBtn);
    actionsRow.appendChild(dlLink);
    actionsRow.appendChild(delBtn);
    card.appendChild(titleRow);
    card.appendChild(preview);
    card.appendChild(textInfo);
    card.appendChild(actionsRow);
    resultsEl.appendChild(card);
  });

  setActionButtonsEnabled(currentResults.length > 0);
}

// ── ZIP download ──────────────────────────────────────────────────────────────
async function downloadSelectedZip() {
  if (!currentJobId) { setStatus("Genera videos primero para descargar ZIP."); return; }
  const filenames = getSelectedResultFilenames();
  if (filenames.length === 0) { setStatus("No hay videos para ZIP."); return; }
  try {
    const res = await fetch(`/api/download-zip/${currentJobId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filenames }),
    });
    if (!res.ok) throw new Error(await getErrorMessage(res));
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${currentJobId}_videos.zip`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setStatus("ZIP descargado correctamente.");
  } catch (err) {
    setStatus(`Fallo en ZIP: ${err.message}`);
  }
}

// ── TikTok ────────────────────────────────────────────────────────────────────
async function sendSelectedToTiktokDrafts() {
  if (!currentJobId) { setStatus("Genera videos primero."); return; }
  if (!currentTiktokUser) {
    setStatus("Conecta tu cuenta TikTok desde el header (botón 'Conectar TikTok') para enviar drafts.");
    return;
  }
  const filenames = getSelectedResultFilenames();
  if (filenames.length === 0) { setStatus("No hay videos seleccionados."); return; }
  sendTiktokBtn.disabled = true;
  try {
    const res = await fetch(`/api/tiktok/drafts/${currentJobId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filenames }),
    });
    if (!res.ok) throw new Error(await getErrorMessage(res));
    const payload = await res.json();
    setStatus(`TikTok drafts: ${payload.sent}/${payload.attempted} enviados a ${currentTiktokUser.display_name}.`);
    await loadTiktokStatus();
  } catch (err) {
    setStatus(`Fallo en TikTok: ${err.message}`);
  } finally {
    setActionButtonsEnabled(getSelectedResultFilenames().length > 0);
  }
}

// ── Progress bar ──────────────────────────────────────────────────────────────
function showProgress(step, pct) {
  progressSection.hidden = false;
  progressStep.textContent = step;
  const p = Math.round(pct * 100);
  progressPct.textContent = `${p}%`;
  progressFill.style.width = `${p}%`;
}

function hideProgress() {
  progressSection.hidden = true;
  progressFill.style.width = "0%";
}

let _pollTimer = null;

async function pollJobStatus(jobId) {
  try {
    const res = await fetch(`/api/jobs/${jobId}`);
    if (!res.ok) { setStatus("Error al verificar progreso."); stopPolling(); return; }
    const job = await res.json();

    showProgress(job.step || "Procesando...", job.progress || 0);

    if (job.status === "done") {
      stopPolling();
      hideProgress();
      renderResults(job.result);
      setStatus(`Listo: ${job.result.generated_versions} videos generados.`);
      generateBtn.disabled = false;
    } else if (job.status === "error") {
      stopPolling();
      hideProgress();
      setStatus(`Error: ${job.error}`);
      generateBtn.disabled = false;
    }
  } catch (_) {
    // silent — keep polling
  }
}

function stopPolling() {
  if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
}

// ── Generate ──────────────────────────────────────────────────────────────────
generateBtn.addEventListener("click", async () => {
  if (uploadMode === "local") {
    if (confirmedLocalFiles.length === 0) { showFileError("Sube al menos un video desde tu PC antes de generar."); return; }
  } else if (uploadMode === "drive") {
    if (confirmedDriveFileIds.length === 0) { showFileError("Selecciona al menos un video desde Google Drive antes de generar."); return; }
  } else {
    showFileError("Selecciona videos desde tu PC o Google Drive antes de generar.");
    return;
  }

  const versions = Number(versionsInput.value || 1);
  if (versions < 1 || versions > 10) { setStatus("La cantidad de versiones debe ser entre 1 y 10."); return; }

  selectedFonts = fontSelect.getSelectedValues();
  selectedEffects = effectSelect.getSelectedValues();
  if (selectedFonts.length === 0 || selectedEffects.length === 0) {
    setStatus("Debes seleccionar al menos 1 fuente y 1 efecto.");
    return;
  }

  generateBtn.disabled = true;
  setStatus("");
  resultsEl.innerHTML = "";
  stopPolling();
  showProgress("Enviando archivos...", 0.02);

  const formData = new FormData();
  if (uploadMode === "local") {
    confirmedLocalFiles.forEach((file) => formData.append("clips", file));
  } else {
    formData.append("drive_file_ids", JSON.stringify(confirmedDriveFileIds));
  }
  formData.append("versions", String(versions));
  formData.append("style", styleInput.value);
  formData.append("prompt_context", promptContextInput.value || "");
  formData.append("drive_folder_id", "");
  formData.append("text_bold", "true");
  formData.append("text_mode", currentTextMode);
  formData.append("narrator", narratorToggle.checked ? "true" : "false");
  selectedFonts.forEach((font) => formData.append("text_fonts", font));
  selectedEffects.forEach((effect) => formData.append("text_effects", effect));
  if (musicPreset.value) formData.append("music_preset", musicPreset.value);
  if (musicFile.files?.[0]) formData.append("music_file", musicFile.files[0]);

  try {
    const res = await fetch("/api/generate", { method: "POST", body: formData });
    if (!res.ok) throw new Error(await getErrorMessage(res));
    const { job_id } = await res.json();
    showProgress("Procesando clips...", 0.05);
    _pollTimer = setInterval(() => pollJobStatus(job_id), 800);
  } catch (err) {
    hideProgress();
    setStatus(`Fallo: ${err.message}`);
    generateBtn.disabled = false;
  }
});

downloadZipBtn.addEventListener("click", downloadSelectedZip);
sendTiktokBtn.addEventListener("click", sendSelectedToTiktokDrafts);

// ── Init ──────────────────────────────────────────────────────────────────────
setActionButtonsEnabled(false);
loadAuthStatus();
loadPresets();
loadTiktokStatus();
