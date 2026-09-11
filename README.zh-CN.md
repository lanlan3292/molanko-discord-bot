# Molanko Discord Bot

Molanko Discord Bot 是一个基于 Discord.py 构建的机器人 支持一些没用的功能

[English](./README.md)

## 使用

### 1. 拉取仓库

```bash
git clone --depth 1 --single-branch --branch main https://github.com/lanlan3292/molanko-discord-bot.git
cd molanko-discord-bot
mv cogs/screenshot_web.py cogs/screenshot_web.py.disabled
```

### 2. 安装库

```bash
python -m venv .venv
source .venv/bin/activate

python -m pip install -r requirements.txt

npm ci
# 如果存在一些问题你可以尝试 npm install 如果仍然存在一些问题请反馈
```

### 3. 配置 (必须)

将 `.env.example` 复制为 `discord_bot.env` 并填写你的Discord Token

```bash
cp .env.example discord_bot.env
# 然后编辑 discord_bot.env
```

* `TOKEN` — 你的 Discord 机器人令牌

### 4. Badge 命令（`/badge`）

**注意:** 这**不是** Molanko 生态的项目 也**不是**由 lanlan3292 控制的项目 可能会存在一些问题

如果您不需要可以执行一下命令然后直接跳到第5步

```bash
mv cogs/badge.py cogs/badge.py.disabled
```

`/badge` 命令在本地通过内置的 [Badgeworks](https://github.com/ArthurSimin/Badgeworks) 核心（`badgeworks/`，无需外部服务器或 API 密钥）生成 [Devins Badge](https://github.com/intergrav/devins-badges)，并以 PNG 附件和 SVG 源码形式发布。

徽章通过 Node.js（`scripts/badge.mjs`）渲染，因此需要安装 Node 依赖（已在第 2 步的 `npm ci` 中完成）。无需额外配置。

先填写两个必填文本字段，然后在 `icon` 中输入文字，即可搜索全部内置预设/Simple Icons。例如：

```text
/badge top_text:"Available on" bottom_text:"GitHub" icon:github
/badge top_text:"Built with" bottom_text:"Python" icon:python style:compact
/badge top_text:"Plain" bottom_text:"Text badge" logo_position:无
/badge top_text:"Powered by" bottom_text:"Font Awesome" fontawesome_icon:"fa-brands fa-discord"
/badge top_text:"From" bottom_text:"theSVG" thesvg_slug:docker
```

`icon` 使用本地内置图标列表。填写 `fontawesome_icon` 或 `thesvg_slug` 时会自动选择对应来源，无需同时设置 `icon_mode`。若设置了 `icon_mode`，它必须与唯一的来源字段匹配；互相冲突的来源字段会被拒绝。选择 `logo_position:无` 可生成不带图标的徽章。

### 5. 启动

```bash
python main.py
```
