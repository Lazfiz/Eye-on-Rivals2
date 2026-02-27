# mypy: ignore-errors
from datetime import datetime, timezone, timedelta
from urllib.parse import (
    urljoin,
    urlparse,
    parse_qs,
    urlencode,
    urlunparse,
)
from typing import Optional, List, Dict, Any
import os
import time
import re
from pathlib import Path

from selenium import webdriver  # type: ignore[import]
from selenium.webdriver.common.by import By  # type: ignore[import]
from selenium.webdriver import ChromeOptions  # type: ignore[import]
from selenium.webdriver.support.ui import WebDriverWait  # type: ignore[import]
from selenium.webdriver.support.ui import Select  # type: ignore[import]
from selenium.webdriver.support import expected_conditions as EC  # type: ignore[import]  # noqa: E501
from selenium.common.exceptions import (  # type: ignore[import]
    NoSuchElementException,
    TimeoutException,
    StaleElementReferenceException,
)


def runPatent(companyString: str, since_dt: Optional[datetime] = None) -> Dict[str, List[Dict[str, str]]]:
    """
    Robust patents scraping for a given company using WIPO Patentscope.

    Strategy
    - Build an Applicant/Assignee-focused query with common aliases.
    - Navigate directly to results.jsf with encoded query (fast path).
    - If no results are parsed, fall back to advancedSearch.jsf UI flow.
    - Extract rows using multiple selectors and resilient text reads.
    - Respect a date window and stop when all items are older than start.

    Returns
    - Dict with 'Patents': [{Title, URL, Date}]
      Date is normalized to YYYY-MM-DD when possible.
    """
    # Config
    END_DATE = datetime.now(timezone.utc)
    default_floor = datetime(2000, 1, 1, tzinfo=timezone.utc)
    floor_raw = str(os.environ.get("PATENT_DATE_FLOOR", "2000-01-01") or "2000-01-01").strip()
    try:
        floor_dt = datetime.fromisoformat(floor_raw)
        if floor_dt.tzinfo is None:
            floor_dt = floor_dt.replace(tzinfo=timezone.utc)
        else:
            floor_dt = floor_dt.astimezone(timezone.utc)
    except Exception:
        floor_dt = default_floor
    dynamic_floor_dt: Optional[datetime] = None
    if isinstance(since_dt, datetime):
        try:
            if since_dt.tzinfo is None:
                since_utc = since_dt.replace(tzinfo=timezone.utc)
            else:
                since_utc = since_dt.astimezone(timezone.utc)
            dynamic_floor_dt = since_utc - timedelta(days=30)
        except Exception:
            dynamic_floor_dt = None
    if dynamic_floor_dt is not None:
        effective_floor_dt = max(floor_dt, dynamic_floor_dt)
        floor_source = "dynamic+env"
    else:
        effective_floor_dt = floor_dt
        floor_source = "env"
    BASE_URL = "https://patentscope.wipo.int/"
    # RESULTS_ROW_SEL unused (using ROW_SELECTORS instead)
    NEXT_SELECTORS = [
        ".js-paginator-next",
        "a[id^='resultListCommandsForm:'][id*='j_idt'][aria-label='Next Page']",
        "a[id^='resultListForm:'][id*='j_idt'][aria-label='Next Page']",
        "a[rel='next']",
        "a.pagination__next",
        "button[aria-label='Next']",
        "button[aria-label='Next page']",
        "a[aria-label='Next']",
        "a[aria-label='Next page']",
        ".ui-paginator-next",
        ".pi-paginator-next",
        "a.ui-paginator-next",
        "button.ui-paginator-next",
        "a.pi-paginator-next",
        "button.pi-paginator-next",
        "a.next",
        ".pagination .next a",
    ]

    # Alternate row selectors to handle layout variants
    ROW_SELECTORS = [
        ".ps-patent-result--first-row",
        ".ps-search-result-item",
        "tr.ps-result",
        "tr.result-list__row",
        ".result-list__row",
        ".result-item-container",
        "div.result-item",
        "a.result-title",
    ]

    # Company alias map for better matching in Patentscope
    COMPANY_ALIASES = {
        "Topcon": [
            "Topcon",
            "Topcon Corporation",
            "Topcon Healthcare",
            "TOPCON",
            "Topcon Medical Systems",
            "Topcon Medical Systems, Inc.",
            "Topcon Corp.",
        ],
        "Nidek": [
            "Nidek",
            "NIDEK",
            "NIDEK CO.",
            "NIDEK CO., LTD.",
            "Nidek Co., Ltd.",
            "NIDEK CO LTD",
            "NIDEK CO.,LTD.",
            "NIDEK INC.",
            "NIDEK TECHNOLOGIES",
            "NIDEK TECHNOLOGIES S.R.L.",
            "株式会社ニデック",
        ],
        "Canon": [
            "Canon",
        ],
        "OptoVue": [
            "Optovue",
            "OPTOVUE",
            "Visionix",
            "Luneau Technology",
            "Visionix-Optovue",
        ],
        "Zeiss": [
            "Zeiss",
        ],
    }

    def _is_xpath(sel: str) -> bool:
        s = sel.strip().lower()
        return s.startswith("/") or s.startswith("(") or s.startswith("xpath=")

    def _norm_xpath(sel: str) -> str:
        return sel[6:] if sel.lower().startswith("xpath=") else sel

    def _click_if_present(driver, selectors: List[str]) -> bool:
        for sel in selectors:
            try:
                if _is_xpath(sel):
                    el = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, _norm_xpath(sel))
                        )
                    )
                else:
                    el = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                    )
                el.click()
                return True
            except Exception:
                continue
        return False

    def build_company_query(name: str) -> str:
        aliases = COMPANY_ALIASES.get(name, [name])
        # Build terms including exact aliases and simple wildcard stems
        terms: List[str] = []
        for a in aliases:
            a_clean = a.strip()
            if not a_clean:
                continue
            terms.append(f'"{a_clean}"')
            stem = a_clean.split()[0]
            if stem and stem[-1].isalpha():
                terms.append(f"{stem}*")
        # De-duplicate while preserving order
        seen = set()
        uniq_terms: List[str] = []
        for t in terms:
            if t not in seen:
                seen.add(t)
                uniq_terms.append(t)
        alias_or = " OR ".join(uniq_terms) if uniq_terms else f'"{name.strip()}"'
        # AN-weighted query for better relevance/precision.
        return f'AN:({alias_or})'

    def _aliases_for_company(name: str) -> List[str]:
        n = (name or "").strip()
        if not n:
            return []
        for k, v in COMPANY_ALIASES.items():
            if k.lower() == n.lower():
                return list(v)
        return [n]

    # Setup headless Chrome (resilient flags)
    options = ChromeOptions()
    headful_env = str(os.environ.get("SCRAPER_HEADFUL", "")).strip()
    patents_headful = headful_env in ("1", "true", "True", "yes", "YES")
    if not patents_headful:
        options.add_argument("--headless=new")
    print(f"[Patents] Browser mode: {'headed' if patents_headful else 'headless'} | company={companyString}")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,800")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    # Anti-bot hardening
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")
    try:
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
    except Exception:
        pass
    try:
        options.page_load_strategy = "eager"
    except Exception:
        pass

    driver = webdriver.Chrome(options=options)
    try:
        driver.set_page_load_timeout(30)
    except Exception:
        pass

    Patents: Dict[str, List[Dict[str, str]]] = {"Patents": []}
    seen_urls = set()
    try:
        max_pages = int(str(os.environ.get("PATENT_MAX_PAGES", "0") or "0").strip())
    except Exception:
        max_pages = 0
    try:
        debug_max_pages = int(str(os.environ.get("PATENT_DEBUG_MAX_PAGES", "0") or "0").strip())
    except Exception:
        debug_max_pages = 0
    if debug_max_pages > 0:
        max_pages = debug_max_pages
    print(f"[Patents] Max pages: {max_pages}")
    print(f"[Patents] Debug cap active: {str(debug_max_pages > 0).lower()}")
    print(f"[Patents] Date floor: {floor_dt.strftime('%Y-%m-%d')}")
    print(f"[Patents] Effective floor: {effective_floor_dt.strftime('%Y-%m-%d')} (source={floor_source})")

    filtered_before_date_floor = 0
    filtered_unparseable_date = 0
    kept_items = 0

    def parse_date_to_utc(date_text: str) -> Optional[datetime]:
        """Return timezone-aware UTC datetime if parseable; else None."""
        if not date_text:
            return None
        text = date_text.strip()
        for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                dt_naive = datetime.strptime(text, fmt)
                return dt_naive.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        try:
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt
        except Exception:
            return None

    def normalize_date_str(date_text: str) -> str:
        dt = parse_date_to_utc(date_text)
        if dt is None:
            return (date_text or "").strip()
        return dt.strftime("%Y-%m-%d")

    def resolve_url(href: str) -> str:
        if not href:
            return ""
        abs_url = urljoin(BASE_URL, href.strip())
        try:
            u = urlparse(abs_url)
            qs = parse_qs(u.query)
            # Canonicalize Patentscope detail links to stable docId URLs.
            if "detail.jsf" in (u.path or "") and "docId" in qs and qs["docId"]:
                stable_q = urlencode({"docId": qs["docId"][0]})
                return urlunparse((u.scheme, u.netloc, u.path, "", stable_q, ""))
            # Drop volatile tracking query params globally.
            if "_cid" in qs:
                del qs["_cid"]
                return urlunparse((u.scheme, u.netloc, u.path, "", urlencode(qs, doseq=True), ""))
            return urlunparse((u.scheme, u.netloc, u.path, "", urlencode(qs, doseq=True), ""))
        except Exception:
            return abs_url
    
    # Debug snapshot helper: writes current page HTML to backend/patent_debug/{company}_{tag}.html
    def _save_snapshot(tag: str) -> None:
        try:
            out_dir = Path(__file__).resolve().parents[1] / "patent_debug"
            out_dir.mkdir(parents=True, exist_ok=True)
            fname = f"{companyString.strip()}_{tag}.html"
            path = out_dir / fname
            with open(path, "w", encoding="utf-8") as f:
                src = ""
                try:
                    src = driver.page_source or ""
                except Exception:
                    src = ""
                f.write(src)
        except Exception:
            # never fail scraping due to diagnostics
            pass

    def _find_rows_any() -> List[Any]:
        rows_all: List[Any] = []
        for sel in ROW_SELECTORS:
            try:
                rows_all = driver.find_elements(By.CSS_SELECTOR, sel)
            except Exception:
                rows_all = []
            if rows_all:
                break
        return rows_all

    def _result_count_text() -> str:
        """Best-effort visible results summary text for debugging."""
        selectors = [
            ".results-count",
            ".b-infobox__text",
            "[class*='result'][class*='count']",
            "[id*='result'][id*='count']",
        ]
        for sel in selectors:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
            except Exception:
                els = []
            for el in els:
                try:
                    txt = (el.text or "").strip()
                except Exception:
                    txt = ""
                if txt:
                    return txt
        return ""

    def _extract_result_count(text: str) -> int:
        try:
            m = re.search(r"(\d[\d,\.]*)", text or "")
            if not m:
                return 0
            return int(re.sub(r"[^\d]", "", m.group(1)))
        except Exception:
            return 0

    def _active_page_text() -> str:
        selectors = [
            "span[id$='pageNumber']",
            ".ui-paginator-page.ui-state-active",
            ".pi-paginator-page.p-highlight",
            "[aria-current='page']",
            ".pagination .active",
        ]
        for sel in selectors:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
            except Exception:
                els = []
            for el in els:
                try:
                    t = (el.text or "").strip()
                except Exception:
                    t = ""
                if t:
                    return t
        return ""

    def _paginator_state() -> Dict[str, Optional[int]]:
        """Best-effort paginator parser: current page and total pages."""
        current: Optional[int] = None
        total: Optional[int] = None

        # 1) Try explicit current page markers
        for sel in (
            "span[id$='pageNumber']",
            ".ps-paginator--page--value span[id$='pageNumber']",
            ".ui-paginator-page.ui-state-active",
            ".pi-paginator-page.p-highlight",
            "[aria-current='page']",
        ):
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
            except Exception:
                els = []
            for el in els:
                try:
                    t = (el.text or "").strip()
                except Exception:
                    t = ""
                if t.isdigit():
                    current = int(t)
                    break
            if current is not None:
                break

        # 2) Parse "x / y" from paginator containers
        for sel in (".ps-paginator--page--value", ".ps-paginator", "[class*='paginator']"):
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
            except Exception:
                els = []
            for el in els:
                try:
                    txt = (el.text or "").strip()
                except Exception:
                    txt = ""
                m = re.search(r"(\d[\d,\.]*)\s*/\s*(\d[\d,\.]*)", txt)
                if not m:
                    continue
                try:
                    c = int(re.sub(r"[^\d]", "", m.group(1)))
                    t = int(re.sub(r"[^\d]", "", m.group(2)))
                except Exception:
                    continue
                if current is None:
                    current = c
                total = t
                break
            if total is not None:
                break

        return {"current_page": current, "total_pages": total}

    def _first_row_marker() -> str:
        rows = _find_rows_any()
        if not rows:
            return ""
        row = rows[0]
        txt = ""
        href = ""
        try:
            txt = (row.text or "").strip()
        except Exception:
            txt = ""
        try:
            a = row.find_element(By.CSS_SELECTOR, "a[href]")
            href = (a.get_attribute("href") or "").strip()
        except Exception:
            href = ""
        return f"{txt}|{href}"

    def _wait_for_advance(prev_url: str, prev_marker: str, prev_page: str, timeout: int = 12) -> bool:
        def _stable_url(u: str) -> str:
            try:
                p = urlparse(u or "")
                # ignore volatile path params (e.g., ;jsessionid=...)
                return urlunparse((p.scheme, p.netloc, p.path, "", p.query, ""))
            except Exception:
                return u or ""

        prev_stable = _stable_url(prev_url)
        wait = WebDriverWait(driver, timeout)
        try:
            wait.until(
                lambda d: (
                    (_stable_url(d.current_url) != prev_stable)
                    or (_active_page_text() and _active_page_text() != prev_page)
                    or (_first_row_marker() and _first_row_marker() != prev_marker)
                )
            )
            return True
        except Exception:
            return False

    def set_per_page_100() -> bool:
        """Best-effort per-page size change to 100; continue even if not applied."""
        before_rows = len(_find_rows_any())
        before_count = _result_count_text()
        print(f"[Patents] perPage before: rows={before_rows}, visible_count='{before_count or '(not found)'}'")

        def _verify_applied() -> bool:
            after_rows_local = len(_find_rows_any())
            try:
                sel_val = driver.execute_script(
                    """var s=document.querySelector("#resultListCommandsForm\\:perPage\\:input, select[id*='perPage'], select[name*='perPage']");
                    return s ? String(s.value || '') : '';"""
                ) or ""
            except Exception:
                sel_val = ""
            return (str(sel_val).strip() == "100") or (before_rows <= 10 and after_rows_local > 10)

        select_found = False
        applied = False
        for attempt in (1, 2):
            changed = False
            # 1) Try known select IDs/selectors and dispatch events + PrimeFaces.
            for sel in (
                "#resultListCommandsForm\\:perPage\\:input",
                "select#resultListCommandsForm\\:perPage\\:input",
                "select[name*='perPage']",
                "select[id*='perPage']",
            ):
                try:
                    els = driver.find_elements(By.CSS_SELECTOR, sel)
                except Exception:
                    els = []
                if els:
                    select_found = True
                for el in els:
                    try:
                        try:
                            Select(el).select_by_value("100")
                        except Exception:
                            pass
                        driver.execute_script(
                            """var s=arguments[0];
                            try { s.value='100'; } catch(e) {}
                            try { s.dispatchEvent(new Event('input', {bubbles:true})); } catch(e) {}
                            try { s.dispatchEvent(new Event('change', {bubbles:true})); } catch(e) {}
                            try { s.dispatchEvent(new Event('blur', {bubbles:true})); } catch(e) {}
                            try {
                                var oc = s.getAttribute('onchange');
                                if (oc) { (new Function(oc)).call(s); }
                            } catch(e) {}
                            try {
                                if (window.PrimeFaces && PrimeFaces.ab && s.id) {
                                    PrimeFaces.ab({s:s.id,e:'change',p:s.id,u:'results-container'});
                                }
                            } catch(e) {}
                            """,
                            el,
                        )
                        changed = True
                    except Exception:
                        continue

            # 2) Try clicking visible control/option containing "100".
            if not changed:
                for csel in (
                    "button", "a", "li", "span", "div", ".ui-dropdown-item", ".p-dropdown-item"
                ):
                    try:
                        nodes = driver.find_elements(By.CSS_SELECTOR, csel)
                    except Exception:
                        nodes = []
                    for n in nodes:
                        try:
                            t = (n.text or "").strip()
                            if t != "100":
                                continue
                            driver.execute_script("arguments[0].click();", n)
                            changed = True
                            break
                        except Exception:
                            continue
                    if changed:
                        break

            # 3) Generic JS fallback for any perPage-ish element.
            if not changed:
                try:
                    changed = bool(
                        driver.execute_script(
                            """var changed=false;
                            var nodes=[...document.querySelectorAll("select[id*='perPage'], select[name*='perPage'], [id*='perPage'], [name*='perPage']")];
                            nodes.forEach(function(n){
                              try {
                                if (n.tagName==='SELECT') n.value='100';
                                n.dispatchEvent(new Event('input', {bubbles:true}));
                                n.dispatchEvent(new Event('change', {bubbles:true}));
                                if (window.PrimeFaces && PrimeFaces.ab && n.id) {
                                  PrimeFaces.ab({s:n.id,e:'change',p:n.id,u:'results-container'});
                                }
                                changed=true;
                              } catch(e) {}
                            });
                            return changed;"""
                        )
                    )
                except Exception:
                    changed = False

            if changed:
                time.sleep(1.4)
            applied = _verify_applied()
            if applied:
                break
            if attempt == 1:
                time.sleep(1.0)

        after_rows = len(_find_rows_any())
        after_count = _result_count_text()
        print(f"[Patents] perPage control found: {str(select_found).lower()}")
        print(f"[Patents] perPage after: rows={after_rows}, visible_count='{after_count or '(not found)'}'")
        print(f"[Patents] perPage verified: {str(applied).lower()}")
        if not applied:
            print("[Patents] per_page_not_applied")
            _save_snapshot("per_page_fail")
        return applied

    def collect_current_page() -> Dict[str, Any]:
        """
        Collect items for the current page.
        Returns info for stop-condition logic.
        """
        wait = WebDriverWait(driver, 15)
        try:
            # Wait until any row selector OR known detail links appear
            wait.until(
                lambda d: (
                    any(
                        d.find_elements(By.CSS_SELECTOR, sel)
                        for sel in ROW_SELECTORS
                    )
                    or d.find_elements(
                        By.CSS_SELECTOR, "a[href*='detail.jsf?docId=']"
                    )
                )
            )
        except TimeoutException:
            # Proceed; we'll attempt anchor-based fallback below
            pass

        rows = _find_rows_any()
        if not rows:
            # Fallback: identify result containers via detail links
            anchors = []
            try:
                anchors = driver.find_elements(
                    By.CSS_SELECTOR, "a[href*='detail.jsf?docId=']"
                )
            except Exception:
                anchors = []
            if anchors:
                tmp_rows: List[Any] = []
                for a in anchors:
                    try:
                        cont = a.find_element(
                            By.XPATH, "ancestor::*[self::tr or self::div][1]"
                        )
                    except Exception:
                        cont = a
                    tmp_rows.append(cont)
                rows = tmp_rows
            else:
                return {
                    "known_dates": [],
                    "added": 0,
                    "rows": 0,
                    "parsed_date_count": 0,
                    "unknown_date_count": 0,
                    "min_date": None,
                    "max_date": None,
                }

        known_dates: List[datetime] = []
        added = 0
        parsed_date_count = 0
        unknown_date_count = 0

        for row in rows:
            try:
                # Title
                title_el = None
                for sel in (
                    ".needTranslation-title",
                    ".ps-result-title",
                    "a.needTranslation-title",
                ):
                    try:
                        title_el = row.find_element(By.CSS_SELECTOR, sel)
                        txt = ""
                        try:
                            txt = (title_el.text or "").strip()
                        except StaleElementReferenceException:
                            try:
                                txt = (
                                    title_el.get_attribute("textContent") or ""
                                ).strip()
                            except Exception:
                                txt = ""
                        if title_el and txt:
                            break
                    except (NoSuchElementException,
                            StaleElementReferenceException):
                        title_el = None
                if not title_el:
                    # Fallback to anchor text when dedicated title element not found
                    try:
                        a = row.find_element(
                            By.CSS_SELECTOR, "a[href*='detail.jsf?docId=']"
                        )
                        ttxt = ""
                        try:
                            ttxt = (a.text or "").strip()
                        except StaleElementReferenceException:
                            try:
                                ttxt = (
                                    a.get_attribute("textContent") or ""
                                ).strip()
                            except Exception:
                                ttxt = ""
                        if ttxt:
                            title_el = a
                        else:
                            continue
                    except Exception:
                        continue

                try:
                    title = (title_el.text or "").strip()
                except StaleElementReferenceException:
                    try:
                        title = (
                            title_el.get_attribute("textContent") or ""
                        ).strip()
                    except Exception:
                        title = ""

                # Link
                link_href = ""
                try:
                    link_el = row.find_element(By.CSS_SELECTOR, "a[href]")
                    link_href = (link_el.get_attribute("href") or "").strip()
                except (NoSuchElementException,
                        StaleElementReferenceException):
                    link_href = ""
                url_abs = resolve_url(link_href)

                # Date
                date_text = ""
                for dsel in (
                    "[id$='resultListTableColumnPubDate']",
                    ".result-list__pubdate",
                    "[id*='PubDate']",
                    ".ps-result-pubdate",
                ):
                    try:
                        dt_el = row.find_element(By.CSS_SELECTOR, dsel)
                        raw = ""
                        try:
                            raw = (dt_el.text or "").strip()
                        except StaleElementReferenceException:
                            try:
                                raw = (
                                    dt_el.get_attribute("textContent") or ""
                                ).strip()
                            except Exception:
                                raw = ""
                        if raw:
                            date_text = raw
                            break
                    except (NoSuchElementException,
                            StaleElementReferenceException):
                        continue

                dt = parse_date_to_utc(date_text)
                if dt is not None:
                    known_dates.append(dt)
                    parsed_date_count += 1
                else:
                    unknown_date_count += 1

                nonlocal filtered_before_date_floor, filtered_unparseable_date, kept_items
                if dt is None:
                    # Keep unknown dates for safety, but track quality.
                    filtered_unparseable_date += 1
                    include = True
                else:
                    include = (effective_floor_dt <= dt <= END_DATE)
                    if not include and dt < effective_floor_dt:
                        filtered_before_date_floor += 1

                key = url_abs or (title + "|" + (date_text or ""))
                if include and key not in seen_urls:
                    seen_urls.add(key)
                    Patents["Patents"].append(
                        {
                            "Title": title,
                            "URL": url_abs,
                            "Date": normalize_date_str(date_text),
                        }
                    )
                    added += 1
                    kept_items += 1
            except (NoSuchElementException, TimeoutException):
                continue

        min_date = min(known_dates) if known_dates else None
        max_date = max(known_dates) if known_dates else None
        return {
            "known_dates": known_dates,
            "added": added,
            "rows": len(rows),
            "parsed_date_count": parsed_date_count,
            "unknown_date_count": unknown_date_count,
            "min_date": min_date,
            "max_date": max_date,
        }

    def compute_next_url(current_url: str) -> Optional[str]:
        """Try URL-based pagination (?page= or ?offset=)."""
        try:
            u = urlparse(current_url)
            qs = parse_qs(u.query)
            if "page" in qs and qs["page"]:
                try:
                    page = int(qs["page"][0])
                except Exception:
                    page = 1
                qs["page"] = [str(page + 1)]
                new_q = urlencode(qs, doseq=True)
                return urlunparse(
                    (u.scheme, u.netloc, u.path, u.params, new_q, u.fragment)
                )
            if "offset" in qs and qs["offset"]:
                try:
                    offset = int(qs["offset"][0])
                except Exception:
                    offset = 0
                per_page = 100
                if "perPage" in qs and qs["perPage"]:
                    try:
                        per_page = int(qs["perPage"][0])
                    except Exception:
                        per_page = 100
                qs["offset"] = [str(offset + per_page)]
                new_q = urlencode(qs, doseq=True)
                return urlunparse(
                    (u.scheme, u.netloc, u.path, u.params, new_q, u.fragment)
                )
            return None
        except Exception:
            return None

    def go_next_page() -> bool:
        """
        Navigate to next page via direct URL or clicking "next".
        Returns True if page likely advanced.
        """
        prev_url = driver.current_url
        prev_marker = ""
        prev_page = _active_page_text()
        prev_state = _paginator_state()
        try:
            prev_marker = _first_row_marker()
        except Exception:
            prev_marker = ""

        # 1) Explicit next controls.
        for sel in NEXT_SELECTORS:
            try:
                btns = driver.find_elements(By.CSS_SELECTOR, sel)
                btn = next((b for b in btns if b.is_enabled()), None)
                if not btn:
                    continue
                try:
                    btn.click()
                except Exception:
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                    driver.execute_script("arguments[0].click();", btn)
                if _wait_for_advance(prev_url, prev_marker, prev_page):
                    print(f"[Patents] next_page action: clicked_selector:{sel}")
                    return True
            except (NoSuchElementException, TimeoutException):
                continue

        # 2) Click active page + 1 if numeric paginator exists.
        try:
            current_num = int(prev_page) if prev_page.isdigit() else None
        except Exception:
            current_num = None
        if current_num is not None:
            wanted = str(current_num + 1)
            for sel in ("a.ui-paginator-page", "a.pi-paginator-page", "a[aria-label]", "a"):
                try:
                    links = driver.find_elements(By.CSS_SELECTOR, sel)
                except Exception:
                    links = []
                for lnk in links:
                    try:
                        t = (lnk.text or "").strip()
                        if t != wanted:
                            continue
                        if not lnk.is_displayed() or not lnk.is_enabled():
                            continue
                        driver.execute_script("arguments[0].click();", lnk)
                        if _wait_for_advance(prev_url, prev_marker, prev_page):
                            print("[Patents] next_page action: clicked_page_number")
                            return True
                    except Exception:
                        continue

        # 3) Use href from paginator-like links.
        for sel in ("a.ui-paginator-next", "a.pi-paginator-next", "a[rel='next']", "a[href*='page=']", "a[href*='offset=']"):
            try:
                links = driver.find_elements(By.CSS_SELECTOR, sel)
            except Exception:
                links = []
            for lnk in links:
                try:
                    href = (lnk.get_attribute("href") or "").strip()
                    if not href:
                        continue
                    driver.get(href)
                    if _wait_for_advance(prev_url, prev_marker, prev_page):
                        print("[Patents] next_page action: href_navigation")
                        return True
                except Exception:
                    continue

        # 4) URL-based fallback increment.
        nxt = compute_next_url(prev_url)
        if nxt:
            try:
                driver.get(nxt)
                if _wait_for_advance(prev_url, prev_marker, prev_page):
                    print("[Patents] next_page action: url_increment")
                    return True
            except Exception:
                pass

        # Recovery path when paginator indicates more pages exist.
        cur = prev_state.get("current_page")
        tot = prev_state.get("total_pages")
        has_more = isinstance(cur, int) and isinstance(tot, int) and cur < tot
        if has_more:
            print(f"[Patents] recovery: paginator indicates more pages ({cur}/{tot})")

            # 1) Retry click-based next once with short wait.
            for sel in NEXT_SELECTORS:
                try:
                    btns = driver.find_elements(By.CSS_SELECTOR, sel)
                except Exception:
                    btns = []
                for btn in btns:
                    try:
                        if not btn.is_enabled():
                            continue
                        driver.execute_script("arguments[0].click();", btn)
                        if _wait_for_advance(prev_url, prev_marker, prev_page, timeout=8):
                            print(f"[Patents] next_page action: recovery_retry_click:{sel}")
                            return True
                    except Exception:
                        continue

            # 2) JSF PrimeFaces AJAX trigger from known next controls.
            for sel in (
                "a.js-paginator-next",
                "a[aria-label='Next Page']",
                "a[id^='resultListCommandsForm:'][aria-label='Next Page']",
                "a[id^='resultListForm:'][aria-label='Next Page']",
            ):
                try:
                    links = driver.find_elements(By.CSS_SELECTOR, sel)
                except Exception:
                    links = []
                for lnk in links:
                    try:
                        eid = (lnk.get_attribute("id") or "").strip()
                        if not eid:
                            continue
                        driver.execute_script(
                            """if (window.PrimeFaces && PrimeFaces.ab) {
                                PrimeFaces.ab({s: arguments[0], p: arguments[0], u: 'results-container @(.js-ps-global-messages)'});
                            }""",
                            eid,
                        )
                        if _wait_for_advance(prev_url, prev_marker, prev_page, timeout=10):
                            print(f"[Patents] next_page action: recovery_primefaces:{sel}")
                            return True
                    except Exception:
                        continue

            # 3) Retry page-number jump (current + 1) explicitly.
            cur_int = cur if isinstance(cur, int) else 0
            wanted = str(cur_int + 1)
            for sel in ("a.ui-paginator-page", "a.pi-paginator-page", "a", "[aria-label]"):
                try:
                    links = driver.find_elements(By.CSS_SELECTOR, sel)
                except Exception:
                    links = []
                for lnk in links:
                    try:
                        t = (lnk.text or "").strip()
                        if t != wanted:
                            continue
                        driver.execute_script("arguments[0].click();", lnk)
                        if _wait_for_advance(prev_url, prev_marker, prev_page, timeout=8):
                            print("[Patents] next_page action: recovery_page_number")
                            return True
                    except Exception:
                        continue

        print("[Patents] next_page action: next_click_no_change")
        if has_more:
            print("[Patents] paginator_desync_or_action_failed")
        return False

    def navigate_direct_results(company: str) -> None:
        # Build direct results URL to avoid brittle advanced UI steps
        company_clause = build_company_query(company.strip())
        params = {
            "query": company_clause,
            "perPage": "100",
            "sortBy": "DP",
        }
        result_url = (
            "https://patentscope.wipo.int/search/en/result.jsf?"
            + urlencode(params)
        )
        try:
            driver.get(result_url)
        except TimeoutException:
            pass

        # Accept cookies if present
        _click_if_present(
            driver,
            [
                "#onetrust-accept-btn-handler",
                "button#onetrust-accept-btn-handler",
                "button[data-testid='uc-accept-all-button']",
                'xpath=//button[contains(., "Accept All")]',
                'xpath=//button[contains(., "Accept")]',
                'xpath=//button[contains(., "Agree")]',
            ],
        )

    def navigate_generic_results(company: str) -> None:
        alias_list = COMPANY_ALIASES.get(company.strip(), [company.strip()])
        q = " OR ".join(f'"{a}"' for a in alias_list)
        params = {"query": q, "perPage": "100", "sortBy": "DP"}
        base = "https://patentscope.wipo.int/search/en/result.jsf?"
        url = base + urlencode(params)
        try:
            driver.get(url)
        except TimeoutException:
            pass
        _click_if_present(
            driver,
            [
                "#onetrust-accept-btn-handler",
                "button#onetrust-accept-btn-handler",
                "button[data-testid='uc-accept-all-button']",
                'xpath=//button[contains(., "Accept All")]',
                'xpath=//button[contains(., "Accept")]',
                'xpath=//button[contains(., "Agree")]',
            ],
        )

    def navigate_generic_results_keywords(company: str) -> None:
        alias_list = _aliases_for_company(company)
        q_alias = " OR ".join(f'"{a}"' for a in alias_list if str(a).strip())
        if not q_alias:
            q_alias = f'"{company.strip()}"'
        kw = '"Ophthalmology" OR Ophthalmic OR "Optical Coherence Tomography" OR Retina'
        query = f"PA:({q_alias}) AND ({kw})"
        # Use descending publication date so newest records are collected first.
        params = {"query": query, "perPage": "100", "sortBy": "-DP"}
        base = "https://patentscope.wipo.int/search/en/result.jsf?"
        url = base + urlencode(params)
        print(f"[Patents] Query: {query}")
        print(f"[Patents] Query URL: {url}")
        try:
            driver.get(url)
        except TimeoutException:
            pass
        _save_snapshot("after_query")
        _click_if_present(
            driver,
            [
                "#onetrust-accept-btn-handler",
                "button#onetrust-accept-btn-handler",
                "button[data-testid='uc-accept-all-button']",
                'xpath=//button[contains(., "Accept All")]',
                'xpath=//button[contains(., "Accept")]',
                'xpath=//button[contains(., "Agree")]',
            ],
        )
        set_per_page_100()
        _save_snapshot("after_per_page")

    def navigate_advanced_flow(company: str) -> None:
        url = "https://patentscope.wipo.int/search/en/advancedSearch.jsf"
        try:
            driver.get(url)
        except TimeoutException:
            pass

        # Cookie consent (best-effort)
        _click_if_present(
            driver,
            [
                "#onetrust-accept-btn-handler",
                "button#onetrust-accept-btn-handler",
                "button[data-testid='uc-accept-all-button']",
                'xpath=//button[contains(., "Accept All")]',
                'xpath=//button[contains(., "Accept")]',
                'xpath=//button[contains(., "Agree")]',
            ],
        )

        wait = WebDriverWait(driver, 15)
        try:
            search_bar = wait.until(
                EC.element_to_be_clickable(
                    (By.ID, "advancedSearchForm:advancedSearchInput:input")
                )
            )
        except TimeoutException:
            return
        search_bar.click()
        company_clause = build_company_query(company.strip())
        search_bar.send_keys(company_clause)

        try:
            button = driver.find_element(
                By.ID, "advancedSearchForm:searchButton"
            )
            button.click()
        except (NoSuchElementException, StaleElementReferenceException):
            try:
                search_bar.submit()
            except Exception:
                pass

        # Sort by publication date desc
        try:
            sort_select = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.ID, "resultListCommandsForm:sort:input")
                )
            )
            try:
                # JSF select can be brittle; try clicking option via JS
                driver.execute_script(
                    "var s=arguments[0]; s.value='-DP'; s.dispatchEvent("
                    "new Event('change'))",
                    sort_select,
                )
            except Exception:
                pass
        except TimeoutException:
            pass

        # Per page 100
        try:
            per_page = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.ID, "resultListCommandsForm:perPage:input")
                )
            )
            try:
                driver.execute_script(
                    "var s=arguments[0]; s.value='100'; s.dispatchEvent("
                    "new Event('change'))",
                    per_page,
                )
            except Exception:
                pass
        except TimeoutException:
            pass

    def scrape_pages() -> None:
        page_counter = 0
        older_floor_unknown_grace = 0
        while True:
            page_counter += 1
            info = collect_current_page()
            rows_count = int(info.get("rows", 0) or 0)
            added_count = int(info.get("added", 0) or 0)
            parsed_date_count = int(info.get("parsed_date_count", 0) or 0)
            unknown_date_count = int(info.get("unknown_date_count", 0) or 0)
            min_date_obj = info.get("min_date")
            max_date_obj = info.get("max_date")
            min_date_str = min_date_obj.strftime("%Y-%m-%d") if isinstance(min_date_obj, datetime) else ""
            max_date_str = max_date_obj.strftime("%Y-%m-%d") if isinstance(max_date_obj, datetime) else ""
            count_text = _result_count_text()
            if count_text:
                print(f"[Patents] Page {page_counter}: rows={rows_count}, added={added_count}, visible_count='{count_text}'")
            else:
                print(f"[Patents] Page {page_counter}: rows={rows_count}, added={added_count}, visible_count='(not found)'")
            pstate = _paginator_state()
            print(
                f"[Patents] Page {page_counter} paginator: "
                f"current_page={pstate.get('current_page')}, total_pages={pstate.get('total_pages')}"
            )
            print(
                f"[Patents] Page {page_counter} date_summary: "
                f"parsed_date_count={parsed_date_count}, "
                f"unknown_date_count={unknown_date_count}, "
                f"min_date={min_date_str or 'N/A'}, "
                f"max_date={max_date_str or 'N/A'}"
            )

            # Early stop when pages are entirely older than floor date.
            if parsed_date_count > 0 and isinstance(max_date_obj, datetime) and max_date_obj < effective_floor_dt:
                if unknown_date_count == 0:
                    print("[Patents] Stop reason: older_than_date_floor")
                    break
                older_floor_unknown_grace += 1
                if older_floor_unknown_grace >= 2:
                    print("[Patents] Stop reason: older_than_date_floor")
                    break
                print("[Patents] older_than_date_floor candidate (unknown dates present); allowing one extra page")
            else:
                older_floor_unknown_grace = 0

            if max_pages > 0 and page_counter > max_pages:
                print("[Patents] Stop reason: max_pages")
                break
            if not go_next_page():
                if _extract_result_count(count_text) > 100 and rows_count <= 10:
                    print("[Patents] ui_controls_not_advancing")
                _save_snapshot(f"next_fail_page_{page_counter}")
                print("[Patents] Stop reason: no_next_page")
                break

    try:
        # Single strategy: company + ophthalmic keywords.
        navigate_generic_results_keywords(companyString)
        scrape_pages()
    finally:
        driver.quit()

    print(
        "[Patents] Filter counters: "
        f"filtered_before_date_floor={filtered_before_date_floor}, "
        f"filtered_unparseable_date={filtered_unparseable_date}, "
        f"kept_items={kept_items}"
    )

    return Patents
