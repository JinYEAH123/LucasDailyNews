# Lucas Daily News · Lucas 每日新闻

每天温哥华时间下午 5 点，从全球主流媒体里挑出**最重要的 3 条新闻**，
按 12 岁 G7 男孩能读懂、且愿意读下去的方式重写，并附上背景阅读、延展阅读和视频。

- **今日** — `docs/index.html`
- **往期** — `docs/archive.html`（按日期从新到旧）

---

## 它是怎么工作的

```
data/editions/YYYY-MM-DD.json   ← 每天一期的内容（唯一的事实来源）
        │
        │  scripts/render_site.py
        ▼
docs/                            ← 生成的静态网页，GitHub Pages 直接托管
├── index.html                   ← 最新一期
├── archive.html                 ← 往期列表
├── editions/YYYY-MM-DD.html     ← 每期的固定链接
└── index.json                   ← 机器可读的目录
```

每天下午 5 点，GitHub Actions 会：

1. 跑 `scripts/generate_edition.py` — Claude 用联网搜索通读过去 24 小时全球报道，
   选出 top 3，再改写成给 Lucas 读的版本，写进 `data/editions/`；
2. 跑 `scripts/render_site.py` — 重新生成 `docs/`；
3. 提交并推送。网页链接始终不变，内容自动滚动更新。

### 时间窗口

**每一期覆盖：前一天下午 5:00 → 当天下午 5:00（温哥华时间）。**

GitHub 的定时任务只认 UTC、不跟随夏令时，所以工作流在 `00:00` 和 `01:00` UTC
各触发一次，由任务自己核对温哥华当地时间，只有正好落在下午 5 点那一次才真正干活。
夏令时切换时不需要改任何配置。

### 选题规则

规则写在 `scripts/generate_edition.py` 的 `EDITORIAL_POLICY` 里，改那一段就能调整口味：

- 每天恰好 3 条，按重要性排序；
- 取自**政治 / 社会 / 财经 / 科技**四个板块，优先让 3 条分布在不同板块；
- 聚焦**中国**和**美国**；其他国家或其他板块，只有当事件大到足以在任何地方都上头条时才进入
  （重大战事进展、诺贝尔奖、大型灾害等）；
- 重要 ≠ 有戏剧性。看的是影响多少人、影响多久、是否改变了某种结构。明星八卦和血腥犯罪不进 top 3；
- 每条新闻的所有链接，必须是搜索结果里真实出现过的 URL——宁可留空，也不编造链接。

### 每条新闻包含什么

| 部分 | 说明 |
| --- | --- |
| 标题 + 导语 | 一眼看懂发生了什么，想读再往下点 |
| 为什么重要 | 和 Lucas 自己的生活连起来 |
| 读完整篇 | 4–6 段改写，术语第一次出现就解释，尽量用他能想象的比喻 |
| 值得记住的词 | 2–4 个关键词的简单定义 |
| 背景阅读 | 不了解来龙去脉的话从这里开始 |
| 延展阅读 | 基础清楚之后往深里走 |
| 看视频 | 搜索里真找到合适的 YouTube 才附上 |
| 饭桌上聊聊 | 3 个没有标准答案的问题 |

网页右上角可以在 **English / 中文** 之间切换，也可以切换浅色 / 深色。
英文是给 Lucas 读的，中文是给一起吃饭的家长读的。

---

## 首次设置

### 1. 打开网页托管

仓库 **Settings → Pages → Source: Deploy from a branch**，
分支选本分支（或合并后选 `main`），目录选 **`/docs`**。

保存后，网页地址是：

```
https://jinyeah123.github.io/LucasDailyNews/
```

### 2. 配置 API 密钥

自动生成需要一个 Anthropic API key（在 https://console.anthropic.com 创建）。

仓库 **Settings → Secrets and variables → Actions → New repository secret**：

- Name：`ANTHROPIC_API_KEY`
- Secret：你的密钥

没有这个 secret，网页照常显示已有内容，只是不会自动更新。

### 3. 配置邮件推送（可选）

每天 5 点生成完，会把当期作为 newsletter 发给你和你添加的邮箱。
不配置也不影响网页，发信步骤会自己跳过。

**先拿一个「应用专用密码」**——不要用邮箱的登录密码：

- Gmail：需要先开启两步验证，然后到 [应用专用密码](https://myaccount.google.com/apppasswords)
  生成一个 16 位密码。SMTP 主机 `smtp.gmail.com`，端口 `587`。
- Outlook / Hotmail：主机 `smtp-mail.outlook.com`，端口 `587`。
- iCloud：主机 `smtp.mail.me.com`，端口 `587`，同样需要 App 专用密码。

**再到 Settings → Secrets and variables → Actions 添加：**

| Secret | 值 |
| --- | --- |
| `SMTP_HOST` | 如 `smtp.gmail.com` |
| `SMTP_PORT` | `587`（若用 465 隐式 TLS 就填 `465`） |
| `SMTP_USER` | 你的完整邮箱地址 |
| `SMTP_PASSWORD` | 上一步的应用专用密码 |
| `SMTP_FROM` | 可选，默认等于 `SMTP_USER`。Gmail 会把不匹配的发件人改写掉，一般留空 |
| `NEWSLETTER_RECIPIENTS` | 收件人列表，见下 |

同一页的 **Variables** 标签里再加一个 `SITE_URL`，值是你的 GitHub Pages 地址
（邮件里「看两方的说法」等链接要用它）。不填会用默认值。

**收件人格式**，逗号或换行分隔，可以给每个人指定语言（`en` / `zh`，默认 `en`）：

```
lucas@example.com:en, mum@example.com:zh, grandpa@example.com:zh
```

**要增减读者，改这一个 secret 就行。** 收件人地址存在 secret 里而不是仓库文件里，
是为了不让邮箱地址进入 git 历史——仓库公开时这一点很要紧。

**关于邮件里的内容**：正文包含标题、导语、为什么重要、完整改写、生词、
背景与延展阅读、视频，以及「饭桌上聊聊」的三个问题。
**正反两方的提示不放进邮件**，只在邮件里给一个链接回网页——
邮件没法折叠，提示一旦印在问题旁边，Lucas 就会直接看答案，
独立思考那一层就没了。这也是发信需要 `SITE_URL` 的原因。

### 4. 试跑一次

**Actions → Daily edition → Run workflow**，可以手动填日期，也可以留空。
手动触发不受 5 点限制，随时可以跑。勾选 `skip_email` 可以只生成不发信。

---

## 本地使用

```bash
pip install anthropic

# 生成当前窗口这一期
python3 scripts/generate_edition.py

# 补一期历史，或重新生成某一天
python3 scripts/generate_edition.py --date 2026-08-16
python3 scripts/generate_edition.py --date 2026-08-17 --force

# 先看看效果，不写文件
python3 scripts/generate_edition.py --dry-run

# 重新生成网页（改了样式或模板之后跑这个）
python3 scripts/render_site.py

# 本地预览
python3 -m http.server -d docs 8000   # 然后打开 http://localhost:8000
```

邮件相关：

```bash
# 先看看邮件长什么样，不发出去
python3 scripts/send_newsletter.py --dry-run /tmp/mail.html --lang zh

# 只发给自己试一次（不写入已发送记录，可以反复试）
export SMTP_HOST=smtp.gmail.com SMTP_USER=you@gmail.com SMTP_PASSWORD=xxxx
python3 scripts/send_newsletter.py --to you@gmail.com --lang zh

# 正式发给整个列表
export NEWSLETTER_RECIPIENTS="lucas@x.com:en, mum@x.com:zh"
python3 scripts/send_newsletter.py

# 重发某一天（默认同一天不会发第二次）
python3 scripts/send_newsletter.py --date 2026-08-17 --force
```

`data/sent.json` 记录每期发出的时间和收件人数量，用来防止同一天重复发送。
里面不含任何邮箱地址。

手写或手改某一期，直接编辑 `data/editions/YYYY-MM-DD.json` 再跑 `render_site.py` 即可，
不需要调用 API。

### 成本

每期两次 Claude 调用（一次联网调研，一次改写），大约几毛到一块多美元，
一个月十几美元上下，取决于当天新闻的复杂程度。

---

## 目录结构

```
data/editions/          每期内容 JSON
data/sent.json          已发送记录（只有日期和人数，无邮箱地址）
scripts/
  generate_edition.py   调 Claude API 生成一期
  render_site.py        JSON → 静态网页
  send_newsletter.py    JSON → 邮件，经 SMTP 发出
  assets/               样式与脚本源文件（会被复制进 docs/assets）
docs/                   生成产物，GitHub Pages 托管
.github/workflows/
  daily-edition.yml     每天下午 5 点（温哥华）生成、渲染、发信
```

每天 5 点那一次跑的顺序是：**生成 → 渲染 → 发信 → 提交推送**。
发信排在提交之前，但即使发信失败，提交步骤照样执行——
一次邮件故障只会损失一封信，不会连当天的内容一起丢掉。
不过任务最后仍会标红，你能在 Actions 里看到。

`docs/` 是生成出来的，不要手改——改 `scripts/assets/` 或 JSON，然后重新渲染。
