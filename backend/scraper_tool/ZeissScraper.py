import time
import os
import re
from datetime import datetime, timezone
from typing import Any, List, Optional, Dict
from urllib.parse import urljoin
import requests # Still needed for the new runJobs

# Use Playwright
from playwright.sync_api import (
    sync_playwright,
    Page,
    Locator,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
)

# --- Date logic from your original file, simplified ---
START_DATE = datetime(datetime.now(timezone.utc).year - 1, 1, 1, tzinfo=timezone.utc)

def _normalize_date(raw: Optional[str]) -> str:
    """
    Normalize a raw date string to an ISO-8601 date string (YYYY-MM-DD).
    """
    if not raw:
        return ""
    raw = raw.strip()

    # Try ISO directly (from <time datetime="...">)
    try:
        s = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.date().isoformat()
    except Exception:
        pass

    # Known formats (from your HTML: "Oct 07, 2025")
    fmts = [
        "%b %d, %Y", "%B %d, %Y", "%Y-%m-%d", "%d %B %Y",
        "%d %b %Y", "%d.%m.%Y", "%Y.%m.%d", "%Y/%m/%d", "%d/%m/%Y",
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.date().isoformat()
        except Exception:
            continue
    
    # Try ISO-like prefix
    try:
        if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
            dt = datetime.strptime(raw[:10], "%Y-%m-%d")
            return dt.date().isoformat()
    except Exception:
        pass
    
    return raw # Return original if parsing failed

def _to_datetime(value: Any) -> Optional[datetime]:
    """
    Best-effort conversion of a string to a timezone-aware datetime in UTC.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    
    iso_date = _normalize_date(s)
    if iso_date != s: # If normalization worked
        try:
            dt = datetime.fromisoformat(iso_date)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    
    # Try isoformat directly for full timestamps
    try:
        s2 = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s2)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass
        
    return None
# --- End Date Logic ---


def runNews(log: bool = False, since_dt: Optional[datetime] = None):
    """
    Fetches news from Zeiss, rewritten with Playwright for reliability.
    Scrapes all data from the list page, no N+1 loop needed.
    """
    newsUrl = "https://www.zeiss.com/meditec-ag/en/media-news/press-releases.html"
    BASE_URL = "https://www.zeiss.com/"
    
    NewsArticles: Dict[str, List[Dict[str, str]]] = {"News": []}
    seen_urls = set()

    headful_env = str(os.environ.get("SCRAPER_HEADFUL", "")).strip()
    if headful_env in ("1", "true", "True", "yes", "YES"):
        headful = True
    elif headful_env in ("0", "false", "False", "no", "NO"):
        headful = False
    else:
        # Preserve existing behavior for Zeiss: headless by default.
        headful = False

    try:
        slow_mo_ms = int(str(os.environ.get("SCRAPER_SLOWMO_MS", "0") or "0").strip())
    except Exception:
        slow_mo_ms = 0
    if slow_mo_ms < 0:
        slow_mo_ms = 0

    keep_open_on_error = str(os.environ.get("SCRAPER_KEEP_OPEN_ON_ERROR", "")).strip() in ("1", "true", "True", "yes", "YES")
    had_error = False
    try:
        debug_max_pages = int(str(os.environ.get("SCRAPER_DEBUG_MAX_PAGES", "0") or "0").strip())
    except Exception:
        debug_max_pages = 0

    # --- SELECTORS BASED ON YOUR HTML ---
    ARTICLE_ROW_SELECTORS = [
        "a[href*='/media-news/press-releases/']",
        "a.article-teaser-item__content-link",
        "article a.article-teaser-item__content-link",
        "article a[href*='/media-news/']",
    ]
    TITLE_SELECTORS = [
        ".headline__main span",
        ".headline__main",
        ".article-teaser-item__headline",
    ]
    DATE_SELECTOR = ".article-teaser-item__eyebrow span"
    EMPTY_STATE_SELECTORS = [
        ".no-results",
        ".search-results--empty",
        "[data-testid='no-results']",
    ]
    # ------------------------------------
    
    NEXT_SELECTORS = [
        "a[rel='next']", "a.pagination__next", "button[aria-label='Next']",
        "a.next", ".pagination .next a", "a.page-link-next",
        "a:has-text('Next')", "a.pi-paginator-next", "a.ui-paginator-next",
    ]

    print("[Zeiss News] Starting Playwright...")
    print(f"[Zeiss News] Debug mode: {'headed' if headful else 'headless'}, slow_mo={slow_mo_ms}ms, keep_open_on_error={keep_open_on_error}")
    if debug_max_pages > 0:
        print(f"[Zeiss News] Debug page limit enabled: max_pages={debug_max_pages}")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not headful,
            slow_mo=slow_mo_ms,
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
        )
        context.set_default_timeout(30000)  # 30-second timeout for all actions
        page = context.new_page()

        try:
            print(f"[Zeiss News] Loading list page: {newsUrl}")
            page.goto(newsUrl, wait_until="domcontentloaded")

            # --- Click cookie reject/consent if present ---
            cookie_clicked = False
            try:
                cookie_button_selector = "#onetrust-reject-all-handler"
                page.locator(cookie_button_selector).click(timeout=10000)
                cookie_clicked = True
                print("[Zeiss News] Clicked 'Technically necessary' (cookie reject) button.")
                page.wait_for_selector(cookie_button_selector, state="hidden", timeout=5000)
            except PlaywrightTimeoutError:
                print("[Zeiss News] No cookie consent found, proceeding.")
            except Exception as e:
                print(f"[Zeiss News] Error clicking cookie banner: {e}")
            print(f"[Zeiss News] Cookie action taken: {cookie_clicked}")

            # Wait for either articles OR explicit empty state.
            article_ready = False
            empty_ready = False
            try:
                page.wait_for_function(
                    """({articleSelectors, emptySelectors}) => {
                        const hasArticle = articleSelectors.some((s) => !!document.querySelector(s));
                        const hasEmpty = emptySelectors.some((s) => !!document.querySelector(s));
                        return hasArticle || hasEmpty;
                    }""",
                    arg={"articleSelectors": ARTICLE_ROW_SELECTORS, "emptySelectors": EMPTY_STATE_SELECTORS},
                    timeout=20000,
                )
            except PlaywrightTimeoutError:
                body_text = (page.locator("body").inner_text() or "").strip()
                if len(body_text) > 200:
                    raise RuntimeError("selector_changed: Zeiss list page loaded but no article/empty selector appeared")
                print("[Zeiss News] Page appears blank and no selectors appeared; returning empty.")
                return NewsArticles

            matched_article_selector = None
            for sel in ARTICLE_ROW_SELECTORS:
                if page.locator(sel).count() > 0:
                    matched_article_selector = sel
                    article_ready = True
                    break

            for sel in EMPTY_STATE_SELECTORS:
                if page.locator(sel).count() > 0:
                    empty_ready = True
                    break

            print(f"[Zeiss News] Matched article selector: {matched_article_selector}")
            print(f"[Zeiss News] Empty state detected: {empty_ready}")

            if not article_ready and empty_ready:
                print("[Zeiss News] Explicit empty state found; returning empty news.")
                return NewsArticles
            if not article_ready:
                raise RuntimeError("selector_changed: Zeiss page has content but article selector did not match")
            
            page_counter = 0
            
            while True:
                page_counter += 1
                print(f"[Zeiss News] Scraping page {page_counter}...")
                if debug_max_pages > 0 and page_counter > debug_max_pages:
                    print(f"[Zeiss News] Reached debug max pages ({debug_max_pages}). Stopping early.")
                    break

                # Wait for rows to exist
                try:
                    page.wait_for_selector(matched_article_selector, timeout=15000)
                except PlaywrightTimeoutError:
                    print("[Zeiss News] Timeout waiting for article list.")
                    break # Stop if no articles are found
                
                rows = page.locator(matched_article_selector).all()
                if not rows:
                    print("[Zeiss News] No article rows found on this page.")
                    break
                
                prev_first_text = ""
                for tsel in TITLE_SELECTORS:
                    try:
                        prev_first_text = (rows[0].locator(tsel).first.text_content() or "").strip()
                        if prev_first_text:
                            break
                    except Exception:
                        continue

                dates_on_page: List[datetime] = []
                new_items_on_page = 0
                
                for el in rows:
                    try:
                        href = (el.get_attribute("href") or "").strip()
                        url = urljoin(BASE_URL, href)

                        if not url or url in seen_urls:
                            continue
                        
                        title = ""
                        for tsel in TITLE_SELECTORS:
                            try:
                                title = (el.locator(tsel).first.text_content() or "").strip()
                                if title:
                                    break
                            except Exception:
                                continue
                        if not title:
                            try:
                                title = (el.text_content() or "").strip()
                            except Exception:
                                title = ""
                        if not title:
                            continue
                        raw_date = ""
                        try:
                            raw_date = (el.locator(DATE_SELECTOR).first.text_content() or "").strip()
                        except Exception:
                            raw_date = ""

                        if not raw_date:
                            try:
                                # pull potential date text from closest card/container
                                nearby = el.evaluate(
                                    """(node) => {
                                        const p = node.closest('li, article, div, section');
                                        return p ? (p.innerText || '') : (node.innerText || '');
                                    }"""
                                ) or ""
                                m = re.search(r"([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}|\d{1,2}[./]\d{1,2}[./]\d{4}|\d{4}-\d{2}-\d{2})", nearby)
                                if m:
                                    raw_date = m.group(1)
                            except Exception:
                                pass

                        if not raw_date:
                            # URL fallback, e.g. /2025/08-12-2025.html
                            m2 = re.search(r"(\d{2})-(\d{2})-(\d{4})", url)
                            if m2:
                                mm, dd, yyyy = m2.group(1), m2.group(2), m2.group(3)
                                raw_date = f"{yyyy}-{mm}-{dd}"

                        date_str = _normalize_date(raw_date)
                        dt = _to_datetime(date_str)

                        if dt:
                            dates_on_page.append(dt)
                        
                        # Include items by cutoff when provided; otherwise include all parseable dated items.
                        if dt is not None and ((since_dt is not None and dt >= since_dt) or (since_dt is None)):
                            if log:
                                print(f"[Zeiss News] Found: {title} ({date_str})")
                            NewsArticles["News"].append({
                                "Headline": title,
                                "URL": url,
                                "Date": date_str,
                            })
                            seen_urls.add(url)
                            new_items_on_page += 1

                    except Exception as e:
                        print(f"[Zeiss News] Error parsing one article card: {e}")
                        continue
                
                print(f"[Zeiss News] Found {new_items_on_page} new items on page {page_counter}.")

                # Stop if all dates on the page are older than our start date
                if dates_on_page and all(d < START_DATE for d in dates_on_page):
                    print("[Zeiss News] All articles on page are older than start date. Stopping.")
                    break

                # --- Paginate ---
                print("[Zeiss News] Checking for 'Next' button...")
                found_btn = None
                for sel in NEXT_SELECTORS:
                    btns = page.locator(sel).all()
                    for btn in btns:
                        try:
                            if btn.is_visible() and btn.is_enabled():
                                classes = btn.get_attribute("class") or ""
                                if "disabled" not in classes.lower() and "ui-state-disabled" not in classes.lower():
                                    found_btn = btn
                                    break
                        except Exception:
                            continue
                    if found_btn:
                        print(f"[Zeiss News] 'Next' button found with selector '{sel}', clicking...")
                        break
                
                if not found_btn:
                    print("[Zeiss News] No more pages available.")
                    break

                # Click and wait for content to change (AJAX-aware)
                try:
                    found_btn.scroll_into_view_if_needed()
                    found_btn.click(timeout=10000)
                    
                    print("[Zeiss News] Waiting for page content to update...")
                    page.wait_for_function(
                        """({ expectedText, articleSelector, titleSelectors }) => {
                            try {
                                const firstRow = document.querySelector(articleSelector);
                                if (!firstRow) return false;
                                let newText = "";
                                for (const s of titleSelectors) {
                                    const t = firstRow.querySelector(s);
                                    if (t && t.textContent) { newText = t.textContent.trim(); if (newText) break; }
                                }
                                return newText !== expectedText && newText !== "";
                            } catch (e) { return false; }
                        }""",
                        arg={
                            "expectedText": prev_first_text,
                            "articleSelector": matched_article_selector,
                            "titleSelectors": TITLE_SELECTORS,
                        },
                        timeout=20000
                    )
                    print("[Zeiss News] Page content updated.")
                except Exception as e:
                    print(f"[Zeiss News] Pagination failed: {e}. Stopping.")
                    break # Stop pagination

        except PlaywrightTimeoutError:
            had_error = True
            print("[Zeiss News] Page timed out. Returning partial results.")
        except Exception as e:
            had_error = True
            print(f"[Zeiss News] A critical error occurred: {e}")
            raise
        finally:
            if had_error and keep_open_on_error:
                try:
                    print("[Zeiss News] Debug hold enabled; keeping browser open for 60s...")
                    time.sleep(60)
                except Exception:
                    pass
            browser.close()
            print("[Zeiss News] Browser closed.")

    return NewsArticles


def runJobs(log: bool = False, since_dt: Optional[datetime] = None):
    """
    Fetches jobs from LinkedIn using the new URL.
    Attempts to fix geo-localization by setting locale.
    """
    # --- THIS IS YOUR NEW URL ---
    jobsUrl = "https://www.linkedin.com/jobs/search/?currentJobId=4333549264&f_C=938659%2C6556%2C18251391%2C6555%2C9262284%2C5264505&geoId=92000000&origin=COMPANY_PAGE_JOBS_CLUSTER_EXPANSION&originToLandingJobPostings=4333549264%2C4317593522%2C4332994407%2C4333084561%2C4334255041%2C4318232664%2C4317582624%2C4337965940%2C4318245168"
    # ----------------------------

    JobPostings = {'Jobs': []}

    print("[Zeiss Jobs] Starting Playwright for LinkedIn...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # --- FIX FOR BRAZIL PROBLEM ---
        # Set locale and timezone to request US/English content
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
            java_script_enabled=True,
            accept_downloads=False,
            locale="en-US",
            timezone_id="America/New_York"
        )
        # ------------------------------
        
        context.set_default_timeout(30000) # 30-second timeout
        page = context.new_page()

        try:
            print(f"[Zeiss Jobs] Loading LinkedIn page: {jobsUrl}")
            page.goto(jobsUrl, wait_until="domcontentloaded")

            # Try to click away the sign-in modal.
            try:
                page.locator(
                    '[data-tracking-control-name="public_jobs_contextual-sign-in-modal_modal_dismiss"]'
                ).click(timeout=5000)
                print("[Zeiss Jobs] Clicked modal dismiss button.")
            except PlaywrightTimeoutError:
                print("[Zeiss Jobs] No sign-in modal found, proceeding.")

            # Check for "No Results" banner
            noResults = page.locator(".jobs-search-no-results-banner__image").count()
            if noResults > 0:
                print("[Zeiss Jobs] No jobs found.")
                browser.close()
                return JobPostings

            # Find all job cards
            jobElements = page.locator(".base-search-card").all()
            print(f"[Zeiss Jobs] Found {len(jobElements)} job cards.")

            for element in jobElements:
                try:
                    jobTitle = (element.locator(".base-search-card__title").text_content() or "").strip()
                    jobUrl = (element.locator("a.base-card__full-link").get_attribute("href") or "").strip()
                    
                    if jobTitle and jobUrl:
                        JobPostings['Jobs'].append({
                            'Job Title': jobTitle,
                            'URL': jobUrl,
                        })
                except Exception:
                    continue # Skip broken card

        except PlaywrightTimeoutError:
            print("[Zeiss Jobs] Page timed out (Likely blocked by LinkedIn).")
        except Exception as e:
            print(f"[Zeiss Jobs] A critical error occurred: {e}")
        finally:
            browser.close()
            print("[Zeiss Jobs] Browser closed.")

    if log:
        for job in JobPostings['Jobs']:
            print(f"Job: {job['Job Title']}. URL: {job['URL']}")
    
    return JobPostings


if __name__ == "__main__":
    
    print("--- [TEST RUN] Starting ZeissScraper.py directly ---")
    
    print("\n--- Testing runNews ---")
    news_results = runNews(log=True)
    news_count = len(news_results.get('News', []))
    print(f"--- runNews finished. Found {news_count} news articles. ---")
    if news_count > 0:
        print(f"Example: {news_results['News'][0]}")

    print("\n--- Testing runJobs ---")
    jobs_results = runJobs(log=True)
    jobs_count = len(jobs_results.get('Jobs', []))
    print(f"--- runJobs finished. Found {jobs_count} job postings. ---")
    if jobs_count > 0:
        print(f"Example: {jobs_results['Jobs'][0]}")
    
    print(f"\n--- [TEST RUN] Complete ---")
    print(f"Total News: {news_count}")
    print(f"Total Jobs: {jobs_count}")
