/**
 * IFC Analyzer — Script Frontend
 * Gère l'upload, l'affichage des résultats, les filtres et le résumé.
 */

// ============================================================
// ÉLÉMENTS DOM
// ============================================================
const fileInput = document.getElementById("fileInput");
const selectFileBtn = document.getElementById("selectFileBtn");
const analyzeBtn = document.getElementById("analyzeBtn");
const fileNameDisplay = document.getElementById("fileName");
const loader = document.getElementById("loader");
const successMessage = document.getElementById("successMessage");
const warningsDiv = document.getElementById("warnings");
const summarySection = document.getElementById("summarySection");
const summaryCards = document.getElementById("summaryCards");
const typeCountSection = document.getElementById("typeCountSection");
const typeCountCards = document.getElementById("typeCountCards");
const filterSection = document.getElementById("filterSection");
const filterButtons = document.getElementById("filterButtons");
const tableSection = document.getElementById("tableSection");
const tableHead = document.getElementById("tableHead");
const tableBody = document.getElementById("tableBody");
const noResultsMsg = document.getElementById("noResultsMsg");
const exportAllPdfBtn = document.getElementById("exportAllPdfBtn");
const exportTypePdfBtn = document.getElementById("exportTypePdfBtn");
const sendToTrackerBtn = document.getElementById("sendToTrackerBtn");
const uploadCard = document.querySelector(".upload-card");

// ============================================================
// ÉTAT GLOBAL
// ============================================================
let allElements = [];
let currentFilter = "Tous";
let dbStatuses = {};

// Backend renvoie des types et statuts en français (clés canoniques) ;
// on les affiche en anglais via ces tables.
const TYPE_LABELS_EN = {
    "Tous":       "All",
    "Mur":        "Wall",
    "Mur rideau": "Curtain wall",
    "Porte":      "Door",
    "Fenêtre":    "Window",
    "Dalle":      "Slab",
    "Escalier":   "Stairs",
    "Toiture":    "Roof",
    "Poutre":     "Beam",
    "Poteau":     "Column",
    "Inconnu":    "Unknown",
};
function typeLabel(t) { return TYPE_LABELS_EN[t] || t || "—"; }

const STATUS_LABELS_EN = {
    "in_building":  "In building",
    "démonté":      "Dismantled",
    "transporté":   "In transit",
    "stocké":       "Stored",
    "réutilisé":    "Reused",
    "à réutiliser": "To reuse",
    "à recycler":   "To recycle",
};
function statusLabel(s) { return STATUS_LABELS_EN[s] || s; }

const _LS_KEY_LAST_EXTRACTION = "ifc_analyzer:last_extraction_v1";

// IndexedDB (quota >> localStorage : ~100Mo+ contre 5Mo)
const _IDB_NAME  = "ifc_analyzer_db";
const _IDB_STORE = "extractions";

function _openIdb() {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open(_IDB_NAME, 1);
        req.onupgradeneeded = () => {
            const db = req.result;
            if (!db.objectStoreNames.contains(_IDB_STORE)) {
                db.createObjectStore(_IDB_STORE);
            }
        };
        req.onsuccess = () => resolve(req.result);
        req.onerror   = () => reject(req.error);
    });
}

function saveLastExtraction(payload) {
    return _openIdb().then(db => new Promise((resolve, reject) => {
        const tx = db.transaction(_IDB_STORE, "readwrite");
        tx.objectStore(_IDB_STORE).put(payload, _LS_KEY_LAST_EXTRACTION);
        tx.oncomplete = () => { db.close(); resolve(); };
        tx.onerror    = () => { db.close(); reject(tx.error); };
    })).catch(err => console.warn("saveLastExtraction failed:", err));
}

function loadLastExtraction() {
    return _openIdb().then(db => new Promise((resolve, reject) => {
        const tx  = db.transaction(_IDB_STORE, "readonly");
        const req = tx.objectStore(_IDB_STORE).get(_LS_KEY_LAST_EXTRACTION);
        req.onsuccess = () => { db.close(); resolve(req.result || null); };
        req.onerror   = () => { db.close(); reject(req.error); };
    })).catch(err => { console.warn("loadLastExtraction failed:", err); return null; });
}

async function _purgeStoredExtraction() {
    try {
        const db = await _openIdb();
        const tx = db.transaction(_IDB_STORE, "readwrite");
        tx.objectStore(_IDB_STORE).delete(_LS_KEY_LAST_EXTRACTION);
        await new Promise((res) => { tx.oncomplete = res; tx.onerror = res; });
        db.close();
    } catch (e) { /* silencieux */ }
}

// Règles :
// - Refresh (F5/Ctrl+R) → on purge (l'utilisateur veut repartir à zéro)
// - Ouverture directe (URL tapée, bookmark, nouvel onglet) → on purge
// - Navigation depuis une autre page de l'app (clic sidebar) → on restaure
function _shouldRestoreExtraction() {
    try {
        const nav = performance.getEntriesByType("navigation")[0];
        const navType = nav ? nav.type : (performance.navigation && performance.navigation.type === 1 ? "reload" : "navigate");
        if (navType === "reload") return false;
        // Restaurer uniquement si on vient d'une autre page du même domaine
        if (document.referrer) {
            try {
                const ref = new URL(document.referrer);
                if (ref.origin === window.location.origin && ref.pathname !== window.location.pathname) {
                    return true;
                }
            } catch (_) {}
        }
        return false;
    } catch (e) {
        return false;
    }
}

async function restoreLastExtractionIfAny() {
    if (!_shouldRestoreExtraction()) {
        await _purgeStoredExtraction();
        return;
    }

    const saved = await loadLastExtraction();
    if (!saved || !Array.isArray(saved.elements) || saved.elements.length === 0) return;

    allElements = saved.elements;
    currentFilter = "Tous";

    showSuccessMessage(saved.message || "Extraction restored.");
    showWarnings(saved.avertissements || []);
    if (saved.resume) {
        showSummary(saved.resume);
        showTypeCount(saved.resume.par_type);
        showFilters(saved.resume.par_type);
    } else {
        // fallback : construire un résumé minimal si nécessaire
        const parType = allElements.reduce((acc, e) => {
            const t = e.type || "Inconnu";
            acc[t] = (acc[t] || 0) + 1;
            return acc;
        }, {});
        const resume = { total: allElements.length, par_type: parType };
        showSummary(resume);
        showTypeCount(parType);
        showFilters(parType);
    }

    showTable(allElements);
    // fetchDbStatuses() // Désactivé : les statuts tracker sont privés par utilisateur
}

// ============================================================
// EXPORT PDF
// ============================================================

exportAllPdfBtn.addEventListener("click",  e => showFormatPicker(e, exportAllToCsv,  () => exportAllToPdf()));
exportTypePdfBtn.addEventListener("click", e => showFormatPicker(e, exportTypeToCsv, () => exportTypeToPdf()));

function toCsvCell(value) {
    const str = typeof value === "string" ? value.replace(/<[^>]*>/g, "") : String(value ?? "");
    return `"${str.replace(/"/g, '""')}"`;
}

function buildCsv(cols, elems) {
    const header = cols.map(c => toCsvCell(c.header)).join(";");
    const rows = elems.map(e =>
        cols.map(c => toCsvCell(c.value(e))).join(";")
    );
    return [header, ...rows].join("\r\n");
}

function downloadCsv(content, filename) {
    const bom = "\uFEFF";
    const blob = new Blob([bom + content], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

function exportAllToCsv() {
    const types = [...new Set(allElements.map(e => e.type))];
    const sections = types.map(typeName => {
        const elems = allElements.filter(e => e.type === typeName);
        const cols = getColumnsForType(typeName);
        return `${typeName}\r\n${buildCsv(cols, elems)}`;
    });
    downloadCsv(sections.join("\r\n\r\n"), "ifc-export-complet.csv");
}

function exportTypeToCsv() {
    const elems = currentFilter === "Tous"
        ? allElements
        : allElements.filter(e => e.type === currentFilter);
    const cols = getColumnsForType(currentFilter === "Tous" ? null : currentFilter);
    const filename = currentFilter === "Tous" ? "ifc-tous.csv" : `ifc-${currentFilter.toLowerCase()}.csv`;
    downloadCsv(buildCsv(cols, elems), filename);
}

// ============================================================
// FORMAT PICKER (CSV / PDF)
// ============================================================

function showFormatPicker(event, csvFn, pdfFn) {
    event.stopPropagation();
    document.querySelectorAll(".fmt-picker").forEach(el => el.remove());

    const btn  = event.currentTarget;
    const rect = btn.getBoundingClientRect();

    const picker = document.createElement("div");
    picker.className = "fmt-picker";
    picker.innerHTML = `
        <button class="fmt-opt" data-fmt="csv"><span>📄</span> CSV</button>
        <button class="fmt-opt" data-fmt="pdf"><span>📑</span> PDF</button>
    `;
    picker.style.cssText = `
        position:fixed;
        top:${rect.bottom + 4}px;
        left:${rect.left}px;
        z-index:9999;
        background:white;
        border:1px solid #d1d5db;
        border-radius:8px;
        box-shadow:0 4px 16px rgba(0,0,0,.15);
        display:flex;
        flex-direction:column;
        min-width:130px;
        overflow:hidden;
    `;

    picker.querySelector('[data-fmt="csv"]').addEventListener("click", e => {
        e.stopPropagation();
        picker.remove();
        csvFn();
    });
    picker.querySelector('[data-fmt="pdf"]').addEventListener("click", e => {
        e.stopPropagation();
        picker.remove();
        pdfFn();
    });

    document.body.appendChild(picker);
    setTimeout(() => document.addEventListener("click", () => picker.remove(), { once: true }));
}

// ── PDF helpers ──────────────────────────────────────────────

function buildTableData(cols, elems) {
    return {
        headers: cols.map(c => c.header),
        rows: elems.map(e => cols.map(c => {
            const v = c.value(e);
            return typeof v === "string" ? v.replace(/<[^>]*>/g, "") : String(v ?? "");
        })),
    };
}

async function downloadTablePdf(title, headers, rows, filename) {
    const res = await fetch("/api/export-table-pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, headers, rows, filename }),
    });
    if (!res.ok) { alert("PDF generation error."); return; }
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
}

function exportAllToPdf() {
    const types   = [...new Set(allElements.map(e => e.type))];
    const allCols = getColumnsForType(null);
    const { headers, rows } = buildTableData(allCols, allElements);
    downloadTablePdf("Full export — IFC Analyzer", headers, rows, "ifc-full-export.pdf");
}

function exportTypeToPdf() {
    const elems = currentFilter === "Tous"
        ? allElements
        : allElements.filter(e => e.type === currentFilter);
    const cols  = getColumnsForType(currentFilter === "Tous" ? null : currentFilter);
    const label = currentFilter === "Tous" ? "All elements" : typeLabel(currentFilter);
    const fname = currentFilter === "Tous" ? "ifc-all.pdf" : `ifc-${currentFilter.toLowerCase()}.pdf`;
    const { headers, rows } = buildTableData(cols, elems);
    downloadTablePdf(`Selection export — ${label}`, headers, rows, fname);
}

// ============================================================
// ENVOI DIRECT AU TRACKER (sans passer par un fichier JSON)
// ============================================================

sendToTrackerBtn.addEventListener("click", async () => {
    if (!allElements || allElements.length === 0) {
        alert("Nothing to send. Analyze an IFC file first.");
        return;
    }

    const projectName = prompt(
        "Project name to create in the Tracker:",
        `IFC Project - ${new Date().toLocaleDateString("en-GB")}`
    );
    if (projectName === null) return; // annulé

    const components = allElements.map(e => ({
        id: e.id || null,
        type: e.type || null,
        material: e.materiau || null,
        ifc_location: e.etage || null,
        status: "in_building",
        hauteur:    e.hauteur    ?? null,
        longueur:   e.longueur   ?? null,
        epaisseur:  e.epaisseur  ?? null,
        net_area:   e.net_area   ?? null,
        net_volume: e.net_volume ?? null,
    }));

    const orig = sendToTrackerBtn.innerHTML;
    sendToTrackerBtn.disabled = true;
    sendToTrackerBtn.innerHTML = `<i data-lucide="loader-2"></i> Sending…`;
    if (window.lucide) lucide.createIcons();

    try {
        const res = await fetch("/api/tracker/import", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                components,
                project_name: projectName.trim() || null,
            }),
        });
        if (!res.ok) {
            let msg = `HTTP ${res.status}`;
            try { const j = await res.json(); msg = j.detail || msg; } catch {}
            alert(`Send error: ${msg}`);
            return;
        }
        const data = await res.json();
        const created = data.created ?? components.length;
        const goTracker = confirm(
            `✅ Project "${data.project_name}" created with ${created} components.\n\n` +
            `Open the Tracker now?`
        );
        if (goTracker) window.location.href = "/tracker";
    } catch (err) {
        alert(`Network error: ${err.message}`);
    } finally {
        sendToTrackerBtn.disabled = false;
        sendToTrackerBtn.innerHTML = orig;
        if (window.lucide) lucide.createIcons();
    }
});

// ============================================================
// ÉVÉNEMENTS
// ============================================================

// Clic sur le bouton de sélection de fichier
selectFileBtn.addEventListener("click", () => fileInput.click());

// Sélection de fichier via input
fileInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) {
        handleFileSelected(file);
    }
});

// Clic sur le bouton d'analyse
analyzeBtn.addEventListener("click", () => {
    const file = fileInput.files[0];
    if (file) {
        uploadAndAnalyze(file);
    }
});

// Drag & Drop
uploadCard.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadCard.classList.add("drag-over");
});

uploadCard.addEventListener("dragleave", () => {
    uploadCard.classList.remove("drag-over");
});

uploadCard.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadCard.classList.remove("drag-over");
    const file = e.dataTransfer.files[0];
    if (file && file.name.toLowerCase().endsWith(".ifc")) {
        // Mettre à jour l'input file
        const dt = new DataTransfer();
        dt.items.add(file);
        fileInput.files = dt.files;
        handleFileSelected(file);
    } else {
        alert("Please drop a valid .ifc file.");
    }
});

// ============================================================
// FONCTIONS
// ============================================================

/**
 * Gère la sélection d'un fichier
 */
function handleFileSelected(file) {
    fileNameDisplay.textContent = `📄 ${file.name} (${formatFileSize(file.size)})`;
    analyzeBtn.disabled = false;
}

/**
 * Formate la taille d'un fichier
 */
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

/**
 * Upload et analyse du fichier IFC via l'API
 */
async function uploadAndAnalyze(file) {
    // Afficher le loader, masquer les anciens résultats
    showLoader(true);
    hideResults();

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch("/api/upload", {
            method: "POST",
            body: formData,
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Analysis error");
        }

        // Stocker les éléments
        allElements = data.elements;
        currentFilter = "Tous";

        // Persister l'extraction pour retrouver les données après navigation (/tracker → /)
        saveLastExtraction({
            message: data.message,
            avertissements: data.avertissements,
            resume: data.resume,
            elements: data.elements,
            saved_at: new Date().toISOString(),
        });

        // Afficher les résultats
        showSuccessMessage(data.message);
        showWarnings(data.avertissements);
        showSummary(data.resume);
        showTypeCount(data.resume.par_type);
        showFilters(data.resume.par_type);
        showTable(allElements);

        // Charger les statuts depuis la DB (async, ne bloque pas)
        fetchDbStatuses()

    } catch (error) {
        alert(`Error: ${error.message}`);
    } finally {
        showLoader(false);
    }
}

/**
 * Affiche ou masque le loader
 */
function showLoader(show) {
    loader.classList.toggle("hidden", !show);
}

/**
 * Masque tous les résultats
 */
function hideResults() {
    successMessage.classList.add("hidden");
    warningsDiv.classList.add("hidden");
    summarySection.classList.add("hidden");
    typeCountSection.classList.add("hidden");
    filterSection.classList.add("hidden");
    tableSection.classList.add("hidden");
}

/**
 * Affiche le message de succès
 */
function showSuccessMessage(message) {
    successMessage.innerHTML = `<i data-lucide="check-circle"></i> ${message}`;
    successMessage.classList.remove("hidden");
    lucide.createIcons();
}

/**
 * Affiche les avertissements (éléments manquants)
 */
function showWarnings(warnings) {
    if (!warnings || warnings.length === 0) {
        warningsDiv.classList.add("hidden");
        return;
    }

    warningsDiv.innerHTML = warnings
        .map(
            (w) => `<div class="warning-item"><i data-lucide="alert-triangle"></i> ${w}</div>`
        )
        .join("");
    warningsDiv.classList.remove("hidden");
    lucide.createIcons();
}

/**
 * Affiche le résumé global dans des cartes
 */
function showSummary(resume) {
    summaryCards.innerHTML = `
        <div class="stat-card">
            <div class="stat-value">${resume.total}</div>
            <div class="stat-label">Total elements</div>
        </div>
        <div class="stat-card gray">
            <div class="stat-value">${Object.keys(resume.par_type).length}</div>
            <div class="stat-label">Element types</div>
        </div>
    `;
    summarySection.classList.remove("hidden");
}

/**
 * Affiche le comptage par type dans des cartes
 */
function showTypeCount(parType) {
    if (!parType || Object.keys(parType).length === 0) {
        typeCountSection.classList.add("hidden");
        return;
    }

    // Couleurs par type
    const typeColors = {
        "Mur": "#2563eb",
        "Fenêtre": "#7c3aed",
        "Porte": "#d97706",
        "Dalle": "#0891b2",
        "Escalier": "#ea580c",
        "Mur rideau": "#059669",
    };

    typeCountCards.innerHTML = Object.entries(parType)
        .map(([type, count]) => {
            const color = typeColors[type] || "#6b7280";
            return `
                <div class="type-card" style="border-left-color: ${color}">
                    <span class="type-name">${typeLabel(type)}</span>
                    <span class="type-count" style="background: ${color}">${count}</span>
                </div>
            `;
        })
        .join("");

    typeCountSection.classList.remove("hidden");
}

/**
 * Affiche les boutons de filtre
 */
function showFilters(parType) {
    const types = ["Tous", ...Object.keys(parType)];

    filterButtons.innerHTML = types
        .map(
            (type) =>
                `<button class="filter-btn ${type === currentFilter ? "active" : ""}" 
                         data-type="${type}">${typeLabel(type)}</button>`
        )
        .join("");

    // Ajouter les événements de clic
    filterButtons.querySelectorAll(".filter-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            currentFilter = btn.dataset.type;
            // Mettre à jour l'état actif
            filterButtons.querySelectorAll(".filter-btn").forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            // Filtrer le tableau
            const filtered = currentFilter === "Tous"
                ? allElements
                : allElements.filter((e) => e.type === currentFilter);
            showTable(filtered);
        });
    });

    filterSection.classList.remove("hidden");
}

// Colonnes spécifiques par type (clés = valeurs canoniques fr coté backend)
const TYPE_COLUMNS = {
    "Mur": [
        { header: "Height (m)", value: e => formatDimension(e.hauteur) },
        { header: "Length (m)", value: e => formatDimension(e.longueur) },
        { header: "Thickness (m)", value: e => formatDimension(e.epaisseur) },
        { header: "Volume (m³)", value: e => e.volume != null ? e.volume + " m³" : "" },
    ],
    "Porte": [
        { header: "Height (m)", value: e => formatDimension(e.hauteur) },
        { header: "Length (m)", value: e => formatDimension(e.longueur) },
        { header: "Leaves", value: e => e.nb_battants != null ? e.nb_battants : "" },
    ],
    "Dalle": [
        { header: "NetArea (m²)", value: e => e.net_area != null ? e.net_area : "" },
        { header: "NetVolume (m³)", value: e => e.net_volume != null ? e.net_volume : "" },
        { header: "Width (m)", value: e => formatDimension(e.epaisseur) },
    ],
    "Escalier": [
        { header: "Risers", value: e => e.number_of_riser != null ? e.number_of_riser : "" },
        { header: "Treads", value: e => e.number_of_treads != null ? e.number_of_treads : "" },
        { header: "Tread length (m)", value: e => e.tread_length != null ? e.tread_length : "" },
        { header: "Riser height (m)", value: e => e.riser_height != null ? e.riser_height : "" },
    ],
    "Mur rideau": [],
};

// Colonnes par défaut (pour Tous, Fenêtre, Mur rideau, etc.)
const DEFAULT_COLUMNS = [
    { header: "Height (m)", value: e => formatDimension(e.hauteur) },
    { header: "Length (m)", value: e => formatDimension(e.longueur) },
    { header: "Thickness (m)", value: e => formatDimension(e.epaisseur) },
    { header: "Volume (m³)", value: e => e.volume != null ? e.volume + " m³" : "" },
];

// Statuts DB — badge coloré
const STATUS_COLORS_MAIN = {
    "in_building":  { bg: "#dbeafe", color: "#1e40af" },
    "démonté":       { bg: "#fef3c7", color: "#92400e" },
    "transporté":    { bg: "#e0e7ff", color: "#3730a3" },
    "stocké":        { bg: "#fce7f3", color: "#9d174d" },
    "réutilisé":     { bg: "#d1fae5", color: "#065f46" },
    "à réutiliser":  { bg: "#d1fae5", color: "#065f46" },
    "à recycler":    { bg: "#dcfce7", color: "#14532d" },
};

function getStatusBadge(elementId) {
    const s = dbStatuses[elementId];
    if (!s) return `<span style="font-size:.75rem;color:#9ca3af;">—</span>`;
    const c = STATUS_COLORS_MAIN[s] || { bg: "#f3f4f6", color: "#374151" };
    return `<span style="display:inline-block;padding:2px 10px;border-radius:999px;font-size:.75rem;font-weight:700;background:${c.bg};color:${c.color};white-space:nowrap;">${statusLabel(s)}</span>`;
}

async function fetchDbStatuses() {
    const ids = allElements.map(e => e.id).filter(Boolean);
    if (!ids.length) return;
    try {
        const res = await fetch("/api/tracker/statuses", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ids }),
        });
        if (!res.ok) return;
        dbStatuses = await res.json();
        // Re-rendre le tableau avec les statuts
        const visible = currentFilter === "Tous"
            ? allElements
            : allElements.filter(e => e.type === currentFilter);
        showTable(visible);
    } catch (_) {}
}

// Colonnes communes à tous les types
const COMMON_COLUMNS = [
    { header: "Name / ID", value: e => `<span title="${e.id}">${e.nom || e.id}</span>` },
    { header: "Type", value: e => typeLabel(e.type) },
    { header: "Floor", value: e => e.etage || "—" },
    { header: "Material", value: e => e.materiau || "Unknown" },
    { header: "Status", value: e => getStatusBadge(e.id) },
];

function getColumnsForType(typeName) {
    // "Tous" (typeName null) : uniquement les colonnes communes
    if (!typeName) {
        return [...COMMON_COLUMNS];
    }
    const specific = TYPE_COLUMNS[typeName] || DEFAULT_COLUMNS;
    return [...COMMON_COLUMNS, ...specific];
}

/**
 * Affiche le tableau des éléments avec colonnes dynamiques
 */
function showTable(elements) {
    if (!elements || elements.length === 0) {
        tableHead.innerHTML = "";
        tableBody.innerHTML = "";
        noResultsMsg.classList.remove("hidden");
        tableSection.classList.remove("hidden");
        return;
    }

    noResultsMsg.classList.add("hidden");

    // Déterminer les colonnes selon le filtre actif
    const columns = currentFilter !== "Tous"
        ? getColumnsForType(currentFilter)
        : getColumnsForType(null);

    // Générer le thead
    tableHead.innerHTML = `<tr>${columns.map(c => `<th>${c.header}</th>`).join("")}</tr>`;

    // Générer le tbody
    tableBody.innerHTML = elements
        .map((elem) => {
            const cells = columns.map(c => {
                const titleAttr = c.title ? ` title="${c.title(elem)}"` : "";
                return `<td${titleAttr}>${c.value(elem)}</td>`;
            }).join("");
            return `<tr>${cells}</tr>`;
        })
        .join("");

    tableSection.classList.remove("hidden");
}

/**
 * Crée un badge coloré (OUI = vert, NON = rouge, INCONNU = gris)
 */
function getBadge(value) {
    if (value === "OUI") {
        return `<span class="badge badge-oui">YES</span>`;
    } else if (value === "NON") {
        return `<span class="badge badge-non">NO</span>`;
    } else {
        return `<span class="badge badge-inconnu">UNKNOWN</span>`;
    }
}

/**
 * Formate une dimension (null → tiret)
 */
function formatDimension(value) {
    return value != null ? value : "";
}

/**
 * Crée un badge de score coloré avec mini barre de progression
 */
function getScoreBadge(score) {
    const percent = Math.round(score * 100);
    let colorClass = "score-low";
    if (score >= 0.7) colorClass = "score-high";
    else if (score >= 0.4) colorClass = "score-mid";

    return `
        <div class="score-badge ${colorClass}">
            <span class="score-value">${score}</span>
            <div class="score-bar-mini">
                <div class="score-bar-fill" style="width: ${percent}%"></div>
            </div>
        </div>
    `;
}

/**
 * Retourne la classe CSS pour une carte de score
 */
function getScoreCardClass(score) {
    if (score >= 0.7) return "green";
    if (score >= 0.4) return "orange";
    return "red";
}

/**
 * Crée une barre de progression pour les cartes résumé
 */
function getScoreBar(score) {
    const percent = Math.round(score * 100);
    let color = "var(--danger)";
    if (score >= 0.7) color = "var(--success)";
    else if (score >= 0.4) color = "var(--warning)";

    return `
        <div class="score-bar-container">
            <div class="score-bar-track">
                <div class="score-bar-fill-big" style="width: ${percent}%; background: ${color}"></div>
            </div>
            <span class="score-bar-label">${percent}%</span>
        </div>
    `;
}

// ============================================================
// INITIALISATION — Lucide icons
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
    lucide.createIcons();
});

// Restaurer automatiquement la dernière extraction (après définition de toutes les fonctions)
restoreLastExtractionIfAny();
