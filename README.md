# 全球财经十图看板

静态看板，按发布日期保存不可变期次。打开页面只读取 `data/editions/<日期>.json`，不会在浏览时请求实时行情。第一期是 **2026-09-21**，覆盖 **2026-09-14 – 2026-09-20**。

图表使用 Chart.js 4.4.1。样式与第一期原文保持原样，日期选择是后来加上的。

## 本地运行

已有服务在 43123 时直接打开即可。否则在仓库根目录：

```bash
python3 -m http.server 43123 --bind 0.0.0.0
```

浏览器打开 http://127.0.0.1:43123/

不带 `?date=` 时显示 `data/index.json` 里的 `latest`。选择日期后地址变为 `?date=YYYY-MM-DD`，刷新和前进后退都认这个参数。资源路径都是相对的，挂在 `https://<user>.github.io/<repo>/` 下也能载入。

## 发布一期

手工期次是一份完整 JSON：十张卡片、十张图、核心观点、为什么重要、结尾、免责声明、来源链接。数字和句子都要属于这一期。缺字段、空正文、来源对不上，或图表数字与上一期完全相同，都只会写入 `data/drafts/<日期>.json`，不会改 `latest`。

```bash
python3 scripts/validate_edition.py incoming/2026-09-28.json
python3 scripts/new_edition.py --date 2026-09-28 --content incoming/2026-09-28.json --force
git add data/index.json data/editions && git commit -m "Publish edition 2026-09-28" && git push
```

`--force` 跳过 `config/update.json` 的周期。同一天再发布时，旧文件会先归档到 `data/editions/<日期>/revisions/`，再写入新文件，不会直接盖掉。校验失败或脚本中途出错时，`latest` 和上一份已发布文件保持不动。

检查已发布索引：

```bash
python3 scripts/validate_edition.py
```

## 配置更新

`config/update.json` 的 `cadence` 决定哪一天、哪个 UTC 小时才算到期。GitHub Actions 可以每天跑，未到期就直接跳过，除非手动勾选 force。

默认是每周一 06:00 UTC 之后。改 `frequency`（`weekly` 或 `daily`）、`weekday`、`hourUtc` 即可。

模型写稿是可选的。把 `analysis.enabled` 设为 `true`，并在仓库里配置：

- Secret `ANALYSIS_API_KEY`
- Variable 或 Secret `ANALYSIS_API_URL`

两个都没有时，唯一支持的路径就是上面的 `--content`。密钥只放在环境和 Actions Secrets 里，不要写进仓库。接口失败或某个字段没有值时，该字段标成 `missing`，带上来源 URL 和错误，草稿留下，不拿上一期的数字冒充新数据。

## 部署

`.github/workflows/pages.yml` 在推送到 `main` 时把仓库根目录部署到 GitHub Pages。`.github/workflows/update.yml` 每天检查一次，也支持手动指定日期。只有脚本打印 `STATUS=promoted` 时才会提交并部署。用默认 `GITHUB_TOKEN` 推上去不会再次触发 `pages.yml`，所以成功的更新在 `update.yml` 里自己部署。

仓库设置里把 Pages 的 Source 选成 GitHub Actions。需要先有一个 GitHub 仓库，并且本机 `gh auth` 能推送。本仓库当前的 remote 如果不是那个 GitHub 地址，不要假定页面已经上线。
