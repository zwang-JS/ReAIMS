/**
 * ReAIMS — theme-boot.js
 *
 * 在 document_start 运行：CSS 已经注入、页面的其它脚本还没跑、第一帧还没画。
 *
 * 为什么需要这个脚本（而不是让 CSS 自己搞定）
 * ------------------------------------------
 * "跟随系统"这个选项本来就不需要 JS —— CSS 里的 prefers-color-scheme 会处理，
 * 也因此结构上不可能闪烁。但只要用户显式选了浅色或深色，就必须在【绘制之前】
 * 把 data-reaims-theme 写到 <html> 上。
 *
 * 而 chrome.storage 是异步的：等它 resolve，第一帧往往已经画完了，
 * 用户会看到浅色闪一下再跳成深色。所以这里把用户的选择额外镜像一份到
 * localStorage —— 它是同步可读的，且 content script 与页面同源、共用同一个
 * storage 对象，因此可以在 document_start 同步读出来立刻落属性。
 *
 * chrome.storage.sync 仍然是跨设备的事实来源，localStorage 只是同步缓存；
 * 两者不一致时以 storage 为准，并回写镜像。
 *
 * 本脚本会在每个 frame（all_frames）里各跑一次 —— 这是必要的，
 * 因为每个 document 都需要自己的 data-reaims-theme 属性。
 */
(() => {
  "use strict";

  const THEME_KEY = "theme";
  const MIRROR_KEY = "reaims:theme";
  const THEMES = ["light", "dark", "system"];

  /* 镜像读写：localStorage 在部分受限/分区上下文里会直接抛异常，
     不能让它把整个脚本带崩 —— 失败时安静地退回"跟随系统"，
     那条路径不需要属性，照样是对的。 */
  const mirror = {
    read() {
      try {
        const v = localStorage.getItem(MIRROR_KEY);
        return THEMES.indexOf(v) !== -1 ? v : null;
      } catch (e) {
        return null;
      }
    },
    write(value) {
      try {
        localStorage.setItem(MIRROR_KEY, value);
      } catch (e) {
        /* 忽略 */
      }
    },
  };

  function applyTheme(theme) {
    /* document_start 时 documentElement 通常已经存在，但规范并不保证
       （about:blank、XML 文档等边角情况下可能是 null），所以要判空。 */
    const el = document.documentElement;
    if (!el) return false;

    if (theme === "light" || theme === "dark") {
      el.setAttribute("data-reaims-theme", theme);
    } else {
      /* "system" -> 不写任何属性，完全交给 CSS 的 prefers-color-scheme 解析。
         这条路径不需要 JS 参与，也就不存在闪烁。 */
      el.removeAttribute("data-reaims-theme");
    }
    return true;
  }

  function applyWhenReady(theme) {
    if (applyTheme(theme)) return;
    /* 极罕见：文档元素还没被创建。等它出现再落，避免整个主题静默失效。 */
    const observer = new MutationObserver(() => {
      if (applyTheme(theme)) observer.disconnect();
    });
    observer.observe(document, { childList: true });
  }

  /* ---- 1) 同步落一次（读镜像，避免闪烁） ---- */
  let current = mirror.read() || "system";
  applyWhenReady(current);

  /* ---- 2) 异步与事实来源对账 ---- */
  if (typeof chrome === "undefined" || !chrome.storage || !chrome.storage.sync) {
    return;
  }

  chrome.storage.sync.get({ [THEME_KEY]: "system" }, (data) => {
    if (chrome.runtime && chrome.runtime.lastError) return;

    const stored = THEMES.indexOf(data[THEME_KEY]) !== -1 ? data[THEME_KEY] : "system";
    if (stored === current) return;

    current = stored;
    mirror.write(stored);
    applyWhenReady(stored);
  });

  /* ---- 3) 实时同步 ----
     chrome.storage.onChanged 会在所有扩展上下文触发，包括每个 frame 的
     content script。所以弹窗或悬浮按钮改了主题之后，不需要 service worker
     中转，所有已打开的页面和框架会立即跟着变。 */
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "sync" || !changes[THEME_KEY]) return;

    const next = changes[THEME_KEY].newValue;
    /* value 相同时直接返回 —— 否则写入方自己也会收到事件，形成回环 */
    if (THEMES.indexOf(next) === -1 || next === current) return;

    current = next;
    mirror.write(next);
    applyTheme(next);
  });
})();
