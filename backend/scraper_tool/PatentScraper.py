import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE_URL = "https://topconhealthcare.eu/"

# ... (_normalize_date and resolve_url are unchanged) ...
def _normalize_date(date_text: str) -> str:
    if not date_text: return ""
    date_text = date_text.strip()
    try:
        dt = datetime.fromisoformat(date_text.split("T")[0])
        return dt.strftime("%Y-%m-%d")
    except Exception: pass
    try:
        dt = datetime.strptime(date_text.strip(), "%B %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""

def resolve_url(href: str) -> str:
    return urljoin(BASE_URL, href.strip()) if href else ""


def runNews(log=False, since_dt: Optional[datetime] = None):
    url = "https://topconhealthcare.eu/en_UK/news"
    NewsArticles = {'News': []}
    articles_to_visit = []
    seen_urls = set()
    
    # --- KEY CHANGE: Print log *before* any Playwright code ---
    if log: print("[TopCon News] Worker started. Initializing Playwright...")
    
    browser = None
    
    # --- KEY CHANGE: Move 'with sync_playwright()' INSIDE the try block ---
    try:
        with sync_playwright() as p:
            if log: print("[TopCon News] Starting Playwright browser...")
            browser = p.chromium.launch(
                headless=True,
                timeout=60000 
            )
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
            )
            context.set_default_timeout(30000)
            page = context.new_page()

            if log: print(f"[TopCon News] Loading list page: {url}")
            page.goto(url, wait_until="domcontentloaded")
            
            try:
                cookie_button_selector = "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll"
                page.locator(cookie_button_selector).click(timeout=10000)
                if log: print("[TopCon News] Clicked 'Allow all cookies' button.")
                page.wait_for_selector(cookie_button_selector, state="hidden", timeout=5000)
            except PlaywrightTimeoutError:
                if log: print("[TopCon News] Cookie banner not found or already clicked.")
            except Exception as e:
                if log: print(f"[TopCon News] Error clicking cookie banner: {e}")

            
            ARTICLE_CARD_SELECTOR = ".c-card"
            articleElements = page.locator(ARTICLE_CARD_SELECTOR).all()
            if log: print(f"[TopCon News] Found {len(articleElements)} article cards.")

            for element in articleElements:
                try:
                    linkEl = element.locator("a[href]").first
                    href = (linkEl.get_attribute("href") or "").strip()
                    if href:
                        full = resolve_url(href).rstrip("/").lower()
                        if full and full not in seen_urls:
                            seen_urls.add(full)
                            articles_to_visit.append(full)
                except Exception as e:
                    if log: print(f"[TopCon News] Error parsing card, skipping: {e}")
                    continue

            if log: print(f"[TopCon News] Found {len(articles_to_visit)} unique articles to visit.")

            for article_url in articles_to_visit:
                try:
                    if log: print(f"[TopCon News] Visiting: {article_url}")
                    page.goto(article_url, wait_until="domcontentloaded")
                    
                    titleEl = page.locator("h1.c-hero__title").first
                    headline = (titleEl.text_content() or "").strip()

                    dateEl = page.locator("time").first
                    raw_date = (dateEl.get_attribute("datetime") or dateEl.text_content() or "").strip()
                    date_str = _normalize_date(raw_date)
                    
                    try:
                        if not date_str:
                            if log: print(f"[TopCon News] Skipping - no date found.")
                            continue
                        dt_item = datetime.fromisoformat(date_str.split("T")[0])
                        if since_dt is not None:
                            if dt_item.date() < since_dt.date():
                                if log: print(f"[TopCon News] Skipping - older than cutoff.")
                                continue
                        else:
                            pass
                    except Exception:
                        if log: print(f"[TopCon News] Skipping - could not parse date {date_str}.")
                        continue
                    
                    NewsArticles['News'].append({
                        'Headline': headline,
                        'URL': article_url,
                        'Date': date_str
                    })
                
                except PlaywrightTimeoutError:
                    if log: print(f"[TopCon News] Timeout visiting {article_url}")
                    continue
                except Exception as e:
                    if log: print(f"[TopCon News] Error getting details for {article_url}: {e}")
                    continue
            
            if log: print(f"[TopCon News] Successfully scraped {len(NewsArticles['News'])} articles.")

    except PlaywrightTimeoutError as e:
        print(f"[TopCon News] A Playwright operation timed out: {e}")
    except Exception as e:
        print(f"[TopCon News] A critical error occurred: {e}")
    finally:
        if browser:
            browser.close()
            if log: print("[TopCon News] Browser closed.")
        else:
            if log: print("[TopCon News] Browser was not initialized, nothing to close.")

    return NewsArticles


def runJobs(log=False, since_dt: Optional[datetime] = None):
    jobsUrl = "https://www.linkedin.com/jobs/search/?f_C=65268002&geoId=92000000"
    JobPostings = {'Jobs': []}

    # --- KEY CHANGE: Print log *before* any Playwright code ---
    if log: print("[TopCon Jobs] Worker started. Initializing Playwright for LinkedIn...")
    
    browser = None
    
    # --- KEY CHANGE: Move 'with sync_playwright()' INSIDE the try block ---
    try:
        with sync_playwright() as p:
            if log: print("[TopCon Jobs] Starting Playwright browser...")
            browser = p.chromium.launch(
                headless=True,
                timeout=60000
            )
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
                java_script_enabled=True,
                accept_downloads=False,
                locale="en-US", 
                timezone_id="America/New_York"
            )
            
            context.set_default_timeout(30000) 
            page = context.new_page()

            if log: print(f"[TopCon Jobs] Loading LinkedIn page: {jobsUrl}")
            page.goto(jobsUrl, wait_until="domcontentloaded")

            try:
                page.locator('[data-tracking-control-name="public_jobs_contextual-sign-in-modal_modal_dismiss"]').click(timeout=5000)
                if log: print("[TopCon Jobs] Clicked modal dismiss button.")
            except PlaywrightTimeoutError:
                if log: print("[TopCon Jobs] No sign-in modal found, proceeding.")

            noResults = page.locator(".jobs-search-no-results-banner__image").count()
            if noResults > 0:
                if log: print("[TopCon Jobs] No jobs found.")
                browser.close() # Close browser before returning
                return JobPostings

            jobElements = page.locator(".base-search-card").all()
            if log: print(f"[TopCon Jobs] Found {len(jobElements)} job cards.")

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
                    continue 

    except PlaywrightTimeoutError:
        print("[TopCon Jobs] Page timed out (Likely blocked by LinkedIn).")
    except Exception as e:
        print(f"[TopCon Jobs] A critical error occurred: {e}")
    finally:
        if browser:
            browser.close()
            if log: print("[TopCon Jobs] Browser closed.")
        else:
            if log: print("[TopCon Jobs] Browser was not initialized, nothing to close.")

    if log and len(JobPostings['Jobs']) > 0:
        for job in JobPostings['Jobs']:
            print(f"Job: {job['Job Title']}. URL: {job['URL']}")
    
    return JobPostings


def _date_from_patent_item(item: Dict[str, str]) -> Optional[datetime]:
    raw = str(item.get("Date") or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def runPatent(companyString: str, since_dt: Optional[datetime] = None) -> Dict[str, List[Dict[str, str]]]:
    """
    Stable entrypoint expected by ScraperRunner.
    Delegates to the backup implementation and applies optional incremental filtering.
    """
    from PatentScraperBackup import runPatent as _run_patent_backup

    data = _run_patent_backup(companyString, since_dt=since_dt)
    items = data.get("Patents", []) if isinstance(data, dict) else []
    if not isinstance(items, list):
        items = []

    if since_dt is None:
        return {"Patents": [x for x in items if isinstance(x, dict)]}

    # Safety pass aligned with backup's dynamic overlap floor.
    safety_floor = since_dt - timedelta(days=30)

    out: List[Dict[str, str]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        dt = _date_from_patent_item(it)
        if dt is None or dt.date() >= safety_floor.date():
            out.append(it)
    return {"Patents": out}


if __name__ == "__main__":
    
    print("--- [TEST RUN] Starting TopConScraper.py directly ---")
    
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
