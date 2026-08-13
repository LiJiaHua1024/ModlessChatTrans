"use strict";

function getApi() {
  return (window.pywebview && window.pywebview.api) ? window.pywebview.api : null;
}

const I18N = {};
const STATE = {
  working: false,
  version: "",
  program: {},
  llmProviders: [],
  traditionalServices: [],
  supportedLanguages: [],
  capture: null,
  translation: null,
  presentation: null,
  send: null,
  context: null,
  glossary: null,
  blacklist: null,
  settings: null,
};

const langOptions = { player: { src: [], tgt: [] }, send: { src: [], tgt: [] } };
const langLoading = { player: false, send: false };

let currentPage = "capture";
let glossSelectedSrc = null;
let updateRelease = null;
let downloadFailed = false;

const TOAST_ICONS = {
  success: '<svg viewBox="0 0 20 20" fill="currentColor"><path d="M10 2a8 8 0 1 1 0 16 8 8 0 0 1 0-16zm3.36 4.65l-4.11 4.1-1.63-1.62a.75.75 0 1 0-1.06 1.06l2.16 2.15c.29.29.77.29 1.06 0l4.64-4.63a.75.75 0 1 0-1.06-1.06z"/></svg>',
  info: '<svg viewBox="0 0 20 20" fill="currentColor"><path d="M10 2a8 8 0 1 1 0 16 8 8 0 0 1 0-16zm0 3.6a1.2 1.2 0 1 0 0 2.4 1.2 1.2 0 0 0 0-2.4zM8.75 8.5a.75.75 0 0 1 .75-.75h.5a.75.75 0 0 1 .75.75v4.25H11a.75.75 0 0 1 0 1.5H9a.75.75 0 0 1 0-1.5h.25V9.25H9.5a.75.75 0 0 1-.75-.75z"/></svg>',
  warning: '<svg viewBox="0 0 20 20" fill="currentColor"><path d="M10 2.75c.33 0 .64.18.8.47l6.68 11.71a.94.94 0 0 1-.81 1.4H3.33a.94.94 0 0 1-.81-1.4L9.2 3.22c.16-.29.47-.47.8-.47zm0 4.36a.75.75 0 0 0-.75.75v3.5a.75.75 0 0 0 1.5 0v-3.5a.75.75 0 0 0-.75-.75zm0 6.14a1 1 0 1 0 0 2 1 1 0 0 0 0-2z"/></svg>',
  error: '<svg viewBox="0 0 20 20" fill="currentColor"><path d="M10 2a8 8 0 1 1 0 16 8 8 0 0 1 0-16zm2.53 5.47a.75.75 0 0 0-1.06 0L10 8.94 8.53 7.47a.75.75 0 0 0-1.06 1.06L8.94 10l-1.47 1.47a.75.75 0 1 0 1.06 1.06L10 11.06l1.47 1.47a.75.75 0 1 0 1.06-1.06L11.06 10l1.47-1.47a.75.75 0 0 0 0-1.06z"/></svg>',
};

function t(key, ...args) {
  let s = I18N[key] !== undefined ? I18N[key] : key;
  if (args && args.length) {
    let i = 0;
    s = s.replace(/\{[^{}]*\}/g, () => {
      const v = args[i++];
      return v !== undefined && v !== null ? String(v) : "{}";
    });
  }
  return s;
}

function $(sel, root) { return (root || document).querySelector(sel); }
function $all(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

function post(url, body) {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  }).then((res) => res.json().catch(() => ({})));
}

function postHandle(url, body) {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  }).then((res) => res.json().catch(() => ({})));
}

/* ═══════════════════════════ i18n 应用 ═══════════════════════════ */

function applyI18n() {
  $all("[data-i18n]").forEach((node) => {
    const key = node.getAttribute("data-i18n");
    if (I18N[key] !== undefined) node.textContent = I18N[key];
  });
  $all("[data-i18n-placeholder]").forEach((node) => {
    const key = node.getAttribute("data-i18n-placeholder");
    if (I18N[key] !== undefined) node.placeholder = I18N[key];
  });
}

/* ═══════════════════════════ Toast ═══════════════════════════ */

function showToast(kind, title, content, duration) {
  const region = $("#toastRegion");
  const toast = el("div", "toast toast-kind-" + kind);

  const icon = el("div", "toast-icon");
  icon.innerHTML = TOAST_ICONS[kind] || TOAST_ICONS.info;

  const body = el("div", "toast-body");
  const titleEl = el("div", "toast-title", title || "");
  body.appendChild(titleEl);
  if (content) {
    const contentEl = el("div", "toast-content", content);
    body.appendChild(contentEl);
  }

  const close = el("button", "toast-close");
  close.innerHTML = '<svg class="icon"><use href="#icon-close"/></svg>';

  toast.appendChild(icon);
  toast.appendChild(body);
  toast.appendChild(close);
  region.appendChild(toast);

  let timer = null;
  const dismiss = () => {
    if (timer) { clearTimeout(timer); timer = null; }
    toast.classList.add("leaving");
    setTimeout(() => { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 250);
  };

  close.addEventListener("click", dismiss);
  if (duration && duration > 0) {
    timer = setTimeout(dismiss, duration);
  }
}

/* ═══════════════════════════ TeachingTip ═══════════════════════════ */

const tipEl = $("#teachingTip");

function showTeachingTip(anchorBtn, content) {
  const tipContent = $("#teachingTipText");
  tipContent.textContent = content;
  tipEl.hidden = false;

  const anchorRect = anchorBtn.getBoundingClientRect();
  const tipRect = tipEl.getBoundingClientRect();
  const spaceBelow = window.innerHeight - anchorRect.bottom;

  let top, left;
  if (spaceBelow > tipRect.height + 24) {
    tipEl.classList.remove("tail-bottom");
    top = anchorRect.bottom + 8;
  } else {
    tipEl.classList.add("tail-bottom");
    top = anchorRect.top - tipRect.height - 8;
  }
  left = Math.max(12, Math.min(anchorRect.left + anchorRect.width / 2 - tipRect.width / 2, window.innerWidth - tipRect.width - 12));
  tipEl.style.top = top + "px";
  tipEl.style.left = left + "px";
}

function hideTeachingTip() {
  tipEl.hidden = true;
}

$("#teachingTipClose").addEventListener("click", hideTeachingTip);
document.addEventListener("pointerdown", (e) => {
  if (tipEl.hidden) return;
  if (tipEl.contains(e.target)) return;
  if (e.target.closest(".help-button")) return;
  hideTeachingTip();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") hideTeachingTip();
});

$all(".help-button").forEach((btn) => {
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const key = btn.getAttribute("data-tip");
    if (tipEl.hidden || tipEl.dataset.currentKey !== key) {
      tipEl.dataset.currentKey = key;
      showTeachingTip(btn, t(key));
    } else {
      hideTeachingTip();
    }
  });
});

/* ═══════════════════════════ 对话框 ═══════════════════════════ */

function setupDialog(dialogId, cancelable = false) {
  const dialog = $(dialogId);
  dialog.addEventListener("cancel", (e) => e.preventDefault());
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog && !cancelable) e.preventDefault();
  });
  return dialog;
}

const confirmDialog = setupDialog("#confirmDialog");
const infoDialog = setupDialog("#infoDialog");
const updateDialog = setupDialog("#updateDialog");
const downloadDialog = setupDialog("#downloadDialog");

let confirmResolver = null;
$("#confirmPrimary").addEventListener("click", () => {
  confirmDialog.close();
  if (confirmResolver) { const r = confirmResolver; confirmResolver = null; r(true); }
});
$("#confirmSecondary").addEventListener("click", () => {
  confirmDialog.close();
  if (confirmResolver) { const r = confirmResolver; confirmResolver = null; r(false); }
});

function showConfirm(title, content, primaryText, secondaryText) {
  $("#confirmTitle").textContent = title;
  $("#confirmContent").textContent = content;
  $("#confirmPrimary").textContent = primaryText || t("ok");
  $("#confirmSecondary").textContent = secondaryText || t("cancel");
  confirmDialog.showModal();
  return new Promise((resolve) => { confirmResolver = resolve; });
}

let infoResolver = null;
$("#infoOk").addEventListener("click", () => {
  infoDialog.close();
  if (infoResolver) { const r = infoResolver; infoResolver = null; r(true); }
});

function showInfo(title, content) {
  $("#infoTitle").textContent = title;
  $("#infoContent").textContent = content;
  $("#infoOk").textContent = t("ok");
  infoDialog.showModal();
  return new Promise((resolve) => { infoResolver = resolve; });
}

/* ═══════════════════════════ 更新对话框 ═══════════════════════════ */

function formatPublishTime(iso) {
  if (!iso) return t("unknown");
  try {
    const d = new Date(iso);
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch (e) {
    return iso;
  }
}

function showUpdateDialog(release, currentVersion, noteHtml) {
  updateRelease = release;
  $("#updCurrentVersion").textContent = "v" + currentVersion;
  $("#updLatestVersion").textContent = release.tag_name || t("unknown");
  $("#updPublishTime").textContent = formatPublishTime(release.published_at);
  const author = release.author || {};
  $("#updPublisher").textContent = (typeof author === "object" && author.login) ? author.login : t("unknown");
  const isPre = !!release.prerelease;
  $("#updPrerelease").hidden = !isPre;
  if (noteHtml) {
    $("#updNotes").innerHTML = noteHtml;
  } else {
    $("#updNotes").textContent = release.body || t("noReleaseNotes");
  }
  const htmlUrl = release.html_url || "";
  const notesLink = $("#updFullNotes");
  if (htmlUrl) {
    notesLink.hidden = false;
    notesLink.href = htmlUrl;
  } else {
    notesLink.hidden = true;
  }
  updateDialog.showModal();
}

$("#updSkipBtn").addEventListener("click", () => updateDialog.close());
$("#updDownloadBtn").addEventListener("click", () => {
  updateDialog.close();
  startDownload();
});

function startDownload() {
  downloadFailed = false;
  $("#dlTitle").textContent = t("downloadingUpdate");
  $("#dlTitle").classList.remove("error-text");
  $("#dlVersion").textContent = updateRelease ? t("downloadingVersion", updateRelease.tag_name || t("unknown")) : "";
  $("#dlPercent").textContent = "0%";
  $("#dlSize").textContent = "0 B / 0 B";
  $("#dlSpeed").textContent = "0 B/s";
  $("#dlTime").textContent = t("calculating");
  $("#dlThreads").textContent = t("detecting");
  $("#dlProgress").classList.remove("error");
  $(".progress-fill", $("#dlProgress")).style.width = "0%";
  const cancelBtn = $("#dlCancelBtn");
  cancelBtn.textContent = t("cancel");
  cancelBtn.disabled = false;
  downloadDialog.showModal();
  post("/api/update/download", {});
}

$("#dlCancelBtn").addEventListener("click", () => {
  $("#dlCancelBtn").disabled = true;
  $("#dlCancelBtn").textContent = t("cancelling");
  post("/api/update/cancel", {});
});

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GiB`;
}

function formatSpeed(bytesPerSec) {
  if (bytesPerSec < 1024) return `${bytesPerSec.toFixed(0)} B/s`;
  if (bytesPerSec < 1024 * 1024) return `${(bytesPerSec / 1024).toFixed(1)} KiB/s`;
  return `${(bytesPerSec / (1024 * 1024)).toFixed(1)} MiB/s`;
}

function formatRemaining(seconds) {
  if (seconds < 60) return t("timeSec", Math.max(0, Math.round(seconds)));
  if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    if (secs > 0) return t("timeMinSec", minutes, secs);
    return t("timeMin", minutes);
  }
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  if (minutes > 0) return t("timeHourMin", hours, minutes);
  return t("timeHour", hours);
}

function handleDownloadProgress(data) {
  if (!downloadDialog.open) {
    startDownload();
  }
  const { downloaded, total, speed } = data;
  if (total > 0) {
    const percent = Math.min(100, Math.floor((downloaded * 100) / total));
    $("#dlPercent").textContent = percent + "%";
    $(".progress-fill", $("#dlProgress")).style.width = percent + "%";
    $("#dlSize").textContent = `${formatSize(downloaded)} / ${formatSize(total)}`;
    if (speed > 0 && percent < 100) {
      $("#dlTime").textContent = formatRemaining((total - downloaded) / speed);
    } else if (percent >= 100) {
      $("#dlTime").textContent = t("complete");
    } else {
      $("#dlTime").textContent = t("calculating");
    }
  }
  $("#dlSpeed").textContent = formatSpeed(speed);
}

function handleDownloadThreadCount(data) {
  if (data.threads > 1) {
    $("#dlThreads").textContent = t("multiThreadDownload", data.threads);
  } else {
    $("#dlThreads").textContent = t("singleThreadDownload");
  }
}

function handleDownloadFinished(data) {
  if (downloadDialog.open) downloadDialog.close();
  const cancelBtn = $("#dlCancelBtn");
  cancelBtn.disabled = false;
  cancelBtn.textContent = t("cancel");
  if (data.path) {
    showInfo(t("downloadDone"), t("downloadDoneContent", data.path));
  } else {
    showToast("info", t("downloadCancelled"), t("downloadCancelledContent"), 3000);
  }
}

function handleDownloadError(data) {
  downloadFailed = true;
  $("#dlTitle").textContent = t("downloadFailed");
  $("#dlTitle").classList.add("error-text");
  $("#dlPercent").textContent = t("error");
  $("#dlProgress").classList.add("error");
  $("#dlSize").textContent = data.error || "";
  const cancelBtn = $("#dlCancelBtn");
  cancelBtn.textContent = t("close");
  cancelBtn.disabled = false;
}

/* ═══════════════════════════ 通用控件初始化 ═══════════════════════════ */

function initClearButtons(root) {
  $all(".win-input", root || document).forEach((box) => {
    const input = box.querySelector("input");
    if (!input) return;
    const sync = () => box.classList.toggle("has-value", !!input.value);
    input.addEventListener("input", sync);
    sync();
    box.querySelector(".input-clear").addEventListener("click", () => {
      input.value = "";
      input.dispatchEvent(new Event("input"));
      input.focus();
    });
  });
}

function initSwitches(root) {
  $all(".win-switch", root || document).forEach((sw) => {
    const input = sw.querySelector(".switch-input");
    const text = sw.querySelector(".switch-text");
    const sync = () => {
      if (text) text.textContent = input.checked ? t("on") : t("off");
    };
    input.addEventListener("change", sync);
    sync();
  });
}

function initComboboxes(root) {
  $all(".win-combobox", root || document).forEach((combo) => {
    const input = combo.querySelector(".combobox-input");
    const chevron = combo.querySelector(".combobox-chevron");
    const popup = combo.querySelector(".combobox-popup");
    let items = [];
    try {
      const raw = combo.getAttribute("data-items") || "[]";
      const parsed = JSON.parse(raw);
      items = parsed.map((v) => (typeof v === "string" ? { label: v, value: v } : v));
    } catch (e) {
      items = [];
    }

    const sentinelLabel = combo.getAttribute("data-sentinel") || "";
    combo.getItems = () => items;
    combo.setItems = (newItems) => {
      items = newItems;
      combo.setAttribute("data-items", JSON.stringify(items));
    };

    const render = (highlight) => {
      popup.innerHTML = "";
      const filter = input.value.trim().toLowerCase();
      const visible = items.filter((it) => !filter || String(it.label).toLowerCase().includes(filter));
      if (!visible.length) {
        const empty = el("div", "combobox-option");
        empty.textContent = "-";
        empty.style.cursor = "default";
        popup.appendChild(empty);
        return;
      }
      let highlightIndex = -1;
      visible.forEach((it, idx) => {
        const opt = el("div", "combobox-option", it.label);
        opt.dataset.index = String(idx);
        if (highlight === it.label) {
          opt.classList.add("highlighted");
          highlightIndex = idx;
        }
        opt.addEventListener("pointerdown", (e) => {
          e.preventDefault();
          input.value = it.label;
          input.dispatchEvent(new Event("input"));
          popup.hidden = true;
          combo.classList.remove("open");
          input.focus();
        });
        popup.appendChild(opt);
      });
      popup._visible = visible;
      popup._highlightIndex = highlightIndex;
    };

    const open = () => {
      if (combo.classList.contains("disabled")) return;
      popup.hidden = false;
      combo.classList.add("open");
      render(null);
    };
    const closePopup = () => {
      popup.hidden = true;
      combo.classList.remove("open");
    };

    input.addEventListener("focus", open);
    input.addEventListener("input", () => {
      if (popup.hidden) open();
      render(null);
    });
    input.addEventListener("keydown", (e) => {
      const visible = popup._visible || [];
      let idx = popup._highlightIndex;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (popup.hidden) { open(); return; }
        idx = idx < 0 ? 0 : Math.min(idx + 1, visible.length - 1);
        render(visible[idx] ? visible[idx].label : null);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (popup.hidden) { open(); return; }
        idx = idx < 0 ? visible.length - 1 : Math.max(idx - 1, 0);
        render(visible[idx] ? visible[idx].label : null);
      } else if (e.key === "Enter") {
        if (!popup.hidden && idx >= 0 && visible[idx]) {
          e.preventDefault();
          input.value = visible[idx].label;
          input.dispatchEvent(new Event("input"));
          closePopup();
        }
      } else if (e.key === "Escape") {
        closePopup();
        input.blur();
      }
    });
    input.addEventListener("blur", () => {
      setTimeout(closePopup, 120);
    });
    chevron.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      if (popup.hidden) { input.focus(); open(); } else { closePopup(); }
    });

    combo.getComboValue = () => {
      const raw = input.value || "";
      if (sentinelLabel && raw === sentinelLabel) return "";
      return raw;
    };
    combo.setComboValue = (value) => {
      if (sentinelLabel && !value) {
        input.value = sentinelLabel;
      } else {
        input.value = value || "";
      }
    };
  });
}

function initSpinboxes(root) {
  $all(".win-spinbox", root || document).forEach((spin) => {
    const input = spin.querySelector(".spinbox-input");
    const min = parseFloat(spin.getAttribute("data-min"));
    const max = parseFloat(spin.getAttribute("data-max"));
    const step = parseFloat(spin.getAttribute("data-step")) || 1;

    const clamp = (v) => {
      let n = Number(v);
      if (isNaN(n)) n = min;
      n = Math.max(min, Math.min(max, n));
      return n;
    };
    const commit = () => {
      const n = clamp(input.value);
      input.value = Number.isInteger(step) ? String(Math.round(n)) : String(Math.round(n * 10) / 10);
    };

    spin.getValue = () => clamp(input.value);
    spin.setValue = (v) => { input.value = String(clamp(v)); };

    spin.querySelector(".spin-up").addEventListener("click", () => {
      spin.setValue(clamp(input.value) + step);
    });
    spin.querySelector(".spin-down").addEventListener("click", () => {
      spin.setValue(clamp(input.value) - step);
    });
    input.addEventListener("change", commit);
    input.addEventListener("blur", commit);
  });
}

function setSelectOptions(selectEl, options, selectedValue, placeholderKey) {
  selectEl.innerHTML = "";
  if (placeholderKey) {
    const ph = el("option", "", t(placeholderKey));
    ph.value = "";
    ph.disabled = true;
    selectEl.appendChild(ph);
  }
  options.forEach((opt) => {
    const o = el("option", "", opt.label);
    o.value = opt.value;
    selectEl.appendChild(o);
  });
  if (selectedValue !== undefined && selectedValue !== null && selectedValue !== "") {
    selectEl.value = String(selectedValue);
  }
}

/* ═══════════════════════════ 导航 ═══════════════════════════ */
function switchPage(page) {
  currentPage = page;
  $all(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.page === page);
  });
  $all(".page").forEach((p) => {
    p.classList.toggle("active", p.id === "page-" + page);
  });
  hideTeachingTip();
  hideStartMenu();
  if (page === "presentation" && STATE.presentation && STATE.presentation.tts_available) {
    refreshPreTts();
  } else {
    stopPreTtsPolling();
  }
}

$all(".nav-item").forEach((item) => {
  item.addEventListener("click", (e) => {
    e.preventDefault();
    switchPage(item.dataset.page);
  });
});

function setNavCollapsed(collapsed) {
  const pane = $("#navPane");
  pane.classList.toggle("collapsed", collapsed);
  $all(".nav-item", pane).forEach((item) => {
    if (collapsed) {
      const label = item.querySelector(".nav-label");
      item.title = label ? label.textContent : "";
    } else {
      item.removeAttribute("title");
    }
  });
  try {
    localStorage.setItem("mct-nav-collapsed", collapsed ? "1" : "0");
  } catch (e) {}
}

$("#navToggle").addEventListener("click", () => {
  setNavCollapsed(!$("#navPane").classList.contains("collapsed"));
});

/* ═══════════════════════════ 外部链接 ═══════════════════════════ */

function openExternal(url) {
  const bridge = getApi();
  if (bridge && typeof bridge.open_external === "function") {
    bridge.open_external(url).catch(() => {});
  } else {
    window.open(url, "_blank");
  }
}

$all("[data-external]").forEach((link) => {
  link.addEventListener("click", (e) => {
    e.preventDefault();
    if (link.href && link.href !== "#" && link.href !== window.location.href) {
      openExternal(link.href);
    }
  });
});

/* ═══════════════════════════ 语言输入模式 ═══════════════════════════ */

function playerServiceType() {
  return STATE.translation && STATE.translation.player ? STATE.translation.player.service_type : "llm";
}

function sendServiceType() {
  const tr = STATE.translation;
  if (tr && tr.independent && tr.send) return tr.send.service_type;
  return playerServiceType();
}

function setLangInputMode(kind, serviceType) {
  const textInput = $("#" + kind + "SrcInput");
  const select = $("#" + kind + "SrcSelect");
  const tgtTextInput = $("#" + kind + "TgtInput");
  const tgtSelect = $("#" + kind + "TgtSelect");
  const isLlm = serviceType === "llm";
  textInput.hidden = !isLlm;
  select.hidden = isLlm;
  tgtTextInput.hidden = !isLlm;
  tgtSelect.hidden = isLlm;
}

function updateLangInputModes() {
  setLangInputMode("cap", playerServiceType());
  setLangInputMode("send", sendServiceType());
}

function populateLangSelects(pageKind) {
  const srcSelect = $("#" + pageKind + "SrcSelect");
  const tgtSelect = $("#" + pageKind + "TgtSelect");
  const langKey = pageKind === "cap" ? "player" : "send";
  const { src, tgt } = langOptions[langKey];

  const srcValue = pageKind === "cap" ? STATE.capture.source_language : STATE.send.source_language;
  const tgtValue = pageKind === "cap" ? STATE.capture.target_language : STATE.send.target_language;

  setSelectOptions(srcSelect, src.map((v) => ({ label: v, value: v })), srcValue, "srcLangSelectPlaceholder");
  setSelectOptions(tgtSelect, tgt.map((v) => ({ label: v, value: v })), tgtValue, "tgtLangSelectPlaceholder");
}

function loadLanguages(kind, service) {
  if (!service) return;
  if (langLoading[kind]) return;
  langLoading[kind] = true;
  setLangSelectsDisabled(kind, true);

  const spinnerId = kind === "player" ? "#trPlayerTradSpinner" : "#trSendTradSpinner";
  const spinner = $(spinnerId);
  if (spinner) spinner.hidden = false;

  post("/api/languages/load", { kind, service });
}

function handleLanguagesLoaded(data) {
  const kind = data.kind || "player";
  langLoading[kind] = false;
  langOptions[kind] = { src: data.src || [], tgt: data.tgt || [] };
  if (kind === "player") {
    populateLangSelects("cap");
    if (!(STATE.translation && STATE.translation.independent)) {
      langOptions.send = { src: (data.src || []).slice(), tgt: (data.tgt || []).slice() };
      populateLangSelects("send");
      setLangSelectsDisabled("send", false);
    }
  } else {
    populateLangSelects("send");
  }
  setLangSelectsDisabled(kind, false);
  const spinnerId = kind === "player" ? "#trPlayerTradSpinner" : "#trSendTradSpinner";
  const spinner = $(spinnerId);
  if (spinner) spinner.hidden = true;
}

function handleLanguagesError(data) {
  const kind = data.kind || "player";
  langLoading[kind] = false;
  setLangSelectsDisabled(kind, false);
  const spinnerId = kind === "player" ? "#trPlayerTradSpinner" : "#trSendTradSpinner";
  const spinner = $(spinnerId);
  if (spinner) spinner.hidden = true;
}

function loadInitialLanguages() {
  if (playerServiceType() === "traditional") {
    const provider = $("#trPlayerTradProvider").value;
    if (provider && !langOptions.player.src.length) {
      loadLanguages("player", provider);
    }
  }
  if (STATE.translation && STATE.translation.independent && sendServiceType() === "traditional") {
    const provider = $("#trSendTradProvider").value;
    if (provider && !langOptions.send.src.length) {
      loadLanguages("send", provider);
    }
  }
}

function setLangSelectsDisabled(kind, disabled) {
  const targets = kind === "player" ? ["cap"] : ["send"];
  if (kind === "player" && !(STATE.translation && STATE.translation.independent)) {
    targets.push("send");
  }
  targets.forEach((k) => {
    $("#" + k + "SrcSelect").disabled = disabled;
    $("#" + k + "TgtSelect").disabled = disabled;
  });
}

/* ═══════════════════════════ 翻译服务面板 ═══════════════════════════ */

function buildLlmFields(P, model, data) {
  const p = P + model.charAt(0).toUpperCase() + model.slice(1);
  const providerOpts = STATE.llmProviders.map((v) => ({ label: v, value: v }));
  const urlItems = [{ label: t("defaultEndpoint"), value: "" }];
  if (data.api_base) urlItems.push({ label: data.api_base, value: data.api_base });
  const keyItems = [{ label: t("noApiKey"), value: "" }];
  if (data.api_key && data.api_key !== t("noApiKey")) keyItems.push({ label: data.api_key, value: data.api_key });

  return `
    <label class="form-label">${t("selectService")}</label>
    <div class="form-control">
      <select class="win-select" id="tr${p}Provider" style="width:200px"></select>
    </div>
    <label class="form-label">${t("apiKey")}</label>
    <div class="form-control">
      <div class="win-input" id="tr${p}Key" style="width:300px">
        <input type="text" placeholder="${t("apiKeyPlaceholder")}">
        <button type="button" class="input-clear" tabindex="-1"><svg class="icon"><use href="#icon-close"/></svg></button>
      </div>
    </div>
    <label class="form-label">${t("apiUrl")}</label>
    <div class="form-control">
      <div class="win-combobox wide" id="tr${p}Url" data-items='${JSON.stringify(urlItems)}' data-sentinel="${t("defaultEndpoint")}">
        <div class="combobox-field">
          <input type="text" class="combobox-input" autocomplete="off">
          <button type="button" class="combobox-chevron" tabindex="-1"><svg class="icon"><use href="#icon-chevron-down"/></svg></button>
        </div>
        <div class="combobox-popup" hidden></div>
      </div>
    </div>
    <label class="form-label">${t("modelCode")}</label>
    <div class="form-control">
      <div class="win-input" id="tr${p}Model" style="width:300px">
        <input type="text" placeholder="${t("modelPlaceholder")}">
        <button type="button" class="input-clear" tabindex="-1"><svg class="icon"><use href="#icon-close"/></svg></button>
      </div>
    </div>
    <label class="form-label">${t("deepTranslate")}</label>
    <div class="form-control">
      <div class="control-row">
        <label class="win-switch">
          <input type="checkbox" class="switch-input" id="tr${p}Deep">
          <span class="switch-visual"><span class="switch-thumb"></span></span>
          <span class="switch-text">${t("off")}</span>
        </label>
        <button type="button" class="help-button" data-tip="deepTranslateHelp"><svg class="icon"><use href="#icon-help"/></svg></button>
      </div>
    </div>`;
}

function buildServicePanel(kind, section) {
  const panel = $("#tr" + kind.charAt(0).toUpperCase() + kind.slice(1) + "Panel");
  panel.innerHTML = "";
  const isLlm = section.service_type === "llm";
  const llm = section.llm || { provider: "", api_key: "", api_base: "", model: "", deep_translate: false };
  const fallback = section.fallback_llm || { provider: "", api_key: "", api_base: "", model: "", deep_translate: false };
  const trad = section.traditional || { provider: "", api_key: "", folder_id: "", region: "" };
  const strategy = section.fallback_strategy || "direct";

  const P = kind.charAt(0).toUpperCase() + kind.slice(1);

  const wrap = el("div", "service-root");

  const segWrap = el("div", "service-segmented-wrap");
  const seg = el("div", "win-segmented");
  const segLlm = el("button", "seg-item" + (isLlm ? " active" : ""), t("aiTranslate"));
  segLlm.dataset.segValue = "llm";
  const segTrad = el("button", "seg-item" + (isLlm ? "" : " active"), t("traditionalTranslate"));
  segTrad.dataset.segValue = "traditional";
  seg.appendChild(segLlm);
  seg.appendChild(segTrad);
  segWrap.appendChild(seg);
  wrap.appendChild(segWrap);

  const llmSection = el("div", "service-section");
  llmSection.dataset.section = "llm";

  const pivotWrap = el("div", "service-pivot-wrap");
  const pivot = el("div", "win-pivot");
  const pivotMain = el("button", "pivot-item active", t("mainModel"));
  pivotMain.dataset.model = "main";
  const pivotFb = el("button", "pivot-item", t("fallbackModel"));
  pivotFb.dataset.model = "fallback";
  pivot.appendChild(pivotMain);
  pivot.appendChild(pivotFb);
  pivotWrap.appendChild(pivot);
  llmSection.appendChild(pivotWrap);

  const mainPage = el("div", "form-grid form-grid-right");
  mainPage.dataset.modelPage = "main";
  mainPage.innerHTML = buildLlmFields(P, "main", llm);
  const fbPage = el("div", "form-grid form-grid-right");
  fbPage.dataset.modelPage = "fallback";
  fbPage.hidden = true;
  fbPage.innerHTML = buildLlmFields(P, "fallback", fallback);

  llmSection.appendChild(mainPage);
  llmSection.appendChild(fbPage);

  const strategyRow = el("div", "form-grid form-grid-right");
  const strategyLabel = el("label", "form-label", t("fallbackStrategy"));
  const strategyControl = el("div", "form-control");
  const strategySelect = el("select", "win-select");
  strategySelect.id = "tr" + P + "Strategy";
  strategySelect.style.width = "400px";
  const strategyItems = [
    { label: t("strategyDirect"), value: "direct" },
    { label: t("strategyRetry"), value: "retry_exhausted" },
    { label: t("strategyRace"), value: "race_on_failure" },
    { label: t("strategyAlwaysRace"), value: "always_race" },
  ];
  strategyItems.forEach((it) => {
    const o = el("option", "", it.label);
    o.value = it.value;
    strategySelect.appendChild(o);
  });
  strategySelect.value = strategy;
  strategyControl.appendChild(strategySelect);
  strategyRow.appendChild(strategyLabel);
  strategyRow.appendChild(strategyControl);
  llmSection.appendChild(strategyRow);

  const tradSection = el("div", "service-section");
  tradSection.dataset.section = "traditional";

  const tradGrid = el("div", "form-grid form-grid-right");
  tradGrid.innerHTML = `
    <label class="form-label">${t("selectService")}</label>
    <div class="form-control">
      <div class="control-row">
        <select class="win-select" id="tr${P}TradProvider" style="width:200px"></select>
        <div class="win-spinner" id="tr${P}TradSpinner" hidden></div>
      </div>
    </div>
    <label class="form-label">${t("apiKey")}</label>
    <div class="form-control">
      <div class="win-combobox wide" id="tr${P}TradKey" data-items='${JSON.stringify([{ label: t("noApiKey"), value: "" }, ...(trad.api_key ? [{ label: trad.api_key, value: trad.api_key }] : [])])}' data-sentinel="${t("noApiKey")}">
        <div class="combobox-field">
          <input type="text" class="combobox-input" autocomplete="off">
          <button type="button" class="combobox-chevron" tabindex="-1"><svg class="icon"><use href="#icon-chevron-down"/></svg></button>
        </div>
        <div class="combobox-popup" hidden></div>
      </div>
    </div>
    <label class="form-label" id="tr${P}TradFolderLabel">${t("yandexFolderId")}</label>
    <div class="form-control">
      <div class="win-input" id="tr${P}TradFolderId" style="width:300px">
        <input type="text" placeholder="${t("yandexFolderIdPlaceholder")}">
        <button type="button" class="input-clear" tabindex="-1"><svg class="icon"><use href="#icon-close"/></svg></button>
      </div>
    </div>
    <label class="form-label" id="tr${P}TradRegionLabel">${t("azureRegion")}</label>
    <div class="form-control">
      <div class="win-input" id="tr${P}TradRegion" style="width:300px">
        <input type="text" placeholder="${t("azureRegionPlaceholder")}">
        <button type="button" class="input-clear" tabindex="-1"><svg class="icon"><use href="#icon-close"/></svg></button>
      </div>
    </div>`;
  tradSection.appendChild(tradGrid);

  if (isLlm) {
    tradSection.hidden = true;
  } else {
    llmSection.hidden = true;
  }

  wrap.appendChild(llmSection);
  wrap.appendChild(tradSection);
  panel.appendChild(wrap);

  initClearButtons(panel);
  initSwitches(panel);
  initComboboxes(panel);

  const providerSelect = $("#tr" + P + "MainProvider");
  setSelectOptions(providerSelect, STATE.llmProviders.map((v) => ({ label: v, value: v })), llm.provider, "selectServicePlaceholder");
  const fbProviderSelect = $("#tr" + P + "FallbackProvider");
  setSelectOptions(fbProviderSelect, STATE.llmProviders.map((v) => ({ label: v, value: v })), fallback.provider, "selectServicePlaceholder");

  $("#tr" + P + "MainKey input").value = llm.api_key || "";
  $("#tr" + P + "FallbackKey input").value = fallback.api_key || "";
  const mainUrl = $("#tr" + P + "MainUrl");
  const fbUrl = $("#tr" + P + "FallbackUrl");
  mainUrl.setComboValue(llm.api_base ? llm.api_base : "");
  fbUrl.setComboValue(fallback.api_base ? fallback.api_base : "");
  $("#tr" + P + "MainModel input").value = llm.model || "";
  $("#tr" + P + "FallbackModel input").value = fallback.model || "";
  $("#tr" + P + "MainDeep").checked = !!llm.deep_translate;
  $("#tr" + P + "FallbackDeep").checked = !!fallback.deep_translate;

  const tradProviderSelect = $("#tr" + P + "TradProvider");
  setSelectOptions(tradProviderSelect, STATE.traditionalServices.map((v) => ({ label: v, value: v })), trad.provider, "selectServicePlaceholder");
  $("#tr" + P + "TradKey").setComboValue(trad.api_key || "");
  $("#tr" + P + "TradFolderId input").value = trad.folder_id || "";
  $("#tr" + P + "TradRegion input").value = trad.region || "";
  updateTradExtraFields(kind, trad.provider);

  segLlm.addEventListener("click", () => switchServiceType(kind, "llm"));
  segTrad.addEventListener("click", () => switchServiceType(kind, "traditional"));
  pivotMain.addEventListener("click", () => switchModelPage(kind, "main"));
  pivotFb.addEventListener("click", () => switchModelPage(kind, "fallback"));

  const tradSelect = $("#tr" + P + "TradProvider");
  tradSelect.addEventListener("change", () => {
    updateTradExtraFields(kind, tradSelect.value);
    const service = tradSelect.value;
    if (service) loadLanguages(kind, service);
  });

  $all(".help-button", panel).forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const key = btn.getAttribute("data-tip");
      if (tipEl.hidden || tipEl.dataset.currentKey !== key) {
        tipEl.dataset.currentKey = key;
        showTeachingTip(btn, t(key));
      } else {
        hideTeachingTip();
      }
    });
  });
  syncSwitchesText(panel);
}

function syncSwitchesText(root) {
  $all(".win-switch", root || document).forEach((sw) => {
    const input = sw.querySelector(".switch-input");
    const text = sw.querySelector(".switch-text");
    if (text) text.textContent = input.checked ? t("on") : t("off");
  });
}

function switchServiceType(kind, serviceType) {
  const P = kind.charAt(0).toUpperCase() + kind.slice(1);
  const panel = $("#tr" + P + "Panel");
  const segs = $all(".seg-item", panel);
  segs.forEach((s) => s.classList.toggle("active", s.dataset.segValue === serviceType));
  const llmSection = $('[data-section="llm"]', panel);
  const tradSection = $('[data-section="traditional"]', panel);
  llmSection.hidden = serviceType !== "llm";
  tradSection.hidden = serviceType !== "traditional";

  if (kind === "player") {
    STATE.translation.player.service_type = serviceType;
  } else {
    STATE.translation.send.service_type = serviceType;
  }
  updateLangInputModes();

  if (serviceType === "traditional") {
    const provider = $("#tr" + P + "TradProvider").value;
    if (provider && !langOptions[kind].src.length) {
      loadLanguages(kind, provider);
    }
  }
}

function switchModelPage(kind, model) {
  const P = kind.charAt(0).toUpperCase() + kind.slice(1);
  const panel = $("#tr" + P + "Panel");
  $all(".pivot-item", panel).forEach((p) => p.classList.toggle("active", p.dataset.model === model));
  $all("[data-model-page]", panel).forEach((p) => {
    p.hidden = p.dataset.modelPage !== model;
  });
}

function updateTradExtraFields(kind, serviceName) {
  const P = kind.charAt(0).toUpperCase() + kind.slice(1);
  const lower = (serviceName || "").trim().toLowerCase();
  const isYandex = lower === "yandex";
  const isBing = lower === "bing";
  $("#tr" + P + "TradFolderLabel").hidden = !isYandex;
  $("#tr" + P + "TradFolderId").hidden = !isYandex;
  $("#tr" + P + "TradRegionLabel").hidden = !isBing;
  $("#tr" + P + "TradRegion").hidden = !isBing;
}

function rebuildServicePanels() {
  buildServicePanel("player", STATE.translation.player);
  if (STATE.translation.independent && STATE.translation.send) {
    buildServicePanel("send", STATE.translation.send);
  }
  updateIndependentUi();
}

function updateIndependentUi() {
  const independent = STATE.translation.independent;
  $("#trIndependent").checked = independent;
  const tabBar = $("#trTabBar");
  tabBar.hidden = !independent;
  $("#trTabPlayer").classList.add("active");
  $("#trTabSend").classList.remove("active");
  $("#trPlayerPanel").hidden = false;
  $("#trSendPanel").hidden = true;
  updateLangInputModes();
}

/* 翻译服务 TabBar 切换 */
$("#trTabPlayer").addEventListener("click", () => {
  $("#trTabPlayer").classList.add("active");
  $("#trTabSend").classList.remove("active");
  $("#trPlayerPanel").hidden = false;
  $("#trSendPanel").hidden = true;
});
$("#trTabSend").addEventListener("click", () => {
  $("#trTabSend").classList.add("active");
  $("#trTabPlayer").classList.remove("active");
  $("#trSendPanel").hidden = false;
  $("#trPlayerPanel").hidden = true;
});

/* 黑名单 TabBar 切换 */
function switchBlacklistTab(tab) {
  $("#blTabUsers").classList.toggle("active", tab === "users");
  $("#blTabMessages").classList.toggle("active", tab === "messages");
  $("#blUsersPanel").hidden = tab !== "users";
  $("#blMessagesPanel").hidden = tab !== "messages";
}
$("#blTabUsers").addEventListener("click", () => switchBlacklistTab("users"));
$("#blTabMessages").addEventListener("click", () => switchBlacklistTab("messages"));

$("#trIndependent").addEventListener("change", () => {
  const checked = $("#trIndependent").checked;
  STATE.translation.independent = checked;
  if (checked) {
    if (!STATE.translation.send) {
      STATE.translation.send = {
        service_type: playerServiceType(),
        llm: { provider: "", api_key: "", api_base: "", model: "", deep_translate: false },
        fallback_llm: null,
        fallback_strategy: "direct",
        traditional: { provider: "", api_key: "", folder_id: "", region: "" },
      };
    }
    buildServicePanel("send", STATE.translation.send);
  }
  updateIndependentUi();
  if (!checked) {
    const playerType = playerServiceType();
    if (playerType === "traditional") {
      const provider = $("#trPlayerTradProvider").value;
      if (provider && langOptions.player.src.length) {
        langOptions.send = { src: langOptions.player.src.slice(), tgt: langOptions.player.tgt.slice() };
        populateLangSelects("send");
      } else if (provider) {
        loadLanguages("player", provider);
      }
    }
  }
});

/* ═══════════════════════════ 术语表 ═══════════════════════════ */

function renderGlossaryTable(items) {
  const body = $("#glossTableBody");
  body.innerHTML = "";
  if (!items || !items.length) {
    body.appendChild(el("div", "win-table-empty"));
    return;
  }
  items.forEach((item) => {
    const row = el("div", "win-table-row");
    row.dataset.src = item[0];
    row.addEventListener("click", () => selectGlossaryRow(item[0]));
    const srcCol = el("span", "col col-a", item[0]);
    const tgtCol = el("span", "col col-a", item[1]);
    row.appendChild(srcCol);
    row.appendChild(tgtCol);
    body.appendChild(row);
  });
  glossSelectedSrc = null;
  $("#glossDeleteBtn").disabled = true;
}

function selectGlossaryRow(src) {
  glossSelectedSrc = src;
  $all(".win-table-row", $("#glossTableBody")).forEach((row) => {
    row.classList.toggle("selected", row.dataset.src === src);
  });
  const item = (STATE.glossary && STATE.glossary.items || []).find((it) => it[0] === src);
  if (item) {
    $("#glossSrc input").value = item[0];
    $("#glossTgt input").value = item[1];
    $("#glossSrc").classList.add("has-value");
    $("#glossTgt").classList.add("has-value");
    $("#glossDeleteBtn").disabled = false;
  }
}

function clearGlossaryInputs() {
  $("#glossSrc input").value = "";
  $("#glossTgt input").value = "";
  $("#glossSrc").classList.remove("has-value");
  $("#glossTgt").classList.remove("has-value");
  $all(".win-table-row", $("#glossTableBody")).forEach((row) => row.classList.remove("selected"));
  glossSelectedSrc = null;
  $("#glossDeleteBtn").disabled = true;
}

$("#glossClearInputBtn").addEventListener("click", clearGlossaryInputs);

$("#glossAddBtn").addEventListener("click", async () => {
  const src = $("#glossSrc input").value.trim();
  const tgt = $("#glossTgt input").value.trim();
  if (!src) {
    showToast("warning", t("inputError"), t("glossarySrcEmpty"), 3000);
    return;
  }
  let oldSrc = null;
  const selected = $(".win-table-row.selected", $("#glossTableBody"));
  if (selected) oldSrc = selected.dataset.src;

  const result = await postHandle("/api/glossary/add", { src, tgt, old_src: oldSrc });
  if (result && result.needs_confirm) {
    const ok = await showConfirm(t("confirmOverwrite"), t("confirmOverwriteContent", src), t("ok"), t("cancel"));
    if (!ok) return;
    const result2 = await postHandle("/api/glossary/add", { src, tgt, old_src: oldSrc, confirmed: true });
    if (result2 && result2.ok) {
      STATE.glossary.items = result2.items;
      renderGlossaryTable(result2.items);
      clearGlossaryInputs();
    }
  } else if (result && result.ok) {
    STATE.glossary.items = result.items;
    renderGlossaryTable(result.items);
    clearGlossaryInputs();
  }
});

$("#glossDeleteBtn").addEventListener("click", async () => {
  if (!glossSelectedSrc) return;
  const result = await postHandle("/api/glossary/delete", { src: glossSelectedSrc });
  if (result && result.ok) {
    STATE.glossary.items = result.items;
    renderGlossaryTable(result.items);
    clearGlossaryInputs();
  }
});

$("#glossClearAllBtn").addEventListener("click", async () => {
  if (!STATE.glossary || !STATE.glossary.items.length) {
    showToast("info", t("hint"), t("glossaryEmpty"), 2000);
    return;
  }
  const ok = await showConfirm(t("confirmClear"), t("confirmClearGlossary"), t("ok"), t("cancel"));
  if (!ok) return;
  const result = await postHandle("/api/glossary/clear", {});
  if (result && result.ok) {
    STATE.glossary.items = [];
    renderGlossaryTable([]);
    clearGlossaryInputs();
  }
});

/* ═══════════════════════════ 黑名单 ═══════════════════════════ */

function renderUsersTable(users) {
  const body = $("#blUsersTableBody");
  body.innerHTML = "";
  if (!users || !users.length) return;
  users.forEach((name) => {
    const row = el("div", "win-table-row");
    row.dataset.name = name;
    row.addEventListener("click", () => {
      $all(".win-table-row", body).forEach((r) => r.classList.toggle("selected", r === row));
      $("#blDeleteUserBtn").disabled = false;
    });
    const col = el("span", "col", name);
    row.appendChild(col);
    body.appendChild(row);
  });
  $("#blDeleteUserBtn").disabled = true;
}

function renderMessagesTable(messages) {
  const body = $("#blMsgTableBody");
  body.innerHTML = "";
  if (!messages || !messages.length) return;
  messages.forEach((rule, index) => {
    const row = el("div", "win-table-row");
    row.dataset.index = String(index);
    row.addEventListener("click", () => {
      $all(".win-table-row", body).forEach((r) => r.classList.toggle("selected", r === row));
      $("#blDeleteRuleBtn").disabled = false;
    });
    const patternCol = el("span", "col col-b", rule.pattern);
    const typeCol = el("span", "col col-c", rule.is_regex ? t("regexType") : t("keywordType"));
    row.appendChild(patternCol);
    row.appendChild(typeCol);
    body.appendChild(row);
  });
  $("#blDeleteRuleBtn").disabled = true;
}

$("#blClearUsersInputBtn").addEventListener("click", () => { $("#blUsersInput").value = ""; });

$("#blAddUsersBtn").addEventListener("click", async () => {
  const text = $("#blUsersInput").value;
  const result = await postHandle("/api/blacklist/users/add", { text });
  if (result && result.ok) {
    STATE.blacklist.users = result.users;
    renderUsersTable(result.users);
    $("#blUsersInput").value = "";
  }
});

$("#blDeleteUserBtn").addEventListener("click", async () => {
  const selected = $(".win-table-row.selected", $("#blUsersTableBody"));
  if (!selected) return;
  const name = selected.dataset.name;
  const result = await postHandle("/api/blacklist/users/delete", { name });
  if (result && result.ok) {
    STATE.blacklist.users = result.users;
    renderUsersTable(result.users);
  }
});

$("#blClearAllUsersBtn").addEventListener("click", async () => {
  if (!STATE.blacklist || !STATE.blacklist.users.length) {
    showToast("info", t("hint"), t("userBlacklistEmpty"), 2000);
    return;
  }
  const ok = await showConfirm(t("confirmClear"), t("confirmClearUsers"), t("ok"), t("cancel"));
  if (!ok) return;
  const result = await postHandle("/api/blacklist/users/clear", {});
  if (result && result.ok) {
    STATE.blacklist.users = [];
    renderUsersTable([]);
  }
});

$("#blClearPatternBtn").addEventListener("click", () => {
  $("#blPattern input").value = "";
  $("#blPattern").classList.remove("has-value");
  $("#blRegex").checked = false;
});

$("#blAddRuleBtn").addEventListener("click", async () => {
  const pattern = $("#blPattern input").value.trim();
  if (!pattern) {
    showToast("info", t("hint"), t("pleaseEnterRule"), 2000);
    return;
  }
  const isRegex = $("#blRegex").checked;
  const result = await postHandle("/api/blacklist/messages/add", { pattern, is_regex: isRegex });
  if (result && result.ok) {
    STATE.blacklist.messages = result.messages;
    renderMessagesTable(result.messages);
    $("#blPattern input").value = "";
    $("#blPattern").classList.remove("has-value");
    $("#blRegex").checked = false;
  }
});

$("#blDeleteRuleBtn").addEventListener("click", async () => {
  const selected = $(".win-table-row.selected", $("#blMsgTableBody"));
  if (!selected) return;
  const index = parseInt(selected.dataset.index, 10);
  const rule = (STATE.blacklist.messages || [])[index];
  if (!rule) return;
  const result = await postHandle("/api/blacklist/messages/delete", { pattern: rule.pattern });
  if (result && result.ok) {
    STATE.blacklist.messages = result.messages;
    renderMessagesTable(result.messages);
  }
});

$("#blClearAllRulesBtn").addEventListener("click", async () => {
  if (!STATE.blacklist || !STATE.blacklist.messages.length) {
    showToast("info", t("hint"), t("messageBlacklistEmpty"), 2000);
    return;
  }
  const ok = await showConfirm(t("confirmClear"), t("confirmClearRules"), t("ok"), t("cancel"));
  if (!ok) return;
  const result = await postHandle("/api/blacklist/messages/clear", {});
  if (result && result.ok) {
    STATE.blacklist.messages = [];
    renderMessagesTable([]);
  }
});

/* ═══════════════════════════ 启动页 ═══════════════════════════ */

function setWorkingStatus(working) {
  STATE.working = working;
  const pill = $("#stStatusPill");
  pill.textContent = working ? t("working") : t("stopped");
  pill.classList.toggle("working", working);
  pill.classList.toggle("stopped", !working);
  $("#stStartBtn").disabled = working;
  if (working) hideStartMenu();
}

function showStartMenu() {
  const menu = $("#stStartMenu");
  menu.hidden = false;
  const btn = $("#stStartBtn").getBoundingClientRect();
  menu.style.top = (btn.bottom + 6) + "px";
  menu.style.left = Math.max(12, btn.left) + "px";
}

function hideStartMenu() {
  $("#stStartMenu").hidden = true;
}

$("#stStartBtn").addEventListener("click", (e) => {
  e.stopPropagation();
  if (STATE.working) return;
  if ($("#stStartMenu").hidden) showStartMenu();
  else hideStartMenu();
});
document.addEventListener("pointerdown", (e) => {
  if ($("#stStartMenu").hidden) return;
  if (e.target.closest("#stStartMenu") || e.target.closest("#stStartBtn")) return;
  hideStartMenu();
});

async function doStart(mode) {
  hideStartMenu();
  if (STATE.working) return;
  const form = gatherForm();
  form.mode = mode;
  try {
    await post("/api/start", form);
  } catch (e) {
    showToast("error", t("startFailed"), String(e), 5000);
  }
}

$("#stDirectStart").addEventListener("click", () => doStart("direct"));
$("#stSaveAndStart").addEventListener("click", () => doStart("save_and_start"));

$("#stSaveBtn").addEventListener("click", async () => {
  const form = gatherForm();
  try {
    await post("/api/save", form);
  } catch (e) {
    showToast("error", t("saveFailed"), String(e), 5000);
  }
});

function buildAccessLinks(ips, port) {
  const list = $("#stAccessLinks");
  list.innerHTML = "";
  ips.forEach((ip) => {
    const address = ip + ":" + port;
    const url = "http://" + address;
    const link = el("a", "hyperlink", address);
    link.href = url;
    link.addEventListener("click", (e) => {
      e.preventDefault();
      openExternal(url);
      post("/api/link-clicked", {});
    });
    list.appendChild(link);
  });
  $("#stAccessCard").hidden = false;
}

/* ═══════════════════════════ TTS / Pre-TTS ═══════════════════════ */

function populateVoiceSelect(voices, currentVoice) {
  const select = $("#presTtsVoice");
  const options = [{ label: t("ttsVoiceAuto"), value: "auto" }];
  voices.forEach((v) => options.push({ label: v.display, value: v.value }));
  setSelectOptions(select, options, currentVoice);
}

$("#presTtsTestBtn").addEventListener("click", () => {
  $("#presTtsTestBtn").disabled = true;
  $("#presTtsTestSpinner").hidden = false;
  post("/api/tts/test", {
    voice: $("#presTtsVoice").value || "auto",
    speed: $("#presTtsSpeed").value || "+0%",
  });
});

function handleTtsTestResult(data) {
  $("#presTtsTestBtn").disabled = false;
  $("#presTtsTestSpinner").hidden = true;
  if (data.success) {
    showToast("success", t("ttsTestDone"), t("ttsTestDoneContent"), 2000);
  } else {
    showToast("error", t("ttsTestFailed"), t("ttsTestFailedContent", data.error), 5000);
  }
}

function updatePreTtsState(preTts) {
  const readName = $("#presTtsReadName").checked;
  const available = preTts.available;
  const running = preTts.running;

  const btn = $("#presPreTtsBtn");
  const stopBtn = $("#presPreTtsStopBtn");
  const progress = $("#presPreTtsProgress");
  const status = $("#presPreTtsStatus");

  stopBtn.hidden = !running;
  progress.hidden = !running;

  if (!available) {
    btn.disabled = true;
    status.textContent = t("preTtsIdle");
    return;
  }

  if (running) {
    btn.disabled = true;
    const total = Math.max(preTts.total, 1);
    $(".progress-fill", progress).style.width = Math.min(100, Math.round((preTts.done / total) * 100)) + "%";
    if (preTts.total > 0) {
      status.textContent = t("preTtsRunning", preTts.done, preTts.total);
    } else {
      status.textContent = t("preTtsScanning");
    }
    return;
  }

  if (readName) {
    btn.disabled = true;
    status.textContent = t("preTtsDisabledByReadName");
    return;
  }

  btn.disabled = false;
  const result = preTts.result;
  if (result && result.total !== undefined) {
    const sizeMb = (result.size_bytes || 0) / (1024 * 1024);
    status.textContent = t("preTtsLastResult", result.synthesized || 0, result.skipped || 0, result.total || 0, sizeMb.toFixed(1));
  } else {
    status.textContent = t("preTtsIdle");
  }
}

let preTtsPollTimer = null;

function stopPreTtsPolling() {
  if (preTtsPollTimer) {
    clearInterval(preTtsPollTimer);
    preTtsPollTimer = null;
  }
}

function refreshPreTts() {
  fetch("/api/pre-tts/status")
    .then((res) => res.json())
    .then((data) => {
      updatePreTtsState(data);
      if (data.running && !preTtsPollTimer) {
        preTtsPollTimer = setInterval(async () => {
          if (document.hidden) return;
          try {
            const res = await fetch("/api/pre-tts/status");
            const data2 = await res.json();
            updatePreTtsState(data2);
            if (!data2.running) stopPreTtsPolling();
          } catch (e) {
            stopPreTtsPolling();
          }
        }, 500);
      }
    })
    .catch(() => {});
}

$("#presPreTtsBtn").addEventListener("click", () => {
  post("/api/pre-tts/start", {});
  refreshPreTts();
});
$("#presPreTtsStopBtn").addEventListener("click", () => {
  post("/api/pre-tts/stop", {});
  refreshPreTts();
});
$("#presPreTtsClearBtn").addEventListener("click", async () => {
  const ok = await showConfirm(t("confirmClearPreTts"), t("confirmClearPreTtsContent"), t("ok"), t("cancel"));
  if (!ok) return;
  post("/api/pre-tts/clear", {});
  refreshPreTts();
});

$("#presTtsReadName").addEventListener("change", () => {
  syncSwitchesText($("#page-presentation"));
  updatePreTtsStateFromUi();
});

function updatePreTtsStateFromUi() {
  updatePreTtsState({
    available: STATE.presentation && STATE.presentation.tts_available,
    running: false,
    done: 0,
    total: 0,
    result: null,
  });
}

/* ═══════════════════════════ 设置页 ═══════════════════════════ */

$("#seLangSaveBtn").addEventListener("click", async () => {
  const select = $("#seLangSelect");
  const code = select.value;
  const option = select.options[select.selectedIndex];
  await post("/api/settings/language", { code, name: option ? option.textContent : code });
});

$("#seCheckUpdateBtn").addEventListener("click", () => {
  $("#seCheckUpdateBtn").disabled = true;
  $("#seUpdateSpinner").hidden = false;
  post("/api/update/check", {
    silent: false,
    include_prerelease: $("#seIncludePrerelease").checked,
  }).finally(() => {
    $("#seCheckUpdateBtn").disabled = false;
    $("#seUpdateSpinner").hidden = true;
  });
});

$("#seClearCacheBtn").addEventListener("click", async () => {
  const res = await postHandle("/api/cache/inspect", {});
  if (!res || !res.ok) return;
  if (res.stale_count === 0) {
    showToast("info", t("nothingToClear"), t("cacheNothing"), 3000);
    return;
  }
  const kept = res.total - res.stale_count;
  const ok = await showConfirm(
    t("confirmClearCache"),
    t("confirmClearCacheContent", res.stale_count, res.total, kept),
    t("ok"), t("cancel")
  );
  if (!ok) return;
  post("/api/cache/clear", {});
});

/* ═══════════════════════════ 上下文翻译 ═══════════════════════════ */

$("#ctxTruncMode").addEventListener("change", () => {
  $("#ctxTruncValue").hidden = $("#ctxTruncMode").value !== "custom";
});

/* ═══════════════════════════ 表单收集 ═══════════════════════════ */

function gatherService(kind) {
  const P = kind.charAt(0).toUpperCase() + kind.slice(1);
  const panel = $("#tr" + P + "Panel");
  const segLlm = $('.seg-item[data-seg-value="llm"]', panel);
  const isLlm = segLlm.classList.contains("active");

  if (isLlm) {
    return {
      service_type: "llm",
      llm: {
        provider: $("#tr" + P + "MainProvider").value || "",
        api_key: $("#tr" + P + "MainKey input").value || "",
        api_base: $("#tr" + P + "MainUrl").getComboValue(),
        model: $("#tr" + P + "MainModel input").value || "",
        deep_translate: $("#tr" + P + "MainDeep").checked,
      },
      fallback_llm: {
        provider: $("#tr" + P + "FallbackProvider").value || "",
        api_key: $("#tr" + P + "FallbackKey input").value || "",
        api_base: $("#tr" + P + "FallbackUrl").getComboValue(),
        model: $("#tr" + P + "FallbackModel input").value || "",
        deep_translate: $("#tr" + P + "FallbackDeep").checked,
      },
      fallback_strategy: $("#tr" + P + "Strategy").value || "direct",
      traditional: null,
    };
  }

  return {
    service_type: "traditional",
    llm: null,
    fallback_llm: null,
    fallback_strategy: "direct",
    traditional: {
      provider: $("#tr" + P + "TradProvider").value || "",
      api_key: $("#tr" + P + "TradKey").getComboValue(),
      folder_id: $("#tr" + P + "TradFolderId input").value || "",
      region: $("#tr" + P + "TradRegion input").value || "",
    },
  };
}

function gatherForm() {
  const captureType = playerServiceType();
  const sendType = sendServiceType();

  return {
    capture: {
      log_path: $("#capLogPath input").value || "",
      log_encoding: $("#capEncoding").getComboValue() || "auto",
      monitor_mode: document.querySelector('input[name="capMode"]:checked').value,
      filter_server_messages: $("#capFilterServer").checked,
      replace_garbled_chars: $("#capReplaceGarbled").checked,
      src_lang: captureType === "llm" ? ($("#capSrcInput input").value || "") : ($("#capSrcSelect").value || ""),
      tgt_lang: captureType === "llm" ? ($("#capTgtInput input").value || "") : ($("#capTgtSelect").value || ""),
    },
    translation: {
      independent: $("#trIndependent").checked,
      player: gatherService("player"),
      send: ($("#trIndependent").checked && STATE.translation.send) ? gatherService("send") : null,
    },
    presentation: {
      web_port: $("#presWebPort").getValue(),
      tts: {
        enabled: $("#presTtsEnable").checked,
        voice: $("#presTtsVoice").value || "auto",
        speed: $("#presTtsSpeed").value || "+0%",
        read_player_name: $("#presTtsReadName").checked,
      },
    },
    send: {
      monitor_clipboard: $("#sendClipboard").checked,
      src_lang: sendType === "llm" ? ($("#sendSrcInput input").value || "") : ($("#sendSrcSelect").value || ""),
      tgt_lang: sendType === "llm" ? ($("#sendTgtInput input").value || "") : ($("#sendTgtSelect").value || ""),
    },
    context: {
      strategy: $("#ctxStrategy").value || "disabled",
      context_length: $("#ctxLength").getValue(),
      context_timeout: $("#ctxTimeout").getValue(),
      truncation_mode: $("#ctxTruncMode").value || "disabled",
      truncation_value: $("#ctxTruncValue").getValue(),
    },
    settings: {
      interface_language: $("#seLangSelect").value || "",
      update_frequency: $("#seFreqSelect").value || "startup",
      include_prerelease: $("#seIncludePrerelease").checked,
    },
  };
}

/* ═══════════════════════════ 状态填充 ═══════════════════════════ */

function applyState(snapshot) {
  Object.assign(STATE, {
    working: !!snapshot.working,
    version: snapshot.version || "",
    program: snapshot.program || {},
    llmProviders: snapshot.llm_providers || [],
    traditionalServices: snapshot.traditional_services || [],
    supportedLanguages: snapshot.supported_languages || [],
    capture: snapshot.capture,
    translation: snapshot.translation,
    presentation: snapshot.presentation,
    send: snapshot.send,
    context: snapshot.context,
    glossary: snapshot.glossary,
    blacklist: snapshot.blacklist,
    settings: snapshot.settings,
  });

  if (snapshot.i18n) {
    Object.keys(snapshot.i18n).forEach((k) => { I18N[k] = snapshot.i18n[k]; });
    applyI18n();
  }

  langOptions.player = snapshot.capture.lang_options || { src: [], tgt: [] };
  langOptions.send = snapshot.send.lang_options || { src: [], tgt: [] };

  populateCapturePage();
  populateSendPage();
  populateContextPage();
  populatePresentationPage();
  populateStartPage();
  populateAboutPage();
  populateSettingsPage();
  rebuildServicePanels();
  renderGlossaryTable(snapshot.glossary.items || []);
  renderUsersTable(snapshot.blacklist.users || []);
  renderMessagesTable(snapshot.blacklist.messages || []);

  updateLangInputModes();
  populateLangSelects("cap");
  populateLangSelects("send");
  loadInitialLanguages();

  const preTts = snapshot.pre_tts;
  if (preTts) updatePreTtsState(preTts);

  const tts = snapshot.presentation.tts;
  if (snapshot.presentation.tts_available && !tts.voices_loaded) {
    post("/api/tts/voices/load", {});
  }
}

function populateCapturePage() {
  const c = STATE.capture;
  $("#capLogPath input").value = c.log_path || "";
  $("#capLogPath").classList.toggle("has-value", !!c.log_path);
  $("#capEncoding").setComboValue(c.log_encoding || "auto");
  document.querySelector('input[name="capMode"][value="' + (c.monitor_mode || "efficient") + '"]').checked = true;
  $("#capFilterServer").checked = !!c.filter_server_messages;
  $("#capReplaceGarbled").checked = !!c.replace_garbled_chars;
  $("#capSrcInput input").value = c.source_language || "";
  $("#capTgtInput input").value = c.target_language || "";
  $("#capSrcInput").classList.toggle("has-value", !!c.source_language);
  $("#capTgtInput").classList.toggle("has-value", !!c.target_language);
}

function populateSendPage() {
  const s = STATE.send;
  $("#sendClipboard").checked = !!s.monitor_clipboard;
  $("#sendSrcInput input").value = s.source_language || "";
  $("#sendTgtInput input").value = s.target_language || "";
  $("#sendSrcInput").classList.toggle("has-value", !!s.source_language);
  $("#sendTgtInput").classList.toggle("has-value", !!s.target_language);
}

function populateContextPage() {
  const ctx = STATE.context;
  setSelectOptions($("#ctxStrategy"), [
    { label: t("contextStrategyDisabled"), value: "disabled" },
    { label: t("contextStrategyFixed"), value: "fixed" },
    { label: t("contextStrategyTimeBased"), value: "time_based" },
  ], ctx.strategy || "disabled");
  $("#ctxLength").setValue(ctx.context_length !== undefined ? ctx.context_length : 10);
  $("#ctxTimeout").setValue(ctx.context_timeout !== undefined ? ctx.context_timeout : 120);
  setSelectOptions($("#ctxTruncMode"), [
    { label: t("contextTruncAuto"), value: "auto" },
    { label: t("contextTruncDisabled"), value: "disabled" },
    { label: t("contextTruncCustom"), value: "custom" },
  ], ctx.truncation_mode || "disabled");
  $("#ctxTruncValue").setValue(ctx.truncation_value || 1);
  $("#ctxTruncValue").hidden = (ctx.truncation_mode || "disabled") !== "custom";
}

function populatePresentationPage() {
  const p = STATE.presentation;
  const tts = p.tts;
  $("#presWebPort").setValue(p.web_port || 8080);

  $("#presTtsEnable").checked = !!tts.enabled;
  $("#presTtsEnable").disabled = !p.tts_available;

  const voiceSelect = $("#presTtsVoice");
  if (!p.tts_available) {
    voiceSelect.disabled = true;
    setSelectOptions(voiceSelect, [], "", "ttsVoiceUnavailable");
  } else {
    voiceSelect.disabled = false;
    if (tts.voices_loaded) {
      populateVoiceSelect(tts.voices || [], tts.voice || "auto");
    }
  }

  const speedSelect = $("#presTtsSpeed");
  setSelectOptions(speedSelect, [
    { label: t("ttsSpeedVerySlow"), value: "-50%" },
    { label: t("ttsSpeedSlow"), value: "-25%" },
    { label: t("ttsSpeedNormal"), value: "+0%" },
    { label: t("ttsSpeedFast"), value: "+25%" },
    { label: t("ttsSpeedVeryFast"), value: "+50%" },
  ], tts.speed || "+0%");
  speedSelect.disabled = !p.tts_available;

  $("#presTtsReadName").checked = !!tts.read_player_name;
  $("#presTtsReadName").disabled = !p.tts_available;
  $("#presTtsTestBtn").disabled = !p.tts_available;
  $("#presPreTtsClearBtn").disabled = !p.tts_available;
  syncSwitchesText($("#page-presentation"));

  if (!p.tts_available) {
    $("#presTtsError").hidden = false;
    $("#presTtsError").textContent = t("ttsImportError", p.tts_import_error || t("unknown"));
    $("#presTtsStatus").textContent = t("ttsDependencyFailed");
    $("#presTtsStatus").classList.add("error-text");
  } else {
    $("#presTtsError").hidden = true;
    $("#presTtsStatus").classList.remove("error-text");
    const status = tts.voice_status;
    if (status && status.key && I18N[status.key] !== undefined) {
      $("#presTtsStatus").textContent = t(status.key, ...(status.args || []));
    } else if (!tts.voices_loaded) {
      $("#presTtsStatus").textContent = "";
    } else {
      $("#presTtsStatus").textContent = "";
    }
  }
}

function populateStartPage() {
  setWorkingStatus(STATE.working);
  if (!STATE.working) {
    $("#stAccessCard").hidden = true;
  }
}

function populateAboutPage() {
  const program = STATE.program || {};
  $("#aboutVersion").textContent = STATE.version || "";
  $("#aboutAuthor").textContent = program.author || "";
  $("#aboutEmail").textContent = program.email || "";
  const github = $("#aboutGithub");
  github.textContent = program.github || "";
  github.href = program.github || "#";
  const license = $("#aboutLicense");
  license.textContent = program.license_name || "";
  license.href = program.license_url || "#";
}

function populateSettingsPage() {
  const s = STATE.settings;
  setSelectOptions($("#seLangSelect"),
    STATE.supportedLanguages.map((pair) => ({ label: pair[0], value: pair[1] })),
    s.interface_language || "");
  setSelectOptions($("#seFreqSelect"), [
    { label: t("freqStartup"), value: "startup" },
    { label: t("freqDaily"), value: "daily" },
    { label: t("freqWeekly"), value: "weekly" },
    { label: t("freqMonthly"), value: "monthly" },
    { label: t("freqNever"), value: "never" },
  ], s.update_frequency || "startup");
  $("#seIncludePrerelease").checked = !!s.include_prerelease;
  $("#seCurrentVersion").textContent = "v" + (s.current_version || "");
  $("#seUpdaterWarn").hidden = !!s.updater_available;
  $("#seCheckUpdateBtn").disabled = !s.updater_available;
}

/* ═══════════════════════════ SSE ═══════════════════════════ */

function connectEvents() {
  const source = new EventSource("/api/events");

  const handler = (name, fn) => {
    source.addEventListener(name, (e) => {
      let data = {};
      try { data = JSON.parse(e.data); } catch (err) {}
      fn(data);
    });
  };

  handler("toast", (data) => {
    showToast(data.kind, data.title, data.content, data.duration);
  });
  handler("update-available", (data) => {
    showUpdateDialog(data.release, data.current_version, data.note_html);
  });
  handler("download-progress", handleDownloadProgress);
  handler("download-thread-count", handleDownloadThreadCount);
  handler("download-finished", handleDownloadFinished);
  handler("download-error", handleDownloadError);
  handler("tts-test-result", handleTtsTestResult);
  handler("voices-loaded", (data) => {
    if (!data.ok) {
      const voiceSelect = $("#presTtsVoice");
      voiceSelect.disabled = true;
      setSelectOptions(voiceSelect, [], "", "ttsVoiceUnavailable");
      $("#presTtsStatus").textContent = t("ttsVoiceLoadFailed");
      return;
    }
    STATE.presentation.tts.voices_loaded = true;
    STATE.presentation.tts.voices = data.voices || [];
    populateVoiceSelect(data.voices || [], STATE.presentation.tts.voice || "auto");
    $("#presTtsStatus").textContent = t("ttsVoicesLoaded", data.count || 0);
  });
  handler("languages-loading", (data) => {
    const kind = data.kind || "player";
    langLoading[kind] = true;
    setLangSelectsDisabled(kind, true);
    const spinnerId = kind === "player" ? "#trPlayerTradSpinner" : "#trSendTradSpinner";
    const spinner = $(spinnerId);
    if (spinner) spinner.hidden = false;
  });
  handler("languages-loaded", handleLanguagesLoaded);
  handler("languages-error", handleLanguagesError);
  handler("start-finished", (data) => {
    setWorkingStatus(true);
    buildAccessLinks(data.ips || ["127.0.0.1"], data.web_port || 8080);
  });
  handler("start-error", (data) => {
    setWorkingStatus(false);
    showToast("error", t("startFailed"), data.error || "", 5000);
  });
  handler("pre-tts-started", () => {
    updatePreTtsState({ available: true, running: true, done: 0, total: 0, result: null });
    refreshPreTts();
  });
}

function processPendingEvents(events) {
  (events || []).forEach((item) => {
    const fake = new CustomEvent(item.event);
    fake._data = item.data;
    const handlers = {
      toast: (d) => showToast(d.kind, d.title, d.content, d.duration),
      "update-available": (d) => showUpdateDialog(d.release, d.current_version, d.note_html),
      "download-progress": handleDownloadProgress,
      "download-thread-count": handleDownloadThreadCount,
      "download-finished": handleDownloadFinished,
      "download-error": handleDownloadError,
      "tts-test-result": handleTtsTestResult,
      "start-finished": (d) => {
        setWorkingStatus(true);
        buildAccessLinks(d.ips || ["127.0.0.1"], d.web_port || 8080);
      },
      "start-error": (d) => {
        setWorkingStatus(false);
        showToast("error", t("startFailed"), d.error || "", 5000);
      },
      "voices-loaded": (d) => {
        if (!d.ok) return;
        STATE.presentation.tts.voices_loaded = true;
        STATE.presentation.tts.voices = d.voices || [];
        populateVoiceSelect(d.voices || [], STATE.presentation.tts.voice || "auto");
        $("#presTtsStatus").textContent = t("ttsVoicesLoaded", d.count || 0);
      },
      "languages-loaded": handleLanguagesLoaded,
      "languages-error": handleLanguagesError,
    };
    const fn = handlers[item.event];
    if (fn) fn(item.data);
  });
}

/* ═══════════════════════════ 启动入口 ═══════════════════════════ */

let bootstrapped = false;

async function bootstrap() {
  if (bootstrapped) return;
  bootstrapped = true;

  initClearButtons();
  initSwitches();
  initComboboxes();
  initSpinboxes();

  try {
    if (localStorage.getItem("mct-nav-collapsed") !== "0") {
      setNavCollapsed(true);
    }
  } catch (e) {}

  $("#capBrowseBtn").addEventListener("click", async () => {
    let folder = null;
    const bridge = getApi();
    if (bridge && typeof bridge.select_folder === "function") {
      try {
        folder = await bridge.select_folder();
      } catch (e) {
        folder = null;
      }
    } else {
      folder = window.prompt("Folder path");
    }
    if (folder) {
      $("#capLogPath input").value = folder;
      $("#capLogPath input").dispatchEvent(new Event("input"));
    }
  });

  try {
    const res = await fetch("/api/state");
    const snapshot = await res.json();
    applyState(snapshot);
    processPendingEvents(snapshot.pending_events || []);
    connectEvents();
  } catch (e) {
    document.body.innerHTML = '<div style="padding:40px;color:var(--text-primary)">Failed to load state</div>';
  }
}

document.addEventListener("DOMContentLoaded", bootstrap);
