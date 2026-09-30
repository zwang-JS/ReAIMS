/**
 * ReAIMS — ui.js
 *
 * document_idle 运行。注入右下角的悬浮主题切换按钮。
 *
 * 为什么要放进 Shadow DOM
 * ----------------------
 * 按钮是我们要往页面里加的唯一一个 DOM 元素。如果直接挂在页面 DOM 里，
 * Banner 的 `TABLE TD { color: black }`、`.tabon a { color: #fff }`、
 * `span { line-height: 1.6em }` 等几十条规则会继承进来，按钮会随页面结构变形。
 * Shadow DOM 正好挡住这一层 —— 页面 CSS 无法穿透 shadow 边界。
 *
 * 代价：可继承属性（font-family / color / line-height / letter-spacing…）
 * 【会】穿过边界继承进来，所以下面的 :host 规则必须把它们逐个显式重置。
 *
 * 宿主元素自身的定位（fixed 到右下角）放在 07-widgets.css 里，
 * 因为那是页面级 CSS，用 id 选择器更可靠。
 */
(() => {
  "use strict";

  /* 只在顶层框架注入。子框架里各来一个按钮会重影。
     window.top 的跨源访问本身是允许的（这里只做比较、不读属性）。 */
  try {
    if (window.top !== window) return;
  } catch (e) {
    return;
  }

  const HOST_ID = "reaims-theme-toggle";
  const THEME_KEY = "theme";
  const TOGGLE_KEY = "showToggle";
  const MIRROR_KEY = "reaims:theme";

  const THEMES = ["light", "dark", "system"];

  /* 阴影内部的样式。用 var(--reaims-*) 取 01-tokens.css 里的令牌 ——
     自定义属性会继承进 shadow 边界，所以扩展 UI 与注入样式共用同一个设计系统。
     每个 var() 都带兜底值，万一令牌没加载按钮也不至于变成裸样式。 */
  const SHADOW_CSS = `
    :host {
      /* 重置所有会穿透 shadow 边界继承进来的属性 */
      font-family: var(--reaims-font, -apple-system, "Segoe UI", Roboto, sans-serif);
      font-size: 15px;
      font-style: normal;
      font-weight: 400;
      line-height: normal;
      letter-spacing: normal;
      text-align: left;
      text-transform: none;
      color: var(--reaims-ink, #17161a);
      direction: ltr;
    }

    .toggle {
      display: grid;
      place-items: center;
      width: 44px;
      height: 44px;
      margin: 0;
      padding: 0;
      box-sizing: border-box;
      border: 1px solid var(--reaims-line-strong, #d3d0da);
      border-radius: 50%;
      background-color: var(--reaims-surface, #ffffff);
      color: var(--reaims-ink, #17161a);
      box-shadow: var(--reaims-shadow, 0 1px 2px rgb(0 0 0 / 0.06));
      cursor: pointer;
      transition:
        background-color var(--reaims-dur, 140ms) var(--reaims-ease, ease),
        border-color var(--reaims-dur, 140ms) var(--reaims-ease, ease),
        transform var(--reaims-dur, 140ms) var(--reaims-ease, ease);
    }

    .toggle:hover {
      background-color: var(--reaims-surface-3, #f2f1f5);
      border-color: var(--reaims-brand, #a50b5e);
    }

    .toggle:active {
      transform: scale(0.94);
    }

    .toggle:focus-visible {
      outline: 2px solid var(--reaims-brand, #a50b5e);
      outline-offset: 2px;
    }

    .toggle svg {
      width: 20px;
      height: 20px;
      display: none;
      pointer-events: none;
    }

    /* 当前是浅色 -> 显示月亮（点击切到深色）；当前是深色 -> 显示太阳。
       图标传达的是"点了会发生什么"，不是"现在是什么"。 */
    :host([data-effective="light"]) .icon-moon { display: block; }
    :host([data-effective="dark"])  .icon-sun  { display: block; }

    @media (prefers-reduced-motion: reduce) {
      .toggle { transition: none; }
    }
  `;

  const ICONS = `
    <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         stroke-width="1.8" stroke-linecap="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4.2" />
      <path d="M12 2.6v2.1M12 19.3v2.1M2.6 12h2.1M19.3 12h2.1M5.3 5.3l1.5 1.5M17.2 17.2l1.5 1.5M18.7 5.3l-1.5 1.5M6.8 17.2l-1.5 1.5" />
    </svg>
    <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M20.5 14.6A8.6 8.6 0 0 1 9.4 3.5a8.6 8.6 0 1 0 11.1 11.1z" />
    </svg>
  `;

  let host = null;
  let button = null;

  /* 当前"实际生效"的主题。
     属性没写 = 用户选了跟随系统，此时要看操作系统偏好。 */
  function effectiveTheme() {
    const explicit = document.documentElement.getAttribute("data-reaims-theme");
    if (explicit === "light" || explicit === "dark") return explicit;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function refreshIcon() {
    if (!host) return;

    const effective = effectiveTheme();
    host.setAttribute("data-effective", effective);

    const nextLabel = effective === "dark" ? "切换到浅色模式" : "切换到深色模式";
    if (button) {
      button.setAttribute("aria-label", nextLabel);
      button.setAttribute("title", `${nextLabel}（Alt+Shift+D）`);
    }
  }

  function saveTheme(theme) {
    try {
      localStorage.setItem(MIRROR_KEY, theme);
    } catch (e) {
      /* 忽略：这只是给下次加载用的同步缓存 */
    }

    if (chrome.storage && chrome.storage.sync) {
      chrome.storage.sync.set({ [THEME_KEY]: theme });
    }
  }

  function onToggle() {
    const next = effectiveTheme() === "dark" ? "light" : "dark";

    /* 先本地落一次，手感更跟手；storage.onChanged 随后会再确认一遍（幂等）。
       注意 theme-boot.js 也在监听同一个事件，所以所有已打开的页面 / 框架
       会一起跟着变。 */
    document.documentElement.setAttribute("data-reaims-theme", next);
    refreshIcon();
    saveTheme(next);
  }

  function mount() {
    if (host || document.getElementById(HOST_ID)) return;

    host = document.createElement("div");
    host.id = HOST_ID;

    const shadow = host.attachShadow({ mode: "open" });
    shadow.innerHTML = `<style>${SHADOW_CSS}</style>
      <button type="button" class="toggle">${ICONS}</button>`;
    button = shadow.querySelector(".toggle");

    button.addEventListener("click", onToggle);

    /* 挂到 <html> 而不是 <body>：body 上万一有 transform / filter
       会让 position: fixed 的参照系变成 body，按钮就跟着页面滚走了。 */
    (document.documentElement || document.body).appendChild(host);

    refreshIcon();
  }

  function unmount() {
    if (!host) return;
    host.remove();
    host = null;
    button = null;
  }

  function applyVisibility(show) {
    if (show) mount();
    else unmount();
  }

  /* ---- 快捷键：Alt+Shift+D ----
     由 content script 自己监听，不需要在 manifest 里申请 commands 权限。
     用 e.code 而不是 e.key，避免受键盘布局影响。 */
  document.addEventListener(
    "keydown",
    (event) => {
      if (event.altKey && event.shiftKey && event.code === "KeyD") {
        event.preventDefault();
        onToggle();
      }
    },
    true
  );

  /* ---- 与外部改动保持同步 ---- */

  /* 系统主题变了（用户选了"跟随系统"时图标要跟着换） */
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  if (media.addEventListener) media.addEventListener("change", refreshIcon);

  if (chrome.storage && chrome.storage.sync) {
    chrome.storage.sync.get({ [TOGGLE_KEY]: true }, (data) => {
      if (chrome.runtime && chrome.runtime.lastError) return;
      applyVisibility(data[TOGGLE_KEY] !== false);
    });

    chrome.storage.onChanged.addListener((changes, area) => {
      if (area !== "sync") return;

      /* 弹窗里改了主题 -> 更新图标 */
      if (changes[THEME_KEY]) refreshIcon();

      /* 弹窗里开关了悬浮按钮 */
      if (changes[TOGGLE_KEY]) applyVisibility(changes[TOGGLE_KEY].newValue !== false);
    });
  } else {
    /* 拿不到 storage 也要能用 */
    mount();
  }
})();
