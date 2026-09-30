/* 验证首次进入的默认主题 —— 直接执行 theme-boot.js 的逻辑，不依赖浏览器或扩展加载。
 *
 * 为什么需要它：默认主题是用户可见的行为，却只由两个文件里的一个常量决定
 * （theme-boot.js 与 popup.js 各有一个 DEFAULT_THEME）。改了一处、漏了另一处，
 * 会得到一个"页面是浅色、弹窗显示深色"的诡异状态，而没有任何检查会报出来。
 * 另外单机上也确实没法用命令行加载扩展来端到端验证 —— 这个 Chrome 是 branded build，
 * 会把 --load-extension 直接忽略（"is not allowed in Google Chrome, ignoring."）。
 * 所以把逻辑本身跑起来，是这里能做的最直接的验证。
 *
 * 用法：
 *     node tools/check_theme_default.js
 *
 * 退出码 0 = 全部通过，1 = 有失败。
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SRC = path.join(__dirname, "..", "src", "content", "theme-boot.js");
const POPUP = path.join(__dirname, "..", "src", "popup", "popup.js");

if (!fs.existsSync(SRC)) {
  console.error("找不到 theme-boot.js：", SRC);
  process.exit(2);
}
const code = fs.readFileSync(SRC, "utf8");

/* 把 theme-boot.js 需要的东西桩起来，记录它对 <html> 做了什么。
   stored === undefined 表示"storage 里从没存过"，此时 chrome.storage.sync.get()
   会把调用方传进去的默认值原样回调回来 —— 照这个真实语义桩，才能验证默认值本身。 */
function run({ mirror, stored }) {
  const written = [];
  const mirrorWrites = [];

  const sandbox = {
    console,
    MutationObserver: class { observe() {} disconnect() {} },
    document: {
      documentElement: {
        setAttribute: (k, v) => written.push(["set", k, v]),
        removeAttribute: (k) => written.push(["remove", k]),
      },
      addEventListener() {},
    },
    localStorage: {
      getItem: () => mirror,
      setItem: (k, v) => mirrorWrites.push([k, v]),
    },
    chrome: {
      runtime: {},
      storage: {
        sync: {
          get(defaults, cb) {
            cb(stored === undefined ? defaults : { ...defaults, theme: stored });
          },
        },
        onChanged: { addListener() {} },
      },
    },
  };

  vm.createContext(sandbox);
  vm.runInContext(code, sandbox);

  return {
    themeOps: written.filter((op) => op[1] === "data-reaims-theme"),
    mirrorWrites,
  };
}

let failures = 0;
function expect(cond, what) {
  console.log(`    ${cond ? "PASS" : "FAIL"}  ${what}`);
  if (!cond) failures++;
}

/* 两个文件里的 DEFAULT_THEME 必须一致 —— 这是最容易被改漏的地方 */
console.log("=== 两个文件里的 DEFAULT_THEME 是否一致 ===");
{
  const grab = (file) => {
    const m = fs.readFileSync(file, "utf8").match(/const DEFAULT_THEME\s*=\s*"([^"]+)"/);
    return m ? m[1] : null;
  };
  const a = grab(SRC);
  const b = grab(POPUP);
  console.log(`    theme-boot.js = ${JSON.stringify(a)}   popup.js = ${JSON.stringify(b)}`);
  expect(a !== null && a === b, "两处默认值一致");
}

console.log("\n=== 场景 1：全新用户（镜像为空、storage 里也没有任何值）===");
{
  const { themeOps, mirrorWrites } = run({ mirror: null, stored: undefined });
  console.log(`    对 data-reaims-theme 的操作: ${JSON.stringify(themeOps)}`);
  expect(themeOps.some((o) => o[0] === "set" && o[2] === "light"), "落成 light（默认浅色）");
  expect(!themeOps.some((o) => o[0] === "set" && o[2] === "dark"), "没有落成 dark");
  expect(!themeOps.some((o) => o[0] === "remove"), "没有走「不写属性」那条路（那代表跟随系统）");
  // 这里【不该】写镜像：stored 与 current 都是 light，代码会提前 return。
  // 不是缺陷 —— 镜像存在的意义是"下次加载能同步读到用户的选择"，而默认值本就等于
  // 镜像该有的值，空着读出来仍是 light。
  expect(mirrorWrites.length === 0, "没有多余的镜像写入");
}

console.log("\n=== 场景 2：镜像丢了、但 storage 里存着用户的选择（决定下次会不会闪）===");
{
  const { themeOps, mirrorWrites } = run({ mirror: null, stored: "dark" });
  expect(themeOps.some((o) => o[0] === "set" && o[2] === "dark"), "对账后落成 dark");
  expect(mirrorWrites.some(([, v]) => v === "dark"),
         "把 dark 回写进镜像 —— 下次加载才能同步读到，不会先闪一帧浅色");
}

console.log("\n=== 场景 3：用户之前显式选过深色（镜像里有）===");
{
  const { themeOps } = run({ mirror: "dark", stored: "dark" });
  expect(themeOps.some((o) => o[0] === "set" && o[2] === "dark"), "仍然落成 dark（没被默认值带跑）");
}

console.log("\n=== 场景 4：用户选了「跟随系统」===");
{
  const { themeOps } = run({ mirror: "system", stored: "system" });
  expect(themeOps.some((o) => o[0] === "remove"), "移除了属性（= 交给 prefers-color-scheme）");
}

console.log("\n=== 场景 5：storage 里是非法值 ===");
{
  const { themeOps } = run({ mirror: null, stored: "chartreuse" });
  expect(themeOps.some((o) => o[0] === "set" && o[2] === "light"), "回落到默认浅色");
}

console.log();
console.log(failures === 0 ? "全部通过" : `${failures} 项失败`);
process.exit(failures === 0 ? 0 : 1);
