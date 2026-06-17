const bridge = window.AstrBotPluginPage;

const STATUS_LABELS = {
  normal: "已规范",
  pending_review: "待整改",
  needs_image_edit: "待优化图片",
};

const state = {
  loaded: null,
  draft: null,
  currentId: null,
  currentFilter: "all",
  search: "",
  statusTimer: null,
};

const els = {};

function $(id) { return document.getElementById(id); }
function clone(value) { return JSON.parse(JSON.stringify(value)); }
function escapeHtml(value) {
  return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}

function clearStatusTimer() {
  if (state.statusTimer) { window.clearTimeout(state.statusTimer); state.statusTimer = null; }
}

function setStatus(message, tone = "info", autoHide = tone === "success") {
  clearStatusTimer();
  const banner = els.statusBanner;
  if (!message) { banner.textContent = ""; banner.dataset.tone = ""; banner.classList.add("hidden"); return; }
  banner.textContent = message;
  banner.dataset.tone = tone;
  banner.classList.remove("hidden");
  if (autoHide) { state.statusTimer = window.setTimeout(() => setStatus(""), 2600); }
}

function getStrategies() { return state.draft?.strategies || []; }
function getCurrentStrategy() {
  if (!state.currentId) return null;
  return getStrategies().find((st) => st.id === state.currentId) || null;
}

function makeEmptyStrategy() {
  return { id: "", name: "", category: "", subcategory: "", trigger_words: [], status: "pending_review", text_content: "", image_paths: [] };
}

function filterStrategies() {
  let list = getStrategies();
  if (state.currentFilter === "normal") list = list.filter((st) => st.status === "normal");
  else if (state.currentFilter === "pending") list = list.filter((st) => st.status !== "normal");
  if (state.search) {
    const q = state.search.toLowerCase();
    list = list.filter((st) => {
      const joined = [st.name, st.category, st.subcategory, ...(st.trigger_words || []), st.text_content || ""].join(" ").toLowerCase();
      return joined.includes(q);
    });
  }
  return list;
}

function renderCategoryOptions() {
  const cats = state.draft?.categories || [];
  const select = els.categoryInput;
  select.innerHTML = '<option value="">-- 选择分类 --</option>';
  for (const cat of cats) select.innerHTML += `<option value="${escapeHtml(cat)}">${escapeHtml(cat)}</option>`;
}

function renderStrategyList() {
  const filtered = filterStrategies();
  els.listMeta.textContent = `${filtered.length} 篇攻略`;
  const container = els.strategyList;
  container.innerHTML = filtered.map((st) => {
    const badgeClass = st.status === "normal" ? "normal" : st.status === "pending_review" ? "pending" : "image-edit";
    const statusLabel = STATUS_LABELS[st.status] || "未知";
    return `<article class="strategy-card ${state.currentId === st.id ? "active" : ""}" data-strategy-id="${st.id}">
        <div class="strategy-card-head">
          <div class="strategy-card-title">${escapeHtml(st.name || "未命名攻略")}</div>
          <span class="badge ${badgeClass}">${statusLabel}</span>
        </div>
        <div class="strategy-card-meta">${escapeHtml(st.category || "未分类")} | ${(st.trigger_words || []).join(", ") || "无触发词"}</div>
      </article>`;
  }).join("");

  for (const node of container.querySelectorAll("[data-strategy-id]")) {
    node.addEventListener("click", () => selectStrategy(node.dataset.strategyId));
  }
}

function renderEditor() {
  const st = getCurrentStrategy();
  if (!st) { els.emptyState.classList.remove("hidden"); els.editor.classList.add("hidden"); return; }
  els.emptyState.classList.add("hidden"); els.editor.classList.remove("hidden");

  els.editorEyebrow.textContent = `ID: ${st.id || "(新建)"}`;
  els.editorTitle.textContent = st.name || "未命名攻略";
  els.nameInput.value = st.name || "";
  els.categoryInput.value = st.category || "";
  els.subcategoryInput.value = st.subcategory || "";
  els.statusInput.value = st.status || "pending_review";
  els.textContentInput.value = st.text_content || "";

  renderTagList();
  renderImagePreview();
  updateStats();
}

function renderTagList() {
  const st = getCurrentStrategy();
  const container = els.triggerWordsContainer;
  if (!container) return;
  container.innerHTML = "";
  for (const val of (st.trigger_words || [])) {
    const tag = document.createElement("span");
    tag.className = "keyword-tag";
    tag.textContent = val;
    tag.addEventListener("click", () => {
      st.trigger_words = st.trigger_words.filter((v) => v !== val);
      renderTagList();
    });
    tag.title = "点击移除";
    container.appendChild(tag);
  }
}

function addTriggerWord() {
  const st = getCurrentStrategy();
  if (!st) return;
  const kw = els.triggerWordInput.value.trim();
  if (!kw) return;
  if ((st.trigger_words || []).includes(kw)) { setStatus("触发词已存在", "error", true); return; }
  (st.trigger_words = st.trigger_words || []).push(kw);
  els.triggerWordInput.value = "";
  renderTagList();
}

function renderImagePreview() {
  const st = getCurrentStrategy();
  const container = els.imagePreviewContainer;
  const paths = st.image_paths || [];
  if (!paths.length) { container.innerHTML = '<div class="inline-hint">暂无图片</div>'; return; }
  let html = '<div style="display:flex;flex-wrap:wrap;gap:10px;">';
  for (let i = 0; i < paths.length; i++) {
    html += `<div style="position:relative;">
      <img class="image-preview" src="/api/plugin/astrbot_plugin_mc_strategy_index/media/images/${paths[i]}" style="max-width:200px;max-height:200px;" onerror="this.style.display='none'" />
      <button style="position:absolute;top:2px;right:2px;background:var(--danger);color:#fff;border:none;border-radius:50%;width:20px;height:20px;cursor:pointer;font-size:12px;line-height:1;" onclick="event.stopPropagation();window._removeImage(${i})">x</button>
    </div>`;
  }
  html += '</div>';
  container.innerHTML = html;
  window._removeImage = (idx) => { st.image_paths.splice(idx, 1); renderImagePreview(); };
}

function updateStats() {
  const strategies = getStrategies();
  els.statTotal.textContent = strategies.length;
  els.statNormal.textContent = strategies.filter((s) => s.status === "normal").length;
  els.statPending.textContent = strategies.filter((s) => s.status !== "normal").length;
}

function renderAll() { renderStrategyList(); renderEditor(); renderCategoryOptions(); }

function selectStrategy(id) { syncCurrentStrategy(); state.currentId = id; renderAll(); }

function syncCurrentStrategy() {
  const st = getCurrentStrategy();
  if (!st) return;
  st.name = els.nameInput.value.trim();
  st.category = els.categoryInput.value;
  st.subcategory = els.subcategoryInput.value.trim();
  st.status = els.statusInput.value;
  st.text_content = els.textContentInput.value;
}

// API
async function loadState() {
  const data = await bridge.apiGet("state");
  state.loaded = data;
  state.draft = { strategies: clone(data.strategies || []), categories: clone(data.categories || []), index_image_path: data.index_image_path || "", trigger_words: data.trigger_words || [] };
  if (state.currentId && !getStrategies().find((s) => s.id === state.currentId)) state.currentId = null;
  renderAll();
}

async function saveStrategy() {
  syncCurrentStrategy();
  const st = getCurrentStrategy();
  if (!st || !st.name) { setStatus("攻略名称不能为空", "error", false); return; }
  setStatus("保存中...", "info", false);
  try {
    const resp = await bridge.apiPost("save-strategy", st);
    state.loaded = resp;
    state.draft = { strategies: clone(resp.strategies || []), categories: clone(resp.categories || []) };
    if (resp.id) state.currentId = resp.id;
    renderAll();
    setStatus("保存成功", "success");
  } catch (e) { setStatus(e?.message || "保存失败", "error", false); }
}

async function deleteStrategy() {
  const st = getCurrentStrategy();
  if (!st || !st.id) return;
  if (!confirm(`确定删除「${st.name}」？`)) return;
  setStatus("删除中...", "info", false);
  try {
    const resp = await bridge.apiPost("delete-strategy", { id: st.id });
    state.loaded = resp; state.draft = { strategies: clone(resp.strategies || []), categories: clone(resp.categories || []) };
    state.currentId = null; renderAll();
    setStatus("删除成功", "success");
  } catch (e) { setStatus(e?.message || "删除失败", "error", false); }
}

async function uploadImage() {
  const st = getCurrentStrategy();
  if (!st || !st.id) { setStatus("请先保存攻略后再上传图片", "error", false); return; }
  const file = els.hiddenUploadInput.files?.[0];
  if (!file) return;
  setStatus("上传中...", "info", false);
  try {
    const resp = await bridge.upload(`upload-image/${st.id}`, file);
    state.loaded = resp; state.draft = { strategies: clone(resp.strategies || []), categories: clone(resp.categories || []) };
    renderImagePreview();
    setStatus("上传成功", "success");
  } catch (e) { setStatus(e?.message || "上传失败", "error", false); }
  finally { els.hiddenUploadInput.value = ""; }
}

function installEvents() {
  els = {
    refreshBtn: $("refreshBtn"), searchInput: $("searchInput"), newStrategyBtn: $("newStrategyBtn"),
    listMeta: $("listMeta"), strategyList: $("strategyList"), emptyState: $("emptyState"),
    editor: $("editor"), editorEyebrow: $("editorEyebrow"), editorTitle: $("editorTitle"),
    statusBanner: $("statusBanner"), saveBtn: $("saveBtn"), deleteBtn: $("deleteBtn"),
    nameInput: $("nameInput"), categoryInput: $("categoryInput"), subcategoryInput: $("subcategoryInput"),
    statusInput: $("statusInput"),
    triggerWordsContainer: $("triggerWordsContainer"), triggerWordInput: $("triggerWordInput"), addTriggerWordBtn: $("addTriggerWordBtn"),
    textContentInput: $("textContentInput"), uploadImageBtn: $("uploadImageBtn"),
    hiddenUploadInput: $("hiddenUploadInput"), imagePreviewContainer: $("imagePreviewContainer"),
    statTotal: $("statTotal"), statNormal: $("statNormal"), statPending: $("statPending"),
  };

  for (const node of document.querySelectorAll(".tab")) {
    node.addEventListener("click", () => { state.currentFilter = node.dataset.filter; document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t === node)); renderStrategyList(); });
  }
  els.searchInput.addEventListener("input", () => { state.search = els.searchInput.value.trim(); renderStrategyList(); });
  els.newStrategyBtn.addEventListener("click", () => { const s = makeEmptyStrategy(); state.draft.strategies.push(s); state.currentId = s.id; renderAll(); setStatus("已创建攻略草稿", "info", true); });
  els.saveBtn.addEventListener("click", saveStrategy);
  els.deleteBtn.addEventListener("click", deleteStrategy);
  els.refreshBtn.addEventListener("click", async () => { setStatus("刷新中...", "info", false); await loadState(); setStatus("已刷新", "success"); });

  els.nameInput.addEventListener("input", () => { const st = getCurrentStrategy(); if (st) { st.name = els.nameInput.value; els.editorTitle.textContent = st.name || "未命名攻略"; renderStrategyList(); }});
  els.categoryInput.addEventListener("change", () => { const st = getCurrentStrategy(); if (st) { st.category = els.categoryInput.value; renderStrategyList(); }});
  els.statusInput.addEventListener("change", () => { const st = getCurrentStrategy(); if (st) { st.status = els.statusInput.value; renderStrategyList(); }});

  els.addTriggerWordBtn.addEventListener("click", addTriggerWord);
  els.triggerWordInput.addEventListener("keypress", (e) => { if (e.key === "Enter") { e.preventDefault(); addTriggerWord(); }});

  els.uploadImageBtn.addEventListener("click", () => els.hiddenUploadInput.click());
  els.hiddenUploadInput.addEventListener("change", uploadImage);
}

await bridge.ready();
installEvents();
await loadState();
