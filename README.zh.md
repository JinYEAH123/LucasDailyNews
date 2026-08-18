# 少年每日新闻 · Daily News for Kids

**世界新闻，值得争一争。**

[English](README.md)

每天在你指定的时刻，它从全球主流媒体里挑出最重要的几条新闻，按你设定的孩子年龄改写，
然后发布成网页、邮件和一张可转发的长图。每条新闻末尾有三个饭桌问题——
以及每个问题**正反两方**的说法，折叠起来，让孩子先说自己的想法。

全部跑在 GitHub Actions 和 GitHub Pages 上。没有服务器、不用注册、中间没有任何第三方服务。
仓库和内容都是你自己的。

---

## 它每天产出什么

| | |
| --- | --- |
| **一个网页** | 当日新闻，加上每天的固定链接和往期存档；一或两种语言，浅色深色皆可 |
| **一封邮件** | 同一期内容发到你和你添加的邮箱，每个人收到自己那种语言 |
| **一张长图** | 适合发朋友圈的竖版 PNG，结尾是回到完整网页的二维码 |

每条新闻先给标题和简要概述；完整改写、值得记住的词、背景阅读、延展阅读、视频、
以及正反两方的提示，都点开才展示。

---

## 设置

几乎没有什么是可设置的。每天三条，取自政治、社会、财经、科技、科学，
以美国和中国为重心，外加大到不属于任何单一国家的事件——
这是编辑方针，对所有人都一样。板块、地区、条数都刻意不做成选项。

真正可设置的只有这些，都在一个 `config.toml` 里：

```toml
[child]
name = "Lucas"      # 可留空，页面上显示「为 ___ 而做」
age  = 12           # 5-18，决定页面默认打开哪个阅读难度

[edition]
languages = ["en", "zh"]

[schedule]
timezone = "America/Vancouver"    # 任意 IANA 时区
hour     = 17                     # 0-23，当地时间

[site]
url = "https://yourname.github.io/your-repo/"
```

三种写法：浏览器打开 **`docs/setup.html`**、运行 **`python3 scripts/setup.py`**，
或者直接改 **`config.example.toml`**。

## 三个阅读难度

每一期都会写三遍——**6–11 岁、12–15 岁、16 岁以上**——三个版本同在一个页面里。
切换只是改根元素上的一个属性，所以是瞬时的，离线也能用，不需要服务器。

不同难度之间变化的是：句子长短、一个事实需要多少铺垫、生词收几个、
饭桌问题有多难。**不变**的是讲哪几条新闻、以及它们可以有多严肃。
7 岁的孩子会读到用他能想象的距离来解释霍尔木兹海峡，
而不是被换成一条关于小狗的新闻。

`[child] age` 只决定页面默认打开哪一档。任何读者都可以用页面顶部的按钮切换，
选择会记在那台设备上。

## 第一次配置

### 1. 复制一份

Fork 这个仓库，或者用 **Use this template**。下面的操作都在你自己那份的 **Settings** 里。

### 2. 打开网页

**Settings → Pages → Deploy from a branch**，分支 `main`，目录 **`/docs`**。
地址会是 `https://<你的用户名>.github.io/<仓库名>/`。
把它填进 `config.toml` 的 `[site] url`——长图上的二维码指向那里。

### 3. 配置 API 密钥

在 <https://console.anthropic.com> 创建，然后
**Settings → Secrets and variables → Actions → New repository secret**：

| Secret | 值 |
| --- | --- |
| `ANTHROPIC_API_KEY` | 你的密钥 |

没有它网页照常显示已有内容，只是不再更新。

### 4. 邮件推送（可选）

先拿一个**应用专用密码**，不要用邮箱登录密码。
Gmail 需要先开启两步验证，然后到 <https://myaccount.google.com/apppasswords>。

| Secret | 值 |
| --- | --- |
| `SMTP_HOST` | `smtp.gmail.com` · `smtp-mail.outlook.com` · `smtp.mail.me.com` |
| `SMTP_PORT` | `587`，隐式 TLS 用 `465` |
| `SMTP_USER` | 你的完整邮箱地址 |
| `SMTP_PASSWORD` | 应用专用密码 |
| `SMTP_FROM` | 可选，默认等于 `SMTP_USER` |
| `NEWSLETTER_RECIPIENTS` | 见下 |

收件人用逗号分隔，可以逐人指定语言和阅读难度——
一个家里有两个不同年龄的孩子，靠的就是这个：

```
lucas@example.com:en:12-15, mia@example.com:en:6-11, mum@example.com:zh
```

增减读者就改这一个 secret。地址放在 secret 而不是仓库文件里是有意的——
公开仓库不该把家人的邮箱写进 git 历史。

### 5. 先跑一次

**Actions → Daily edition → Run workflow。** 手动触发不看时钟，
不用等到你设定的那个时刻。

---

## 每天是怎么跑的

```
config.toml
     │
     ▼
generate_edition.py   联网检索全球报道，把三条新闻和链接记录一次，
     │                然后逐个阅读难度改写
     ▼
data/editions/YYYY-MM-DD.json      ← 唯一的事实来源
     │
     ├── build_poster.py    → docs/posters/YYYY-MM-DD-<语言>.png
     ├── render_site.py     → docs/（当日页、固定链接、往期、设置表单）
     └── send_newsletter.py → 经 SMTP 发邮件
```

工作流**每小时**触发一次，由任务自己判断这是不是你设的那个钟点。
正因为如此，任意时区、任意时刻都能用，夏令时也不需要改任何配置。
它还能自愈：判断标准是「过了截止时刻，且今天这期还不存在」，
所以某一次运行被延迟或丢掉，下一个整点会把这一天补上，而不是整天丢失。

发信排在提交之前，但允许失败——提交步骤照样执行，
一次邮件故障只损失一封信，不会连当天的内容一起丢掉。任务最后仍会标红，你能看到。

---

## 编辑方针

规则以自然语言写在 `scripts/generate_edition.py` 的 `EDITORIAL_POLICY` 里，
改那段文字就能调整这份报纸的口味。要点：

- **重要 = 后果，不是戏剧性**——影响多少人、影响多久、是否改变了某种结构。
  明星八卦不是头条，血腥犯罪不是头条。
- **在排序允许时让新闻分布在不同板块**，但绝不为了凑板块而塞一条弱新闻。
- **每个 URL 必须在检索结果里真实出现过。** 禁止构造、猜测或「修复」链接；
  宁可留空也不编造。视频只有真搜到了才附上。
- **有争议的说法要标明有争议**，并给出两种读法。
- **每个问题的正反两方都要按最强的样子写**——不能一边两条好论据加一条准备被打倒的弱论据，
  也不能通过顺序、标签或用力程度暗示作者偏向哪一边。

有两个结构性的做法在支撑这些规则：检索和改写是分开的两次调用，
所以改写阶段只能用检索真正找到的链接；提示在网页上保持折叠、在邮件里干脆不放，
所以孩子总是先遇到问题，再遇到别人的答案。

---

## 本地运行

```bash
pip install anthropic segno playwright opencv-python-headless
playwright install chromium

python3 scripts/setup.py                    # 写 config.toml
python3 scripts/generate_edition.py         # 抓取并生成今天这期
python3 scripts/build_poster.py --both      # 长图
python3 scripts/render_site.py              # 生成 docs/
python3 -m http.server -d docs 8000         # 打开 localhost:8000 预览
```

常用参数：

```bash
python3 scripts/generate_edition.py --date 2026-08-16 --force
python3 scripts/generate_edition.py --dry-run
python3 scripts/render_site.py --single one-page.html
python3 scripts/send_newsletter.py --dry-run mail.html --lang zh
python3 scripts/send_newsletter.py --to you@example.com
python3 scripts/build_poster.py --keep-html
```

想手写或手改某一期，直接编辑 `data/editions/YYYY-MM-DD.json` 再跑 `render_site.py`，
不需要调用 API。

### 成本

每天五次 Claude 调用：一次联网调研，一次记录选中的新闻和链接，
三个阅读难度各一次。大约每天 2–3 美元，一个月 60–90 美元上下。
其中大部分成本来自写三个版本——只写一个难度大约是三分之一。

---

## 目录结构

```
config.toml               你的设置
config.example.toml       带注释的起点
data/editions/            每天一个 JSON，唯一的事实来源
data/sent.json            哪些天发过邮件（只有日期和人数，无邮箱地址）
scripts/
  appconfig.py            设置、板块与地区目录、三个年龄档
  setup.py                命令行设置向导
  setup_page.py           生成网页版设置表单
  generate_edition.py     Claude API → 当期 JSON（三个年龄版本）
  render_site.py          JSON → docs/
  build_poster.py         JSON → 带二维码的长图（二维码会自动校验）
  send_newsletter.py      JSON → 经 SMTP 发邮件
  assets/                 样式与切换脚本，会被复制进 docs/assets
docs/                     生成产物，GitHub Pages 托管
.github/workflows/        每小时触发的任务
```

`docs/` 是生成出来的——要改就改 `scripts/assets/` 或 JSON，然后重新渲染。

---

## 已知限制

- **请核对来源。** 链接规则让编造 URL 变得很不可能，但不是不可能：
  模型仍可能引用一个真实存在、内容却被它记错的页面。
  每条新闻都保留原始链接，正是为了这个。
- **加一个板块或一个年龄档**，只需要在 `scripts/appconfig.py` 的
  `CATEGORIES` 或 `AGE_BANDS` 里加一条。网页 CSS、年龄切换器、输出 schema、
  长图和邮件都是从这两张表生成的。
- **长图需要先填好 `[site] url`**，否则二维码指向空地址。
- 二维码每次生成后都会从成品 PNG 里重新解码校验，不一致就让任务失败。
  二维码坏掉在肉眼审阅时完全看不出来，所以必须校验而不是靠看。
