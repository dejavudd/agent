"use strict";

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };

const HAS_MARKED = typeof window.marked !== "undefined";
if (typeof window.mermaid !== "undefined") {
  mermaid.initialize({ startOnLoad: false, theme: "default" });
}

let state = { subjects: [], subject: null, weeks: [], next_week: 1, api_provider: "", recommendations: [], rag: {} };
let profileState = null;
let activeWeek = null;

// ----------------------------------------------------------------- utilities
function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2600);
}

async function api(path, opts) {
  const res = await fetch(path, opts);
  let data = null;
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) throw new Error((data && data.error) || `${res.status} ${res.statusText}`);
  return data;
}

// Mermaid treats an unquoted "(" inside a node label as round-node syntax, so
// labels like [machine language (기계어)] — which our bilingual notes produce
// constantly — are syntax errors and the whole diagram silently fails. Quote any
// [ ] or { } node label that contains parentheses and isn't already quoted.
function sanitizeMermaid(src) {
  return src.replace(
    /([\[{])([^\[\]{}"][^\[\]{}]*?)([\]}])/g,
    (m, open, label, close) =>
      /[()]/.test(label) ? `${open}"${label.replace(/"/g, "'")}"${close}` : m
  );
}

function makeMermaidViewer(src) {
  const box = el("div", "mermaid-viewer");
  const tools = el("div", "mermaid-tools");
  const canvas = el("div", "mermaid-canvas");
  const diagram = el("div", "mermaid");
  const zoomText = el("span", "mermaid-zoom", "100%");
  diagram.textContent = src;
  diagram.dataset.zoom = "1";

  [
    ["－", "缩小", "out"],
    ["＋", "放大", "in"],
    ["重置", "恢复原始大小", "reset"],
    ["适应宽度", "适应当前区域宽度", "fit"],
  ].forEach(([label, title, action]) => {
    const btn = el("button", "mini mermaid-btn", label);
    btn.type = "button";
    btn.title = title;
    btn.addEventListener("click", () => setMermaidZoom(diagram, action));
    tools.appendChild(btn);
  });

  tools.appendChild(zoomText);
  canvas.appendChild(diagram);
  box.appendChild(tools);
  box.appendChild(canvas);
  return { box, diagram };
}

function setMermaidZoom(diagram, action) {
  const svg = diagram.querySelector("svg");
  const canvas = diagram.closest(".mermaid-canvas");
  if (!svg || !canvas) return;

  if (!diagram.dataset.baseWidth) {
    const viewBox = svg.viewBox && svg.viewBox.baseVal;
    const rect = svg.getBoundingClientRect();
    diagram.dataset.baseWidth = Math.max((viewBox && viewBox.width) || 0, rect.width || 0, 640);
  }

  const baseWidth = Number(diagram.dataset.baseWidth || 640);
  let zoom = Number(diagram.dataset.zoom || 1);
  if (action === "in") zoom += 0.2;
  if (action === "out") zoom -= 0.2;
  if (action === "reset") zoom = 1;
  if (action === "fit") zoom = Math.max(0.35, (canvas.clientWidth - 24) / baseWidth);
  zoom = Math.max(0.35, Math.min(4, zoom));

  svg.style.maxWidth = "none";
  svg.style.width = `${Math.round(baseWidth * zoom)}px`;
  svg.style.height = "auto";
  diagram.dataset.zoom = String(zoom);

  const label = diagram.closest(".mermaid-viewer")?.querySelector(".mermaid-zoom");
  if (label) label.textContent = `${Math.round(zoom * 100)}%`;
}

async function renderMarkdown(container, md) {
  if (!HAS_MARKED) { container.innerHTML = ""; container.appendChild(el("pre", null, md)); return; }
  container.innerHTML = marked.parse(md);
  // Convert ```mermaid blocks into rendered diagrams.
  const blocks = container.querySelectorAll("code.language-mermaid");
  if (!blocks.length || typeof window.mermaid === "undefined") return;
  const divs = [];
  blocks.forEach((code) => {
    const viewer = makeMermaidViewer(sanitizeMermaid(code.textContent));
    code.closest("pre").replaceWith(viewer.box);
    divs.push(viewer.diagram);
  });
  // Render each diagram in isolation so one malformed diagram can't blank the rest.
  for (const div of divs) {
    const src = div.textContent;
    try {
      await mermaid.run({ nodes: [div] });
      setMermaidZoom(div, "reset");
    } catch (_) {
      div.classList.add("mermaid-error");
      div.textContent = "图表渲染失败";
      const pre = el("pre", "mermaid-src", src); div.after(pre);
    }
  }
}

// -------------------------------------------------------------------- render
async function refresh() {
  state = await api("/api/state");
  const ragMode = state.rag && state.rag.mode ? state.rag.mode : "local";
  $("#provider").textContent = `模型接口：${state.api_provider} | 检索模式：${ragMode}`;
  const ragStatus = $("#rag-status");
  if (ragStatus) {
    ragStatus.textContent = state.rag && state.rag.ok
      ? "LightRAG 服务已连接，当前使用增强检索。"
      : "LightRAG 未配置或不可用，当前使用本地课程资料检索。";
  }
  renderSubjects(); renderWeeks(); renderRecommendations();
}

// --------------------------------------------------------------- subjects
function renderSubjects() {
  const sel = $("#subject-select"); sel.innerHTML = "";
  const has = state.subjects.length > 0;
  if (!has) {
    const o = el("option", null, "暂无课程，请先新建"); o.value = ""; sel.appendChild(o);
  }
  state.subjects.forEach((s) => {
    const o = el("option", null, `${displaySubjectName(s.name)}（${s.weeks} 个章节）`); o.value = s.slug;
    if (s.slug === state.subject) o.selected = true;
    sel.appendChild(o);
  });
  sel.disabled = !has;
  $("#subject-rename").disabled = !has;
  $("#subject-delete").disabled = !has;
}

function renderRecommendations() {
  const box = $("#recommendations");
  if (!box) return;
  const recs = state.recommendations || [];
  box.innerHTML = "";
  if (!recs.length) { box.classList.add("hidden"); return; }
  box.classList.remove("hidden");
  box.appendChild(el("h3", null, "个性化推荐下一步"));
  recs.slice(0, 4).forEach((rec) => {
    const card = el("div", "rec-card");
    const main = el("div");
    main.appendChild(el("strong", null, translateRecommendationTitle(rec.title || "下一步")));
    main.appendChild(el("p", "muted", translateRecommendationReason(rec.reason || "")));
    const btn = el("button", "mini", "执行");
    btn.onclick = () => runRecommendation(rec, btn);
    card.appendChild(main);
    card.appendChild(btn);
    box.appendChild(card);
  });
}

function translateRecommendationTitle(text) {
  return String(text || "")
    .replace(/^Complete student image$/, "完善学习画像")
    .replace(/^Ask one grounded question$/, "提出一个课程资料问答")
    .replace(/^Ingest Week (\d+)/, "生成第 $1 章节分层笔记")
    .replace(/^Create Week (\d+) quiz$/, "生成第 $1 章节题库")
    .replace(/^Submit Week (\d+) answers$/, "提交第 $1 章节答案")
    .replace(/^Create Week (\d+) extension materials$/, "生成第 $1 章节拓展材料");
}

function translateRecommendationReason(text) {
  return String(text || "")
    .replace("Learning goal is missing, so resource push cannot be personalized deeply.", "学习目标尚未填写，系统暂时无法进行深度个性化推送。")
    .replace("Source PDFs exist but tiered notes are not generated.", "已上传课程资料，但还没有生成分层学习笔记。")
    .replace("Quiz practice is needed to check key knowledge points.", "建议生成题库，用来检查本单元关键知识点。")
    .replace("Quiz exists but no deeper feedback has been generated.", "题库已生成，但还没有形成深度反馈。")
    .replace("Extension materials can provide reading directions and practice cases.", "可以生成拓展阅读方向和实操案例，补充课堂资料。")
    .replace("No course-knowledge RAG tutoring event has been recorded yet.", "还没有记录课程资料问答事件。");
}

function translateStatus(status) {
  return ({
    New: "未处理",
    Ingested: "已生成笔记",
    Quizzed: "已测评",
    Reviewed: "已审查",
    Empty: "空章节",
  })[status] || status;
}

function displaySubjectName(name) {
  const map = {
    "Introduction to Computer Science": "计算机科学导论",
    "Agentic Study System": "个性化学习系统",
  };
  return map[name] || name || "未命名课程";
}

function displayWeekName(week) {
  return `章节 ${String(week).padStart(2, "0")}`;
}

function localizeVisibleText(text) {
  return String(text || "")
    .replace(/^Week\s+(\d+)/i, "章节 $1")
    .replace(/Beginner\.md/gi, "基础讲义")
    .replace(/Intermediate\.md/gi, "进阶讲义")
    .replace(/Advanced\.md/gi, "拓展讲义")
    .replace(/Diagrams\.md/gi, "知识图解")
    .replace(/Extension\.md/gi, "拓展材料")
    .replace(/Quiz\.md/gi, "智能题库")
    .replace(/Answers\.md/gi, "作答记录")
    .replace(/Feedback\.md/gi, "诊断反馈")
    .replace(/Essay\.md/gi, "综合论述")
    .replace(/Critique\.md/gi, "审查报告")
    .replace(/^Ingest$/i, "生成讲义")
    .replace(/^Diagrams$/i, "知识图解")
    .replace(/^Quiz$/i, "测评")
    .replace(/^Review$/i, "审查")
    .replace(/^Debate$/i, "追问")
    .replace(/^Edit$/i, "更多")
    .replace(/^Delete$/i, "删除")
    .replace(/^Empty$/i, "空章节")
    .replace(/^no PDFs$/i, "尚未接入课程资料")
    .replace(/^no PDF$/i, "尚未接入课程资料");
}

function displayFileLabel(name) {
  const base = String(name || "").replace(/\.md$/i, "");
  const map = {
    Beginner: "基础讲义",
    Intermediate: "进阶讲义",
    Interleaved: "交错练习",
    Advanced: "拓展讲义",
    Diagrams: "知识图解",
    Extension: "拓展材料",
    Quiz: "智能题库",
    Answers: "作答记录",
    Feedback: "诊断反馈",
    Essay: "综合论述",
    Critique: "审查报告",
  };
  return map[base] || localizeVisibleText(base || name);
}

function pdfSummary(pdfs) {
  if (!pdfs || !pdfs.length) return "尚未接入课程资料";
  if (pdfs.length === 1) return pdfs[0];
  return `${pdfs.length} 份课程资料`;
}

function runRecommendation(rec, btn) {
  const week = rec.week;
  if (rec.action === "profile") return showView("personalization");
  if (rec.action === "rag") return showView("rag");
  if (rec.action === "ingest") return runIngest(week, btn);
  if (rec.action === "extension") return runExtension(week, btn);
  if (rec.action === "quiz" || rec.action === "open_quiz") return openQuiz(week);
}

async function selectSubject(slug) {
  try { await api("/api/subject/select", jsonBody({ slug })); await refresh(); }
  catch (e) { toast("切换课程失败：" + e.message); }
}

async function newSubject() {
  const name = (prompt("请输入课程名称，例如：人工智能导论") || "").trim();
  if (!name) return;
  try { await api("/api/subject/create", jsonBody({ name })); toast(`课程“${name}”已创建。`); await refresh(); }
  catch (e) { toast("创建课程失败：" + e.message); }
}

async function renameSubject() {
  if (!state.subject) return;
  const cur = (state.subjects.find((s) => s.slug === state.subject) || {}).name || "";
  const name = (prompt("请输入新的课程名称：", cur) || "").trim();
  if (!name || name === cur) return;
  try { await api("/api/subject/rename", jsonBody({ slug: state.subject, name })); toast("课程已重命名。"); await refresh(); }
  catch (e) { toast("重命名失败：" + e.message); }
}

async function deleteSubject() {
  if (!state.subject) return;
  const cur = (state.subjects.find((s) => s.slug === state.subject) || {});
  if (!confirm(`确定删除课程”${cur.name}”以及其中全部 ${cur.weeks} 个章节吗？此操作不可恢复。`)) return;
  try { await api("/api/subject/delete", jsonBody({ slug: state.subject })); toast("课程已删除。"); await refresh(); }
  catch (e) { toast("删除课程失败：" + e.message); }
}

function renderWeeks() {
  const ul = $("#weeks"); ul.innerHTML = "";
  const weeksAll = $("#weeks-all");
  if (weeksAll) weeksAll.checked = false;
  if (!state.weeks.length) {
    ul.appendChild(el("li", "empty-note", "暂无章节，请先导入课程资料。"));
    $("#weeks-bar").classList.add("hidden");
    return;
  }
  $("#weeks-bar").classList.add("hidden");
  state.weeks.forEach((w) => {
    const li = el("li", "unit-card");
    const row = el("div", "unit-top");
    const head = el("div", "wk-head");
    const cb = el("input"); cb.type = "checkbox"; cb.className = "week-cb"; cb.value = String(w.week);
    head.appendChild(cb);
    const left = el("div");
    const wkLabel = displayWeekName(w.week);
    const sequence = el("span", "unit-sequence", `章节 ${String(w.week).padStart(2, "0")}`);
    const title = el("span", "name", w.title ? localizeVisibleText(w.title) : wkLabel);
    left.appendChild(sequence);
    left.appendChild(title);
    const files = [...w.tiers,
      w.has_diagrams ? "Diagrams.md" : null,
      w.has_extension ? "Extension.md" : null,
      w.has_quiz ? "Quiz.md" : null, w.has_answers ? "Answers.md" : null,
      w.has_feedback ? "Feedback.md" : null, w.has_essay ? "Essay.md" : null,
      ].filter(Boolean);
    const generated = w.generated_assets || [];
    left.appendChild(el("div", "sub", pdfSummary(w.pdfs)));
    head.appendChild(left);
    row.appendChild(head);
    row.appendChild(el("span", "badge " + w.status, translateStatus(w.status)));
    li.appendChild(row);

    // openable file chips
    if (files.length) {
      const chips = el("div", "unit-resources");
      files.forEach((f) => {
        const c = el("button", "chip-file", displayFileLabel(f));
        c.title = displayFileLabel(f);
        c.onclick = () => openFile(w.week, f);
        chips.appendChild(c);
      });
      generated.forEach((f) => {
        const c = el("button", "chip-file generated", displayFileLabel(f));
        c.title = displayFileLabel(f);
        c.onclick = () => openGenerated(w.week, f);
        chips.appendChild(c);
      });
      li.appendChild(chips);
    }

    // actions
    const acts = el("div", "actions");
    acts.appendChild(actionBtn("生成讲义", (btn) => runIngest(w.week, btn), !w.pdfs.length));
    acts.appendChild(actionBtn("知识图解", (btn) => runExplore(w.week, btn), !w.tiers.length));
    acts.appendChild(actionBtn("拓展材料", (btn) => runExtension(w.week, btn), !w.tiers.length));
    acts.appendChild(actionBtn("测评", () => openQuiz(w.week), !w.tiers.length));
    li.appendChild(acts);
    ul.appendChild(li);
  });
}

function actionBtn(label, fn, disabled) {
  const b = el("button", "mini", localizeVisibleText(label)); b.disabled = !!disabled;
  if (!disabled) b.onclick = () => fn(b);
  return b;
}

async function withSpinner(btn, fn) {
  const original = btn ? btn.innerHTML : null;
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>'; }
  try { return await fn(); }
  finally { if (btn) { btn.disabled = false; btn.innerHTML = original; } }
}

// ------------------------------------------------------------------ actions
async function runIngest(week, btn) {
  const original = btn ? btn.innerHTML : null;
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> 解析中...'; }

  await new Promise((resolve) => {
    const es = new EventSource(`/api/ingest/stream?week=${week}`);

    es.addEventListener("step", (e) => {
      const d = JSON.parse(e.data);
      if (btn) btn.innerHTML = `<span class="spinner"></span> ${d.msg}`;
      toast(d.msg);
    });

    es.addEventListener("tier_done", (e) => {
      const d = JSON.parse(e.data);
      const labels = { Beginner: "基础", Intermediate: "进阶", Advanced: "拓展" };
      if (btn) btn.innerHTML = `<span class="spinner"></span> ${labels[d.tier] || d.tier}讲义已完成`;
    });

    es.addEventListener("done", async (e) => {
      es.close();
      if (btn) { btn.disabled = false; btn.innerHTML = original; }
      toast(`第 ${week} 章节分层笔记已生成。`);
      await refresh();
      openFile(week, "Beginner.md");
      resolve();
    });

    es.addEventListener("error", (e) => {
      es.close();
      if (btn) { btn.disabled = false; btn.innerHTML = original; }
      try {
        const d = JSON.parse(e.data);
        toast("生成笔记失败：" + (d.msg || "未知错误"));
      } catch (_) {
        toast("生成笔记失败，请检查服务器日志。");
      }
      resolve();
    });

    es.onerror = () => {
      es.close();
      if (btn) { btn.disabled = false; btn.innerHTML = original; }
      toast("连接中断，请重试。");
      resolve();
    };
  });
}

async function runExplore(week, btn) {
  toast(`正在为第 ${week} 章节补充图解资料...`);
  try {
    const r = await withSpinner(btn, () => api("/api/explore", jsonBody({ week })));
    toast(r.count ? `已找到 ${r.count} 张图解资料。` : "未找到外部图解，系统仍保留 Mermaid 知识图。");
    await refresh(); openFile(week, r.file);
  } catch (e) { toast("图解检索失败：" + e.message); }
}

async function runExtension(week, btn) {
  toast(`正在生成第 ${week} 章节拓展学习材料...`);
  try {
    const r = await withSpinner(btn, () => api("/api/extension", jsonBody({ week })));
    toast("拓展学习材料已生成。");
    await refresh(); openFile(week, r.file);
  } catch (e) { toast("拓展材料生成失败：" + e.message); }
}

async function logBehavior(type, payload) {
  try { await api("/api/behavior", jsonBody({ type, payload })); } catch (_) {}
}

function jsonBody(obj) {
  return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(obj) };
}


// ------------------------------------------------------------------- viewer
function showView(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === name));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === name));
}

async function openFile(week, name) {
  showView("viewer");
  activeWeek = week;
  $("#viewer-title").textContent = `第 ${String(week).padStart(2, "0")} 章节 | ${name}`;
  try {
    const md = await (await fetch(`/api/week/${week}/file/${name}`)).text();
    await renderMarkdown($("#viewer-body"), md);
    rewriteAssetImages($("#viewer-body"), week);
    logBehavior("open_file", { week, file: name });
  } catch (e) { $("#viewer-body").textContent = "文件加载失败。"; }
}

async function openGenerated(week, name) {
  activeWeek = week;
  logBehavior("open_generated_asset", { week, file: name });
  if (name.toLowerCase().endsWith(".html")) {
    window.open(`/api/week/${week}/generated/${encodeURIComponent(name)}`, "_blank");
    return;
  }
  showView("viewer");
  $("#viewer-title").textContent = `第 ${String(week).padStart(2, "0")} 章节 | ${name}`;
  const res = await fetch(`/api/week/${week}/generated/${encodeURIComponent(name)}`);
  const text = await res.text();
  await renderMarkdown($("#viewer-body"), text);
}

// Diagrams.md embeds images as `assets/NAME`; map those to the asset endpoint.
function rewriteAssetImages(container, week) {
  container.querySelectorAll("img").forEach((img) => {
    const src = img.getAttribute("src") || "";
    if (/^(https?:)?\/\//.test(src) || src.startsWith("/")) return;  // leave remote/absolute
    const file = src.replace(/^\.?\//, "").replace(/^assets\//, "");
    img.src = `/api/week/${week}/asset/${encodeURIComponent(file)}`;
  });
}

async function openDiagnostic() {
  showView("viewer");
  $("#viewer-title").textContent = "学习诊断报告 Diagnostic.md";
  const md = await (await fetch("/api/diagnostic")).text();
  renderMarkdown($("#viewer-body"), md);
}

// ---------------------------------------------------------- personalization
const PROFILE_FIELDS = {
  "basic.major": "#profile-major",
  "basic.grade": "#profile-grade",
  "basic.target_course": "#profile-course",
  "basic.learning_goal": "#profile-goal",
  "basic.time_budget": "#profile-time",
  "dimensions.knowledge_base": "#profile-knowledge",
  "dimensions.cognitive_style": "#profile-style",
  "dimensions.weak_points": "#profile-weak",
  "dimensions.interests": "#profile-interests",
  "dimensions.resource_preferences": "#profile-resources",
  "dimensions.assessment_preference": "#profile-assessment",
  "state.progress_summary": "#profile-progress",
};

function getNested(obj, path) {
  return path.split(".").reduce((cur, key) => (cur && cur[key] != null ? cur[key] : ""), obj);
}

function setNested(obj, path, value) {
  const parts = path.split(".");
  let cur = obj;
  parts.slice(0, -1).forEach((key) => { cur[key] = cur[key] || {}; cur = cur[key]; });
  cur[parts[parts.length - 1]] = value;
}

function renderProfile(profile, markdown) {
  profileState = profile || {};
  Object.entries(PROFILE_FIELDS).forEach(([path, selector]) => {
    const input = $(selector);
    if (input) input.value = getNested(profileState, path);
  });
  // 访谈框是纯输入区，不回填历史记录，避免残留上次内容
  if (markdown) renderMarkdown($("#profile-preview"), markdown);
}

function collectProfile() {
  const profile = profileState ? JSON.parse(JSON.stringify(profileState)) : {};
  Object.entries(PROFILE_FIELDS).forEach(([path, selector]) => {
    const input = $(selector);
    setNested(profile, path, input ? input.value.trim() : "");
  });
  profile.raw_notes = $("#profile-notes").value.trim();
  return profile;
}

async function loadProfile() {
  try {
    const r = await api("/api/profile");
    renderProfile(r.profile, r.markdown);
    toast("学习画像已加载。");
  } catch (e) { toast("加载画像失败：" + e.message); }
}

async function saveProfile(btn) {
  try {
    const r = await withSpinner(btn, () => api("/api/profile/save", jsonBody({ profile: collectProfile() })));
    renderProfile(r.profile, r.markdown);
    toast("学习画像已保存。");
  } catch (e) { toast("保存画像失败：" + e.message); }
}

async function buildProfile(btn) {
  const notes = $("#profile-notes").value.trim();
  if (!notes && !confirm("没有输入访谈记录，是否仅根据当前诊断信息构建画像？")) return;
  try {
    const r = await withSpinner(btn, () => api("/api/profile/build", jsonBody({ notes })));
    renderProfile(r.profile, r.markdown);
    toast("学习画像已更新。");
  } catch (e) { toast("构建画像失败：" + e.message); }
}

async function generatePath(btn) {
  try {
    const r = await withSpinner(btn, () => api("/api/path", { method: "POST" }));
    toast("个性化学习计划已生成。");
    await openPath(r.file);
  } catch (e) { toast("生成学习计划失败：" + e.message); }
}

async function openPath(name) {
  showView("viewer");
  $("#viewer-title").textContent = name || "个性化学习计划";
  try {
    const res = await fetch("/api/path");
    if (!res.ok) {
      $("#viewer-body").textContent = "还没有生成学习计划，请先点击「生成个性化学习计划」。";
      return;
    }
    const md = await res.text();
    await renderMarkdown($("#viewer-body"), md);
  } catch (e) { $("#viewer-body").textContent = "请先生成个性化学习计划。"; }
}

// ------------------------------------------------------------------ rag tutor
async function askRag(btn) {
  const question = $("#rag-question").value.trim();
  if (!question) { toast("请先输入问题。"); return; }
  $("#rag-answer").innerHTML = "";
  try {
    const result = await withSpinner(btn, () => api("/api/rag/ask", jsonBody({
      question,
      mode: $("#rag-mode").value || "mix",
    })));
    const sources = (result.sources || []).map((s, i) => `- [${i + 1}] ${s.source || JSON.stringify(s)} ${s.score ? `（相关度 ${s.score}）` : ""}`).join("\n");
    const md = `${result.answer || ""}${sources ? "\n\n## 参考来源\n" + sources : ""}`;
    await renderMarkdown($("#rag-answer"), md);
    await refresh();
  } catch (e) { toast("知识问答失败：" + e.message); }
}

function setIndexStatus(cls, msg) {
  const el = $("#rag-index-status");
  el.className = "rag-index-status " + cls;
  el.textContent = msg;
  el.classList.remove("hidden");
}

async function pollIndexStatus(totalUploaded) {
  const maxWait = 300000;
  const start = Date.now();
  setIndexStatus("indexing", `⏳ 正在建立知识图谱，已上传 ${totalUploaded} 个文件，请稍候...`);
  while (Date.now() - start < maxWait) {
    await new Promise(r => setTimeout(r, 5000));
    try {
      const s = await api("/api/rag/status");
      if (!s.configured) break;
      const pending = (s.pending || 0) + (s.processing || 0);
      const done = s.processed || 0;
      const failed = s.failed || 0;
      if (pending === 0) {
        if (failed > 0 && done === 0) {
          setIndexStatus("error", `❌ 索引失败（${failed} 个文件），请检查 LightRAG 日志`);
        } else if (failed > 0) {
          setIndexStatus("done", `✅ 知识图谱已就绪（${done} 个成功，${failed} 个失败），现在可以提问`);
        } else {
          setIndexStatus("done", `✅ 知识图谱已就绪（${done} 个文件），现在可以提问`);
        }
        return;
      }
      setIndexStatus("indexing", `⏳ 建立知识图谱中：${done} 完成 / ${pending} 处理中 / ${failed} 失败`);
    } catch (e) {
      if (e.message && (e.message.includes("404") || e.message.includes("Not Found"))) {
        setIndexStatus("error", "❌ 服务器未就绪，请重启后重试");
        return;
      }
    }
  }
  setIndexStatus("error", "⚠️ 建图超时，请刷新后重试");
}

async function indexActiveWeek(btn) {
  try {
    setIndexStatus("indexing", "⏳ 正在上传课程资料...");
    const result = await withSpinner(btn, () => api("/api/rag/index-week", jsonBody({})));
    if (result.mode === "lightrag") {
      if (result.uploaded.length === 0) {
        setIndexStatus("done", "ℹ️ 没有新文件需要上传，知识图谱已是最新状态。");
      } else {
        pollIndexStatus(result.uploaded.length);
      }
    } else {
      setIndexStatus("done", "ℹ️ " + (result.message || "当前使用本地检索，无需手动索引。"));
    }
    await refresh();
  } catch (e) {
    setIndexStatus("error", "❌ 索引失败：" + e.message);
  }
}

// ---------------------------------------------------------------------- quiz
let quizWeek = null;
let quizSpec = null;                       // parsed Quiz.json for the open week
const weekInfo = (week) => state.weeks.find((w) => w.week === week) || {};

const TIER_ORDER = ["Beginner", "Intermediate", "Interleaved", "Advanced"];
const TIER_LABEL = {
  Beginner: "基础题",
  Intermediate: "进阶题",
  Interleaved: "交错复习题",
  Advanced: "综合论述题",
};
const isObjective = (t) => t === "mcq" || t === "cloze";

async function fetchFile(week, name) {
  const r = await fetch(`/api/week/${week}/file/${name}`);
  return r.ok ? r.text() : "";
}

async function openQuiz(week) {
  showView("quiz");
  quizWeek = week;
  activeWeek = week;
  quizSpec = null;
  $("#quiz-header").innerHTML = `<strong>第 ${String(week).padStart(2, "0")} 章节智能测评</strong>`;
  const w = weekInfo(week);
  if (!w.has_quiz) {
    $("#quiz-empty").classList.remove("hidden");
    $("#quiz-body").classList.add("hidden");
    return;
  }
  $("#quiz-empty").classList.add("hidden");
  $("#quiz-body").classList.remove("hidden");

  const rawJson = await fetchFile(week, "Quiz.json");
  if (rawJson) { try { quizSpec = JSON.parse(rawJson); } catch (_) { quizSpec = null; } }

  const list = $("#quiz-list"); list.innerHTML = "";
  if (quizSpec && Array.isArray(quizSpec.questions)) {
    renderQuizInteractive(quizSpec.questions);
  } else {
    // Legacy week (Quiz.md only, no structured answers): show static markdown.
    const art = el("article", "markdown"); list.appendChild(art);
    renderMarkdown(art, await fetchFile(week, "Quiz.md"));
    $("#quiz-score").textContent = "旧版题库，请重新生成以使用交互式检查。";
  }

  $("#quiz-essay").value = w.has_essay ? await fetchFile(week, "Essay.md") : "";
  if (w.has_feedback) renderMarkdown($("#quiz-feedback"), await fetchFile(week, "Feedback.md"));
  else $("#quiz-feedback").innerHTML = "";
}

function renderQuizInteractive(questions) {
  const list = $("#quiz-list"); list.innerHTML = "";
  TIER_ORDER.forEach((tier) => {
    const group = questions.filter((q) => q.tier === tier);
    if (!group.length) return;
    list.appendChild(el("h3", "qz-h", TIER_LABEL[tier] || tier));
    group.forEach((q, i) => list.appendChild(renderCard(q, i + 1)));
  });
  updateScore();
}

function renderCard(q, n) {
  const card = el("div", "q-card");
  card._q = q;

  const head = el("div", "q-head");
  head.appendChild(el("span", "q-id", q.id || `#${n}`));
  const badge = el("span", "q-badge"); badge.dataset.role = "badge";
  head.appendChild(badge);
  card.appendChild(head);
  card.appendChild(el("div", "q-prompt", q.prompt || ""));

  const body = el("div", "q-body");
  if (q.type === "mcq") {
    (q.options || []).forEach((opt) => {
      const lbl = el("label", "q-opt");
      const radio = el("input"); radio.type = "radio"; radio.name = q.id; radio.value = opt;
      lbl.appendChild(radio); lbl.appendChild(el("span", null, opt));
      body.appendChild(lbl);
    });
  } else if (q.type === "cloze" || q.type === "short") {
    const inp = el("input", "q-input"); inp.type = "text"; inp.placeholder = "请输入你的答案...";
    if (q.type === "cloze") inp.addEventListener("keydown", (e) => { if (e.key === "Enter") checkCard(card); });
    body.appendChild(inp);
  } else if (q.type === "essay") {
    body.appendChild(el("div", "q-essay-note", "请在下方综合论述区作答，保存后可启动论述审查。"));
  }
  card.appendChild(body);

  if (q.type !== "essay") {
    const acts = el("div", "q-acts");
    const objective = isObjective(q.type);
    const btn = el("button", "mini", objective ? "检查" : "查看参考答案");
    btn.onclick = () => (objective ? checkCard(card) : revealCard(card));
    acts.appendChild(btn);
    card.appendChild(acts);
  }
  const rev = el("div", "q-reveal hidden"); rev.dataset.role = "reveal";
  card.appendChild(rev);
  return card;
}

// --- checking -------------------------------------------------------------
function normalize(s) {
  return (s || "").toString().toLowerCase().trim()
    .replace(/\s+/g, " ")
    .replace(/^[\s"'(.,;:!?-]+|[\s"').,;:!?-]+$/g, "");
}
function mcqLetter(s) {
  const m = normalize(s).match(/^([a-z])\b/);
  return m ? m[1] : normalize(s);
}
function isCorrect(q, value) {
  if (q.type === "mcq") return mcqLetter(value) === mcqLetter(q.answer);
  if (q.type === "cloze") return (q.answers || []).map(normalize).includes(normalize(value));
  return null;
}
function cardValue(card) {
  const q = card._q;
  if (q.type === "mcq") {
    const sel = card.querySelector(`input[name="${q.id}"]:checked`);
    return sel ? sel.value : "";
  }
  const inp = card.querySelector(".q-input");
  return inp ? inp.value : "";
}

function checkCard(card, quiet) {
  const q = card._q;
  const value = cardValue(card);
  if (!value) { if (!quiet) toast("请先选择或输入答案。"); return; }
  const ok = isCorrect(q, value);
  const badge = card.querySelector('[data-role="badge"]');
  badge.textContent = ok ? "✓" : "✗";
  badge.className = "q-badge " + (ok ? "ok" : "bad");
  card.classList.toggle("answered-ok", !!ok);
  card.classList.toggle("answered-bad", !ok);
  card.dataset.checked = "1";
  revealCard(card);
  updateScore();
  logBehavior("quiz_item_checked", { week: quizWeek, id: q.id, type: q.type, correct: !!ok });
}

function revealCard(card) {
  const q = card._q;
  const rev = card.querySelector('[data-role="reveal"]');
  rev.innerHTML = "";
  const ans = q.type === "cloze" ? (q.answers || []).join("  /  ") : (q.answer || "");
  if (ans) {
    const a = el("div", "q-ans");
    a.appendChild(el("strong", null, "参考答案："));
    a.appendChild(el("span", null, ans));
    rev.appendChild(a);
  }
  if (q.explanation) rev.appendChild(el("div", "q-exp", q.explanation));
  rev.classList.remove("hidden");
  card.dataset.revealed = "1";
}

function updateScore() {
  const cards = [...$("#quiz-list").querySelectorAll(".q-card")];
  const objective = cards.filter((c) => isObjective(c._q.type));
  if (!objective.length) { $("#quiz-score").textContent = ""; return; }
  const correct = objective.filter((c) => c.classList.contains("answered-ok")).length;
  const checked = objective.filter((c) => c.dataset.checked === "1").length;
  let txt = `客观题：${correct} / ${objective.length} 正确`;
  if (checked < objective.length) txt += `，已检查 ${checked} 题`;
  $("#quiz-score").textContent = txt;
}

function assembleAnswers() {
  const lines = [`# 第 ${quizWeek} 章节 - 我的答案`, ""];
  TIER_ORDER.forEach((tier) => {
    const cards = [...$("#quiz-list").querySelectorAll(".q-card")]
      .filter((c) => c._q.tier === tier && c._q.type !== "essay");
    if (!cards.length) return;
    lines.push(`## ${TIER_LABEL[tier] || tier}`);
    cards.forEach((c) => lines.push(`- ${c._q.id}: ${cardValue(c).replace(/\s+/g, " ").trim()}`));
    lines.push("");
  });
  return lines.join("\n");
}

async function saveQuizFile(name, content, btn) {
  const fn = () => api("/api/save", jsonBody({ week: quizWeek, name, content }));
  return btn ? withSpinner(btn, fn) : fn();
}

$("#quiz-generate").onclick = async (e) => {
  toast(`正在生成第 ${quizWeek} 章节题库，请稍候...`);
  try {
    await withSpinner(e.target, () => api("/api/quiz", jsonBody({ week: quizWeek })));
    await refresh(); openQuiz(quizWeek); toast("题库已生成。");
  } catch (err) { toast("题库生成失败：" + err.message); }
};

$("#quiz-checkall").onclick = () => {
  [...$("#quiz-list").querySelectorAll(".q-card")]
    .filter((c) => isObjective(c._q.type)).forEach((c) => checkCard(c, true));
  updateScore();
};

$("#quiz-reset").onclick = () => { if (quizSpec) { renderQuizInteractive(quizSpec.questions); $("#quiz-feedback").innerHTML = ""; } };

$("#quiz-essay-save").onclick = async (e) => {
  try {
    await saveQuizFile("Essay.md", $("#quiz-essay").value, e.target);
    await refresh(); toast("综合论述已保存。");
  } catch (err) { toast("保存失败：" + err.message); }
};

$("#quiz-grade").onclick = async (e) => {
  if (!quizSpec) { toast("请先生成交互式题库。"); return; }
  try {
    await saveQuizFile("Answers.md", assembleAnswers(), null);
    toast(`正在提交第 ${quizWeek} 章节答案并生成深度反馈...`);
    const r = await withSpinner(e.target, () => api("/api/grade", jsonBody({ week: quizWeek })));
    renderMarkdown($("#quiz-feedback"), r.feedback);
    await refresh();
    toast(`深度反馈已生成，记录 ${r.findings.length} 个诊断发现。`);
  } catch (err) { toast("反馈生成失败：" + err.message); }
};

// ------------------------------------------------------------------- upload
function uploadFiles(fileList) {
  const fd = new FormData();
  let n = 0;
  [...fileList].forEach((f) => { if (f.name.toLowerCase().endsWith(".pdf")) { fd.append("files", f); n++; } });
  if (!n) { toast("仅支持上传 PDF 文件。"); return; }
  fd.append("week", "new");
  fetch("/api/upload", { method: "POST", body: fd })
    .then((r) => r.json())
    .then((r) => {
      const wk = r && r.week ? String(r.week).padStart(2, "0") : "";
      toast(wk ? `已导入 ${n} 个 PDF，并创建章节 ${wk}。` : `已导入 ${n} 个 PDF。`);
      refresh();
    })
    .catch((e) => toast("上传失败：" + e.message));
}

function wireUpload() {
  const dz = $("#dropzone"), fi = $("#fileinput");
  dz.onclick = () => fi.click();
  fi.onchange = () => { if (fi.files.length) uploadFiles(fi.files); fi.value = ""; };
  ["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); }));
  dz.addEventListener("drop", (e) => uploadFiles(e.dataTransfer.files));
}

// --------------------------------------------------------------------- init
document.querySelectorAll(".tab[data-view]").forEach((t) => t.onclick = () => {
  showView(t.dataset.view);
  if (t.dataset.view === "personalization" && !profileState) loadProfile();
});
$("#open-diagnostic").onclick = openDiagnostic;
$("#profile-load").onclick = loadProfile;
$("#profile-save").onclick = (e) => saveProfile(e.currentTarget);
$("#profile-build").onclick = (e) => buildProfile(e.currentTarget);
$("#path-generate").onclick = (e) => generatePath(e.currentTarget);
$("#path-open").onclick = () => openPath();
$("#rag-ask").onclick = (e) => askRag(e.currentTarget);
$("#rag-index-week").onclick = (e) => indexActiveWeek(e.currentTarget);
$("#subject-select").onchange = (e) => { if (e.target.value) selectSubject(e.target.value); };
$("#subject-new").onclick = newSubject;
$("#subject-rename").onclick = renameSubject;
$("#subject-delete").onclick = deleteSubject;
wireUpload();
refresh();
