# ReAIMS

为香港城市大学 **AIMS**（Ellucian/SunGard Banner 8.33 Self-Service，`banweb.cityu.edu.hk`）做的界面重构 Chrome 扩展。

浅色与深色（同一页，主菜单）：

![浅色模式](docs/preview-light.png)

![深色模式](docs/preview-dark.png)

![数据表](docs/preview-tables.png)

## 快速安装

本扩展未上架 Chrome 应用商店，用开发者模式加载。**不需要 Git，也不需要构建。**

1. 到 [Releases](https://github.com/zwang-JS/ReAIMS/releases/latest) 下载最新的 zip 压缩包（文件名形如 `ReAIMS-vX.Y.Z.zip`）
2. chrome浏览器右上角的三个点->扩展程序->管理扩展程序
3. 右上角打开 **开发者模式**
4. **把下载的 zip 压缩包直接拖进这个页面**，确认安装
5. 打开 AIMS，界面即生效

> **如果拖进去没反应**：把 zip 解压，点左上角 **加载已解压的扩展程序**，选择**解压出来的文件夹**
> （注意是文件夹，不是 zip 本身）。拖 zip 在部分 Chrome 版本上可行，而"解压后加载文件夹"
> 是官方文档写的那条路 —— 两条都列出来，免得卡住。

> **升级**：未打包的扩展不会自动更新。出新版本时重新下载 zip 拖一次即可（先删掉旧的，
> 或用同一个方式覆盖）。

没有构建步骤、没有 npm 依赖 —— 发布包里就是扩展本身（`manifest.json` + `icons/` + `src/`）。

## 功能

- **全站覆盖**：AIMS 的每一个子页面（个人资料、学生记录、选课、学生服务、成绩、课表…）共用同一套样式表，因此也共用同一套新样式，不需要逐页适配。
- **深浅色主题**：浅色 / 深色 / 跟随系统三选一。**首次进入默认浅色**，选择可跨设备同步。
- **三个切换入口**：扩展弹窗、页面右下角悬浮按钮、快捷键 `Alt`+`Shift`+`D`。
- **数据表重构**：梅墨表头条 + 表纸左缘的品红侧脊 + 圆角表纸 + 柔和阴影 + 发丝行线 + 悬停高亮 + 等宽数字对齐 + 表头吸顶。
- **导航重构**：顶栏改为现代吸顶导航；当前标签是一条梅墨条配品红索引边，与表头说同一种语言。
- **打印友好**：深色模式下打印不会打出黑底。

## 文件结构

```
ReAIMS/
├── manifest.json
├── icons/                      PIL 生成，见 tools/gen_icons.py
├── src/
│   ├── styles/
│   │   ├── 01-tokens.css       设计令牌。唯一允许出现字面颜色值的文件
│   │   ├── 02-base.css         全局重置、排版、链接、焦点、文字色归一化
│   │   ├── 03-chrome.css       吸顶身份条、品牌带、标签条、页头、页脚、版心
│   │   ├── 04-tables.css       表格两层做法
│   │   ├── 05-forms.css        输入框、下拉、按钮、标签
│   │   ├── 06-messages.css     提示 / 警告 / 错误
│   │   ├── 07-widgets.css      遗留位图资源、裸色类、悬浮按钮宿主定位
│   │   └── custom.css          最终强制覆盖层 + 打印
│   ├── content/
│   │   ├── theme-boot.js       document_start：同步落主题，零闪烁
│   │   └── ui.js               document_idle：悬浮按钮、快捷键、实时同步
│   └── popup/                  扩展弹窗
└── tools/
    ├── gen_icons.py            生成扩展图标（Pillow）
    ├── package_release.py      打发布 zip（发布资产，dist/ 不入库）
    ├── check_theme_default.js  验证首次进入的默认主题（Node，无依赖）
    └── preview/                静态预览台（见下）
        ├── fetch_vendor.py     抓取第三方资源（vendor/ 不入库）
        ├── build_preview.py    由本地抓取的页面与内置样例合成
        ├── audit_overrides.py  覆盖完备性审计（含自检）
        ├── check_surfaces.py   背景卫生检查（含自检）
        ├── preview.html        主预览页
        └── preview-bare.html   无外壳的裸弹窗页样例
```

> 预览台的 fixture 1 需要一份**你自己抓取的 AIMS 页面**，放在仓库根目录的 `source code.html`。
> 该文件不入库，见下方「关于 source code.html」。

### 数字前缀 = 层叠顺序

`manifest.json` 里 `content_scripts[].css` 的**数组顺序就是层叠顺序**，与文件名前缀一一对应。同为 `!important` 时，后面的文件胜出。

所以要加新样式文件时，别只建文件 —— 必须同时插进 manifest 的数组，并放在正确的层叠位置上。（漏掉 manifest 条目会**静默失败**：页面只是少了一部分样式，看起来像选择器写错了。）

## 开发

### 不登录也能验证样式

`tools/preview/` 是一个静态预览台，直接用浏览器打开即可，不需要扩展、不需要服务器、不需要 AIMS 账号。

```bash
# 首次使用先抓一次第三方资源（理由见下）—— 这一步不能跳过
python tools/preview/fetch_vendor.py

# 重新生成页面（fixture 1 需要根目录的 source code.html，没有就跳过它并给出提示）
python tools/preview/build_preview.py

# 截图核对。注意两点，都是实测踩出来的：
#   1. out/ 目录不会随仓库分发（已 gitignore），必须自己建；
#   2. --screenshot 不认相对路径，必须给绝对路径，否则只会得到
#      "Failed to write file ... path not found"，而 Chrome 仍然退出 0（静默失败）。
mkdir -p tools/preview/out

CHROME="/c/Program Files/Google/Chrome/Application/chrome.exe"
REPO="C:/path/to/ReAIMS"          # ← 改成你这个仓库的绝对路径，正斜杠

"$CHROME" --headless=new --disable-gpu --hide-scrollbars \
  --screenshot="$REPO/tools/preview/out/light.png" --window-size=1440,3000 \
  "file:///$REPO/tools/preview/preview.html?theme=light"
```

> **headless Chrome 起不来的话**：如果报 `Missing headless user data directory`，是默认
> profile 被占用了（你自己开着 Chrome 就会这样）。加一个独立 profile 即可：
> `--user-data-dir=/tmp/reaims-chrome`。本仓库的 `audit_overrides.py` 已经自带这个处理，
> 所以你手敲截图命令时才需要管它。

`?theme=light` / `?theme=dark` 切主题；不带参数 = 不写属性 = "跟随系统"，这也是一条需要单独验证的路径。

**注意预览台的样式表顺序是反的**（我们的在前、AIMS 的在后），这是刻意为之 —— 真实浏览器里 content script CSS 正是注入在页面样式表之前。把顺序"修正"成常规写法会让预览台失去全部价值：它就不再能验证 `!important` 是否覆盖完整了。

预览台包含五组样例：真实主菜单页、真实数据录入表单（从线上抓取）、合成的数据表、消息样式、以及一个**完全没有样式表**的裸弹窗页（`pics.htm` 那类，配色靠 `<body bgcolor text link>` 表现属性写死）。

最后一组单独放在 `preview-bare.html`：它依赖的 `body:not(:has(.cityubar_outer))` 规则，在含有 AIMS 外壳的页面里根本不会触发，所以必须用一个不含外壳的独立页面来验证。

#### 关于第三方资源（必须说明）

预览台要忠实，就得有两样不属于本项目的东西：

1. **AIMS 真实的 `web_defaultapp.css`**。有了它，预览台才能回答最关键的那个问题：我们的 `!important` 到底有没有压过 AIMS 的规则。没有它，预览台就只是个"孤立环境下的效果图"，看着好看却什么也没验证。
2. **CityU / Apple / Google 的品牌图**（校徽、页头 banner、应用商店徽章）与 Banner 的装饰性 GIF —— 让页头和菜单项目符号能正常渲染，而不是一堆破图。

这些东西的版权属于 CityU、Ellucian/SunGard 与 Apple/Google，而本仓库是公开的，所以**不随仓库分发**：`tools/preview/vendor/` 已在 `.gitignore` 里，改由 `tools/preview/fetch_vendor.py` 从浏览器使用的同一批公开地址按需下载到本地。

**缺了它会怎样**：预览台照样能打开、看起来也正常，但它**不再验证层叠覆盖** —— 而那正是这个预览台存在的唯一理由。构建脚本检测到缺失时会打印醒目警告，不会让你在不知情的情况下相信一次没有发生的验证。

#### 关于 source code.html（这个不入库是隐私原因，不是版权原因）

预览台的 fixture 1 用的是你登录 AIMS 后抓下来的真实页面标记 —— 那是这类验证里最有价值的一份材料，因为它是唯一"未经我手改造"的真实结构。

但它**不适合进公开仓库**：抓下来的页面里带着会话期标识。具体来说，AIMS 的会话保活脚本里有这样一段（值已打码 —— 这里刻意不写出真实取值，原因见下）：

```
twbktmlb_cityu.P_Release_Timeout?in_pd=<会话 ID>&in_tm=<时间戳>&in_ran=<一次性随机值>
```

`in_pd`、`in_ran` 都是属于个人会话的值。所以 `source code.html` 已被移出版本控制并写入 `.gitignore`。

> 顺带记一笔教训：这份说明的初版里我把上面那几个真实取值原样写了出来当例子，
> 结果在"移除它们"的那一次提交里又把它们发布了一遍。**说明"某个值不该公开"时，
> 不要附带那个值本身** —— 用占位符。真实取值在 commit `02a9d4a` 的历史里依然
> 可取（这是当初知情后选择保留的），但至少不该出现在当前 HEAD 的文档里。

**要恢复 fixture 1**：自己登录 AIMS，把该页面的 HTML 另存为仓库根目录的 `source code.html`，再跑 `python tools/preview/build_preview.py`。缺这个文件时构建不会崩 —— 它会在 fixture 1 的位置放一个明确标注的占位块，并打印提示，其余四组样例照常生成。

一份便于对照：**缺 capture 时生成出来的页面，与已提交的版本只差 fixture 1 那一节**，其余完全一致。如果你习惯用某个计数来体检（例如数 `div.body` 的个数），注意它会从 5 变成 4 —— 那不是回归，是 fixture 1 本来就没了。`--check` 已经知道这件事：capture 缺失时它会说明"只比较了 fixture 1 以外的部分"，而不是甩一个 STALE 给你；但只要别处真的漂了，它照样会报 STALE。

顺带确认过两件事，都是实测的：

1. `preview.html` 里**不含**这些会话标识（`in_pd` / `in_ran` 命中数为 0）。构建时会把 fixture 1 里**全部三个** `<script>` 块整块剥掉（会话保活一个 + Google 标签两个），而那几行值正好都在会话保活脚本里。
2. 但**并非**所有抓取痕迹都被剥掉了：`preview.html` 里还留着 hidden form 中的采集时间戳（`event_time` 等，值是 `2026-09-30 18:17:xx`）。它们不是会话标识、灵敏度低得多，而且属于真实标记结构的一部分（剥掉就会破坏 fixture 的保真度），所以按你决定"保留 preview.html 的真实标记"一并留下了。写在这里是为了让口径准确：**移出的是会话标识，不是"所有抓取痕迹"。**

> **一个操作提醒**：`source code.html` 现在是 gitignore 的未跟踪文件，所以 `git clean -fdx`
> 会**把它删掉**（同样会删掉 `tools/preview/vendor/` 和 `out/`）。你的抓取件在公开
> 历史 `02a9d4a` 里还能取回，但更省事的是日常清理时用 `git clean -fd`（不加 `-x`），
> 那样只会清理未忽略的未跟踪文件。

### 重新生成图标

```bash
python tools/gen_icons.py
```

需要 Pillow。图标是 4 倍超采样后降采样得到的，保证 16px 下依然干净。

### 覆盖完备性审计

改完 CSS 之后，比起一张张看截图，"每个 AIMS 写死的颜色是不是都被覆盖了"这个问题可以直接机械地回答：

```bash
python tools/preview/audit_overrides.py
```

它会解析 AIMS 样式表里声明过的所有字面颜色，然后把预览台在**深色模式**下渲染一遍，
遍历每一个可见的、带 class 的元素，报出任何计算值仍然等于 AIMS 字面色的地方。

**为什么限定深色模式才能这么判**：深色下我们自己的取值全是暗色，而 AIMS 是 2002 年的
纯浅色设计、取值全是浅色 —— 两者重合不可能是巧合，只可能是漏覆盖。唯一的例外是纯白
（我们的按钮文字和深色下的应用商店徽章底片都用它），这个值被显式排除，也是整份检查里
唯一需要"相信我"的地方。

**这个检查自带自检**，因为一个不可能失败的检查等于没检查：

```bash
python tools/preview/audit_overrides.py --selftest
```

它会故意破坏一条覆盖规则、确认审计确实报 FAIL、再把文件还原。如果哪天你改了审计逻辑，
先跑这个。

> 顺带一提：这个审计真的抓到过一个漏洞。原本单元格规则是按**表的 class** 命中的，
> 于是 `<td class="ntlabel">` 只要出现在一张我们没枚举到的表里，AIMS 那片 `#E3E5EE`
> 浅灰紫底就会原样漏出来。现在单元格规则改成按**单元格 class** 命中，覆盖的完备性
> 不再依赖"我有没有把表类枚举全"。

### 背景卫生检查

```bash
python tools/preview/check_surfaces.py
python tools/preview/check_surfaces.py --selftest
```

这个工具和上面的审计是**互补**的，补的是审计的三个结构性盲区：审计只遍历**带 class 的元素**
（`html` / `body` 没有 class，永远不被检查）；被"抹掉"的底计算值是 `transparent` 而**不是**
AIMS 的字面色；而且纯白被排除在它的危险集合外（我们确实在按钮文字和徽章白片上刻意用白）。
所以"某个容器带着浅色底"和"我们自己的底被误删"这两类问题，审计**在结构上就看不见**。

它做两件事：

1. **深色模式下不该有浅色底** —— 遍历每个可见元素（不过滤 class），报出任何计算出来偏亮的
   不透明底色。这就是能抓住"白底粉字"那个 bug 的检查；刻意保留的浅色面（深色模式下的
   应用商店徽章白片）走显式白名单，并且白名单会被打印出来，不会悄悄放行。
2. **我们自己画的底必须还在** —— 断言 13 个关键面（页面底、品牌带、吸顶栏、标签胶囊、
   表纸、表头着色、info / warning callout、徽章白片…）在明暗两种模式下都等于它该用的令牌。
   其中 `html` / `body` 那两条是**哨兵**：页面底色一旦变透明就会立刻失败 ——
   这正是 `02-base.css` 里那条零特异性背景中和规则最危险的失败模式。

同样自带 `--selftest`：弄坏徽章那条规则，确认 CHECK 2 会报 FAIL，再还原。

### 打发布包

```bash
python tools/package_release.py
```

产出 `dist/ReAIMS-v<版本>.zip`，就是 Release 里那个可以拖进 `chrome://extensions` 的文件。

**为什么文件清单不是从 `manifest.json` 推出来的**：那样会打出一个**坏包**。
`manifest.json` 里根本没有 `src/popup/popup.css` —— 引用它的是 `popup.html` 里的
`<link href="popup.css">`。照 manifest 的引用清单打包，弹窗的整个样式表都会漏掉，
而弹窗只是变成没有样式，构建输出里一点异常都看不出来。所以脚本把整个 `src/` 与 `icons/`
都打进去，然后**解析 manifest 与嵌套 HTML 的引用逐个校验** —— 那才是能抓住这类错误的一步。

另外两条硬要求：`manifest.json` 必须在 zip 的**根目录**（套一层文件夹 Chrome 就会报
"Manifest file is missing or unreadable"，拖入和解压两条路都一样）；时间戳写死，
同一份内容重复构建字节一致。

### 验证默认主题

```bash
node tools/check_theme_default.js
```

默认主题由两个文件里各一个 `DEFAULT_THEME` 常量决定（`theme-boot.js` 与 `popup.js`）。
改了一处漏了另一处，就会得到"页面是浅色、弹窗显示深色"的状态，而**没有任何检查会报出来**，
所以这个脚本第一件事就是断言两处一致；然后用 Node 直接执行 `theme-boot.js` 的逻辑
（把 `localStorage` / `document` / `chrome.storage` 都桩掉），验证五个场景：全新用户落成
浅色、镜像丢失后能对账回用户的选择并回写镜像（决定下次会不会闪一帧）、显式深色不被默认值
带跑、跟随系统仍然不写属性、非法值回落浅色。

之所以用 Node 直接跑逻辑而不是装扩展试：本机的 branded Chrome 会把 `--load-extension`
**直接忽略**（只打一行 `is not allowed in Google Chrome, ignoring.`），命令行加载不了扩展，
所以注入路径只能在浏览器里手工验证。

## 已知限制

- **不含登录页**。AIMS 走 SAML SSO 跳转到 Okta（`auth.cityu.edu.hk`），那是已现代化、基于 Shadow DOM、且全校共用的非 AIMS 页面，本扩展刻意不碰。
- **不能重构 DOM**。只改样式，所以无法把一个表格变成 CSS Grid，也无法移动元素位置。像"把页面标题和搜索框放进同一行"这类调整只能靠 flex 容器与 `order` 实现。
- **仅覆盖 `banweb.cityu.edu.hk`**。AIMS 跳转到其它域名的页面不在范围内。
- **用弹窗改主题后，下一次打开 AIMS 可能会有一次极短的闪烁**。因为页面侧的 `localStorage` 镜像只有在页面里跑过脚本才会更新，而 `theme-boot.js` 从镜像同步读取。只要那时有任一 AIMS 页面开着，镜像就会立即更新，不会闪。
- 表头吸顶（`position: sticky`）用的是 AIMS 的 `td.ddheader` 而非 `<thead>`，因为 Banner 不产生 `<thead>`。极长的多段表格里，多行表头会叠在同一位置。
- **浅色模式下，标记层面写死的浅色/浅彩底也会被一并清掉**。`02-base.css` 里那条背景中和规则是无条件的（不分主题），目的是让 AIMS 画的所有底都不可能漏出来。浅色模式下 AIMS 那些接近纯白的底本来就看不出来，所以基本没有实际差别；但如果某处用的是有意的**彩色**底（例如米黄提示块），它在浅色模式下也会变成我们自己的承载面。这是一处刻意的行为变化 —— 换来的是"深色模式下不可能再出现白底"。
- **只有行内 `!important` 压不过**。如果 AIMS 用 `style="background-color:#fff !important"` 写死底色，作者样式表无论怎么写都赢不了（行内 important 高于作者 important）。目前没遇到，真遇到的话只能改用 USER 来源注入（需要加 `scripting` 权限）。

## 许可

[MIT](LICENSE)

本项目与香港城市大学无隶属关系，为个人非官方项目。

**本仓库不包含任何第三方资源。** 扩展本身只有代码与自绘图标；预览台需要的 AIMS 样式表、CityU 校徽与 banner、Apple / Google 应用商店徽章等，由 `tools/preview/fetch_vendor.py` 按需从公开地址下载到本地（`tools/preview/vendor/` 已 gitignore，不入库）。这些资源的版权分别属于 City University of Hong Kong、Ellucian / SunGard 与 Apple / Google，本项目仅为本地开发调试而引用，不主张任何权利，也不再分发。
