import "./style.css";

const words = {
  zh: {
    project: "私人房间 · 三维重建",
    explore: "空间探索",
    gallery: "渲染画廊",
    notes: "制作方法",
    language: "EN",
    eyebrow: "A PERSONAL SPACE, RECONSTRUCTED",
    title: "把日常，留在空间里。",
    intro:
      "从 16 张实拍照片出发，重建那些熟悉的角落。木纹、织物、光线，以及生活留下的小细节。",
    tag1: "照片驱动复刻",
    tag2: "Blender 场景",
    tag3: "可交互浏览",
    live: "INTERACTIVE / 实时三维",
    viewerTitle: "走近这个房间",
    drag: "拖动旋转 · 滚轮缩放 · 右键平移",
    loading: "正在载入房间",
    loadingHint: "首次打开需要下载模型与材质。",
    ready: "场景已就绪",
    loadError: "三维场景暂未载入",
    loadErrorHint: "可以重试载入，或向下浏览渲染画廊。",
    retry: "重新载入",
    viewpoints: "观察视角",
    dollhouse: "空间全景",
    bedroom: "床与窗",
    kitchen: "厨房与入口",
    desk: "学习角",
    dollhouseDesc: "展开房间，观察家具与空间的关系。",
    bedroomDesc: "回到窗边：百叶、床架和柔软织物。",
    kitchenDesc: "从生活区望向厨房与入口。",
    deskDesc: "靠近书桌，查看学习与生活的细节。",
    adjust: "画面设置",
    cutaway: "隐藏近侧墙面",
    cutawayHelp: "全景模式自动打开，室内视角自动关闭。",
    lighting: "光线",
    daylight: "自然日光",
    warm: "暖色室内",
    exposure: "曝光",
    quality: "画质",
    high: "精细",
    balanced: "流畅",
    qualityHelp: "精细模式提高分辨率与阴影质量。",
    autoRotate: "自动环绕",
    screenshot: "保存当前画面",
    fullscreen: "全屏查看",
    exitFullscreen: "退出全屏",
    reset: "重置视角",
    modelDownload: "下载完整模型（GLB，42 MB）",
    noteLabel: "关于精度",
    shortNote:
      "依照照片重建；房间尺寸为估算。可交互画面的光照与材质效果与离线渲染有所差异。",
    galleryEyebrow: "01 / RENDERED STUDIES",
    galleryTitle: "熟悉的每一面。",
    galleryIntro:
      "四个观察角度，记录这个小空间的材质、陈设与光影。点击图片查看大图。",
    bedroomCaption: "床与窗 · 柔软织物与百叶光线",
    kitchenCaption: "厨房 · 橡木柜体与日常用品",
    deskCaption: "书桌 · 桌面物件与学习角",
    overviewCaption: "全景 · 家具与空间关系",
    unavailable: "此渲染尚未包含在当前构建中",
    close: "关闭",
    archiveEyebrow: "02 / NOTES",
    archiveTitle: "制作方法",
    archiveIntro:
      "物品和材质按照片制作，尺度以一张标准 Twin XL 床垫为准。",
    photosTitle: "16 张参考照片",
    photosText:
      "覆盖房间、家具、床品、天花与桌面。利用不同观察角度核对位置和遮挡关系。",
    scaleTitle: "0.914 × 2.032 m",
    scaleText:
      "标准 Twin XL 床垫（36 × 80 英寸）。它提供尺度参考；房间长宽和层高仍需实测。",
    methodTitle: "可编辑的场景",
    methodText:
      "Blender 中构建几何、材质与灯光；网页以 GLB 展示。未拍到的表面与尺寸采用明确记录的推算。",
    footerTitle: "Room, remembered.",
    footerText: "一个被认真记录的日常空间。",
    footerNote: "照片参考重建 · 尺寸非实测",
    captured: "画面已保存",
    captureFailed: "画面保存失败，请重试",
    fullscreenFailed: "此浏览器暂不支持全屏",
    modelLabel: "房间三维模型",
    envelope: "估算空间（宽 × 长 × 高）",
    shellState: "建筑",
    furnishingState: "家具与物品",
    renderCount: "四个观察角度",
    noWebgl: "此设备暂不支持 WebGL 2，可继续查看下方渲染画廊。",
  },
  en: {
    project: "A PERSONAL ROOM · RECONSTRUCTED",
    explore: "Explore",
    gallery: "Render gallery",
    notes: "How it was built",
    language: "中文",
    eyebrow: "A PERSONAL SPACE, RECONSTRUCTED",
    title: "Room, remembered.",
    intro:
      "A familiar place, rebuilt from 16 photographs. The grain of the wood, the folds of the fabric, the light—and the little details of everyday life.",
    tag1: "Photo-guided",
    tag2: "Blender scene",
    tag3: "Interactive 3D",
    live: "INTERACTIVE / REAL-TIME 3D",
    viewerTitle: "A closer look",
    drag: "Drag to orbit · Scroll to zoom · Right-drag to pan",
    loading: "Bringing the room into view",
    loadingHint: "The first visit downloads the model and its materials.",
    ready: "Scene ready",
    loadError: "The 3D room could not load",
    loadErrorHint: "Try again, or explore the rendered gallery below.",
    retry: "Try again",
    viewpoints: "VIEWPOINTS",
    dollhouse: "The whole room",
    bedroom: "Bed & window",
    kitchen: "Kitchen & entrance",
    desk: "The study corner",
    dollhouseDesc: "Open up the room and explore how everything fits together.",
    bedroomDesc: "By the window: blinds, timber and soft layers of fabric.",
    kitchenDesc: "Look back from the living area towards the kitchenette.",
    deskDesc: "Come closer to the objects that make this a working space.",
    adjust: "THE VIEW",
    cutaway: "Cut away near walls",
    cutawayHelp: "On for the whole-room view; off for interior views.",
    lighting: "Lighting",
    daylight: "Natural daylight",
    warm: "Warm interior",
    exposure: "Exposure",
    quality: "Quality",
    high: "Detailed",
    balanced: "Smooth",
    qualityHelp: "Detailed uses higher resolution and shadow quality.",
    autoRotate: "Auto orbit",
    screenshot: "Save this view",
    fullscreen: "Full screen",
    exitFullscreen: "Exit full screen",
    reset: "Reset view",
    modelDownload: "Download the full model (GLB, 42 MB)",
    noteLabel: "A NOTE ON ACCURACY",
    shortNote:
      "Rebuilt from photographs; room dimensions are estimated. Real-time lighting and materials differ from the offline renders.",
    galleryEyebrow: "01 / RENDERED STUDIES",
    galleryTitle: "Every familiar angle.",
    galleryIntro:
      "Four studies of the materials, objects and light in a small personal space. Select an image to view it in detail.",
    bedroomCaption: "Bed & window · Fabric and filtered light",
    kitchenCaption: "Kitchen · Oak cabinetry and everyday objects",
    deskCaption: "The desk · A corner for study",
    overviewCaption: "Overview · The space and its contents",
    unavailable: "This render is not included in the current build",
    close: "Close",
    archiveEyebrow: "02 / NOTES",
    archiveTitle: "How it was built",
    archiveIntro:
      "The photographs guide the objects and materials. A standard Twin XL mattress sets the scale.",
    photosTitle: "16 reference photographs",
    photosText:
      "Views of the room, furniture, bedding, ceiling and desktop. Multiple angles help resolve positions and occlusions.",
    scaleTitle: "0.914 × 2.032 m",
    scaleText:
      "A standard Twin XL mattress (36 × 80 in). A scale reference; the room itself has not been measured.",
    methodTitle: "An editable scene",
    methodText:
      "Geometry, materials and lighting built in Blender; a GLB for the browser. Unseen surfaces and dimensions are documented estimates.",
    footerTitle: "Room, remembered.",
    footerText: "An everyday space, carefully observed.",
    footerNote: "Photo-guided reconstruction · Dimensions estimated",
    captured: "View saved",
    captureFailed: "Could not save the view. Please try again.",
    fullscreenFailed: "Full screen is unavailable in this browser.",
    modelLabel: "Interactive 3D room",
    envelope: "Estimated envelope (W × L × H)",
    shellState: "Architecture",
    furnishingState: "Furniture & objects",
    renderCount: "Four viewpoints",
    noWebgl:
      "WebGL 2 is unavailable on this device. You can still explore the render gallery below.",
  },
};
let language = /^zh/i.test(navigator.language || "") ? "zh" : "en";
try {
  const saved = localStorage.getItem("room-language");
  if (saved === "en" || saved === "zh") language = saved;
} catch {
  /* Storage may be disabled. */
}
const t = (key) => words[language][key] ?? key;
const icon = (name) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">${
    {
      cube: '<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/>',
      arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
      expand: '<path d="M9 4H4v5m11-5h5v5M4 15v5h5m11-5v5h-5"/>',
      camera:
        '<path d="M3 7h5l2-3h4l2 3h5v13H3z"/><circle cx="12" cy="13" r="4"/>',
      reset: '<path d="M4 10a8 8 0 1 1 1 8M4 4v6h6"/>',
      download: '<path d="M12 3v12m-5-5 5 5 5-5M4 15v6h16v-6"/>',
      plus: '<path d="M12 5v14M5 12h14"/>',
      close: '<path d="m6 6 12 12M6 18 18 6"/>',
    }[name] ?? ""
  }</svg>`;
const label = (key, tag = "span", extra = "") =>
  `<${tag} data-i18n="${key}" ${extra}>${t(key)}</${tag}>`;
const renderKeys = ["bedroom", "kitchen", "desk", "overview"];
const asset = (path) => `${import.meta.env.BASE_URL}${path}`;

document.querySelector("#app").innerHTML = `
  <header class="topbar"><a class="brand" href="#" aria-label="Room, remembered home">${icon("cube")}<span>ROOM<span class="brand-dot">.</span></span></a>${label("project", "span", 'class="project-label"')}<nav aria-label="Main navigation"><a href="#room">${label("explore")}</a><a href="#gallery">${label("gallery")}</a><a href="#archive">${label("notes")}</a></nav><button class="language-button" id="language" aria-label="Switch language">${label("language")}</button></header>
  <main>
    <section class="intro"><div>${label("eyebrow", "p", 'class="eyebrow"')}${label("title", "h1")}${label("intro", "p", 'class="intro-text"')}</div><div class="intro-aside"><span class="edition">VERSION<br><strong>1.0</strong></span><div class="tags">${label("tag1")}${label("tag2")}${label("tag3")}</div></div></section>
    <section id="room" class="room-section" aria-labelledby="viewer-title">
      <div class="section-bar"><div><span class="status-dot"></span>${label("live")}</div><span class="section-index">360° / 3D</span></div>
      <div class="viewer-layout"><div class="stage" id="stage">
        <div class="stage-caption">${label("viewerTitle", "h2", 'id="viewer-title"')}<p id="view-description">${t("dollhouseDesc")}</p></div>
        <div id="canvas-host" role="img" aria-label="${t("modelLabel")}" tabindex="0"></div>
        <div class="loading" id="loading" role="status" aria-live="polite"><div class="loading-symbol">${icon("cube")}</div><p id="loading-title">${t("loading")}</p><span id="loading-hint">${t("loadingHint")}</span><div class="progress-track"><i id="progress"></i></div><span id="progress-text">0%</span><button id="retry" class="primary-button" hidden>${label("retry")}</button></div>
        <div class="stage-toolbar"><button id="reset" class="icon-button" data-title="reset">${icon("reset")}</button><button id="fullscreen" class="icon-button" data-title="fullscreen">${icon("expand")}</button><button id="screenshot" class="icon-button" data-title="screenshot" disabled>${icon("camera")}</button></div>
        <div class="stage-bottom"><span class="stage-hint" data-i18n="drag">${t("drag")}</span><span class="scene-status" id="scene-status">GLB / PBR</span></div>
      </div><aside class="control-panel"><fieldset><legend data-i18n="viewpoints">${t("viewpoints")}</legend><div class="view-buttons">${["dollhouse", "bedroom", "kitchen", "desk"].map((key, i) => `<button class="view-button ${i === 0 ? "active" : ""}" data-view="${key}" aria-pressed="${i === 0}"><span class="view-number">0${i + 1}</span>${label(key)}${icon("arrow")}</button>`).join("")}</div></fieldset>
        <fieldset class="adjustments"><legend data-i18n="adjust">${t("adjust")}</legend><label class="switch-row"><span data-i18n="cutaway">${t("cutaway")}</span><input id="cutaway" type="checkbox" role="switch" checked/><span class="switch" aria-hidden="true"></span></label><p class="control-help" data-i18n="cutawayHelp">${t("cutawayHelp")}</p><div class="select-row"><label for="lighting" data-i18n="lighting">${t("lighting")}</label><select id="lighting"><option value="daylight" data-i18n="daylight">${t("daylight")}</option><option value="warm" data-i18n="warm">${t("warm")}</option></select></div><div class="range-label"><label for="exposure" data-i18n="exposure">${t("exposure")}</label><output for="exposure" id="exposure-value">0.80</output></div><input type="range" id="exposure" min="0.5" max="1.8" step="0.05" value="0.8"/><div class="select-row"><label for="quality" data-i18n="quality">${t("quality")}</label><select id="quality"><option value="high" data-i18n="high">${t("high")}</option><option value="balanced" data-i18n="balanced">${t("balanced")}</option></select></div><p class="control-help" data-i18n="qualityHelp">${t("qualityHelp")}</p><label class="switch-row"><span data-i18n="autoRotate">${t("autoRotate")}</span><input id="rotate" type="checkbox" role="switch"/><span class="switch" aria-hidden="true"></span></label></fieldset>
        <a href="https://github.com/appleweiping/room-replica/releases/download/v1.0.0/room.glb" class="download-button" id="model-download">${icon("download")}${label("modelDownload")}</a><div class="accuracy-note">${label("noteLabel", "span", 'class="tiny-label"')}${label("shortNote", "p")}</div>
      </aside></div>
    </section>
    <section id="gallery" class="gallery-section"><div class="section-heading"><div>${label("galleryEyebrow", "p", 'class="eyebrow"')}${label("galleryTitle", "h2")}</div>${label("galleryIntro", "p")}</div><div class="gallery-grid">${renderKeys.map((key, i) => `<button class="gallery-item" data-render="${key}" aria-label="${t(key === "overview" ? "overviewCaption" : key + "Caption")}"><div class="gallery-image"><img src="${asset(`renders/${key}.jpg`)}" alt="${t(key + "Caption")}" loading="lazy"/><span class="render-fallback" data-i18n="unavailable">${t("unavailable")}</span><span class="enlarge">${icon("plus")}</span></div><div class="gallery-caption"><span class="gallery-number">0${i + 1}</span>${label(key + "Caption")}<span class="image-type">BLENDER RENDER</span></div></button>`).join("")}</div></section>
    <section id="archive" class="archive-section"><div class="section-heading"><div>${label("archiveEyebrow", "p", 'class="eyebrow"')}${label("archiveTitle", "h2")}</div>${label("archiveIntro", "p")}</div><div class="archive-grid">${[
      ["photos", "01"],
      ["scale", "02"],
      ["method", "03"],
    ]
      .map(
        ([key, i]) =>
          `<article><span class="archive-index">${i} / ${key.toUpperCase()}</span>${label(key + "Title", "h3")}${label(key + "Text", "p")}</article>`,
      )
      .join("")}</div></section>
  </main>
  <footer><div>${label("footerTitle", "p", 'class="footer-title"')}${label("footerText", "p")}</div>${label("footerNote", "span")}</footer>
  <dialog id="image-dialog"><button class="dialog-close icon-button" id="dialog-close" data-title="close">${icon("close")}</button><img id="dialog-image" alt=""/><p id="dialog-caption"></p></dialog><div class="toast" id="toast" role="status" aria-live="polite"></div>`;

let currentView = "dollhouse";
let estimatedEnvelope;
const envelopeLine = document.createElement("p");
envelopeLine.className = "envelope-line";
envelopeLine.hidden = true;
document.querySelector(".accuracy-note").append(envelopeLine);
let state = "loading";
let viewer;
let toastTimer;
const modelDownload = document.querySelector("#model-download");
modelDownload.setAttribute("aria-disabled", "true");
modelDownload.setAttribute("tabindex", "-1");
modelDownload.addEventListener("click", (event) => {
  if (state !== "ready") event.preventDefault();
});
function toast(key) {
  const el = document.querySelector("#toast");
  el.textContent = t(key);
  el.classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("visible"), 3000);
}
function localize() {
  if (estimatedEnvelope) {
    envelopeLine.textContent = `${t("envelope")} · ${estimatedEnvelope.map((value) => value.toFixed(2)).join(" × ")} m`;
  }
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-title]").forEach((el) => {
    el.title = t(el.dataset.title);
    el.setAttribute("aria-label", t(el.dataset.title));
  });
  document.querySelector("#view-description").textContent = t(
    currentView + "Desc",
  );
  document
    .querySelector("#canvas-host")
    .setAttribute("aria-label", t("modelLabel"));
  document.querySelectorAll("[data-render]").forEach((el) => {
    el.setAttribute("aria-label", t(el.dataset.render + "Caption"));
    el.querySelector("img").alt = t(el.dataset.render + "Caption");
  });
  document.querySelector("#loading-title").textContent = t(
    state === "error" ? "loadError" : "loading",
  );
  document.querySelector("#loading-hint").textContent = t(
    state === "error" ? "loadErrorHint" : "loadingHint",
  );
}
document.querySelector("#language").addEventListener("click", () => {
  language = language === "zh" ? "en" : "zh";
  try {
    localStorage.setItem("room-language", language);
  } catch {}
  localize();
});
localize();

document
  .querySelectorAll(".gallery-item img")
  .forEach((img) =>
    img.addEventListener("error", () =>
      img.closest(".gallery-item").classList.add("unavailable"),
    ),
  );
const dialog = document.querySelector("#image-dialog");
document.querySelectorAll("[data-render]").forEach((button) =>
  button.addEventListener("click", () => {
    if (button.classList.contains("unavailable")) return;
    const key = button.dataset.render;
    const image = document.querySelector("#dialog-image");
    image.src = asset(`renders/${key}.jpg`);
    image.alt = t(key + "Caption");
    document.querySelector("#dialog-caption").textContent = t(key + "Caption");
    dialog.showModal();
  }),
);
document
  .querySelector("#dialog-close")
  .addEventListener("click", () => dialog.close());
dialog.addEventListener("click", (e) => {
  if (e.target === dialog) dialog.close();
});

function selectView(key) {
  currentView = key;
  document.querySelectorAll("[data-view]").forEach((el) => {
    const active = el.dataset.view === key;
    el.classList.toggle("active", active);
    el.setAttribute("aria-pressed", String(active));
  });
  document.querySelector("#view-description").textContent = t(key + "Desc");
  document.querySelector("#cutaway").checked = key === "dollhouse";
  document.querySelector("#rotate").checked = false;
  viewer?.setView(key);
  viewer?.setAutoRotate(false);
}
document
  .querySelectorAll("[data-view]")
  .forEach((el) =>
    el.addEventListener("click", () => selectView(el.dataset.view)),
  );
document
  .querySelector("#cutaway")
  .addEventListener("change", (e) => viewer?.setCutaway(e.target.checked));
document
  .querySelector("#rotate")
  .addEventListener("change", (e) => viewer?.setAutoRotate(e.target.checked));
document
  .querySelector("#lighting")
  .addEventListener("change", (e) => viewer?.setLighting(e.target.value));
document.querySelector("#exposure").addEventListener("input", (e) => {
  document.querySelector("#exposure-value").textContent = Number(
    e.target.value,
  ).toFixed(2);
  viewer?.setExposure(Number(e.target.value));
});
document
  .querySelector("#quality")
  .addEventListener("change", (e) => viewer?.setQuality(e.target.value));
document
  .querySelector("#reset")
  .addEventListener("click", () => selectView(currentView));
document.querySelector("#screenshot").addEventListener("click", async () => {
  const button = document.querySelector("#screenshot");
  if (!viewer) return;
  button.disabled = true;
  try {
    await viewer.capture();
    toast("captured");
  } catch {
    toast("captureFailed");
  } finally {
    button.disabled = !viewer;
  }
});
document.querySelector("#fullscreen").addEventListener("click", async () => {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await document.querySelector("#stage").requestFullscreen();
  } catch {
    toast("fullscreenFailed");
  }
});
document.addEventListener("fullscreenchange", () => {
  document.querySelector("#fullscreen").dataset.title =
    document.fullscreenElement ? "exitFullscreen" : "fullscreen";
  localize();
});

async function load() {
  state = "loading";
  document.querySelector("#loading").classList.remove("done", "failed");
  document.querySelector("#loading").setAttribute("aria-hidden", "false");
  document.querySelector("#retry").hidden = true;
  document.querySelector("#progress").style.width = "0%";
  document.querySelector("#progress-text").textContent = "0%";
  localize();
  try {
    if (!viewer) {
      const { RoomViewer } = await import("./viewer.js");
      viewer = new RoomViewer(document.querySelector("#canvas-host"));
    }
    await viewer.load(asset("models/room-web.glb"), (percentage) => {
      document.querySelector("#progress").style.width = `${percentage}%`;
      document.querySelector("#progress-text").textContent = `${percentage}%`;
    });
    viewer.setLighting(document.querySelector("#lighting").value);
    viewer.setExposure(Number(document.querySelector("#exposure").value));
    viewer.setQuality(document.querySelector("#quality").value);
    viewer.setView(currentView, false);
    state = "ready";
    modelDownload.removeAttribute("aria-disabled");
    modelDownload.removeAttribute("tabindex");
    document.querySelector("#loading").classList.add("done");
    document.querySelector("#loading").setAttribute("aria-hidden", "true");
    document.querySelector("#screenshot").disabled = false;
    document.querySelector("#scene-status").textContent =
      `${viewer.meshCount.toLocaleString()} OBJECTS / GLB`;
    document.querySelector("#stage").dataset.ready = "true";
  } catch (error) {
    state = "error";
    document.querySelector("#loading").classList.add("failed");
    document.querySelector("#retry").hidden = false;
    localize();
    if (error.message === "WEBGL_UNAVAILABLE")
      document.querySelector("#loading-hint").textContent = t("noWebgl");
    console.error("Room viewer:", error);
  }
}
document.querySelector("#retry").addEventListener("click", load);
fetch(asset("scene-manifest.json"))
  .then((response) => (response.ok ? response.json() : null))
  .then((manifest) => {
    const dimensions = manifest?.dimensions;
    const values = [dimensions?.width, dimensions?.length, dimensions?.height];
    if (
      dimensions?.status !== "photo-estimated" ||
      !values.every((value) => Number.isFinite(value) && value > 0)
    )
      return;
    estimatedEnvelope = values;
    envelopeLine.hidden = false;
    localize();
  })
  .catch(() => {
    /* Metadata is optional; the scene remains usable without it. */
  });
document
  .querySelector("#canvas-host")
  .addEventListener("viewer-context-lost", () => {
    state = "error";
    document.querySelector("#loading").classList.remove("done");
    document.querySelector("#loading").classList.add("failed");
    document.querySelector("#loading").setAttribute("aria-hidden", "false");
    document.querySelector("#retry").hidden = false;
    document.querySelector("#screenshot").disabled = true;
    if (viewer) {
      viewer.dispose();
      viewer = null;
    }
    localize();
  });
load();
