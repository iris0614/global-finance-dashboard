#!/usr/bin/env python3
"""Create one immutable edition. Published files change only after validation."""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from validate_edition import ROOT, is_date, load_json, validate_edition_obj, validate_index

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def read_config() -> dict:
    path = ROOT / "config" / "update.json"
    if not path.is_file():
        return {}
    return load_json(path)


def is_due(config: dict, now: datetime) -> bool:
    cadence = config.get("cadence") or {}
    frequency = str(cadence.get("frequency") or "weekly").lower()
    hour = cadence.get("hourUtc")
    if frequency == "daily":
        return True if hour is None else now.hour >= int(hour)
    if frequency == "weekly":
        weekday = str(cadence.get("weekday") or "monday").lower()
        if weekday not in WEEKDAYS:
            return False
        if WEEKDAYS[now.weekday()] != weekday:
            return False
        return True if hour is None else now.hour >= int(hour)
    return False


def emit(status: str, **fields: str) -> None:
    print(f"STATUS={status}")
    for key, value in fields.items():
        print(f"{key.upper()}={value}")


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def scrub(message: str, secret: str) -> str:
    if secret and secret in message:
        return message.replace(secret, "[redacted]")
    return message


def analysis_configured(config: dict) -> tuple[bool, str, str]:
    analysis = config.get("analysis") or {}
    url = os.environ.get("ANALYSIS_API_URL", "").strip()
    key = os.environ.get("ANALYSIS_API_KEY", "").strip()
    return bool(analysis.get("enabled")) and bool(url) and bool(key), url, key


def call_analysis(date: str, url: str, key: str):
    body = json.dumps({"date": date, "schema": "finance-dashboard-edition"}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        err = scrub(f"{type(exc).__name__}: {exc}", key)
        return {
            "publishDate": date,
            "status": "draft",
            "metrics": [{
                "id": "analysis",
                "value": None,
                "status": "missing",
                "sourceUrl": url,
                "error": err[:500],
            }],
        }, err
    if isinstance(payload, dict) and isinstance(payload.get("edition"), dict):
        payload = payload["edition"]
    if not isinstance(payload, dict):
        return {
            "publishDate": date,
            "status": "draft",
            "metrics": [{
                "id": "analysis",
                "value": None,
                "status": "missing",
                "sourceUrl": url,
                "error": "response was not an edition object",
            }],
        }, "response was not an edition object"
    return payload, None


def chart_numbers(edition: dict) -> list:
    rows = []
    for card in edition.get("cards") or []:
        chart = card.get("chart") if isinstance(card, dict) else None
        datasets = chart.get("datasets") if isinstance(chart, dict) else []
        rows.append([ds.get("data") if isinstance(ds, dict) else None for ds in datasets or []])
    return rows


def prose_changed(new: dict, prev: dict) -> bool:
    if new.get("thesisHtml") != prev.get("thesisHtml"):
        return True
    if (new.get("closing") or {}).get("html") != (prev.get("closing") or {}).get("html"):
        return True
    if (new.get("footer") or {}).get("disclaimerHtml") != (prev.get("footer") or {}).get("disclaimerHtml"):
        return True
    new_cards = new.get("cards") or []
    prev_cards = prev.get("cards") or []
    if len(new_cards) != len(prev_cards):
        return True
    for a, b in zip(new_cards, prev_cards):
        if a.get("takeHtml") != b.get("takeHtml") or a.get("whyHtml") != b.get("whyHtml"):
            return True
    return False


def narrative_errors(new: dict, prev: dict | None) -> list[str]:
    if not prev:
        return []
    errors = []
    new_cards = new.get("cards") if isinstance(new.get("cards"), list) else []
    prev_cards = prev.get("cards") if isinstance(prev.get("cards"), list) else []
    if len(new_cards) == 10 and len(prev_cards) == 10:
        same_numbers = True
        for index, (a, b) in enumerate(zip(new_cards, prev_cards)):
            ad = [ds.get("data") for ds in ((a.get("chart") or {}).get("datasets") or []) if isinstance(ds, dict)]
            bd = [ds.get("data") for ds in ((b.get("chart") or {}).get("datasets") or []) if isinstance(ds, dict)]
            if ad != bd:
                same_numbers = False
                if a.get("takeHtml") == b.get("takeHtml") and a.get("whyHtml") == b.get("whyHtml"):
                    cid = (a.get("chart") or {}).get("id") or index + 1
                    errors.append(f"{cid} 的数字变了，但核心观点和为什么重要仍是上一期原文")
        if same_numbers and new.get("publishDate") != prev.get("publishDate"):
            errors.append("图表数字与上一期完全相同，拒绝把旧数字当成新一期")
        if (
            same_numbers
            and new.get("publishDate") == prev.get("publishDate")
            and not prose_changed(new, prev)
            and chart_numbers(new) == chart_numbers(prev)
        ):
            errors.append("与当前已发布文件完全相同，拒绝静默覆盖")
    return errors


def load_previous(date: str) -> dict | None:
    final = ROOT / "data" / "editions" / f"{date}.json"
    if final.is_file():
        return load_json(final)
    index_path = ROOT / "data" / "index.json"
    if not index_path.is_file():
        return None
    index = load_json(index_path)
    latest = index.get("latest")
    if not latest:
        return None
    path = ROOT / "data" / "editions" / f"{latest}.json"
    if path.is_file():
        return load_json(path)
    return None


def write_draft(date: str, content, errors: list[str]) -> Path:
    if not isinstance(content, dict):
        content = {"publishDate": date, "unparsed": True}
    draft = dict(content)
    draft["status"] = "draft"
    draft["publishDate"] = draft.get("publishDate") or date
    draft["draftErrors"] = errors
    path = ROOT / "data" / "drafts" / f"{date}.json"
    atomic_write(path, dump(draft))
    return path


def promote(date: str, edition: dict) -> None:
    final = ROOT / "data" / "editions" / f"{date}.json"
    rev_dir = ROOT / "data" / "editions" / date / "revisions"
    previous = final.read_bytes() if final.is_file() else None
    archive = None
    if previous is not None:
        prev_obj = json.loads(previous.decode("utf-8"))
        rev_dir.mkdir(parents=True, exist_ok=True)
        existing = sorted(p for p in rev_dir.glob("r*.json") if p.is_file())
        revision = len(existing) + 1
        stamp = utcnow().strftime("%Y%m%dT%H%M%SZ")
        archive = rev_dir / f"r{revision}-{stamp}.json"
        atomic_write(archive, previous.decode("utf-8"))
        revisions = list(prev_obj.get("revisions") or [])
        revisions.append({
            "revision": revision,
            "archivedAt": utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "file": f"data/editions/{date}/revisions/{archive.name}",
        })
        edition["revisions"] = revisions
    else:
        edition.setdefault("revisions", [])
    edition["status"] = "published"
    edition["publishDate"] = date
    tmp = final.with_name(final.name + ".tmp")
    try:
        tmp.write_text(dump(edition), encoding="utf-8")
        written = load_json(tmp)
        errors = validate_edition_obj(written, label=final.name)
        if errors:
            raise RuntimeError("; ".join(errors))
        os.replace(tmp, final)
        update_index(date, written)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        if archive is not None and archive.exists():
            archive.unlink()
        if previous is None:
            if final.exists():
                final.unlink()
        else:
            if final.is_file() and final.read_bytes() != previous:
                restore = final.with_name(final.name + ".restore")
                restore.write_bytes(previous)
                os.replace(restore, final)
        raise


def update_index(date: str, edition: dict) -> None:
    index_path = ROOT / "data" / "index.json"
    original = index_path.read_bytes() if index_path.is_file() else None
    if original:
        index = json.loads(original.decode("utf-8"))
    else:
        index = {"latest": None, "editions": []}
    editions = [entry for entry in index.get("editions") or [] if entry.get("date") != date]
    editions.append({
        "date": date,
        "file": f"data/editions/{date}.json",
        "coverage": edition.get("coverage"),
        "status": "published",
    })
    editions.sort(key=lambda entry: entry["date"])
    index["editions"] = editions
    index["latest"] = editions[-1]["date"]
    tmp = index_path.with_name(index_path.name + ".tmp")
    try:
        tmp.write_text(dump(index), encoding="utf-8")
        os.replace(tmp, index_path)
        errors = validate_index(ROOT)
        if errors:
            raise RuntimeError("; ".join(errors))
    except Exception:
        if tmp.exists():
            tmp.unlink()
        if original is None:
            if index_path.exists():
                index_path.unlink()
        else:
            restore = index_path.with_name(index_path.name + ".restore")
            restore.write_bytes(original)
            os.replace(restore, index_path)
        raise


def finish_draft(date: str, content, errors: list[str]) -> int:
    path = write_draft(date, content, errors)
    print("未发布。已写入草稿，latest 未改。", file=sys.stderr)
    for err in errors:
        print(err, file=sys.stderr)
    emit("draft", date=date, file=str(path.relative_to(ROOT)))
    return 0


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="发布或草稿一份财经看板期次")
    parser.add_argument("--date", help="YYYY-MM-DD")
    parser.add_argument("--content", help="完整期次 JSON，例如 incoming/2026-09-28.json")
    parser.add_argument("--force", action="store_true", help="跳过周期检查")
    args = parser.parse_args(argv[1:])

    config = read_config()
    now = utcnow()
    if not args.force and not is_due(config, now):
        emit("skipped", reason="not due", weekday=WEEKDAYS[now.weekday()], hour=str(now.hour))
        print("未到 config/update.json 里的发布时间。加 --force 可跳过。", file=sys.stderr)
        return 0

    date = args.date or now.strftime("%Y-%m-%d")
    if not is_date(date):
        emit("error", reason="bad date")
        print("--date 必须是 YYYY-MM-DD", file=sys.stderr)
        return 1

    content = None
    if args.content:
        content_path = Path(args.content)
        if not content_path.is_absolute():
            content_path = ROOT / content_path
        if not content_path.is_file():
            emit("error", reason="missing content")
            print(f"找不到 {args.content}", file=sys.stderr)
            return 1
        try:
            content = load_json(content_path)
        except json.JSONDecodeError as exc:
            return finish_draft(date, {"sourceFile": args.content}, [f"内容不是合法 JSON：{exc}"])
        if not isinstance(content, dict):
            return finish_draft(date, {}, ["内容必须是 JSON 对象"])
    else:
        enabled, url, key = analysis_configured(config)
        if not enabled:
            emit(
                "skipped",
                reason="manual content required",
                date=date,
            )
            print(
                "没有 --content，且分析未启用或缺少 ANALYSIS_API_URL / ANALYSIS_API_KEY。不写已发布文件。",
                file=sys.stderr,
            )
            return 0
        content, err = call_analysis(date, url, key)
        if err:
            return finish_draft(date, content, [f"分析接口失败，相关字段标为 missing：{err}"])

    if content.get("publishDate") and content.get("publishDate") != date:
        return finish_draft(date, content, [f"文件里的 publishDate 是 {content.get('publishDate')}，与 --date {date} 不一致"])
    content["publishDate"] = date

    errors = validate_edition_obj(content, label=date)
    prev = None
    try:
        prev = load_previous(date)
    except json.JSONDecodeError as exc:
        errors.append(f"无法读取上一期：{exc}")
    errors.extend(narrative_errors(content, prev))
    if errors:
        return finish_draft(date, content, errors)

    index_before = (ROOT / "data" / "index.json").read_bytes() if (ROOT / "data" / "index.json").is_file() else None
    edition_before = None
    final = ROOT / "data" / "editions" / f"{date}.json"
    if final.is_file():
        edition_before = final.read_bytes()
    try:
        promote(date, content)
    except Exception as exc:
        if index_before is None:
            index_path = ROOT / "data" / "index.json"
            if index_path.exists():
                index_path.unlink()
        elif (ROOT / "data" / "index.json").read_bytes() != index_before:
            restore = ROOT / "data" / "index.json.restore"
            restore.write_bytes(index_before)
            os.replace(restore, ROOT / "data" / "index.json")
        if edition_before is None:
            if final.exists():
                final.unlink()
        elif final.is_file() and final.read_bytes() != edition_before:
            restore = final.with_name(final.name + ".restore")
            restore.write_bytes(edition_before)
            os.replace(restore, final)
        emit("error", reason="promote failed", date=date)
        print(scrub(str(exc), os.environ.get("ANALYSIS_API_KEY", "")), file=sys.stderr)
        return 1

    emit("promoted", date=date, file=f"data/editions/{date}.json")
    return 0


def main(argv: list[str]) -> int:
    try:
        return run(argv)
    except Exception as exc:
        emit("error", reason="crash")
        print(scrub(str(exc), os.environ.get("ANALYSIS_API_KEY", "")), file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
