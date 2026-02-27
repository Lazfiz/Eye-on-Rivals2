import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urljoin

# Use Playwright, same as PatentScraper
from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
)

def _normalize_date(date_text: str) -> str:
    """
    Parses a 'YYYY/MM/DD' date string and returns 'YYYY-MM-DD'.
    """
    if not date_text:
        return ""
    try:
        # Original format was YYYY/MM/DD
        dt = datetime.strptime(date_text.strip(), "%Y/%m/%d")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return date_text # Return original on failure

def runNews(log: bool = False, since_dt: Optional[datetime] = None) -> Dict[str, List[Dict[str, str]]]:
    """
    Fetches news from Nidek, rewritten with Playwright for reliability.
    Checks current and previous year to fill the date window.
    If since_dt is provided, only items with Date >= since_dt (by date) are included.
    """
    current_year = datetime.now().year
    # Check current and previous year to keep coverage fresh.
    base_url = "https://www.nidek-intl.com/news/"
    urls_to_check = [
        f"https://www.nidek-intl.com/news/?term={current_year}&cate=news",
        f"https://www.nidek-intl.com/news/?term={current_year - 1}&cate=news",
    ]
    NewsArticles: Dict[str, List[Dict[str, str]]] = {'News': []}
    seen_urls = set()

    if log: print("[Nidek News] Starting Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
        )
        context.set_default_timeout(30000)  # 30 seconds
        page = context.new_page()

        try:
            for url in urls_to_check:
                if log: print(f"[Nidek News] Loading list page: {url}")
                page.goto(url, wait_until="domcontentloaded")
                
                articleElements = page.locator(".news_post").all()
                if log: print(f"[Nidek News] Found {len(articleElements)} article elements on this page.")

                # This site is great, all info is on the list page.
                for element in articleElements:
                    try:
                        articleName = (element.locator(".txt_bk").text_content() or "").strip()
                        articleDate = (element.locator(".txt_bl").text_content() or "").strip()
                        articleUrl = (element.get_attribute("href") or "").strip()
                        
                        articleUrl = urljoin(base_url, articleUrl)
                        
                        if not articleUrl or articleUrl in seen_urls:
                            continue
                            
                        date_str = _normalize_date(articleDate)

                        if articleName and articleUrl:
                            # Incremental filter: include only if newer than/equal to cutoff when provided
                            try:
                                if since_dt is not None:
                                    if not date_str:
                                        continue
                                    dt_item = datetime.fromisoformat(date_str.split("T")[0])
                                    if dt_item.date() < since_dt.date():
                                        continue
                            except Exception:
                                # If cutoff provided but date cannot be parsed, skip to avoid duplicates
                                if since_dt is not None:
                                    continue
                            NewsArticles['News'].append({
                                'Headline': articleName,
                                'URL': articleUrl,
                                'Date': date_str
                            })
                            seen_urls.add(articleUrl)
                    except Exception as e:
                        if log: print(f"[Nidek News] Failed to parse an article card: {e}")
                        continue # Skip this card

            if log: print(f"[Nidek News] Successfully scraped {len(NewsArticles['News'])} total articles.")

        except PlaywrightTimeoutError:
            print("[Nidek News] Page timed out. Returning partial results.")
        except Exception as e:
            print(f"[Nidek News] A critical error occurred: {e}")
        finally:
            browser.close()
            if log: print("[Nidek News] Browser closed.")

    return NewsArticles


def runJobs(log: bool = False, since_dt: Optional[datetime] = None):
    """
    Fetches jobs from LinkedIn, rewritten with Playwright.
    """
    jobsUrl = "https://www.linkedin.com/jobs/search/?f_C=81583865,1341117,84005,80954639,7798625&geoId=92000000"
    JobPostings = {'Jobs': []}

    if log: print("[Nidek Jobs] Starting Playwright for LinkedIn...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
            java_script_enabled=True,
            accept_downloads=False,
            locale="en-US", 
            timezone_id="America/New_York"
        )
        
        context.set_default_timeout(30000) # 30 seconds
        page = context.new_page()

        try:
            if log: print(f"[Nidek Jobs] Loading LinkedIn page: {jobsUrl}")
            page.goto(jobsUrl, wait_until="domcontentloaded")

            try:
                page.locator(
                    '[data-tracking-control-name="public_jobs_contextual-sign-in-modal_modal_dismiss"]'
                ).click(timeout=5000)
                if log: print("[Nidek Jobs] Clicked modal dismiss button.")
            except PlaywrightTimeoutError:
                if log: print("[Nidek Jobs] No sign-in modal found, proceeding.")

            noResults = page.locator(".jobs-search-no-results-banner__image").count()
            if noResults > 0:
                if log: print("[Nidek Jobs] No jobs found.")
                browser.close()
                return JobPostings

            jobElements = page.locator(".base-search-card").all()
            if log: print(f"[Nidek Jobs] Found {len(jobElements)} job cards.")

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
            print("[Nidek Jobs] Page timed out (Likely blocked by LinkedIn).")
        except Exception as e:
            print(f"[Nidek Jobs] A critical error occurred: {e}")
        finally:
            browser.close()
            if log: print("[Nidek Jobs] Browser closed.")
    
    return JobPostings

if __name__ == "__main__":
    
    print("--- [TEST RUN] Starting NidekScraper.py directly ---")
    
    print("\n--- Testing runNews ---")
    news_results = runNews(log=False) # Set log=False for a cleaner test
    news_count = len(news_results.get('News', []))
    print(f"--- runNews finished. Found {news_count} news articles. ---")
    if news_count > 0:
        print(f"Example: {news_results['News'][0]}")

    print("\n--- Testing runJobs ---")
    jobs_results = runJobs(log=True) # Keep log=True for this test
    jobs_count = len(jobs_results.get('Jobs', []))
    print(f"--- runJobs finished. Found {jobs_count} job postings. ---")
    if jobs_count > 0:
        print(f"Example: {jobs_results['Jobs'][0]}")
    
    print(f"\n--- [TEST RUN] Complete ---")
    print(f"Total News: {news_count}")
    print(f"Total Jobs: {jobs_count}")
