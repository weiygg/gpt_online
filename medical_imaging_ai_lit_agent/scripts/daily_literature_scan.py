#!/usr/bin/env python
"""Daily literature scan for medical imaging AI.

Uses only the Python standard library. It searches PubMed, arXiv, and Crossref,
deduplicates records, writes JSON, and renders a Feishu-friendly Markdown card.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


USER_AGENT = "medical-imaging-ai-lit-agent/0.1 (local research workflow)"
AI_TERMS = [
    "deep learning",
    "artificial intelligence",
    "machine learning",
    "foundation model",
    "vision transformer",
    "transformer",
    "self-supervised",
    "segmentation",
    "detection",
    "classification",
    "radiomics",
]
TRANSLATION_TERMS = [
    "external validation",
    "multi-center",
    "multicenter",
    "prospective",
    "clinical workflow",
    "real-world",
    "reader study",
    "decision support",
    "open source",
    "public dataset",
]


def today_iso() -> str:
    return dt.date.today().isoformat()


def http_json(url: str, sleep_seconds: float = 0.4, timeout: int = 15, retries: int = 4) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read().decode("utf-8", errors="replace")
            if sleep_seconds:
                time.sleep(sleep_seconds)
            return json.loads(data)
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise last_exc or RuntimeError("HTTP JSON request failed")


def http_text(url: str, sleep_seconds: float = 0.4, timeout: int = 15, retries: int = 4) -> str:
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read().decode("utf-8", errors="replace")
            if sleep_seconds:
                time.sleep(sleep_seconds)
            return data
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise last_exc or RuntimeError("HTTP text request failed")


def normalize_title(title: str) -> str:
    title = html.unescape(title or "")
    title = re.sub(r"\s+", " ", title).strip().lower()
    title = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", title)
    return title


def make_record_id(record: dict[str, Any]) -> str:
    key = record.get("doi") or record.get("pmid") or record.get("arxiv_id") or normalize_title(record.get("title", ""))
    return hashlib.sha1(str(key).lower().encode("utf-8")).hexdigest()[:12]


def safe_get_date(text: str) -> str:
    if not text:
        return ""
    m = re.search(r"(20\d{2}|19\d{2})(?:[-/ ](\d{1,2}))?(?:[-/ ](\d{1,2}))?", text)
    if not m:
        return text[:20]
    year = m.group(1)
    month = (m.group(2) or "01").zfill(2)
    day = (m.group(3) or "01").zfill(2)
    return f"{year}-{month}-{day}"


def extract_doi_from_pubmed(item: dict[str, Any]) -> str:
    for article_id in item.get("articleids", []):
        if article_id.get("idtype") == "doi":
            return article_id.get("value", "")
    text = " ".join(str(v) for v in item.values())
    m = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", text)
    return m.group(0).rstrip(".") if m else ""


def search_pubmed(topic: dict[str, Any], days_back: int, max_results: int, ncbi_email: str) -> list[dict[str, Any]]:
    query = topic.get("pubmed") or topic.get("query") or topic["name"]
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": str(max_results),
        "sort": "pub+date",
        "datetype": "pdat",
        "reldate": str(days_back),
    }
    if ncbi_email:
        params["email"] = ncbi_email
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode(params)
    try:
        search = http_json(url)
        ids = search.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        sum_params = {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "json",
        }
        if ncbi_email:
            sum_params["email"] = ncbi_email
        summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?" + urllib.parse.urlencode(sum_params)
        summary = http_json(summary_url)
    except Exception as exc:
        return [{"source": "PubMed", "topic": topic["name"], "error": str(exc)}]

    out = []
    for pmid in summary.get("result", {}).get("uids", []):
        item = summary["result"].get(pmid, {})
        authors = ", ".join(a.get("name", "") for a in item.get("authors", [])[:5])
        out.append(
            {
                "source": "PubMed",
                "topic": topic["name"],
                "title": item.get("title", "").rstrip("."),
                "authors": authors,
                "year": safe_get_date(item.get("pubdate", ""))[:4],
                "date": safe_get_date(item.get("pubdate", "")),
                "venue": item.get("source", ""),
                "doi": extract_doi_from_pubmed(item),
                "pmid": pmid,
                "arxiv_id": "",
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "abstract": "",
            }
        )
    return out


def search_arxiv(topic: dict[str, Any], days_back: int, max_results: int) -> list[dict[str, Any]]:
    query = topic.get("arxiv") or topic.get("query") or topic["name"]
    params = {
        "search_query": "all:" + query,
        "start": "0",
        "max_results": str(max_results),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
    min_date = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_back)
    try:
        text = http_text(url, sleep_seconds=1.1)
        root = ET.fromstring(text)
    except Exception as exc:
        return [{"source": "arXiv", "topic": topic["name"], "error": str(exc)}]

    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for entry in root.findall("a:entry", ns):
        published = entry.findtext("a:published", default="", namespaces=ns)
        try:
            pub_dt = dt.datetime.fromisoformat(published.replace("Z", "+00:00"))
            if pub_dt < min_date:
                continue
        except ValueError:
            pass
        url_text = entry.findtext("a:id", default="", namespaces=ns)
        arxiv_id = url_text.rsplit("/", 1)[-1]
        authors = ", ".join(a.findtext("a:name", default="", namespaces=ns) for a in entry.findall("a:author", ns)[:5])
        out.append(
            {
                "source": "arXiv",
                "topic": topic["name"],
                "title": re.sub(r"\s+", " ", entry.findtext("a:title", default="", namespaces=ns)).strip(),
                "authors": authors,
                "year": published[:4],
                "date": published[:10],
                "venue": "arXiv",
                "doi": "",
                "pmid": "",
                "arxiv_id": arxiv_id,
                "url": url_text,
                "abstract": re.sub(r"\s+", " ", entry.findtext("a:summary", default="", namespaces=ns)).strip(),
            }
        )
    return out


def search_crossref(topic: dict[str, Any], days_back: int, max_results: int) -> list[dict[str, Any]]:
    query = topic.get("crossref") or topic.get("query") or topic["name"]
    from_date = (dt.date.today() - dt.timedelta(days=days_back)).isoformat()
    params = {
        "query": query,
        "rows": str(max_results),
        "sort": "published",
        "order": "desc",
        "filter": f"from-pub-date:{from_date},type:journal-article",
        "select": "title,author,published-print,published-online,container-title,DOI,URL,abstract",
    }
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
    try:
        data = http_json(url, sleep_seconds=0.5, timeout=8)
    except Exception as exc:
        return [{"source": "Crossref", "topic": topic["name"], "error": str(exc)}]

    out = []
    for item in data.get("message", {}).get("items", []):
        title = " ".join(item.get("title", [])).strip()
        authors = []
        for a in item.get("author", [])[:5]:
            authors.append(" ".join(x for x in [a.get("given", ""), a.get("family", "")] if x))
        date_parts = (
            item.get("published-online", {}).get("date-parts")
            or item.get("published-print", {}).get("date-parts")
            or [[]]
        )[0]
        date = "-".join(str(x).zfill(2) for x in date_parts) if date_parts else ""
        out.append(
            {
                "source": "Crossref",
                "topic": topic["name"],
                "title": title,
                "authors": ", ".join(authors),
                "year": str(date_parts[0]) if date_parts else "",
                "date": date,
                "venue": " ".join(item.get("container-title", [])),
                "doi": item.get("DOI", ""),
                "pmid": "",
                "arxiv_id": "",
                "url": item.get("URL", ""),
                "abstract": re.sub("<[^>]+>", "", item.get("abstract", "") or ""),
            }
        )
    return out


def dedupe(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for rec in records:
        if rec.get("error"):
            key = "error:" + rec["source"] + ":" + rec["topic"] + ":" + rec["error"]
        else:
            key = (rec.get("doi") or rec.get("pmid") or rec.get("arxiv_id") or normalize_title(rec.get("title", ""))).lower()
        if key not in merged:
            merged[key] = rec
            merged[key]["sources"] = [rec["source"]]
        else:
            existing = merged[key]
            if rec["source"] not in existing["sources"]:
                existing["sources"].append(rec["source"])
            for field in ["doi", "pmid", "arxiv_id", "abstract", "venue", "authors", "date", "url"]:
                if not existing.get(field) and rec.get(field):
                    existing[field] = rec[field]
    for rec in merged.values():
        rec["id"] = make_record_id(rec)
    return list(merged.values())


def score_record(record: dict[str, Any], topic: dict[str, Any] | None = None) -> tuple[int, list[str], str]:
    text = (record.get("title", "") + " " + record.get("abstract", "")).lower()
    reasons = []
    score = 0
    for term in AI_TERMS:
        if term in text:
            score += 2
            reasons.append(term)
    for term in TRANSLATION_TERMS:
        if term in text:
            score += 3
            reasons.append(term)
    if topic:
        for term in topic.get("priority_keywords", []):
            if term.lower() in text:
                score += 2
                reasons.append(term)
    if record.get("doi") or record.get("pmid"):
        score += 1
    if record.get("source") == "arXiv":
        score += 1
    if "external validation" in reasons or "multi-center" in reasons or "multicenter" in reasons:
        landing = "高"
    elif score >= 8:
        landing = "中"
    else:
        landing = "待核查"
    return score, sorted(set(reasons))[:6], landing


def render_markdown(
    records: list[dict[str, Any]],
    topics: list[dict[str, Any]],
    days_back: int,
    max_items: int,
    enabled_sources: set[str],
) -> str:
    topic_map = {t["name"]: t for t in topics}
    usable = [r for r in records if not r.get("error") and r.get("title")]
    errors = [r for r in records if r.get("error")]
    for rec in usable:
        score, reasons, landing = score_record(rec, topic_map.get(rec.get("topic")))
        rec["score"] = score
        rec["reasons"] = reasons
        rec["landing_potential"] = landing
    usable.sort(key=lambda x: (x.get("score", 0), x.get("date", "")), reverse=True)
    top = usable[:max_items]

    source_labels = {"pubmed": "PubMed", "arxiv": "arXiv", "crossref": "Crossref"}
    source_text = "、".join(source_labels[s] for s in ["pubmed", "arxiv", "crossref"] if s in enabled_sources)
    lines = [
        f"# 医学影像 AI 每日文献卡 - {today_iso()}",
        "",
        f"检索范围：最近 {days_back} 天；来源：{source_text}；去重后 {len(usable)} 条。",
        "",
        "## 今日优先读",
        "",
    ]
    if not top:
        lines.append("今天没有检索到符合条件的新记录。建议放宽关键词或增加检索天数。")
    for i, rec in enumerate(top, 1):
        ident = rec.get("doi") or rec.get("pmid") or rec.get("arxiv_id") or "未解析"
        reasons = "、".join(rec.get("reasons") or ["主题相关"])
        sources = "/".join(rec.get("sources") or [rec.get("source", "")])
        lines.extend(
            [
                f"### {i}. {rec.get('title', '').strip()}",
                "",
                f"- 主题：{rec.get('topic', '')}",
                f"- 作者：{rec.get('authors', '') or '未解析'}",
                f"- 年份/期刊：{rec.get('year', '') or '未知'}；{rec.get('venue', '') or sources}",
                f"- 标识：{ident}",
                f"- 链接：{rec.get('url', '')}",
                f"- 为什么值得看：{reasons}",
                f"- 落地可能性初判：{rec.get('landing_potential', '待核查')}",
                "- 人工复核重点：样本量、数据来源、标签质量、是否外部验证、是否公开代码/模型、是否过度宣称临床价值。",
                "",
            ]
        )

    topic_counts: dict[str, int] = {}
    for rec in usable:
        topic_counts[rec.get("topic", "unknown")] = topic_counts.get(rec.get("topic", "unknown"), 0) + 1
    lines.extend(["## 热点观察", ""])
    if topic_counts:
        for topic, count in sorted(topic_counts.items(), key=lambda kv: kv[1], reverse=True):
            lines.append(f"- {topic}：{count} 条新记录")
    else:
        lines.append("- 暂无足够记录形成热点。")
    lines.extend(
        [
            "",
            "## 落地判断框架",
            "",
            "- A 类：有明确临床需求、可获得数据、外部验证空间，值得立刻立项。",
            "- B 类：方向有潜力，但需要先做 1 周证据评估或数据可得性核查。",
            "- C 类：概念热但落地弱，适合写综述、背景或基金立项依据。",
            "- D 类：暂不投入，证据弱、数据难、竞争过强或临床价值不清。",
            "",
            "## 下一步建议",
            "",
            "- 从今日优先读中选 1-2 篇下载 PDF 深读。",
            "- 用 `prompts/hotspot_feasibility_review.md` 让 Codex/ChatGPT 生成项目可行性评估。",
            "- 让 Claude Code 复核是否存在证据夸大、指标误读、预印本误当正式发表等问题。",
            "- 将最终判断写入 Hermes/Obsidian，保留“为什么继续/为什么放弃”。",
        ]
    )
    if errors:
        lines.extend(["", "## 检索异常", ""])
        for err in errors:
            lines.append(f"- {err.get('source')} / {err.get('topic')}：{err.get('error')}")
    return "\n".join(lines).strip() + "\n"


def send_feishu(markdown: str, chat_id: str, user_id: str, as_identity: str, dry_run: bool) -> None:
    target_arg = "--chat-id" if chat_id else "--user-id"
    target = chat_id or user_id
    if not target:
        raise ValueError("Feishu sending needs --chat-id or --user-id.")
    cmd = [
        "lark-cli",
        "im",
        "+messages-send",
        target_arg,
        target,
        "--markdown",
        markdown,
        "--as",
        as_identity,
        "--idempotency-key",
        "daily-lit-card-" + today_iso() + "-" + hashlib.sha1(target.encode("utf-8")).hexdigest()[:8],
    ]
    if dry_run:
        cmd.append("--dry-run")
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topics", required=True, help="Path to topics JSON.")
    parser.add_argument("--outdir", default="outputs", help="Output directory.")
    parser.add_argument("--days-back", type=int, default=None)
    parser.add_argument("--max-results-per-source", type=int, default=None)
    parser.add_argument("--max-card-items", type=int, default=8)
    parser.add_argument("--sources", default="pubmed", help="Comma-separated subset: pubmed,arxiv,crossref.")
    parser.add_argument("--send-feishu", action="store_true")
    parser.add_argument("--chat-id", default="")
    parser.add_argument("--user-id", default="")
    parser.add_argument("--as-identity", default="bot", choices=["bot", "user"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    topics_path = Path(args.topics)
    config = json.loads(topics_path.read_text(encoding="utf-8"))
    topics = config.get("topics", [])
    days_back = args.days_back or int(config.get("default_days_back", 7))
    max_results = args.max_results_per_source or int(config.get("default_max_results_per_source", 8))
    ncbi_email = os.environ.get("NCBI_EMAIL") or config.get("ncbi_email", "")
    sources = {s.strip().lower() for s in args.sources.split(",") if s.strip()}

    all_records: list[dict[str, Any]] = []
    for topic in topics:
        if "pubmed" in sources:
            all_records.extend(search_pubmed(topic, days_back, max_results, ncbi_email))
        if "arxiv" in sources:
            all_records.extend(search_arxiv(topic, days_back, max_results))
        if "crossref" in sources:
            all_records.extend(search_crossref(topic, days_back, max_results))

    records = dedupe(all_records)
    markdown = render_markdown(records, topics, days_back, args.max_card_items, sources)

    day_dir = Path(args.outdir) / today_iso()
    day_dir.mkdir(parents=True, exist_ok=True)
    (day_dir / "literature_hits.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    (day_dir / "daily_card.md").write_text(markdown, encoding="utf-8")
    print(f"Wrote {day_dir / 'literature_hits.json'}")
    print(f"Wrote {day_dir / 'daily_card.md'}")

    if args.send_feishu or args.dry_run:
        send_feishu(markdown, args.chat_id, args.user_id, args.as_identity, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
