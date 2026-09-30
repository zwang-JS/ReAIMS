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

## 开发与贡献

样式是怎么分层的、预览台怎么用、几项检查各自负责什么、以及已知限制，
都移到了 **[CONTRIBUTING.md](CONTRIBUTING.md)**。

## 许可

[MIT](LICENSE)

本项目与香港城市大学无隶属关系，为个人非官方项目。

**本仓库不包含任何第三方资源。** 扩展本身只有代码与自绘图标；预览台需要的 AIMS 样式表、CityU 校徽与 banner、Apple / Google 应用商店徽章等，由 `tools/preview/fetch_vendor.py` 按需从公开地址下载到本地（`tools/preview/vendor/` 已 gitignore，不入库）。这些资源的版权分别属于 City University of Hong Kong、Ellucian / SunGard 与 Apple / Google，本项目仅为本地开发调试而引用，不主张任何权利，也不再分发。
