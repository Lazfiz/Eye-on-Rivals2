import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urljoin
# --- NO PLAYWRIGHT IMPORT HERE ---

BASE_URL = "https://topconhealthcare.eu/"

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
    # --- FIX: Import Playwright AND OS INSIDE the function ---
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    import os
    # -------------------------------------------------

    url = "https://topconhealthcare.eu/en_UK/news"
    LIST_SELECTOR = ".c-card"
    TITLE_DETAIL_SELECTOR = "h1.c-hero__title"
    NewsArticles = {'News': []}
    seen_urls = set()

    headful_env = str(os.environ.get("SCRAPER_HEADFUL", "")).strip()
    if headful_env in ("0", "false", "False", "no", "NO"):
        headful = False
    elif headful_env in ("1", "true", "True", "yes", "YES"):
        headful = True
    else:
        # Default to headless unless explicitly debugging.
        headful = False

    try:
        slow_mo_ms = int(str(os.environ.get("SCRAPER_SLOWMO_MS", "0") or "0").strip())
    except Exception:
        slow_mo_ms = 0
    if slow_mo_ms < 0:
        slow_mo_ms = 0

    keep_open_on_error = str(os.environ.get("SCRAPER_KEEP_OPEN_ON_ERROR", "")).strip() in ("1", "true", "True", "yes", "YES")
    had_error = False
    
    if log: print("[TopCon News] Starting Playwright...")
    if log: print(f"[TopCon News] Debug mode: {'headed' if headful else 'headless'}, slow_mo={slow_mo_ms}ms, keep_open_on_error={keep_open_on_error}")
    
    user_data_dir = r"C:\dev\hackathon\eye-on-rivals-profile"
    if log: print(f"[TopCon News] Using scraper-specific profile: {user_data_dir}")

    context = None 

    def _safe_back_to_list(page) -> None:
        """Best-effort return to list page without breaking loop."""
        try:
            current_url = (page.url or "").strip().rstrip("/").lower()
        except Exception:
            current_url = ""
        target_url = url.rstrip("/").lower()

        try:
            if current_url and current_url != target_url:
                if log: print("[TopCon News] Recovering to list via go_back()...")
                page.go_back(wait_until="domcontentloaded", timeout=10000)
            if page.locator(LIST_SELECTOR).count() == 0:
                if log: print("[TopCon News] List selector missing, reloading list URL...")
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector(LIST_SELECTOR, timeout=10000)
        except Exception:
            if log: print("[TopCon News] Recovery fallback: hard reload list URL.")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector(LIST_SELECTOR, timeout=10000)

    try:
        with sync_playwright() as p:
            if log: print("[TopCon News] Launching PERSISTENT Edge (msedge)...")
            
            context = p.chromium.launch_persistent_context(
                user_data_dir,
                headless=not headful,
                channel="msedge",
                slow_mo=slow_mo_ms,
                
                # "Human" arguments
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
                locale="en-GB",
                timezone_id="Europe/London"
            )
            
            # --- Stealth script to hide "navigator.webdriver" ---
            stealth_script = """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            """
            context.add_init_script(stealth_script)
            # --- END ---
            
            context.set_default_timeout(30000)
            context.set_default_navigation_timeout(30000) 
            
            page = context.pages[0] if context.pages else context.new_page()
            if log: print("[TopCon News] Browser/context launched.")

            if log: print(f"[TopCon News] Loading list page: {url}")
            page.goto(url, wait_until="domcontentloaded")
            
            try:
                cookie_button_selector = "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll"
                page.locator(cookie_button_selector).click(timeout=10000)
                if log: print("[TopCon News] Clicked 'Allow all cookies' button.")
                if log: print("[TopCon News]   (This cookie is now saved in the scraper profile.)")
            except PlaywrightTimeoutError:
                if log: print("[TopCon News] Cookie banner not found (already accepted).")

            
            ARTICLE_CARD_SELECTOR = LIST_SELECTOR
            
            # --- NEW LOGIC: Get count first ---
            try:
                page.wait_for_selector(ARTICLE_CARD_SELECTOR, timeout=10000)
                num_articles = page.locator(ARTICLE_CARD_SELECTOR).count()
                if log: print(f"[TopCon News] Found {num_articles} article cards.")
            except PlaywrightTimeoutError:
                if log: print("[TopCon News] No article cards found on page. Exiting.")
                return NewsArticles
            # --- END NEW LOGIC ---

            # --- NEW LOOP: Iterate by index and CLICK ---
            for i in range(num_articles):
                try:
                    # We re-find the locators each time to avoid stale elements
                    article_locators = page.locator(ARTICLE_CARD_SELECTOR)
                    article_to_click = article_locators.nth(i)
                    
                    link_to_click = article_to_click.locator("a[href]").first
                    
                    # Get href for de-duping and for the final JSON
                    href = (link_to_click.get_attribute("href") or "").strip()
                    if not href:
                        if log: print(f"[TopCon News] Article {i} has no href, skipping.")
                        continue
                        
                    article_url = resolve_url(href).rstrip("/").lower()
                    
                    if article_url in seen_urls:
                        if log: print(f"[TopCon News] Article {i} is a duplicate, skipping.")
                        continue
                    seen_urls.add(article_url)

                    if log: print(f"[TopCon News] Clicking article {i+1}/{num_articles}: {article_url}")
                    
                    link_to_click.click()
                    
                    # Wait for the new page to load by looking for its title
                    page.wait_for_selector(TITLE_DETAIL_SELECTOR, timeout=10000)

                    headline = ""
                    try:
                        titleEl = page.locator("h1.c-hero__title").first
                        headline = (titleEl.text_content(timeout=5000) or "").strip()
                        if not headline:
                           if log: print(f"[TopCon News] Page missing title. Skipping.")
                           _safe_back_to_list(page)
                           continue
                    except PlaywrightTimeoutError:
                         if log: print(f"[TopCon News] Page missing title (timeout). Skipping.")
                         _safe_back_to_list(page)
                         continue

                    raw_date = ""
                    date_str = ""
                    try:
                        dateEl = page.locator("time").first
                        raw_date = (dateEl.get_attribute("datetime", timeout=5000) or dateEl.text_content(timeout=5000) or "").strip()
                        date_str = _normalize_date(raw_date)
                    except PlaywrightTimeoutError:
                        if log: print(f"[TopCon News] Page '{headline}' is missing a <time> date element. Skipping.")
                        _safe_back_to_list(page)
                        continue
                    
                    try:
                        if not date_str:
                            if log: print(f"[TopCon News] Skipping - no date found.")
                            _safe_back_to_list(page)
                            continue
                        dt_item = datetime.fromisoformat(date_str.split("T")[0])
                        
                        if since_dt is not None:
                            if dt_item.date() < since_dt.date():
                                if log: print(f"[TopCon News] Skipping - older than cutoff.")
                                _safe_back_to_list(page)
                                continue
                        else:
                            pass

                    except Exception:
                        if log: print(f"[TopCon News] Skipping - could not parse date {date_str}.")
                        _safe_back_to_list(page)
                        continue
                    
                    if log: print(f"[TopCon News]   ... SUCCESS. Adding article '{headline}'")
                    NewsArticles['News'].append({
                        'Headline': headline,
                        'URL': article_url,
                        'Date': date_str
                    })
                    
                    # --- FIX: GO BACK ON SUCCESS ---
                    if log: print(f"[TopCon News] Going back to news list...")
                    _safe_back_to_list(page)
                    # --- END FIX ---
                
                except PlaywrightTimeoutError:
                    if log: print(f"[TopCon News] Timeout clicking/loading article {i}. This page is slow or broken. Skipping.")
                    if log: print(f"[TopCon News] (Timeout) recovering to list...")
                    _safe_back_to_list(page)
                except Exception as e:
                    if log: print(f"[TopCon News] Error processing article {i}: {e}")
                    if log: print(f"[TopCon News] (Exception) recovering to list...")
                    _safe_back_to_list(page)
                
                # --- FIX: REMOVED THE FINALLY BLOCK ---

            if log: print(f"[TopCon News] Successfully scraped {len(NewsArticles['News'])} articles.")

    except PlaywrightTimeoutError as e: # Catching specific Playwright errors
        had_error = True
        print(f"[TopCon News] A Playwright operation failed or timed out: {e}")
    except KeyboardInterrupt:
        print("[TopCon News] Script interrupted by user (Ctrl+C). Stopping.")
    except Exception as e:
        had_error = True
        print(f"[TopCon News] A critical error occurred: {e}")
    finally:
        if had_error and keep_open_on_error:
            try:
                print("[TopCon News] Debug hold enabled; keeping browser open for 60s...")
                time.sleep(60)
            except Exception:
                pass
        if log: print("[TopCon News] Cleanup starting...")
        if context:
            try:
                context.close()
                if log: print("[TopCon News] Cleanup success: Browser Context closed.")
            except Exception as e:
                msg = str(e or "")
                if "Event loop is closed" in msg:
                    if log: print("[TopCon News] Cleanup skipped: Playwright loop already stopped.")
                else:
                    if log: print(f"[TopCon News] Cleanup skipped due to close error: {e}")
        else:
            if log: print("[TopCon News] Context was not initialized, nothing to close.")

    return NewsArticles

def runJobs(log=False, since_dt: Optional[datetime] = None):
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

    # This function is unchanged.
    jobsUrl = "https://www.linkedin.com/jobs/search/?f_C=65268002&geoId=92000000"
    JobPostings = {'Jobs': []}

    if log: print("[TopCon Jobs] Starting Playwright for LinkedIn...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # --- ADDED LOCALE FIX (Anti-Brazil fix) ---
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
            java_script_enabled=True,
            accept_downloads=False,
            locale="en-US", 
            timezone_id="America/New_York"
        )
        # ------------------------------------------
        
        context.set_default_timeout(30000) 
        page = context.new_page()

        try:
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
                browser.close()
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
            browser.close()
            if log: print("[TopCon Jobs] Browser closed.")

    if log:
        for job in JobPostings['Jobs']:
            print(f"Job: {job['Job Title']}. URL: {job['URL']}")
    
    return JobPostings


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
