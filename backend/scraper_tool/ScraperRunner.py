import os
import json
import sys
import uuid
import time
import signal
import random
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote_plus
from concurrent.futures import (
    ProcessPoolExecutor,
    wait,
    FIRST_COMPLETED,
    TimeoutError, 
)
from typing import Dict, Any, List, Optional

# Configuration
LOG = False
FILENAME = "outputData.json"
COMPETITORS = ["TopCon", "Zeiss", "Canon", "OptoVue", "Nidek"]
DEFAULT_SUBTASKS = ["News", "Jobs", "Patents"]
OVERLAP_DAYS = 3
MIN_PARSEABLE_DATES_FOR_DATA_CUTOFF = 1
SUBTASK_MAX_ATTEMPTS = 2
RETRY_BACKOFF_MIN_SECONDS = 0.8
RETRY_BACKOFF_MAX_SECONDS = 2.0
ARTIFACT_RETENTION_DAYS = 7
MAX_NEWS_ITEMS = 200
MAX_PATENTS_ITEMS = 200
MAX_JOBS_ITEMS = 200

# Ensure imports work in subprocesses regardless of CWD
BASE_DIR = Path(__file__).parent.resolve()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Always write output to the backend folder (one level up from scraper_tool)
OUTPUT_PATH = BASE_DIR.parent / FILENAME
PROGRESS_PATH = BASE_DIR.parent / "progress.json"
TIMINGS_PATH = BASE_DIR.parent / "timings.json"
CANCEL_PATH = BASE_DIR.parent / "cancel.json"

# Simple debug logger to a shared file for hang diagnosis
DEBUG_LOG_PATH = BASE_DIR.parent / "scraper_debug.log"
ARTIFACTS_DIR = BASE_DIR.parent / "artifacts"

BLOCKED_TEXT_MARKERS = ("access denied", "forbidden", "blocked")
CHALLENGE_TEXT_MARKERS = ("captcha", "verify you are human", "cloudflare")


def _probe_config(company: str, subtask: str) -> Dict[str, Any]:
    current_year = datetime.now(timezone.utc).year
    jobs_urls = {
        "TopCon": "https://www.linkedin.com/jobs/search/?f_C=65268002&geoId=92000000",
        "Zeiss": "https://www.linkedin.com/jobs/search/?currentJobId=4333549264&f_C=938659%2C6556%2C18251391%2C6555%2C9262284%2C5264505&geoId=92000000&origin=COMPANY_PAGE_JOBS_CLUSTER_EXPANSION&originToLandingJobPostings=4333549264%2C4317593522%2C4332994407%2C4333084561%2C4334255041%2C4318232664%2C4317582624%2C4337965940%2C4318245168",
        "Canon": "https://www.linkedin.com/jobs/search/?f_C=27157455&geoId=92000000",
        "OptoVue": "https://www.linkedin.com/jobs/search/?f_C=18006916&geoId=92000000",
        "Nidek": "https://www.linkedin.com/jobs/search/?f_C=81583865,1341117,84005,80954639,7798625&geoId=92000000",
    }
    if subtask == "News":
        news_urls = {
            "TopCon": "https://topconhealthcare.eu/en_UK/news",
            "Zeiss": "https://www.zeiss.com/meditec-ag/en/media-news/press-releases.html",
            "Canon": f"https://us.medical.canon/news/press-releases/{current_year}/",
            "OptoVue": "https://blog.visionix.com/en-us/visionix-news-blog",
            "Nidek": f"https://www.nidek-intl.com/news/?term={current_year}&cate=news",
        }
        roots = {
            "TopCon": [".c-card"],
            "Zeiss": ["a.article-teaser-item__content-link"],
            "Canon": ["div.col-sm-8:has(h2.header-link)", "h2.header-link a"],
            "OptoVue": [".blog__listing-item"],
            "Nidek": [".news_post"],
        }
        return {
            "url": news_urls.get(company, ""),
            "roots": roots.get(company, []),
            "empty_selectors": [],
            "empty_text": ["no results", "no articles found"],
        }
    if subtask == "Jobs":
        return {
            "url": jobs_urls.get(company, ""),
            "roots": [".base-search-card"],
            "empty_selectors": [".jobs-search-no-results-banner__image"],
            "empty_text": ["no matching jobs", "no jobs found"],
        }
    if subtask == "Patents":
        query = quote_plus(company)
        return {
            "url": f"https://patentscope.wipo.int/search/en/result.jsf?query={query}&perPage=100&sortBy=DP",
            "roots": [
                ".ps-patent-result--first-row",
                ".ps-search-result-item",
                "tr.ps-result",
                "a[href*='detail.jsf?docId=']",
            ],
            "empty_selectors": [".b-infobox__text", ".results-count"],
            "empty_text": ["0 results", "no results were found", "no match for"],
        }
    return {"url": "", "roots": [], "empty_selectors": [], "empty_text": []}


def _safe_selector_exists(page: Any, selector: str) -> bool:
    try:
        return page.locator(selector).count() > 0
    except Exception:
        return False


def _artifact_paths(run_id: Optional[str], company: str, subtask: str) -> Dict[str, Path]:
    rid = (run_id or os.environ.get("RUN_ID") or "no-run-id").strip() or "no-run-id"
    company_dir = ARTIFACTS_DIR / rid / company
    return {
        "dir": company_dir,
        "html": company_dir / f"{subtask}.html",
        "screenshot": company_dir / f"{subtask}_screenshot.png",
    }


def _save_page_evidence(run_id: Optional[str], company: str, subtask: str, page: Any, html: str) -> Dict[str, str]:
    out = _artifact_paths(run_id, company, subtask)
    try:
        out["dir"].mkdir(parents=True, exist_ok=True)
        with open(out["html"], "w", encoding="utf-8") as f:
            f.write(html or "")
        try:
            page.screenshot(path=str(out["screenshot"]), full_page=True)
        except Exception:
            pass
        return {
            "html": str(out["html"]),
            "screenshot": str(out["screenshot"]),
        }
    except Exception:
        return {}


def _classify_probe(run_id: Optional[str], company: str, subtask: str, force_capture: bool = False) -> Dict[str, Any]:
    cfg = _probe_config(company, subtask)
    url = cfg.get("url") or ""
    started = time.perf_counter()
    meta: Dict[str, Any] = {
        "url": url,
        "final_url": url,
        "classification": "error",
        "duration_ms": 0,
        "error": None,
        "evidence": {},
    }
    # TopCon has a custom browser lifecycle in scraper modules; avoid a pre-run Playwright probe.
    if company == "TopCon" and subtask in ("News", "Jobs") and not force_capture:
        meta["classification"] = "unknown"
        meta["duration_ms"] = int((time.perf_counter() - started) * 1000)
        return meta
    if not url:
        meta["duration_ms"] = int((time.perf_counter() - started) * 1000)
        return meta
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, timeout=60000)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York",
            )
            page = context.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            status_code = response.status if response else None
            final_url = page.url or url
            html = page.content() or ""
            body = html.lower()

            blocked_text = any(m in body for m in BLOCKED_TEXT_MARKERS)
            challenge_text = any(m in body for m in CHALLENGE_TEXT_MARKERS)
            root_found = any(_safe_selector_exists(page, s) for s in (cfg.get("roots") or []))
            empty_found = any(_safe_selector_exists(page, s) for s in (cfg.get("empty_selectors") or []))
            empty_found = empty_found or any(m in body for m in (cfg.get("empty_text") or []))
            has_content = len(" ".join((html or "").split())) > 200

            if status_code in (403, 429, 503) or blocked_text:
                cls = "blocked"
            elif challenge_text:
                cls = "challenge"
            elif empty_found and not challenge_text and not blocked_text:
                cls = "empty_valid"
            elif root_found:
                cls = "ok"
            elif has_content:
                cls = "selector_changed"
            else:
                cls = "selector_changed"

            meta["url"] = url
            meta["final_url"] = final_url
            meta["classification"] = cls
            if cls in ("blocked", "challenge", "selector_changed") or force_capture:
                meta["evidence"] = _save_page_evidence(run_id, company, subtask, page, html)
            context.close()
            browser.close()
    except Exception as e:
        cls = _status_from_error(e)
        if cls == "error" and any(x in str(e).lower() for x in CHALLENGE_TEXT_MARKERS):
            cls = "challenge"
        meta["classification"] = cls
        meta["error"] = str(e)
    meta["duration_ms"] = int((time.perf_counter() - started) * 1000)
    return meta


def _log_subtask_attempt(
    run_id: Optional[str],
    company: str,
    subtask: str,
    probe_meta: Dict[str, Any],
    classification: str,
    item_count: int,
    duration_ms: int,
    attempts: int,
    error_code: Optional[str] = None,
) -> None:
    _dbg(
        company,
        "subtask_attempt",
        {
            "runId": run_id,
            "company": company,
            "subtask": subtask,
            "url": probe_meta.get("url"),
            "final_url": probe_meta.get("final_url"),
            "classification": classification,
            "item_count": item_count,
            "duration_ms": duration_ms,
            "attempts": attempts,
            "error_code": error_code,
            "evidence": probe_meta.get("evidence", {}),
        },
    )

def _dbg(company: Optional[str], stage: str, extra: Optional[Dict[str, Any]] = None) -> None:
    try:
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "pid": os.getpid(),
            "company": company,
            "stage": stage,
        }
        if extra is not None:
            safe_extra = {}
            for k, v in extra.items():
                try:
                    json.dumps(v)
                    safe_extra[k] = v
                except TypeError:
                    safe_extra[k] = str(v)
            rec["extra"] = safe_extra
            
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _file_mtime_utc(path: Path) -> Optional[datetime]:
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        return None

def _normalize_url(u: Any) -> str:
    if not isinstance(u, str):
        return ""
    s = u.strip()
    if not s:
        return ""
    s = s.split("#", 1)[0].split("?", 1)[0]
    s = s.rstrip("/")
    return s.lower()

def _date_from_item(item: Any) -> Optional[datetime]:
    try:
        ds = item.get("Date")
        if not isinstance(ds, str) or not ds.strip():
            return None
        s = ds.strip()

        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass

        # date-only ISO prefix
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            try:
                dt = datetime.strptime(s[:10], "%Y-%m-%d")
                return dt.replace(tzinfo=timezone.utc)
            except Exception:
                pass

        for fmt in ("%d/%m/%Y", "%d.%m.%Y", "%b %d, %Y", "%B %d, %Y", "%Y/%m/%d"):
            try:
                dt = datetime.strptime(s, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
    except Exception:
        pass
    return None


def _load_existing_state() -> Dict[str, Any]:
    state: Dict[str, Any] = {
        "by_name": {},
        "meta": {},
    }
    existing_by_name: Dict[str, Dict[str, Any]] = {}
    try:
        if OUTPUT_PATH.exists():
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                old_data = json.load(f)
            state["meta"] = old_data.get("_meta", {}) if isinstance(old_data, dict) else {}
            for comp in old_data.get("Competitor", []):
                if isinstance(comp, dict) and "Name" in comp:
                    existing_by_name[str(comp["Name"])] = comp
    except Exception:
        existing_by_name = {}
        state["meta"] = {}
    state["by_name"] = existing_by_name
    return state


def _max_date(items: Any) -> Optional[datetime]:
    if not isinstance(items, list):
        return None
    best: Optional[datetime] = None
    for it in items:
        if not isinstance(it, dict):
            continue
        dt = _date_from_item(it)
        if dt is None:
            continue
        if best is None or dt > best:
            best = dt
    return best


def _dedupe_jobs_current(items: Any) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []
    out: List[Dict[str, Any]] = []
    seen: set = set()
    for it in items:
        if not isinstance(it, dict):
            continue
        key = _normalize_url(it.get("URL"))
        if not key:
            key = str(it.get("Job Title") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def _compute_since_by_company(
    existing_by_name: Dict[str, Dict[str, Any]],
    meta_last_run_at: Optional[str],
) -> Dict[str, Dict[str, Optional[str]]]:
    meta_dt: Optional[datetime] = None
    if isinstance(meta_last_run_at, str) and meta_last_run_at.strip():
        try:
            meta_dt = datetime.fromisoformat(meta_last_run_at.replace("Z", "+00:00"))
            if meta_dt.tzinfo is None:
                meta_dt = meta_dt.replace(tzinfo=timezone.utc)
        except Exception:
            meta_dt = None
    overlap_cutoff: Optional[datetime] = None
    if meta_dt is not None:
        overlap_cutoff = meta_dt - timedelta(days=OVERLAP_DAYS)

    out: Dict[str, Dict[str, Optional[str]]] = {}

    def _pick_cutoff(items: Any) -> Dict[str, Any]:
        total = len(items) if isinstance(items, list) else 0
        parseable = 0
        best: Optional[datetime] = None
        if isinstance(items, list):
            for it in items:
                if not isinstance(it, dict):
                    continue
                dt = _date_from_item(it)
                if dt is None:
                    continue
                parseable += 1
                if best is None or dt > best:
                    best = dt

        if best is not None and parseable >= MIN_PARSEABLE_DATES_FOR_DATA_CUTOFF:
            return {
                "cutoff": best.isoformat(),
                "type": "data|max_date",
                "parseable": parseable,
                "total": total,
            }
        if overlap_cutoff is not None:
            return {
                "cutoff": overlap_cutoff.isoformat(),
                "type": "meta|lastRunAt",
                "parseable": parseable,
                "total": total,
            }
        return {
            "cutoff": None,
            "type": "none",
            "parseable": parseable,
            "total": total,
        }

    for name in COMPETITORS:
        comp = existing_by_name.get(name, {})
        news_info = _pick_cutoff(comp.get("News", []) if isinstance(comp, dict) else [])
        patents_info = _pick_cutoff(comp.get("Patents", []) if isinstance(comp, dict) else [])

        _dbg(name, "cutoff_selected", {
            "source": "News",
            "cutoff_type": news_info["type"],
            "cutoff": news_info["cutoff"],
            "parseable": news_info["parseable"],
            "total": news_info["total"],
        })
        _dbg(name, "cutoff_selected", {
            "source": "Patents",
            "cutoff_type": patents_info["type"],
            "cutoff": patents_info["cutoff"],
            "parseable": patents_info["parseable"],
            "total": patents_info["total"],
        })

        out[name] = {
            "News": news_info["cutoff"],
            "Patents": patents_info["cutoff"],
        }
    return out

def _keys_for_item(item: Any) -> List[str]:
    if not isinstance(item, dict):
        return []
    keys: List[str] = []
    url = _normalize_url(item.get("URL"))
    title = str(item.get("Headline") or item.get("Title") or "").strip().lower()
    date = str(item.get("Date") or "").strip()
    if url:
        keys.append(f"url:{url}")
    keys.append(f"titledate:{title}|{date}")
    return [k for k in keys if k]

def _merge_items(old: List[Dict[str, Any]], new: List[Dict[str, Any]], keys_fn) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen: set = set()

    def add(it: Dict[str, Any]) -> None:
        keys = keys_fn(it) or []
        if any(k in seen for k in keys):
            return
        merged.append(it)
        for k in keys:
            seen.add(k)

    for it in (old or []):
        if isinstance(it, dict):
            add(it)
    for it in (new or []):
        if isinstance(it, dict):
            add(it)
    return merged


def _status_from_error(err: Exception) -> str:
    msg = str(err or "").lower()
    if any(x in msg for x in CHALLENGE_TEXT_MARKERS):
        return "challenge"
    if "selector_changed" in msg or "selector" in msg or "locator" in msg:
        return "selector_changed"
    blocked_markers = (
        "blocked",
        "captcha",
        "challenge",
        "access denied",
        "forbidden",
        "429",
        "403",
    )
    if any(x in msg for x in blocked_markers):
        return "blocked"
    return "error"


def _error_code_from_error(err: Exception) -> str:
    msg = str(err or "").lower()
    if any(x in msg for x in CHALLENGE_TEXT_MARKERS):
        return "CHALLENGE"
    if any(x in msg for x in ("blocked", "access denied", "forbidden", "403", "429", "503")):
        return "BLOCKED"
    if any(x in msg for x in ("timeout", "timed out", "navigation", "net::", "connection", "dns", "econnreset")):
        return "NAV_TIMEOUT"
    if any(x in msg for x in ("selector", "locator", "not found", "no node", "strict mode violation")):
        return "SELECTOR_CHANGED"
    if any(x in msg for x in ("parse", "invalid date", "keyerror", "indexerror", "valueerror", "typeerror")):
        return "PARSER_ERROR"
    return "UNKNOWN_ERROR"


def _should_retry(error_code: str) -> bool:
    return error_code in ("NAV_TIMEOUT", "PARSER_ERROR", "UNKNOWN_ERROR")


def _run_with_retry(company: str, subtask: str, fn):
    last_err: Optional[Exception] = None
    attempts = max(1, int(SUBTASK_MAX_ATTEMPTS))
    for attempt in range(1, attempts + 1):
        try:
            res = fn()
            return res, attempt
        except Exception as e:
            last_err = e
            code = _error_code_from_error(e)
            _dbg(company, "subtask_attempt_error", {
                "subtask": subtask,
                "attempt": attempt,
                "max_attempts": attempts,
                "error": str(e),
                "error_code": code,
            })
            if attempt >= attempts or not _should_retry(code):
                raise
            delay = random.uniform(RETRY_BACKOFF_MIN_SECONDS, RETRY_BACKOFF_MAX_SECONDS)
            _dbg(company, "subtask_retry", {
                "subtask": subtask,
                "attempt": attempt + 1,
                "max_attempts": attempts,
                "backoff_s": round(delay, 3),
                "prev_error_code": code,
            })
            time.sleep(delay)
    if last_err:
        raise last_err
    return fn(), 1


def _cleanup_old_artifacts(current_run_id: Optional[str] = None) -> None:
    try:
        if not ARTIFACTS_DIR.exists():
            return
        cutoff_ts = time.time() - (ARTIFACT_RETENTION_DAYS * 24 * 60 * 60)
        removed = 0
        skipped = 0
        skipped_current_run = 0
        keep_run_id = str(current_run_id or "").strip()
        for child in ARTIFACTS_DIR.iterdir():
            if not child.is_dir():
                continue
            if keep_run_id and child.name == keep_run_id:
                skipped_current_run += 1
                continue
            try:
                if child.stat().st_mtime < cutoff_ts:
                    shutil.rmtree(child, ignore_errors=True)
                    removed += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1
        _dbg(None, "artifacts_cleanup", {
            "retention_days": ARTIFACT_RETENTION_DAYS,
            "removed_dirs": removed,
            "kept_dirs": skipped,
            "skipped_current_run": skipped_current_run,
            "current_run_id": keep_run_id or None,
            "base_dir": str(ARTIFACTS_DIR),
        })
    except Exception as e:
        _dbg(None, "artifacts_cleanup_error", {"error": str(e)})


def _is_valid_news_item(it: Any) -> bool:
    headline = str(it.get("Headline") or it.get("Title") or "").strip() if isinstance(it, dict) else ""
    return (
        isinstance(it, dict)
        and isinstance(it.get("URL"), str)
        and bool(it.get("URL", "").strip())
        and bool(headline)
    )


def _is_valid_patent_item(it: Any) -> bool:
    return (
        isinstance(it, dict)
        and isinstance(it.get("Title"), str)
        and bool(it.get("Title", "").strip())
        and isinstance(it.get("URL"), str)
        and bool(it.get("URL", "").strip())
    )


def _is_valid_job_item(it: Any) -> bool:
    return (
        isinstance(it, dict)
        and isinstance(it.get("Job Title"), str)
        and bool(it.get("Job Title", "").strip())
        and isinstance(it.get("URL"), str)
        and bool(it.get("URL", "").strip())
    )


def _subtask_from_payload(payload: Any, key: str) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    v = payload.get(key)
    if not isinstance(v, list):
        return []
    return [x for x in v if isinstance(x, dict)]

def _scrape_one(
    comp_name: str,
    log: bool = False,
    since_news_iso: Optional[str] = None,
    since_patents_iso: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Worker executed in a separate process.
    CRITICAL FIX: Imports are done LAZILY and SERIALLY to prevent Playwright race conditions.
    """
    since_news_dt: Optional[datetime] = None
    since_patents_dt: Optional[datetime] = None
    try:
        if since_news_iso:
            since_news_dt = datetime.fromisoformat(since_news_iso)
    except Exception:
        since_news_dt = None
    try:
        if since_patents_iso:
            since_patents_dt = datetime.fromisoformat(since_patents_iso)
    except Exception:
        since_patents_dt = None
    
    result: Dict[str, Any] = {
        "Name": comp_name,
        "News": [],
        "Jobs": [],
        "Patents": [],
    }
    subtask_results: Dict[str, Dict[str, Any]] = {
        "News": {"status": "error", "items": [], "error": "not-run"},
        "Jobs": {"status": "error", "items": [], "error": "not-run"},
        "Patents": {"status": "error", "items": [], "error": "not-run"},
    }
    _dbg(comp_name, "start")

    news_ms: int = 0
    jobs_ms: int = 0
    patents_ms: int = 0

    # CRITICAL: Import the company module ONLY ONCE at the start
    # This ensures Playwright is initialized before we start making calls
    try:
        _dbg(comp_name, "importing_module")
        if comp_name == "TopCon":
            import TopConScraper as Mod
        elif comp_name == "Zeiss":
            import ZeissScraper as Mod
        elif comp_name == "Canon":
            import CanonScraper as Mod
        elif comp_name == "OptoVue":
            import OptoVueScraper as Mod
        elif comp_name == "Nidek":
            import NidekScraper as Mod
        else:
            return result
        _dbg(comp_name, "module_imported")
    except Exception as e:
        _dbg(comp_name, "import_error", {"error": str(e)})
        subtask_results["News"] = {"status": "error", "items": [], "error": str(e), "error_code": "UNKNOWN_ERROR"}
        subtask_results["Jobs"] = {"status": "error", "items": [], "error": str(e), "error_code": "UNKNOWN_ERROR"}
        subtask_results["Patents"] = {"status": "error", "items": [], "error": str(e), "error_code": "UNKNOWN_ERROR"}
        result["_subtasks"] = subtask_results
        result["_all_subtasks_failed"] = True
        return result

    # 1. Run News
    _t0 = time.perf_counter()
    news_probe = _classify_probe(run_id, comp_name, "News")
    news_attempts = 1
    try:
        _dbg(comp_name, "news_start")
        payload, news_attempts = _run_with_retry(comp_name, "News", lambda: Mod.runNews(log, since_news_dt))
        result["News"] = _subtask_from_payload(payload, "News")
        news_status = "ok"
        if not result["News"]:
            if news_probe.get("classification") == "empty_valid":
                news_status = "empty_valid"
            else:
                news_status = "selector_changed"
                if not news_probe.get("evidence"):
                    news_probe = _classify_probe(run_id, comp_name, "News", force_capture=True)
        subtask_results["News"] = {
            "status": news_status,
            "items": result["News"],
            "url": news_probe.get("url"),
            "final_url": news_probe.get("final_url"),
            "evidence": news_probe.get("evidence", {}),
        }
        if news_status == "selector_changed":
            subtask_results["News"]["error"] = "No items extracted; probable selector drift"
            subtask_results["News"]["error_code"] = "SELECTOR_CHANGED"
        news_ms = int((time.perf_counter() - _t0) * 1000)
        _log_subtask_attempt(run_id, comp_name, "News", news_probe, news_status, len(result["News"]), news_ms, news_attempts)
        _dbg(
            comp_name,
            "news_done",
            {"items": len(result["News"]) if isinstance(result["News"], list) else 0, "ms": news_ms},
        )
    except Exception as e:
        news_ms = int((time.perf_counter() - _t0) * 1000) if "_t0" in locals() else 0
        _dbg(comp_name, "news_error", {"error": str(e), "ms": news_ms})
        result["News"] = []
        status = _status_from_error(e)
        error_code = _error_code_from_error(e)
        if status in ("blocked", "challenge", "selector_changed") and not news_probe.get("evidence"):
            news_probe = _classify_probe(run_id, comp_name, "News", force_capture=True)
        subtask_results["News"] = {
            "status": status,
            "items": [],
            "error": str(e),
            "error_code": error_code,
            "url": news_probe.get("url"),
            "final_url": news_probe.get("final_url"),
            "evidence": news_probe.get("evidence", {}),
        }
        _log_subtask_attempt(run_id, comp_name, "News", news_probe, status, 0, news_ms, news_attempts, error_code)

    # 2. Run Jobs
    _t0 = time.perf_counter()
    jobs_probe = _classify_probe(run_id, comp_name, "Jobs")
    jobs_attempts = 1
    try:
        _dbg(comp_name, "jobs_start")
        payload, jobs_attempts = _run_with_retry(comp_name, "Jobs", lambda: Mod.runJobs(log, since_news_dt))
        result["Jobs"] = _subtask_from_payload(payload, "Jobs")
        jobs_status = "ok"
        if not result["Jobs"]:
            if jobs_probe.get("classification") == "empty_valid":
                jobs_status = "empty_valid"
            else:
                jobs_status = "selector_changed"
                if not jobs_probe.get("evidence"):
                    jobs_probe = _classify_probe(run_id, comp_name, "Jobs", force_capture=True)
        subtask_results["Jobs"] = {
            "status": jobs_status,
            "items": result["Jobs"],
            "url": jobs_probe.get("url"),
            "final_url": jobs_probe.get("final_url"),
            "evidence": jobs_probe.get("evidence", {}),
        }
        if jobs_status == "selector_changed":
            subtask_results["Jobs"]["error"] = "No items extracted; probable selector drift"
            subtask_results["Jobs"]["error_code"] = "SELECTOR_CHANGED"
        jobs_ms = int((time.perf_counter() - _t0) * 1000)
        _log_subtask_attempt(run_id, comp_name, "Jobs", jobs_probe, jobs_status, len(result["Jobs"]), jobs_ms, jobs_attempts)
        _dbg(
            comp_name,
            "jobs_done",
            {"items": len(result["Jobs"]) if isinstance(result["Jobs"], list) else 0, "ms": jobs_ms},
        )
    except Exception as e:
        jobs_ms = int((time.perf_counter() - _t0) * 1000) if "_t0" in locals() else 0
        _dbg(comp_name, "jobs_error", {"error": str(e), "ms": jobs_ms})
        result["Jobs"] = []
        status = _status_from_error(e)
        error_code = _error_code_from_error(e)
        if status in ("blocked", "challenge", "selector_changed") and not jobs_probe.get("evidence"):
            jobs_probe = _classify_probe(run_id, comp_name, "Jobs", force_capture=True)
        subtask_results["Jobs"] = {
            "status": status,
            "items": [],
            "error": str(e),
            "error_code": error_code,
            "url": jobs_probe.get("url"),
            "final_url": jobs_probe.get("final_url"),
            "evidence": jobs_probe.get("evidence", {}),
        }
        _log_subtask_attempt(run_id, comp_name, "Jobs", jobs_probe, status, 0, jobs_ms, jobs_attempts, error_code)

    # 3. Run Patents
    _t0 = time.perf_counter()
    patents_probe = _classify_probe(run_id, comp_name, "Patents")
    patents_attempts = 1
    try:
        _dbg(comp_name, "patents_start")
        
        # Import PatentScraper HERE, after Playwright has been initialized by the company scraper
        import PatentScraper

        payload, patents_attempts = _run_with_retry(comp_name, "Patents", lambda: PatentScraper.runPatent(comp_name, since_patents_dt))
        result["Patents"] = _subtask_from_payload(payload, "Patents")
        patents_status = "ok"
        if not result["Patents"]:
            if patents_probe.get("classification") == "empty_valid":
                patents_status = "empty_valid"
            else:
                patents_status = "selector_changed"
                if not patents_probe.get("evidence"):
                    patents_probe = _classify_probe(run_id, comp_name, "Patents", force_capture=True)
        subtask_results["Patents"] = {
            "status": patents_status,
            "items": result["Patents"],
            "url": patents_probe.get("url"),
            "final_url": patents_probe.get("final_url"),
            "evidence": patents_probe.get("evidence", {}),
        }
        if patents_status == "selector_changed":
            subtask_results["Patents"]["error"] = "No items extracted; probable selector drift"
            subtask_results["Patents"]["error_code"] = "SELECTOR_CHANGED"
        patents_ms = int((time.perf_counter() - _t0) * 1000)
        _log_subtask_attempt(run_id, comp_name, "Patents", patents_probe, patents_status, len(result["Patents"]), patents_ms, patents_attempts)
        _dbg(
            comp_name,
            "patents_done",
            {"items": len(result["Patents"]) if isinstance(result["Patents"], list) else 0, "ms": patents_ms},
        )
    except Exception as e:
        patents_ms = int((time.perf_counter() - _t0) * 1000) if "_t0" in locals() else 0
        _dbg(comp_name, "patents_error", {"error": str(e), "ms": patents_ms})
        result["Patents"] = []
        status = _status_from_error(e)
        error_code = _error_code_from_error(e)
        if status in ("blocked", "challenge", "selector_changed") and not patents_probe.get("evidence"):
            patents_probe = _classify_probe(run_id, comp_name, "Patents", force_capture=True)
        subtask_results["Patents"] = {
            "status": status,
            "items": [],
            "error": str(e),
            "error_code": error_code,
            "url": patents_probe.get("url"),
            "final_url": patents_probe.get("final_url"),
            "evidence": patents_probe.get("evidence", {}),
        }
        _log_subtask_attempt(run_id, comp_name, "Patents", patents_probe, status, 0, patents_ms, patents_attempts, error_code)
    
    result["_timings"] = {
        "NewsMs": news_ms,
        "JobsMs": jobs_ms,
        "PatentsMs": patents_ms,
    }
    result["_subtasks"] = subtask_results
    failed = sum(1 for st in subtask_results.values() if st.get("status") in ("error", "blocked", "challenge", "selector_changed"))
    result["_failed_subtasks"] = failed
    result["_all_subtasks_failed"] = failed == len(DEFAULT_SUBTASKS)
    
    _dbg(comp_name, "complete", {"total_ms": news_ms + jobs_ms + patents_ms})
    return result


class ProgressReporter:
    # ... (This entire class is unchanged. It's fine.) ...
    DEFAULT_PER_COMPANY_MS = 20000
    ALPHA = 0.3

    def __init__(
        self,
        run_id: Optional[str],
        companies: List[str],
        subtasks: Optional[List[str]] = None,
    ) -> None:
        self.run_id = run_id or os.environ.get("RUN_ID") or str(uuid.uuid4())
        self._companies = list(companies)
        self._subtasks = list(subtasks or DEFAULT_SUBTASKS)
        self._progress_path = PROGRESS_PATH
        self._timings_path = TIMINGS_PATH
        self._cancel_path = CANCEL_PATH
        self._t0_real: Optional[datetime] = None
        self._t0_monotonic: Optional[float] = None
        self._company_start_monotonic: Dict[str, float] = {}
        self._v = 0
        self._timings = self._load_timings()
        per_company: Dict[str, Any] = {}
        for name in self._companies:
            per_company[name] = {
                "state": "queued",
                "elapsedMs": 0,
                "etaMs": None,
                "subtasks": [
                    {
                        "name": st,
                        "state": "queued",
                        "elapsedMs": 0,
                        "etaMs": None,
                        "items": 0,
                        "errors": 0,
                    }
                    for st in self._subtasks
                ],
            }

        self._snapshot: Dict[str, Any] = {
            "runId": self.run_id,
            "startedAt": None,
            "updatedAt": self.now_iso(),
            "v": self._v,
            "elapsedMs": 0,
            "etaMs": None,
            "status": "running",
            "overall": {
                "total": len(self._companies),
                "done": 0,
                "percent": 0,
            },
            "current": {
                "company": None,
                "subtask": None,
                "stepIndex": 0,
                "stepCount": len(self._companies),
            },
            "perCompany": per_company,
            "pid": None,
            "logTail": [],
            "summary": {
                "totalItems": 0,
                "totalErrors": 0,
                "finishedAt": None,
                "totalDurationMs": None,
            },
        }

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _elapsed_ms_from_start(self) -> int:
        if self._t0_monotonic is None:
            return 0
        return max(0, int((time.perf_counter() - self._t0_monotonic) * 1000))

    @staticmethod
    def _safe_default(o: Any) -> str:
        try:
            return str(o)
        except Exception:
            return "<non-serializable>"

    def _atomic_write_json(self, path: Path, data: Any) -> None:
        unique_tmp = f"{path.name}.{os.getpid()}.{int(time.time() * 1000)}.tmp"
        tmp = path.with_name(unique_tmp)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, default=self._safe_default)
                try:
                    f.flush()
                    os.fsync(f.fileno())
                except Exception:
                    pass
            retries = 20
            delay = 0.05
            for _ in range(retries):
                try:
                    os.replace(str(tmp), str(path))
                    break
                except PermissionError:
                    time.sleep(delay)
                    delay = min(0.5, delay * 1.5)
                    continue
                except OSError as e:
                    winerr = getattr(e, "winerror", 0)
                    if winerr in (5, 32): 
                        time.sleep(delay)
                        delay = min(0.5, delay * 1.5)
                        continue
                    raise
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass

    def _load_timings(self) -> Dict[str, Any]:
        if not self._timings_path.exists():
            return {
                "overall": {"emaMs": 0.0, "lastMs": 0.0, "n": 0, "updatedAt": self.now_iso()},
                "byCompany": {},
            }
        try:
            with open(self._timings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "overall" not in data:
                    data["overall"] = {"emaMs": 0.0, "lastMs": 0.0, "n": 0, "updatedAt": self.now_iso()}
                if "byCompany" not in data:
                    data["byCompany"] = {}
                return data
        except Exception:
            return {
                "overall": {"emaMs": 0.0, "lastMs": 0.0, "n": 0, "updatedAt": self.now_iso()},
                "byCompany": {},
            }

    def _save_timings(self) -> None:
        self._atomic_write_json(self._timings_path, self._timings)

    def _ema_update(
        self,
        prior: Optional[Dict[str, Any]],
        duration_ms: int,
    ) -> Dict[str, Any]:
        now = self.now_iso()
        if not prior or int(prior.get("n", 0)) == 0:
            ema = float(duration_ms)
            n = 1
        else:
            prev_ema = float(prior.get("emaMs", 0.0))
            ema = (self.ALPHA * float(duration_ms) + (1.0 - self.ALPHA) * prev_ema)
            n = int(prior.get("n", 0)) + 1
        return {"emaMs": float(ema), "lastMs": float(duration_ms), "n": n, "updatedAt": now}

    def _company_ema(self, name: str) -> float:
        c = self._timings.get("byCompany", {}).get(name)
        if not c or int(c.get("n", 0)) == 0:
            return float(self.DEFAULT_PER_COMPANY_MS)
        return float(c.get("emaMs", self.DEFAULT_PER_COMPANY_MS))

    def _update_eta_fields(self) -> None:
        total_remaining = 0
        for name in self._companies:
            pc = self._snapshot["perCompany"][name]
            state = pc.get("state")
            if state in ("done", "error", "canceled"):
                pc["etaMs"] = None
                continue
            ema = self._company_ema(name)
            if state == "running":
                start_mon = self._company_start_monotonic.get(name)
                elapsed = 0
                if start_mon is not None:
                    elapsed = int((time.perf_counter() - start_mon) * 1000)
                remaining = max(int(ema) - elapsed, 0)
                pc["elapsedMs"] = elapsed
                pc["etaMs"] = remaining
                total_remaining += remaining
            else:
                pc["etaMs"] = int(ema)
                total_remaining += int(ema)
        self._snapshot["etaMs"] = (int(total_remaining) if total_remaining > 0 else 0)
        done = sum(1 for n in self._companies if self._snapshot["perCompany"][n]["state"] == "done")
        total = int(self._snapshot["overall"]["total"])
        percent = (done / total * 100.0) if total else 0.0
        self._snapshot["overall"]["done"] = done
        self._snapshot["overall"]["percent"] = percent
        self._snapshot["current"]["stepCount"] = total

    def add_log(
        self,
        typ: str,
        message: str,
        company: Optional[str] = None,
        subtask: Optional[str] = None,
    ) -> None:
        msg = (message or "")[:256]
        self._snapshot["logTail"].append(
            {"ts": self.now_iso(), "type": typ, "company": company, "subtask": subtask, "message": msg}
        )
        if len(self._snapshot["logTail"]) > 100:
            self._snapshot["logTail"] = self._snapshot["logTail"][-100:]

    def write_snapshot(self, force: bool = False) -> None:
        self._snapshot["updatedAt"] = self.now_iso()
        self._snapshot["elapsedMs"] = self._elapsed_ms_from_start()
        if len(self._snapshot["logTail"]) > 100:
            self._snapshot["logTail"] = self._snapshot["logTail"][-100:]
        self._update_eta_fields()
        self._v += 1
        self._snapshot["v"] = self._v
        self._atomic_write_json(self._progress_path, self._snapshot)
    def init(self, run_id: Optional[str] = None, companies: Optional[List[str]] = None, subtasks: Optional[List[str]] = None) -> None: return
    def overall_start(self, pid: Optional[int]) -> None:
        self._t0_real = datetime.now(timezone.utc)
        self._t0_monotonic = time.perf_counter()
        self._snapshot["startedAt"] = self._t0_real.isoformat()
        self._snapshot["pid"] = int(pid) if pid is not None else None
        self._snapshot["status"] = "running"
        self._snapshot["current"]["company"] = None
        self._snapshot["current"]["subtask"] = None
        self._snapshot["current"]["stepIndex"] = 0
        self.add_log("info", "Run started", None, None)
        self.write_snapshot(force=True)

    def company_start(self, name: str, idx: int, total: int) -> None:
        pc = self._snapshot["perCompany"].get(name)
        if not pc: return
        pc["state"] = "running"
        pc["elapsedMs"] = 0
        pc["etaMs"] = int(self._company_ema(name))
        for st in pc["subtasks"]:
            st["state"] = "running"
            st["elapsedMs"] = 0
            st["etaMs"] = None
            st["items"] = 0
            st["errors"] = 0
        self._company_start_monotonic[name] = time.perf_counter()
        self._snapshot["current"]["company"] = name
        self._snapshot["current"]["subtask"] = None
        self._snapshot["current"]["stepIndex"] = int(idx)
        self._snapshot["current"]["stepCount"] = int(total)
        self.add_log("info", f"Company start {name}", name, None)
        self.write_snapshot()

    def company_done(self, name: str, elapsed_ms: int, items: int = 0, errors: int = 0) -> None:
        pc = self._snapshot["perCompany"].get(name)
        if not pc: return
        pc["state"] = "done"
        pc["elapsedMs"] = int(elapsed_ms)
        pc["etaMs"] = None
        for st in pc["subtasks"]:
            st["state"] = "done"
            st["elapsedMs"] = int(elapsed_ms)
            st["etaMs"] = None
        self._snapshot["summary"]["totalItems"] = int(self._snapshot["summary"]["totalItems"]) + int(items)
        self._snapshot["summary"]["totalErrors"] = int(self._snapshot["summary"]["totalErrors"]) + int(errors)
        self.add_log("info", f"Company done {name} in {elapsed_ms}ms (items={items}, errors={errors})", name, None)
        by_company = self._timings.setdefault("byCompany", {})
        updated = self._ema_update(by_company.get(name), int(elapsed_ms))
        by_company[name] = updated
        self._save_timings()
        if name in self._company_start_monotonic:
            del self._company_start_monotonic[name]
        self.write_snapshot()

    def company_error(self, name: str, elapsed_ms: int, items: int = 0, errors: int = 1, message: Optional[str] = None) -> None:
        pc = self._snapshot["perCompany"].get(name)
        if not pc:
            return
        pc["state"] = "error"
        pc["elapsedMs"] = int(elapsed_ms)
        pc["etaMs"] = None
        for st in pc["subtasks"]:
            if st.get("state") not in ("done", "error", "canceled"):
                st["state"] = "error"
            st["elapsedMs"] = int(elapsed_ms)
            st["etaMs"] = None
            st["errors"] = max(int(st.get("errors", 0)), 1)
        self._snapshot["summary"]["totalItems"] = int(self._snapshot["summary"]["totalItems"]) + int(items)
        self._snapshot["summary"]["totalErrors"] = int(self._snapshot["summary"]["totalErrors"]) + int(max(1, errors))
        msg = message or f"Company failed {name} in {elapsed_ms}ms (items={items}, errors={errors})"
        self.add_log("error", msg, name, None)
        by_company = self._timings.setdefault("byCompany", {})
        by_company[name] = self._ema_update(by_company.get(name), int(elapsed_ms))
        self._save_timings()
        if name in self._company_start_monotonic:
            del self._company_start_monotonic[name]
        self.write_snapshot()

    def overall_done(self, total_duration_ms: int) -> None:
        self._snapshot["status"] = "done"
        self._snapshot["summary"]["finishedAt"] = self.now_iso()
        self._snapshot["summary"]["totalDurationMs"] = int(total_duration_ms)
        self._snapshot["current"]["company"] = None
        self._snapshot["current"]["subtask"] = None
        self._snapshot["etaMs"] = 0
        self.add_log("info", f"Run done in {total_duration_ms}ms", None, None)
        self._timings["overall"] = self._ema_update(self._timings.get("overall"), int(total_duration_ms))
        self._save_timings()
        self.write_snapshot()

    def error(self, message: str, company: Optional[str] = None) -> None:
        self._snapshot["status"] = "error"
        self._snapshot["current"]["company"] = None
        self._snapshot["current"]["subtask"] = None
        self.add_log("error", message, company, None)
        self.write_snapshot()

    def _mark_remaining_canceled(self) -> None:
        for name in self._companies:
            pc = self._snapshot["perCompany"][name]
            if pc.get("state") not in ("done", "error", "canceled"):
                pc["state"] = "canceled"
                pc["etaMs"] = None
                for st in pc["subtasks"]:
                    if st.get("state") not in ("done", "error", "canceled"):
                        st["state"] = "canceled"
                        st["etaMs"] = None

    def canceled(self, message: str = "Canceled by user") -> None:
        self._mark_remaining_canceled()
        self._snapshot["status"] = "canceled"
        self._snapshot["summary"]["finishedAt"] = self.now_iso()
        self._snapshot["summary"]["totalDurationMs"] = (self._elapsed_ms_from_start())
        self._snapshot["current"]["company"] = None
        self._snapshot["current"]["subtask"] = None
        self.add_log("warn", message, None, None)
        self.write_snapshot()


def check_cancel(run_id: str) -> bool:
    try:
        if not CANCEL_PATH.exists(): return False
        with open(CANCEL_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict): return False
        rid = data.get("runId")
        return bool(rid) and str(rid) == str(run_id)
    except Exception:
        return False


def main() -> None:
    run_id = os.environ.get("RUN_ID") or None
    reporter = ProgressReporter(run_id, COMPETITORS, DEFAULT_SUBTASKS)
    reporter.overall_start(pid=os.getpid())
    _cleanup_old_artifacts(reporter.run_id)

    data: Dict[str, List[Dict[str, Any]]] = {"Competitor": []}
    
    # --- THIS IS CLAUDE'S FIX ---
    # CRITICAL: Use max_workers=1 to run scrapers sequentially
    # This prevents the Playwright import race condition
    print("[RUNNER] Using max_workers=1 to prevent Playwright import race condition.")
    max_workers = 1  
    # ------------------------------

    results_by_name: Dict[str, Dict[str, Any]] = {}
    pending: List[str] = list(COMPETITORS)
    inflight: Dict[Any, str] = {}
    start_times: Dict[str, float] = {}
    idx_counter = 0
    canceled_flag = False

    OVERALL_JOB_TIMEOUT_SECONDS = 600

    existing_state = _load_existing_state()
    existing_by_name: Dict[str, Dict[str, Any]] = existing_state.get("by_name", {}) if isinstance(existing_state, dict) else {}
    existing_meta: Dict[str, Any] = existing_state.get("meta", {}) if isinstance(existing_state, dict) else {}
    meta_last_run_at = existing_meta.get("lastRunAt") if isinstance(existing_meta, dict) else None
    since_by_company = _compute_since_by_company(existing_by_name, meta_last_run_at)

    executor = ProcessPoolExecutor(max_workers=max_workers)

    run_done_ok = False
    try:
        last_hb = time.perf_counter()
        
        while pending or inflight:
            if not canceled_flag and check_cancel(reporter.run_id):
                canceled_flag = True

            while (
                not canceled_flag
                and pending
                and len(inflight) < max_workers
            ):
                name = pending.pop(0)
                idx_counter += 1
                reporter.company_start(name, idx_counter, len(COMPETITORS))
                start_times[name] = time.perf_counter()
                
                fut = executor.submit(
                    _scrape_one,
                    name,
                    LOG,
                    (since_by_company.get(name, {}) or {}).get("News"),
                    (since_by_company.get(name, {}) or {}).get("Patents"),
                    reporter.run_id,
                )
                
                inflight[fut] = name
                
                # No longer need time.sleep(5) because max_workers=1 handles it.

            if not inflight:
                break

            # --- WATCHDOG LOOP ---
            done, not_done = wait(
                inflight.keys(),
                timeout=1.0,
                return_when=FIRST_COMPLETED,
            )

            for fut in list(done):
                name = inflight.pop(fut)
                try:
                    res = fut.result()
                    errors = 0
                except Exception as e:
                    name_str = str(name)
                    reporter.add_log("error", f"Company {name_str} worker failed: {e}", name_str)
                    _dbg(name_str, "worker_exception", {"error": str(e)})
                    res = {
                        "Name": name_str,
                        "News": [],
                        "Jobs": [],
                        "Patents": [],
                        "_subtasks": {
                            "News": {"status": "error", "items": [], "error": str(e), "error_code": "UNKNOWN_ERROR"},
                            "Jobs": {"status": "error", "items": [], "error": str(e), "error_code": "UNKNOWN_ERROR"},
                            "Patents": {"status": "error", "items": [], "error": str(e), "error_code": "UNKNOWN_ERROR"},
                        },
                        "_all_subtasks_failed": True,
                        "_failed_subtasks": len(DEFAULT_SUBTASKS),
                    }
                    errors = 1

                elapsed_ms = int(
                    (time.perf_counter() - start_times.get(
                        name,
                        time.perf_counter(),
                    )) * 1000
                )
                items = 0
                for key in ("News", "Jobs", "Patents"):
                    v = res.get(key)
                    if isinstance(v, list):
                        items += len(v)

                results_by_name[name] = res

                try:
                    pc = reporter._snapshot["perCompany"].get(name)
                    if pc:
                        timings = res.get("_timings", {}) if isinstance(res, dict) else {}
                        subtask_meta = res.get("_subtasks", {}) if isinstance(res, dict) else {}
                        subtask_errors = 0
                        for st in pc.get("subtasks", []):
                            task = st.get("name")
                            if not isinstance(task, str):
                                continue
                            ms = int(timings.get(f"{task}Ms", 0)) if isinstance(timings, dict) else 0
                            meta = subtask_meta.get(task, {}) if isinstance(subtask_meta, dict) else {}
                            status = meta.get("status") if isinstance(meta, dict) else None
                            if status not in ("ok", "empty_valid", "blocked", "challenge", "selector_changed", "error"):
                                status = "ok"
                            items_list = meta.get("items") if isinstance(meta, dict) else None
                            if not isinstance(items_list, list):
                                v = res.get(task)
                                items_list = v if isinstance(v, list) else []
                            items_count = len(items_list)
                            st["state"] = "done" if status in ("ok", "empty_valid") else "error"
                            st["elapsedMs"] = ms
                            st["etaMs"] = 0
                            st["items"] = items_count
                            st["errors"] = 1 if st["state"] == "error" else 0
                            if st["state"] == "error":
                                subtask_errors += 1
                        errors = max(int(errors), int(subtask_errors))
                        reporter.write_snapshot()
                except Exception:
                    pass

                all_failed = bool(res.get("_all_subtasks_failed")) if isinstance(res, dict) else False
                if all_failed:
                    reporter.company_error(
                        name,
                        elapsed_ms,
                        items=items,
                        errors=max(1, int(errors)),
                        message=f"Company {name} failed: all subtasks failed",
                    )
                else:
                    reporter.company_done(
                        name,
                        elapsed_ms,
                        items=items,
                        errors=errors,
                    )

            # Check for hung jobs (still good to have as a safeguard)
            now = time.perf_counter()
            for fut, name in list(inflight.items()):
                job_start_time = start_times.get(name)
                if job_start_time is None:
                    continue

                elapsed_seconds = now - job_start_time
                if elapsed_seconds > OVERALL_JOB_TIMEOUT_SECONDS:
                    name_str = str(name)
                    print(f"[RUNNER]!! Job for '{name_str}' TIMED OUT after {elapsed_seconds:.0f}s. Killing process.")
                    
                    msg = f"Company {name_str} timed out after {OVERALL_JOB_TIMEOUT_SECONDS}s (Process HUNG)"
                    reporter.add_log("error", msg, name_str)
                    _dbg(name_str, "worker_timeout_hung", {"timeout": OVERALL_JOB_TIMEOUT_SECONDS})

                    try:
                        pid_to_kill = fut._process._pid
                        if pid_to_kill:
                            print(f"[RUNNER]!! Sending SIGTERM to hung PID {pid_to_kill} for '{name_str}'")
                            os.kill(pid_to_kill, signal.SIGTERM)
                    except Exception as e:
                        print(f"[RUNNER]!! Failed to kill process for '{name_str}': {e}")
                    
                    inflight.pop(fut)
                    elapsed_ms = int(elapsed_seconds * 1000)
                    reporter.company_error(name_str, elapsed_ms, items=0, errors=1, message=msg)
                    results_by_name[name_str] = {
                        "Name": name_str,
                        "News": [],
                        "Jobs": [],
                        "Patents": [],
                        "_subtasks": {
                            "News": {"status": "error", "items": [], "error": msg, "error_code": "NAV_TIMEOUT"},
                            "Jobs": {"status": "error", "items": [], "error": msg, "error_code": "NAV_TIMEOUT"},
                            "Patents": {"status": "error", "items": [], "error": msg, "error_code": "NAV_TIMEOUT"},
                        },
                        "_all_subtasks_failed": True,
                        "_failed_subtasks": len(DEFAULT_SUBTASKS),
                    }
            
            if time.perf_counter() - last_hb >= 1.0:
                reporter.write_snapshot()
                last_hb = time.perf_counter()

        # --- END OF LOOP ---

        if canceled_flag:
            reporter.canceled("Canceled by user")
        else:
            total_duration_ms = reporter._elapsed_ms_from_start()
            reporter.overall_done(total_duration_ms=int(total_duration_ms))
            run_done_ok = True
            
    except Exception as e:
        reporter.error(f"Unhandled exception: {e}")
    finally:
        reporter.add_log("info", "Run loop finished, shutting down pool...")
        executor.shutdown(wait=False, cancel_futures=True)

    # --- Final JSON Merge ---
    
    for name in COMPETITORS:
        data["Competitor"].append(
            results_by_name.get(
                name,
                {"Name": name, "News": [], "Jobs": [], "Patents": []},
            )
        )

    def _atomic_write_json_file(path: Path, data: Any) -> None:
        unique_tmp = f"{path.name}.{os.getpid()}.{int(time.time() * 1000)}.tmp"
        tmp = path.with_name(unique_tmp)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
                try:
                    f.flush()
                    os.fsync(f.fileno())
                except Exception: pass
            retries = 20
            delay = 0.05
            for _ in range(retries):
                try:
                    os.replace(str(tmp), str(path))
                    break
                except PermissionError:
                    time.sleep(delay)
                    delay = min(0.5, delay * 1.5)
                    continue
                except OSError as e:
                    winerr = getattr(e, "winerror", 0)
                    if winerr in (5, 32):
                        time.sleep(delay)
                        delay = min(0.5, delay * 1.5)
                        continue
                    raise
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception: pass

    def _sort_items_by_date_desc(items: Any) -> List[Dict[str, Any]]:
        if not isinstance(items, list):
            return []
        clean = [x for x in items if isinstance(x, dict)]
        return sorted(clean, key=lambda x: (_date_from_item(x) or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)

    def _filter_strictly_newer(items: Any, cutoff_iso: Optional[str]) -> List[Dict[str, Any]]:
        if not isinstance(items, list):
            return []
        if not cutoff_iso:
            return [x for x in items if isinstance(x, dict)]
        try:
            cutoff_dt = datetime.fromisoformat(cutoff_iso)
        except Exception:
            cutoff_dt = None
        if cutoff_dt is None:
            return [x for x in items if isinstance(x, dict)]

        out: List[Dict[str, Any]] = []
        for x in items:
            if not isinstance(x, dict):
                continue
            d = _date_from_item(x)
            # Date-only safety: allow same-date items and rely on dedupe keys.
            if d is not None and d.date() >= cutoff_dt.date():
                out.append(x)
        return out

    def _validate_items(items: Any, kind: str, company: str) -> List[Dict[str, Any]]:
        if not isinstance(items, list):
            return []
        kept: List[Dict[str, Any]] = []
        dropped = 0
        reasons = {
            "missing_url": 0,
            "missing_title_headline": 0,
            "missing_job_title": 0,
            "missing_date": 0,
        }
        for it in items:
            ok = False
            if not isinstance(it, dict):
                dropped += 1
                continue
            url_ok = isinstance(it.get("URL"), str) and bool(str(it.get("URL") or "").strip())
            date_ok = isinstance(it.get("Date"), str) and bool(str(it.get("Date") or "").strip())
            if not date_ok:
                reasons["missing_date"] += 1
            if kind == "News":
                title_ok = bool(str(it.get("Headline") or it.get("Title") or "").strip())
                if not url_ok:
                    reasons["missing_url"] += 1
                if not title_ok:
                    reasons["missing_title_headline"] += 1
                ok = bool(url_ok and title_ok)
            elif kind == "Patents":
                title_ok = isinstance(it.get("Title"), str) and bool(str(it.get("Title") or "").strip())
                if not url_ok:
                    reasons["missing_url"] += 1
                if not title_ok:
                    reasons["missing_title_headline"] += 1
                ok = bool(url_ok and title_ok)
            elif kind == "Jobs":
                title_ok = isinstance(it.get("Job Title"), str) and bool(str(it.get("Job Title") or "").strip())
                if not url_ok:
                    reasons["missing_url"] += 1
                if not title_ok:
                    reasons["missing_job_title"] += 1
                ok = bool(url_ok and title_ok)
            if ok:
                kept.append(it)
            else:
                dropped += 1
        if dropped:
            _dbg(company, "output_validation", {
                "source": kind,
                "dropped": dropped,
                "kept": len(kept),
                "reasons": reasons,
            })
        else:
            # keep missing_date informational visibility for permissive validators
            if reasons["missing_date"]:
                _dbg(company, "output_validation_info", {
                    "source": kind,
                    "missing_date": reasons["missing_date"],
                    "kept": len(kept),
                })
        return kept

    merged_out: Dict[str, Any] = {"_meta": dict(existing_meta or {}), "Competitor": []}
    if run_done_ok:
        merged_out["_meta"]["lastRunAt"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    run_stats_companies: Dict[str, Dict[str, int]] = {}
    for name in COMPETITORS:
        old_comp = existing_by_name.get(name, {"Name": name, "News": [], "Jobs": [], "Patents": []})
        new_comp = results_by_name.get(name, {"Name": name, "News": [], "Jobs": [], "Patents": []})

        news_old = old_comp.get("News", []) if isinstance(old_comp, dict) else []
        jobs_old = old_comp.get("Jobs", []) if isinstance(old_comp, dict) else []
        pats_old = old_comp.get("Patents", []) if isinstance(old_comp, dict) else []

        company_cutoffs = (since_by_company.get(name, {}) or {})
        news_new = _validate_items(_filter_strictly_newer(
            new_comp.get("News", []) if isinstance(new_comp, dict) else [],
            company_cutoffs.get("News"),
        ), "News", name)
        jobs_new = _validate_items(_dedupe_jobs_current(new_comp.get("Jobs", []) if isinstance(new_comp, dict) else []), "Jobs", name)
        pats_new = _validate_items(_filter_strictly_newer(
            new_comp.get("Patents", []) if isinstance(new_comp, dict) else [],
            company_cutoffs.get("Patents"),
        ), "Patents", name)

        merged_news_all = _sort_items_by_date_desc(_merge_items(news_old, news_new, _keys_for_item))
        merged_jobs_all = _merge_items(
            [],
            jobs_new,
            lambda x: [f"url:{_normalize_url((x or {}).get('URL'))}"],
        )
        merged_pats_all = _sort_items_by_date_desc(_merge_items(pats_old, pats_new, _keys_for_item))

        merged_news = merged_news_all[:MAX_NEWS_ITEMS]
        merged_jobs = merged_jobs_all[:MAX_JOBS_ITEMS]
        merged_pats = merged_pats_all[:MAX_PATENTS_ITEMS]

        if len(merged_news_all) > len(merged_news):
            _dbg(name, "output_cap_trim", {
                "source": "News",
                "before_count": len(merged_news_all),
                "after_count": len(merged_news),
                "cap": MAX_NEWS_ITEMS,
            })
        if len(merged_jobs_all) > len(merged_jobs):
            _dbg(name, "output_cap_trim", {
                "source": "Jobs",
                "before_count": len(merged_jobs_all),
                "after_count": len(merged_jobs),
                "cap": MAX_JOBS_ITEMS,
            })
        if len(merged_pats_all) > len(merged_pats):
            _dbg(name, "output_cap_trim", {
                "source": "Patents",
                "before_count": len(merged_pats_all),
                "after_count": len(merged_pats),
                "cap": MAX_PATENTS_ITEMS,
            })

        merged_out["Competitor"].append(
            {
                "Name": name,
                "News": merged_news,
                "Jobs": merged_jobs,
                "Patents": merged_pats,
            }
        )
        run_stats_companies[name] = {
            "news": len(merged_news),
            "jobs": len(merged_jobs),
            "patents": len(merged_pats),
        }

    if run_done_ok:
        merged_out.setdefault("_meta", {})
        merged_out["_meta"]["lastRunStats"] = {
            "runId": reporter.run_id,
            "finishedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "perCompany": run_stats_companies,
            "totalErrors": int(reporter._snapshot.get("summary", {}).get("totalErrors", 0)),
        }

    _atomic_write_json_file(OUTPUT_PATH, merged_out)
    _cleanup_old_artifacts(reporter.run_id)


if __name__ == "__main__":
    try:
        main()
    except Exception as _e:
        try:
            rid = os.environ.get("RUN_ID") or None
            ProgressReporter(
                rid,
                COMPETITORS,
                DEFAULT_SUBTASKS,
            ).error(f"Fatal error at entrypoint: {_e}")
        except Exception:
            pass
        raise
