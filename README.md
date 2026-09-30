# ReAIMS

为香港城市大学 **AIMS**（Ellucian/SunGard Banner 8.33 Self-Service，`banweb.cityu.edu.hk`）做的界面重构 Chrome 扩展。

把 2002 年风格的表格汤重构成一套现代、克制、深浅色可切换的界面。**只改样式，不改结构，不注入内容**，所以不会和 AIMS 自己的会话超时、提交防重等脚本打架。

浅色与深色（同一页，主菜单）：

![浅色模式](docs/preview-light.png)

![深色模式](docs/preview-dark.png)

数据表的处理是这套设计的着力点 —— 一张"表纸"、发丝行线、等宽数字对齐、嵌套表独立成块：

![数据表](docs/preview-tables.png)

## 安装

本扩展未上架 Chrome 应用商店，用开发者模式加载：

1. 克隆或下载本仓库
   ```bash
   git clone https://github.com/zwang-JS/ReAIMS.git
   ```
2. 打开 `chrome://extensions`
3. 右上角打开 **开发者模式**
4. 点 **加载已解压的扩展程序**，选择 `ReAIMS/` 目录
5. 打开 AIMS，界面即生效

没有构建步骤、没有 npm 依赖 —— 仓库里就是扩展本身。

## 功能

- **全站覆盖**：AIMS 的每一个子页面（个人资料、学生记录、选课、学生服务、成绩、课表…）共用同一套样式表，因此也共用同一套新样式，不需要逐页适配。
- **深浅色主题**：浅色 / 深色 / 跟随系统三选一。默认跟随系统，可跨设备同步。
- **三个切换入口**：扩展弹窗、页面右下角悬浮按钮、快捷键 `Alt`+`Shift`+`D`。
- **数据表重构**：圆角表纸 + 柔和阴影 + 发丝行线 + 悬停高亮 + 等宽数字对齐 + 表头吸顶。
- **打印友好**：深色模式下打印不会打出黑底。

## 工作原理

### 为什么每条规则都带 `!important`

这不是风格偏好，是**必需**的。

Chrome 会把 `content_scripts[].css` 在文档构建阶段注入，也就是**早于页面自己的 `<link>` 样式表**。同样特异性、同样重要性时，源顺序靠后者胜 —— 也就是说**每一场平局我们都输**。

好消息：AIMS 自己的样式表（`web_defaultapp.css`，53 KB / 332 条规则）里 `!important` 的数量是 **0**。所以只要我们的规则带 `!important`，就无条件胜出。

因此：

- `!important` 用在该用的地方 —— 属性表里凡是 AIMS 也声明过的（`color` / `background-*` / `border*` / `font-*` / `padding*` / `margin*` / `width` / `height` / `display` / `position` …）。
- **不加**在 AIMS 从未声明过的属性上（`border-radius` / `box-shadow` / `transition` / `gap` / `max-width` / `z-index` / `color-scheme`）。加了反而有害：会把同特异性冲突面翻倍，还会让这一层变得难以覆盖。
- **自定义属性（`--reaims-*`）一律不加 `!important`。** 优先级交给选择器就够：`html[data-reaims-theme="dark"]`（0,1,1）永远高于 `:root`（0,1,0），所以主题覆盖与文件顺序无关。

### 主题机制：靠 `color-scheme`，不靠两套令牌

`01-tokens.css` 用 CSS 的 `light-dark()` 把明暗两套值写在**同一行**：

```css
:root                        { color-scheme: light dark; }   /* 跟随系统 */
html[data-reaims-theme="light"] { color-scheme: light; }
html[data-reaims-theme="dark"]  { color-scheme: dark;  }

--reaims-bg: light-dark(#f6f5f7, #131216);
```

这一个选择带来三个好处：

1. **"跟随系统"不需要 JS**，也就不可能有闪烁。只有显式选了浅色/深色，`theme-boot.js` 才会写 `data-reaims-theme`。
2. **原生控件自动跟随** —— 滚动条、`<select>` 弹层、日期选择器、复选框都会变深色。漏掉 `color-scheme` 是深色主题最常见的硬伤。
3. **打印只需要一行**：`@media print { :root { color-scheme: light } }`。这一步不能省 —— `@media print` 下 `prefers-color-scheme` 依然会判定为深色，否则深色模式用户打印出来是整页黑底。

至于"避免闪烁"：`chrome.storage` 是异步的，等它 resolve 时第一帧早画完了。所以 `theme-boot.js` 在 `document_start` 从 **`localStorage` 镜像**同步读取用户的选择并立刻落属性；`chrome.storage.sync` 仍是跨设备的事实来源，镜像只是同步缓存。

### 表格：分两层，而不是一刀切

**AIMS 用同一套 `<table>` 标签做两件事**：页面外壳（标签条、标题块、页脚）和正文内容（成绩、课表、选课结果）。

对字面意义上所有表格加圆角边框和阴影，会把页面外壳切成一堆碎块。所以：

| 层 | 范围 | 效果 |
|---|---|---|
| 全局安全层 | 所有 `td` / `th` | 行高、文字色 |
| 数据表纸层 | `div.body` 内的表格 | 圆角、阴影、发丝线、斑马、悬停、吸顶、等宽数字 |

用 `div.body` 划界是刻意的 —— 它就是 AIMS「正文 / 外壳」的天然分界，一条选择器就能把外壳排除干净。这也顺带解决内边距问题：只有正文里的单元格会被加内边距，标题块和页脚不受影响。

### 两条不要违反的约束

写在 `02-base.css` 顶部，这里再强调一次，因为它们都属于"看起来很安全、实际会炸"的改动：

1. **不要给裸 `td` / `th` 设 `padding`。** AIMS 的 `.whitespace1-4` 是 `padding-top: 0/1/2/3em` 的纵向占位符，而**「重要性」高于「特异性」** —— 一条 `td { padding: 12px !important }` 会把页面上所有纵向留白压成 12px。
2. **不要用 `overflow: hidden` 给表格做圆角。** AIMS 的日历浮层是绝对定位在 `td` 内部的，会被裁掉，日期选择器直接消失。改用「给四角单元格单独设 `border-radius`」。

另外**不要给 `form` 设 `margin`**：AIMS 在标记里给工具栏和隐藏表单写了 `style="margin:0"`，行内样式敌不过 `!important`，一旦设置就会把那两处有意的归零推翻。

### 无障碍：这些是功能，不是样式

以下元素被 AIMS 有意隐藏，**任何规则都不得把它们露出来**：

- `span.fieldlabeltextinvisible` —— 给 `select` / `input` 挂的视觉隐藏标签，读屏软件靠它。`05-forms.css` 里有一条加固规则。
- `.skiplinks` —— "Skip Module Navigation Links" / "Skip to top of page"。它们在 AIMS 里一直是 `display: none`，本扩展刻意保持原状（改成"聚焦时出现"属于行为变更，不在"只改外观"的范围内）。
- `h1` 的字号 —— AIMS 的 `H1 { font-size: 0% }` 是有意把 h1 收起来（源码注释写着 "H1 is reserved for Page Header"），所以只归一化它的字体与颜色，不全局设字号。
- `div.header_inner h1` —— 靠 `position: relative; top: -137px` 顶进头部色带，动它就会错位。

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
    └── preview/                静态预览台（见下）
        ├── fetch_vendor.py     抓取第三方资源（vendor/ 不入库）
        ├── build_preview.py    由本地抓取的页面与内置样例合成
        ├── audit_overrides.py  覆盖完备性审计（含自检）
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

# 截图核对
"/c/Program Files/Google/Chrome/Application/chrome.exe" \
  --headless=new --disable-gpu --hide-scrollbars \
  --screenshot=tools/preview/out/light.png --window-size=1440,3000 \
  "file:///C:/Users/26229/OneDrive/Desktop/ReAIMS/tools/preview/preview.html?theme=light"
```

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

但它**不适合进公开仓库**：抓下来的页面里带着会话期标识。具体来说，AIMS 的会话保活脚本里有这样一段：

```
twbktmlb_cityu.P_Release_Timeout?in_pd=1627904&in_tm=…&in_ran=222415025121659092630
```

`in_pd`、`in_ran` 都是属于个人会话的值。所以 `source code.html` 已被移出版本控制并写入 `.gitignore`。

**要恢复 fixture 1**：自己登录 AIMS，把该页面的 HTML 另存为仓库根目录的 `source code.html`，再跑 `python tools/preview/build_preview.py`。缺这个文件时构建不会崩 —— 它会在 fixture 1 的位置放一个明确标注的占位块，并打印提示，其余四组样例照常生成。

顺带确认过一件事：`preview.html` 里**不含**这些会话标识（`in_pd` / `in_ran` 命中数为 0）。因为构建时会把 fixture 1 的两个 `<script>` 整块剥掉，而那几个值正好都在会话保活脚本里。

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

## 已知限制

- **不含登录页**。AIMS 走 SAML SSO 跳转到 Okta（`auth.cityu.edu.hk`），那是已现代化、基于 Shadow DOM、且全校共用的非 AIMS 页面，本扩展刻意不碰。
- **不能重构 DOM**。只改样式，所以无法把一个表格变成 CSS Grid，也无法移动元素位置。像"把页面标题和搜索框放进同一行"这类调整只能靠 flex 容器与 `order` 实现。
- **仅覆盖 `banweb.cityu.edu.hk`**。AIMS 跳转到其它域名的页面不在范围内。
- **用弹窗改主题后，下一次打开 AIMS 可能会有一次极短的闪烁**。因为页面侧的 `localStorage` 镜像只有在页面里跑过脚本才会更新，而 `theme-boot.js` 从镜像同步读取。只要那时有任一 AIMS 页面开着，镜像就会立即更新，不会闪。
- 表头吸顶（`position: sticky`）用的是 AIMS 的 `td.ddheader` 而非 `<thead>`，因为 Banner 不产生 `<thead>`。极长的多段表格里，多行表头会叠在同一位置。

## 许可

[MIT](LICENSE)

本项目与香港城市大学无隶属关系，为个人非官方项目。

**本仓库不包含任何第三方资源。** 扩展本身只有代码与自绘图标；预览台需要的 AIMS 样式表、CityU 校徽与 banner、Apple / Google 应用商店徽章等，由 `tools/preview/fetch_vendor.py` 按需从公开地址下载到本地（`tools/preview/vendor/` 已 gitignore，不入库）。这些资源的版权分别属于 City University of Hong Kong、Ellucian / SunGard 与 Apple / Google，本项目仅为本地开发调试而引用，不主张任何权利，也不再分发。
