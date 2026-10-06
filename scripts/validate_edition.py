#!/usr/bin/env python3
"""Validate one edition file and the published index."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TOOLTIP_IDS = {
    "c1PercentTrim",
    "yoyPlus",
    "qianren",
    "twoDecimals",
    "yield10y",
    "usdPerBarrel",
    "q3YoyPlus",
    "usdBillions",
    "datasetPct",
    "signedPct",
}
TICK_IDS = {"pct", "thousandsK", "usd", "usdB"}
DATE_RE_LEN = 10


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def is_date(value) -> bool:
    if not isinstance(value, str) or len(value) != DATE_RE_LEN:
        return False
    y, m, d = value.split("-") if value.count("-") == 2 else ("", "", "")
    return len(y) == 4 and y.isdigit() and len(m) == 2 and m.isdigit() and len(d) == 2 and d.isdigit()


def text_of(html) -> str:
    if not isinstance(html, str):
        return ""
    out = []
    skip = False
    for ch in html:
        if ch == "<":
            skip = True
            continue
        if ch == ">":
            skip = False
            continue
        if not skip:
            out.append(ch)
    return "".join(out).strip()


def inside_root(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT.resolve())
        return True
    except ValueError:
        return False


def collect_missing(node, errors: list[str], where: str = "$") -> None:
    if isinstance(node, dict):
        if node.get("status") == "missing":
            url = node.get("sourceUrl") or node.get("url")
            err = node.get("error")
            ident = node.get("id") or node.get("field") or where
            if not url or not err:
                errors.append(f"{where} status=missing 但缺少 sourceUrl 或 error")
            else:
                errors.append(f"{where} 缺数 {ident}：{err}（{url}）")
        for key, value in node.items():
            collect_missing(value, errors, f"{where}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            collect_missing(value, errors, f"{where}[{i}]")


def validate_edition_obj(edition, *, label: str = "edition") -> list[str]:
    errors: list[str] = []
    if not isinstance(edition, dict):
        return [f"{label} 不是对象"]

    for key in ("publishDate", "coverage", "title", "thesisHtml", "cards", "closing", "footer", "status"):
        if key not in edition:
            errors.append(f"{label} 缺少 {key}")

    if "publishDate" in edition and not is_date(edition.get("publishDate")):
        errors.append(f"{label} publishDate 不是 YYYY-MM-DD")

    coverage = edition.get("coverage")
    if not isinstance(coverage, dict) or not is_date(coverage.get("start")) or not is_date(coverage.get("end")):
        errors.append(f"{label} coverage.start/end 必须是 YYYY-MM-DD")
    elif coverage["start"] > coverage["end"]:
        errors.append(f"{label} coverage 起止颠倒")

    if not text_of(edition.get("thesisHtml")):
        errors.append(f"{label} thesis 为空")

    cards = edition.get("cards")
    if not isinstance(cards, list) or len(cards) != 10:
        errors.append(f"{label} 需要 10 张卡片，实际 {0 if not isinstance(cards, list) else len(cards)}")
        cards = []

    ids = []
    for i, card in enumerate(cards):
        prefix = f"{label} 卡片{i + 1}"
        if not isinstance(card, dict):
            errors.append(f"{prefix} 不是对象")
            continue
        if not text_of(card.get("titleHtml")):
            errors.append(f"{prefix} 标题为空")
        if not text_of(card.get("takeHtml")):
            errors.append(f"{prefix} 核心观点为空")
        if not text_of(card.get("whyHtml")):
            errors.append(f"{prefix} 为什么重要为空")
        primary = card.get("primary") if isinstance(card.get("primary"), dict) else {}
        href = primary.get("href")
        if not isinstance(href, str) or not href.startswith(("http://", "https://")):
            errors.append(f"{prefix} 缺少主来源链接")
        if not primary.get("target") or not primary.get("rel"):
            errors.append(f"{prefix} 主链接缺少 target 或 rel")
        cites = card.get("cites") if isinstance(card.get("cites"), list) else []
        for j, cite in enumerate(cites):
            if not isinstance(cite, dict) or not isinstance(cite.get("href"), str) or not cite["href"].startswith(("http://", "https://")):
                errors.append(f"{prefix} 第 {j + 1} 条其他出处链接无效")
        chart = card.get("chart")
        if not isinstance(chart, dict):
            errors.append(f"{prefix} 缺少图表")
            continue
        cid = chart.get("id")
        if not isinstance(cid, str) or not cid:
            errors.append(f"{prefix} 图表缺少 id")
        else:
            ids.append(cid)
        if chart.get("type") not in {"bar", "line"}:
            errors.append(f"{prefix} 图表 type 无效")
        labels = chart.get("labels")
        if not isinstance(labels, list) or not labels:
            errors.append(f"{prefix} 图表缺少 labels")
        datasets = chart.get("datasets")
        if not isinstance(datasets, list) or not datasets:
            errors.append(f"{prefix} 图表缺少 datasets")
        else:
            for di, ds in enumerate(datasets):
                data = ds.get("data") if isinstance(ds, dict) else None
                if not isinstance(data, list) or not data:
                    errors.append(f"{prefix} 数据集 {di + 1} 没有数据")
                    continue
                for value in data:
                    if isinstance(value, bool) or not isinstance(value, (int, float)):
                        errors.append(f"{prefix} 数据集 {di + 1} 含非数字")
                        break
        if chart.get("tooltipFormatter") not in TOOLTIP_IDS:
            errors.append(f"{prefix} tooltipFormatter 未知")
        if chart.get("tickFormatter") not in TICK_IDS:
            errors.append(f"{prefix} tickFormatter 未知")
        y = chart.get("y")
        if not isinstance(y, dict):
            errors.append(f"{prefix} 缺少坐标轴 y")
        else:
            for bound in ("min", "max"):
                if bound in y and (isinstance(y[bound], bool) or not isinstance(y[bound], (int, float))):
                    errors.append(f"{prefix} y.{bound} 不是数字")
        sources = card.get("sources") if isinstance(card.get("sources"), list) else []
        if not sources:
            errors.append(f"{prefix} 缺少可追溯 sources")
        for source in sources:
            if not isinstance(source, dict) or not source.get("url"):
                errors.append(f"{prefix} source 缺少 url")

    if len(ids) != len(set(ids)):
        errors.append(f"{label} 图表 id 重复")
    if len(cards) == 10 and len(ids) != 10:
        errors.append(f"{label} 图表不是 10 张")

    closing = edition.get("closing")
    if not isinstance(closing, dict) or not text_of(closing.get("html")):
        errors.append(f"{label} 结尾为空")
    footer = edition.get("footer")
    if not isinstance(footer, dict) or not text_of(footer.get("disclaimerHtml")):
        errors.append(f"{label} 免责声明为空")
    links = footer.get("links") if isinstance(footer, dict) else None
    if not isinstance(links, list) or not links:
        errors.append(f"{label} 页脚缺少来源链接")
    else:
        for j, link in enumerate(links):
            if not isinstance(link, dict) or not isinstance(link.get("href"), str) or not link["href"].startswith(("http://", "https://")):
                errors.append(f"{label} 页脚第 {j + 1} 条链接无效")

    collect_missing(edition, errors, label)
    return errors


def validate_index(root: Path | None = None) -> list[str]:
    root = root or ROOT
    errors: list[str] = []
    index_path = root / "data" / "index.json"
    if not index_path.is_file():
        return ["data/index.json 不存在"]
    try:
        index = load_json(index_path)
    except json.JSONDecodeError as exc:
        return [f"data/index.json 无法解析：{exc}"]
    editions = index.get("editions")
    if not isinstance(editions, list):
        return ["index.editions 不是数组"]
    dates = []
    for i, entry in enumerate(editions):
        prefix = f"index[{i}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} 不是对象")
            continue
        date = entry.get("date")
        rel = entry.get("file")
        if not is_date(date):
            errors.append(f"{prefix} date 无效")
        else:
            dates.append(date)
        if entry.get("status") != "published":
            errors.append(f"{prefix} 不是 published")
        if not isinstance(rel, str) or rel.startswith("/") or ".." in Path(rel).parts:
            errors.append(f"{prefix} file 必须是站内相对路径")
            continue
        path = (root / rel).resolve()
        if not inside_root(path):
            errors.append(f"{prefix} file 越出仓库")
            continue
        if not path.is_file():
            errors.append(f"{prefix} 指向的文件不存在：{rel}")
            continue
        try:
            edition = load_json(path)
        except json.JSONDecodeError as exc:
            errors.append(f"{rel} 无法解析：{exc}")
            continue
        if edition.get("publishDate") != date:
            errors.append(f"{rel} publishDate 与索引不一致")
        if edition.get("status") != "published":
            errors.append(f"{rel} status 不是 published")
        errors.extend(validate_edition_obj(edition, label=rel))
    latest = index.get("latest")
    if dates:
        if latest != sorted(dates)[-1]:
            errors.append(f"latest 应为 {sorted(dates)[-1]}，实际 {latest}")
    elif latest not in (None, ""):
        errors.append("没有已发布期次时 latest 应为空")
    published_files = sorted((root / "data" / "editions").glob("*.json"))
    indexed = {entry.get("file") for entry in editions if isinstance(entry, dict)}
    for path in published_files:
        rel = f"data/editions/{path.name}"
        if rel not in indexed:
            errors.append(f"{rel} 在磁盘上但未列入索引")
    return errors


def main(argv: list[str]) -> int:
    args = argv[1:]
    if not args:
        errors = validate_index()
    else:
        errors = []
        for raw in args:
            path = Path(raw)
            if not path.is_absolute():
                path = ROOT / path
            if not path.is_file():
                errors.append(f"找不到 {raw}")
                continue
            try:
                edition = load_json(path)
            except json.JSONDecodeError as exc:
                errors.append(f"{raw} 无法解析：{exc}")
                continue
            errors.extend(validate_edition_obj(edition, label=str(raw)))
        if any(a == "--index" for a in args) or not args:
            errors.extend(validate_index())
    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        print(f"STATUS=invalid count={len(errors)}", file=sys.stderr)
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
