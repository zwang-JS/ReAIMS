/**
 * ReAIMS — popup.js
 *
 * 弹窗只做两件事：读写 chrome.storage.sync，以及让弹窗自己跟着主题变。
 *
 * 主题的实时广播不需要在这里做：content script 里的 theme-boot.js 自己监听
 * chrome.storage.onChanged，写完 storage 所有已打开的页面就会跟着变。
 */
(() => {
  "use strict";

  const THEME_KEY = "theme";
  const TOGGLE_KEY = "showToggle";
  const THEMES = ["light", "dark", "system"];

  /* 首次进入（或用户没选过）时用的主题。
     定成常量而不是散落的字面量 —— 只改一处就会得到一个"默认值一半是浅色一半是
     跟随系统"的诡异状态，而且这种不一致没有任何检查会报出来。
     必须和 theme-boot.js 里的 DEFAULT_THEME 保持一致。 */
  const DEFAULT_THEME = "light";

  const segButtons = Array.from(document.querySelectorAll(".seg button"));
  const showToggleInput = document.getElementById("show-toggle");
  const versionEl = document.getElementById("reaims-version");

  let theme = DEFAULT_THEME;

  /* 版本号从 manifest 里读，不在 HTML 里写死。
     写死的话每次发版后弹窗都会显示上一个版本，而这种不一致没有任何检查会报出来。
     直接以 file:// 打开本页做视觉验证时 chrome.runtime 不存在 —— 那就留空，
     宁可空着也不要显示一个可能已经过期的值。 */
  if (versionEl && typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.getManifest) {
    versionEl.textContent = "v" + chrome.runtime.getManifest().version;
  }

  /* 弹窗自己也要跟随主题。机制与页面完全一致：
     显式选择 -> 写属性；跟随系统 -> 不写属性，交给 prefers-color-scheme。 */
  function applyPopupTheme(value) {
    const root = document.documentElement;
    if (value === "light" || value === "dark") {
      root.setAttribute("data-reaims-theme", value);
    } else {
      root.removeAttribute("data-reaims-theme");
    }
  }

  function renderSegmented() {
    segButtons.forEach((button) => {
      const selected = button.dataset.theme === theme;
      button.setAttribute("aria-checked", selected ? "true" : "false");
    });
  }

  function save(key, value) {
    if (!chrome.storage || !chrome.storage.sync) return;
    chrome.storage.sync.set({ [key]: value });
  }

  /* ---- 初始化 ---- */
  /* chrome.storage 在扩展环境里一定存在；但直接以 file:// 打开这个页面
     （做视觉验证时会这么做）时它不存在，不守卫就会抛 ReferenceError，
     把整个脚本带崩、控件停在未渲染状态。
     注意这里只是跳过读写，不能 return —— 下面还要注册点击与键盘处理。 */
  const hasStorage = Boolean(chrome.storage && chrome.storage.sync);

  if (hasStorage) {
    chrome.storage.sync.get({ [THEME_KEY]: DEFAULT_THEME, [TOGGLE_KEY]: true }, (data) => {
      if (chrome.runtime && chrome.runtime.lastError) return;

      theme = THEMES.indexOf(data[THEME_KEY]) !== -1 ? data[THEME_KEY] : DEFAULT_THEME;
      showToggleInput.checked = data[TOGGLE_KEY] !== false;

      applyPopupTheme(theme);
      renderSegmented();
    });
  } else {
    applyPopupTheme(theme);
    renderSegmented();
  }

  /* ---- 外观：三选一 ---- */
  segButtons.forEach((button) => {
    button.addEventListener("click", () => {
      theme = button.dataset.theme;
      applyPopupTheme(theme);
      renderSegmented();
      save(THEME_KEY, theme);
    });
  });

  /* 键盘操作：方向键在三项之间移动（role="radiogroup" 的预期行为） */
  document.querySelector(".seg").addEventListener("keydown", (event) => {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;

    event.preventDefault();
    const index = segButtons.findIndex((b) => b.getAttribute("aria-checked") === "true");
    const next = segButtons[(index + step + segButtons.length) % segButtons.length];
    next.focus();
    next.click();
  });

  /* ---- 悬浮按钮开关 ---- */
  showToggleInput.addEventListener("change", () => {
    save(TOGGLE_KEY, showToggleInput.checked);
  });

  /* ---- 反向同步 ----
     弹窗开着的时候，用户可能用悬浮按钮或快捷键改了主题，这里跟着更新。 */
  if (hasStorage) {
    chrome.storage.onChanged.addListener((changes, area) => {
      if (area !== "sync") return;

      if (changes[THEME_KEY]) {
        const next = changes[THEME_KEY].newValue;
        if (THEMES.indexOf(next) === -1 || next === theme) return;
        theme = next;
        applyPopupTheme(theme);
        renderSegmented();
      }

      if (changes[TOGGLE_KEY]) {
        showToggleInput.checked = changes[TOGGLE_KEY].newValue !== false;
      }
    });
  }
})();
