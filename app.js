const page = document.getElementById("page");
const unitNav = document.getElementById("unitNav");
const pageSelect = document.getElementById("pageSelect");
const prevPage = document.getElementById("prevPage");
const nextPage = document.getElementById("nextPage");
const pageNumber = document.getElementById("pageNumber");
const goToPage = document.getElementById("goToPage");
const popover = document.getElementById("studyPopover");
const sentenceText = document.getElementById("sentenceText");
const ipaText = document.getElementById("ipaText");
const meaningText = document.getElementById("meaningText");
const roleAvatar = document.getElementById("roleAvatar");
const roleName = document.getElementById("roleName");
const voiceStatusText = document.getElementById("voiceStatusText");
const replayAudio = document.getElementById("replayAudio");
const unitTitle = document.getElementById("unitTitle");
const pageTitle = document.getElementById("pageTitle");
const toast = document.getElementById("toast");
const contentRevision = "20260927-cloze-and-roles-v2";

const speakerPalette = [
  ["#75419a", "#f5eef9"], ["#d56843", "#fdf0eb"], ["#2878b5", "#eaf4fb"],
  ["#c44569", "#fbecef"], ["#3c6e71", "#eaf4f3"], ["#b56a24", "#fff2e4"],
];
const speakerProfiles = {
  narrator: ["旁白", "旁", "英式女声 · Emma"],
  millie: ["Millie", "M", "英式女声 · Isabella"], sandy: ["Sandy", "S", "英式女声 · Emma"],
  amy: ["Amy", "A", "英式女声 · Alice"], kitty: ["Kitty", "K", "英式女声 · Lily"],
  nora: ["Nora", "N", "英式女声 · Emma"], simon: ["Simon", "S", "英式男声 · Fable"],
  daniel: ["Daniel", "D", "英式男声 · Daniel"], david: ["David", "D", "英式男声 · George"],
  "mr wu": ["吴老师", "师", "英式男声 · George"], class: ["全班同学", "班", "英式女声 · Lily"],
  "ms li": ["李老师", "师", "英式女声 · Isabella"], "ms lin": ["林老师", "师", "英式女声 · Alice"],
  mum: ["妈妈", "妈", "英式女声 · Emma"], grandpa: ["爷爷", "爷", "英式男声 · George"],
  "sandy & simon": ["Sandy 和 Simon", "同", "本地合成 · 英语女声 SLT（美式）"],
  a: ["A", "A", "本地合成 · 英语女声 SLT（美式）"],
  b: ["B", "B", "本地合成 · 英语男声 Kal（美式）"],
  grandma: ["奶奶", "奶", "英式女声 · Emma"], andy: ["Andy", "A", "英式男声 · Fable"],
  robin: ["Robin", "R", "英式男声 · Daniel"], shirley: ["Shirley", "S", "英式女声 · Isabella"],
  dad: ["爸爸", "爸", "英式男声 · George"], emily: ["Emily", "E", "英式女声 · Alice"],
  sarah: ["Sarah", "S", "英式女声 · Lily"], salesperson: ["售货员", "售", "英式男声 · Fable"],
};

let manifest;
let unitData;
let currentUnit = 1;
let currentPage = 7;
let currentSentence = null;
let currentIndex = -1;
let activeButtons = [];
let activeAnchor = null;
let previewButtons = [];
let previewTimer = null;
let navigationToken = 0;
const catalog = document.getElementById("catalog");
const catalogToggle = document.getElementById("catalogToggle");
const audioPlayer = new Audio();
audioPlayer.preload = "auto";

function params() {
  const search = new URLSearchParams(location.search);
  const requested = Number(search.get("page"));
  return { page: Number.isInteger(requested) ? requested : 0 };
}

function unitForPage(pageValue) {
  return manifest.units.find(unit => pageValue >= unit.start && pageValue <= unit.end);
}

async function boot() {
  manifest = await fetchJson("data/manifest.json");
  pageNumber.max = String(Math.max(...manifest.units.map(unit => unit.end)));
  setCatalogClosed(window.matchMedia("(max-width: 900px)").matches);
  const initial = params();
  renderUnitNav();
  const initialUnit = unitForPage(initial.page) || manifest.units[0];
  await openUnit(initialUnit.id, unitForPage(initial.page) ? initial.page : initialUnit.start, false);
}

async function fetchJson(path) {
  const url = new URL(path, location.href);
  url.searchParams.set("v", contentRevision);
  const response = await fetch(url);
  if (!response.ok) throw new Error(`无法加载 ${path} (${response.status})`);
  return response.json();
}

function setCatalogClosed(closed) {
  catalog.classList.toggle("closed", closed);
  catalog.inert = closed;
  document.body.classList.toggle("catalog-closed", closed);
  catalogToggle.setAttribute("aria-expanded", String(!closed));
  catalogToggle.setAttribute("aria-label", closed ? "打开单元目录" : "关闭单元目录");
}

function renderUnitNav() {
  unitNav.replaceChildren(...manifest.units.map(unit => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `unit-link${unit.frontMatter ? " front-matter" : ""}`;
    button.dataset.unit = String(unit.id);
    button.innerHTML = unit.frontMatter
      ? `<span>0—5 页</span>封面与目录`
      : unit.kind === "project"
        ? `<span>PROJECT ${unit.id === 9 ? 1 : 2} · ${unit.start}—${unit.end} 页</span>${unit.title}`
        : unit.kind === "workbook"
          ? `<span>WORKBOOK · ${unit.start}—${unit.end} 页</span>${unit.title}`
          : unit.kind === "appendix"
            ? `<span>附录 · ${unit.start}—${unit.end} 页</span>${unit.title}`
        : `<span>UNIT ${unit.id} · ${unit.start}—${unit.end} 页</span>${unit.title}`;
    button.addEventListener("click", () => {
      if (window.matchMedia("(max-width: 900px)").matches) setCatalogClosed(true);
      void openUnit(unit.id, unit.start);
    });
    return button;
  }));
}

async function openUnit(unitId, requestedPage, push = true) {
  const token = ++navigationToken;
  hideSentence();
  const target = manifest.units.find(unit => unit.id === Number(unitId)) || manifest.units[0];
  let loaded;
  try { loaded = await fetchJson(`data/unit-${target.id}.json`); }
  catch (error) {
    if (token === navigationToken) showToast("单元数据加载失败，请刷新后重试。");
    console.error(error);
    return;
  }
  if (token !== navigationToken) return;
  currentUnit = target.id;
  unitData = loaded;
  currentPage = Math.min(unitData.pages.at(-1).page, Math.max(unitData.pages[0].page, requestedPage));
  unitNav.querySelectorAll(".unit-link").forEach(button => button.classList.toggle("active", Number(button.dataset.unit) === currentUnit));
  unitTitle.textContent = unitData.frontMatter
    ? `秋实中学牛琮一 · ${unitData.displayTitle}`
    : unitData.kind === "project" || unitData.kind === "workbook" || unitData.kind === "appendix"
      ? `秋实中学牛琮一 · ${unitData.displayTitle}`
      : `秋实中学牛琮一 · Unit ${unitData.id} · ${unitData.title}`;
  pageSelect.replaceChildren(...unitData.pages.map(item => {
    const option = document.createElement("option");
    option.value = String(item.page);
    option.textContent = item.label || `第 ${item.page} 页`;
    return option;
  }));
  pageSelect.value = String(currentPage);
  await renderPage(push, token);
}

async function renderPage(push = false, token = ++navigationToken) {
  if (token !== navigationToken) return;
  hideSentence();
  const pageData = unitData.pages.find(item => item.page === currentPage);
  const pageLabel = pageData.label || `教材第 ${currentPage} 页`;
  pageTitle.textContent = `${pageLabel} · ${pageData.sentences.length} 个英语学习单位`;
  pageSelect.value = String(currentPage);
  pageNumber.value = String(currentPage);
  const availablePages = manifest.units.flatMap(unit =>
    Array.from({ length: unit.end - unit.start + 1 }, (_, index) => unit.start + index)
  );
  const globalIndex = availablePages.indexOf(currentPage);
  prevPage.disabled = globalIndex <= 0;
  nextPage.disabled = globalIndex < 0 || globalIndex >= availablePages.length - 1;
  const loading = document.createElement("div");
  loading.className = "page-loading";
  loading.textContent = `正在打开${pageLabel}…`;
  page.replaceChildren(loading);
  const image = new Image();
  image.className = "page-image";
  image.alt = `译林英语七年级上册${pageLabel}`;
  image.src = pageData.image;
  try { await image.decode(); }
  catch (error) {
    if (token === navigationToken) loading.textContent = "教材图片加载失败，请刷新后重试。";
    console.error(error);
    return;
  }
  if (token !== navigationToken) return;
  page.replaceChildren(image);
  page.style.setProperty("--page-image", `url("${pageData.image}")`);
  pageData.sentences.forEach((sentence, index) => createHotspots(sentence, index));
  if (currentPage >= 149 && currentPage <= 163) trimWordlistOverlaps();
  if (push) history.pushState({}, "", `?page=${currentPage}`);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function createHotspots(sentence, index) {
  sentence.rects.forEach((rect, fragmentIndex) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "hotspot";
    button.dataset.sentenceIndex = String(index);
    button.dataset.fragmentIndex = String(fragmentIndex);
    const wordlist = currentPage >= 149 && currentPage <= 163;
    const horizontalPadding = wordlist ? 0.12 : 0.58;
    const verticalPadding = wordlist ? 0 : 0.2;
    const left = Math.max(0, rect.x - horizontalPadding);
    const top = Math.max(0, rect.y - verticalPadding);
    const right = Math.min(100, rect.x + rect.w + horizontalPadding);
    const bottom = Math.min(100, rect.y + rect.h + verticalPadding);
    Object.assign(button.style, {
      left: `${left}%`,
      top: `${top}%`,
      width: `${right - left}%`,
      height: `${bottom - top}%`,
    });
    button.setAttribute("aria-label", `学习句子：${sentence.text}`);
    button.addEventListener("mouseenter", () => showPreview(index));
    button.addEventListener("mouseleave", schedulePreviewHide);
    button.addEventListener("focus", () => showPreview(index));
    button.addEventListener("blur", schedulePreviewHide);
    button.addEventListener("click", event => { event.stopPropagation(); showSentence(index, button); });
    page.appendChild(button);
  });
}

// Wordlist rows are close together. Make neighbouring hit targets meet at their
// midpoint so the lower word cannot intercept a click on the upper word.
function trimWordlistOverlaps() {
  const buttons = [...page.querySelectorAll(".hotspot")];
  const boxes = buttons.map(button => ({
    button,
    x: parseFloat(button.style.left),
    y: parseFloat(button.style.top),
    w: parseFloat(button.style.width),
    h: parseFloat(button.style.height),
  }));
  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      const left = boxes[i].x <= boxes[j].x ? boxes[i] : boxes[j];
      const right = left === boxes[i] ? boxes[j] : boxes[i];
      if (Math.abs(left.y - right.y) < 0.7 &&
          left.x + left.w > right.x && left.x + left.w < right.x + right.w) {
        const edge = (left.x + left.w + right.x) / 2;
        right.w -= edge - right.x;
        right.x = edge;
        left.w = edge - left.x;
      }
      const first = boxes[i].y <= boxes[j].y ? boxes[i] : boxes[j];
      const second = first === boxes[i] ? boxes[j] : boxes[i];
      const rowDistance = second.y - first.y;
      const sharedWidth = Math.min(first.x + first.w, second.x + second.w) - Math.max(first.x, second.x);
      if (rowDistance < 0.7 || sharedWidth <= 0 || first.y + first.h <= second.y) continue;
      const boundary = (first.y + first.h / 2 + second.y + second.h / 2) / 2;
      first.h = Math.min(first.h, boundary - first.y);
      second.h = Math.max(0.5, second.y + second.h - Math.max(second.y, boundary));
      second.y = Math.max(second.y, boundary);
    }
  }
  boxes.forEach(({ button, x, y, w, h }) => {
    button.style.left = `${x}%`;
    button.style.width = `${w}%`;
    button.style.top = `${y}%`;
    button.style.height = `${h}%`;
  });
}

function paintOriginal(buttons) {
  const pageBounds = page.getBoundingClientRect();
  buttons.forEach(button => {
    const bounds = button.getBoundingClientRect();
    button.style.setProperty("--page-bg-width", `${pageBounds.width}px`);
    button.style.setProperty("--hotspot-bg-x", `${pageBounds.left - bounds.left}px`);
    button.style.setProperty("--hotspot-bg-y", `${pageBounds.top - bounds.top}px`);
  });
}

function showPreview(index) {
  clearTimeout(previewTimer);
  previewButtons.forEach(button => button.classList.remove("preview"));
  previewButtons = [...page.querySelectorAll(`.hotspot[data-sentence-index="${index}"]`)];
  paintOriginal(previewButtons);
  previewButtons.forEach(button => button.classList.add("preview"));
  document.body.classList.add("preview-mode");
}

function schedulePreviewHide() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(() => {
    previewButtons.forEach(button => button.classList.remove("preview"));
    previewButtons = [];
    document.body.classList.remove("preview-mode");
  }, 60);
}

function profileFor(speaker) {
  const key = String(speaker || "narrator").toLowerCase();
  const base = speakerProfiles[key] || [key.replace(/\b\w/g, char => char.toUpperCase()), key[0]?.toUpperCase() || "旁", /mr|dad|father|simon|daniel|david|will|boy|man/.test(key) ? "英式男声 · George" : "英式女声 · Emma"];
  let hash = 0;
  for (const char of key) hash = ((hash << 5) - hash + char.charCodeAt(0)) | 0;
  return { name: base[0], avatar: base[1], voice: base[2], colors: speakerPalette[Math.abs(hash) % speakerPalette.length] };
}

function showSentence(index, anchor) {
  clearTimeout(previewTimer);
  previewButtons.forEach(button => button.classList.remove("preview"));
  previewButtons = [];
  document.body.classList.remove("preview-mode");
  audioPlayer.pause();
  currentIndex = index;
  currentSentence = unitData.pages.find(item => item.page === currentPage).sentences[index];
  activeAnchor = anchor;
  activeButtons.forEach(button => button.classList.remove("active"));
  activeButtons = [...page.querySelectorAll(`.hotspot[data-sentence-index="${index}"]`)];
  const profile = profileFor(currentSentence.speaker);
  document.documentElement.style.setProperty("--speaker-color", profile.colors[0]);
  document.documentElement.style.setProperty("--speaker-soft", profile.colors[1]);
  paintOriginal(activeButtons);
  activeButtons.forEach(button => button.classList.add("active"));
  roleAvatar.textContent = profile.avatar;
  roleName.textContent = profile.name;
  sentenceText.textContent = currentSentence.text;
  ipaText.textContent = currentSentence.ipa || "正在完善音标";
  meaningText.textContent = currentSentence.meaning || "正在完善汉语意思";
  voiceStatusText.textContent = `AI 配音 · ${currentSentence.voice || profile.voice}`;
  popover.classList.remove("hidden");
  document.body.classList.add("focus-mode");
  requestAnimationFrame(() => positionPopover(anchor));
  void playCurrentAudio();
}

function positionPopover(anchor) {
  if (!anchor || popover.classList.contains("hidden")) return;
  if (window.innerWidth <= 900) {
    popover.style.left = "12px";
    popover.style.top = "auto";
    popover.style.bottom = "12px";
    return;
  }
  popover.style.bottom = "auto";
  const rect = anchor.getBoundingClientRect();
  const gap = 14;
  const cardWidth = popover.offsetWidth;
  const cardHeight = popover.offsetHeight;
  const fragments = activeButtons.map(button => button.getBoundingClientRect());
  const sentenceLeft = Math.min(...fragments.map(fragment => fragment.left));
  const sentenceRight = Math.max(...fragments.map(fragment => fragment.right));
  const sentenceTop = Math.min(...fragments.map(fragment => fragment.top));
  const sentenceBottom = Math.max(...fragments.map(fragment => fragment.bottom));
  let left;
  let top = Math.max(74, Math.min(rect.top - 18, window.innerHeight - cardHeight - 16));
  if (sentenceRight + gap + cardWidth <= window.innerWidth - 16) {
    left = sentenceRight + gap;
  } else if (sentenceLeft - gap - cardWidth >= 16) {
    left = sentenceLeft - gap - cardWidth;
  } else {
    left = Math.max(16, Math.min(rect.left, window.innerWidth - cardWidth - 16));
    if (sentenceTop - gap - cardHeight >= 74) top = sentenceTop - gap - cardHeight;
    else if (sentenceBottom + gap + cardHeight <= window.innerHeight - 16) top = sentenceBottom + gap;
  }
  popover.style.left = `${left}px`;
  popover.style.top = `${top}px`;
}

function hideSentence() {
  audioPlayer.pause();
  popover.classList.remove("speaking");
  popover.classList.add("hidden");
  document.body.classList.remove("preview-mode", "focus-mode");
  activeButtons.forEach(button => button.classList.remove("active"));
  activeButtons = [];
  activeAnchor = null;
  currentSentence = null;
  currentIndex = -1;
}

async function playCurrentAudio() {
  if (!currentSentence?.audio) return;
  const url = new URL(currentSentence.audio, location.href);
  url.searchParams.set("v", contentRevision);
  audioPlayer.src = url.href;
  audioPlayer.currentTime = 0;
  try { await audioPlayer.play(); }
  catch (error) {
    if (error.name === "AbortError") return; // another word was selected meanwhile
    console.warn("Audio playback failed", error);
    showToast("音频暂时没有成功加载，请稍后重试。");
  }
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 3200);
}

async function jumpToPage() {
  const requested = pageNumber.value.trim() === "" ? NaN : Number(pageNumber.value);
  const targetUnit = Number.isInteger(requested) ? unitForPage(requested) : null;
  if (!targetUnit) {
    pageNumber.value = String(currentPage);
    showToast("请输入教材范围内的页码：0—165页；0—5为封面与目录。");
    return;
  }
  if (targetUnit.id === currentUnit) {
    currentPage = requested;
    await renderPage(true);
  } else {
    await openUnit(targetUnit.id, requested, true);
  }
}

async function goRelativePage(offset) {
  const availablePages = manifest.units.flatMap(unit =>
    Array.from({ length: unit.end - unit.start + 1 }, (_, index) => unit.start + index)
  );
  const currentIndex = availablePages.indexOf(currentPage);
  const targetPage = availablePages[currentIndex + offset];
  if (targetPage === undefined) return;
  const targetUnit = unitForPage(targetPage);
  if (targetUnit.id === currentUnit) {
    currentPage = targetPage;
    await renderPage(true);
  } else {
    await openUnit(targetUnit.id, targetPage, true);
  }
}

pageSelect.addEventListener("change", async () => { currentPage = Number(pageSelect.value); await renderPage(true); });
prevPage.addEventListener("click", async () => { if (!prevPage.disabled) await goRelativePage(-1); });
nextPage.addEventListener("click", async () => { if (!nextPage.disabled) await goRelativePage(1); });
goToPage.addEventListener("click", jumpToPage);
pageNumber.addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); void jumpToPage(); } });
catalogToggle.addEventListener("click", () => setCatalogClosed(!catalog.classList.contains("closed")));
popover.addEventListener("click", event => event.stopPropagation());
replayAudio.addEventListener("click", () => { void playCurrentAudio(); });
document.addEventListener("click", hideSentence);
document.addEventListener("keydown", event => { if (event.key === "Escape") hideSentence(); });
audioPlayer.addEventListener("play", () => popover.classList.add("speaking"));
audioPlayer.addEventListener("pause", () => popover.classList.remove("speaking"));
audioPlayer.addEventListener("ended", () => popover.classList.remove("speaking"));
audioPlayer.addEventListener("error", () => { popover.classList.remove("speaking"); showToast("音频文件没有成功加载。"); });
window.addEventListener("resize", () => positionPopover(activeAnchor));
window.addEventListener("scroll", () => positionPopover(activeAnchor), { passive: true });
window.addEventListener("popstate", async () => {
  const next = params();
  const nextUnit = unitForPage(next.page) || manifest.units[0];
  await openUnit(nextUnit.id, unitForPage(next.page) ? next.page : nextUnit.start, false);
});
boot().catch(() => { page.innerHTML = '<div class="page-loading">页面数据加载失败，请刷新后重试。</div>'; });
