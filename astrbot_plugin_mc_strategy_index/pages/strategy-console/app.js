const bridge = window.AstrBotPluginPage;

const STATUS_LABELS = { normal: "已规范", pending_review: "待整改", needs_image_edit: "待优化图片" };
const state = { loaded: null, draft: null, currentId: null, currentFilter: "all", search: "", statusTimer: null };
const els = {};

function $(id) { return document.getElementById(id); }
function clone(v) { return JSON.parse(JSON.stringify(v)); }
function esc(v) { return String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;"); }

function setStatus(msg, tone = "info", autoHide = tone === "success") {
  clearTimeout(state.statusTimer);
  const b = els.statusBanner;
  if (!msg) { b.textContent = ""; b.dataset.tone = ""; b.classList.add("hidden"); return; }
  b.textContent = msg; b.dataset.tone = tone; b.classList.remove("hidden");
  if (autoHide) state.statusTimer = setTimeout(() => setStatus(""), 2600);
}

function getStrategies() { return state.draft?.strategies || []; }
function getCurrent() { return state.currentId ? getStrategies().find(s => s.id === state.currentId) || null : null; }
function makeEmpty() { return { id: "", name: "", category: "", subcategory: "", trigger_words: [], status: "pending_review", text_content: "", image_paths: [] }; }

function filterStrategies() {
  let list = getStrategies();
  if (state.currentFilter === "normal") list = list.filter(s => s.status === "normal");
  else if (state.currentFilter === "pending") list = list.filter(s => s.status !== "normal");
  if (state.search) {
    const q = state.search.toLowerCase();
    list = list.filter(s => [s.name, s.category, s.subcategory, ...(s.trigger_words || []), s.text_content || ""].join(" ").toLowerCase().includes(q));
  }
  return list;
}

function renderCategoryOptions() {
  const cats = state.draft?.categories || [];
  const sel = els.categoryInput;
  sel.innerHTML = '<option value="">-- 选择分类 --</option>';
  cats.forEach(c => sel.innerHTML += `<option value="${esc(c)}">${esc(c)}</option>`);
}

function renderStrategyList() {
  const filtered = filterStrategies();
  els.listMeta.textContent = `${filtered.length} 篇攻略`;
  els.strategyList.innerHTML = filtered.map(st => {
    const bc = st.status === "normal" ? "normal" : st.status === "pending_review" ? "pending" : "image-edit";
    return `<article class="strategy-card ${state.currentId === st.id ? "active" : ""}" data-sid="${st.id}">
      <div class="strategy-card-head"><div class="strategy-card-title">${esc(st.name || "未命名")}</div><span class="badge ${bc}">${STATUS_LABELS[st.status] || "?"}</span></div>
      <div class="strategy-card-meta">${esc(st.category || "未分类")} | ${(st.trigger_words || []).join(", ") || "无触发词"}</div>
    </article>`;
  }).join("");
  els.strategyList.querySelectorAll("[data-sid]").forEach(n => n.addEventListener("click", () => selectStrategy(n.dataset.sid)));
}

function renderEditor() {
  const st = getCurrent();
  if (!st) { els.emptyState.classList.remove("hidden"); els.editor.classList.add("hidden"); return; }
  els.emptyState.classList.add("hidden"); els.editor.classList.remove("hidden");
  els.editorEyebrow.textContent = `ID: ${st.id || "(新建)"}`;
  els.editorTitle.textContent = st.name || "未命名";
  els.nameInput.value = st.name || "";
  els.categoryInput.value = st.category || "";
  els.subcategoryInput.value = st.subcategory || "";
  els.statusInput.value = st.status || "pending_review";
  els.textContentInput.value = st.text_content || "";
  renderTagList(); renderImagePreview(); updateStats();
}

function renderTagList() {
  const st = getCurrent(); if (!st) return;
  els.triggerWordsContainer.innerHTML = "";
  (st.trigger_words || []).forEach(val => {
    const tag = document.createElement("span");
    tag.className = "keyword-tag"; tag.textContent = val; tag.title = "点击移除";
    tag.addEventListener("click", () => { st.trigger_words = st.trigger_words.filter(v => v !== val); renderTagList(); });
    els.triggerWordsContainer.appendChild(tag);
  });
}

function addTriggerWord() {
  const st = getCurrent(); if (!st) return;
  const kw = els.triggerWordInput.value.trim(); if (!kw) return;
  if ((st.trigger_words || []).includes(kw)) { setStatus("已存在", "error", true); return; }
  (st.trigger_words = st.trigger_words || []).push(kw);
  els.triggerWordInput.value = ""; renderTagList();
}

function renderImagePreview() {
  const st = getCurrent(); const paths = st.image_paths || [];
  if (!paths.length) { els.imagePreviewContainer.innerHTML = '<div class="inline-hint">暂无图片</div>'; return; }
  let h = '<div style="display:flex;flex-wrap:wrap;gap:10px;">';
  paths.forEach((p, i) => {
    h += `<div style="position:relative;"><img class="image-preview" src="/api/plugin/astrbot_plugin_mc_strategy_index/media/images/${p}" style="max-width:200px;max-height:200px;" onerror="this.style.display='none'" /><button style="position:absolute;top:2px;right:2px;background:var(--danger);color:#fff;border:none;border-radius:50%;width:20px;height:20px;cursor:pointer;font-size:12px;line-height:1;" onclick="event.stopPropagation();window._ri(${i})">x</button></div>`;
  });
  h += '</div>';
  els.imagePreviewContainer.innerHTML = h;
  window._ri = idx => { st.image_paths.splice(idx, 1); renderImagePreview(); };
}

function updateStats() {
  const ss = getStrategies();
  els.statTotal.textContent = ss.length;
  els.statNormal.textContent = ss.filter(s => s.status === "normal").length;
  els.statPending.textContent = ss.filter(s => s.status !== "normal").length;
}

function renderAll() { renderStrategyList(); renderEditor(); renderCategoryOptions(); }
function selectStrategy(id) { syncCurrent(); state.currentId = id; renderAll(); }
function syncCurrent() {
  const st = getCurrent(); if (!st) return;
  st.name = els.nameInput.value.trim(); st.category = els.categoryInput.value;
  st.subcategory = els.subcategoryInput.value.trim(); st.status = els.statusInput.value;
  st.text_content = els.textContentInput.value;
}

async function loadState() {
  const data = await bridge.apiGet("state");
  state.loaded = data; state.draft = { strategies: clone(data.strategies || []), categories: clone(data.categories || []) };
  if (state.currentId && !getStrategies().find(s => s.id === state.currentId)) state.currentId = null;
  if (data.image_count != null) els.imageCount.textContent = data.image_count;
  renderAll();
}

async function saveStrategy() {
  syncCurrent(); const st = getCurrent();
  if (!st || !st.name) { setStatus("名称不能为空", "error", false); return; }
  setStatus("保存中...", "info", false);
  try {
    const resp = await bridge.apiPost("save-strategy", st);
    state.loaded = resp; state.draft = { strategies: clone(resp.strategies || []), categories: clone(resp.categories || []) };
    if (resp.id) state.currentId = resp.id;
    renderAll(); setStatus("保存成功", "success");
  } catch (e) { setStatus(e?.message || "保存失败", "error", false); }
}

async function deleteStrategy() {
  const st = getCurrent(); if (!st || !st.id) return;
  if (!confirm(`确定删除「${st.name}」？`)) return;
  try {
    const resp = await bridge.apiPost("delete-strategy", { id: st.id });
    state.loaded = resp; state.draft = { strategies: clone(resp.strategies || []), categories: clone(resp.categories || []) };
    state.currentId = null; renderAll(); setStatus("删除成功", "success");
  } catch (e) { setStatus(e?.message || "删除失败", "error", false); }
}

async function uploadImage() {
  const st = getCurrent(); if (!st || !st.id) { setStatus("请先保存攻略", "error", false); return; }
  const file = els.hiddenUploadInput.files?.[0]; if (!file) return;
  setStatus("上传中...", "info", false);
  try {
    const resp = await bridge.upload(`upload-image/${st.id}`, file);
    state.loaded = resp; state.draft = { strategies: clone(resp.strategies || []), categories: clone(resp.categories || []) };
    renderImagePreview(); setStatus("上传成功", "success");
  } catch (e) { setStatus(e?.message || "失败", "error", false); }
  finally { els.hiddenUploadInput.value = ""; }
}

async function exportImages() {
  if (!confirm("确定要导出全部图片吗？这将打包下载所有上传的攻略图片。")) return;
  setStatus("正在打包图片...", "info", false);
  try {
    const url = `/api/plugin/astrbot_plugin_mc_strategy_index/export-images`;
    window.open(url, "_blank");
    setStatus("导出已开始", "success");
  } catch (e) { setStatus("导出失败", "error", false); }
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
    exportImagesBtn: $("exportImagesBtn"), imageCount: $("imageCount"),
  };

  document.querySelectorAll(".tab").forEach(n => n.addEventListener("click", () => { state.currentFilter = n.dataset.filter; document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t === n)); renderStrategyList(); }));
  els.searchInput.addEventListener("input", () => { state.search = els.searchInput.value.trim(); renderStrategyList(); });
  els.newStrategyBtn.addEventListener("click", () => { const s = makeEmpty(); state.draft.strategies.push(s); state.currentId = s.id; renderAll(); setStatus("已创建草稿", "info", true); });
  els.saveBtn.addEventListener("click", saveStrategy);
  els.deleteBtn.addEventListener("click", deleteStrategy);
  els.refreshBtn.addEventListener("click", async () => { setStatus("刷新中...", "info", false); await loadState(); setStatus("已刷新", "success"); });
  els.nameInput.addEventListener("input", () => { const st = getCurrent(); if (st) { st.name = els.nameInput.value; els.editorTitle.textContent = st.name || "未命名"; renderStrategyList(); }});
  els.categoryInput.addEventListener("change", () => { const st = getCurrent(); if (st) { st.category = els.categoryInput.value; renderStrategyList(); }});
  els.statusInput.addEventListener("change", () => { const st = getCurrent(); if (st) { st.status = els.statusInput.value; renderStrategyList(); }});
  els.addTriggerWordBtn.addEventListener("click", addTriggerWord);
  els.triggerWordInput.addEventListener("keypress", e => { if (e.key === "Enter") { e.preventDefault(); addTriggerWord(); }});
  els.uploadImageBtn.addEventListener("click", () => els.hiddenUploadInput.click());
  els.hiddenUploadInput.addEventListener("change", uploadImage);
  els.exportImagesBtn.addEventListener("click", exportImages);
}

await bridge.ready();
installEvents();
await loadState();
