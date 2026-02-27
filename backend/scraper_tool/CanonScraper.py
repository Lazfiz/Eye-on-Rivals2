import re
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
)

def _normalize_date(date_text: str) -> str:
    """
    Parses a 'Month DD, YYYY' date string and returns 'YYYY-MM-DD'.
    """
    if not date_text:
        return ""
    try:
        # The date is like 'July 25, 2025'
        cleaned_text = date_text.split("|")[0].strip()
        dt = datetime.strptime(cleaned_text, "%B %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return date_text # Return original on failure

def runNews(log=False, since_dt: Optional[datetime] = None) -> Dict[str, List[Dict[str, str]]]:
    """
    Fetches news from Canon, rewritten with Playwright for reliability.
    """
    current_year = datetime.now().year
    urls_to_check = [
        f"https://us.medical.canon/news/press-releases/{current_year}/",
        f"https://us.medical.canon/news/press-releases/{current_year - 1}/",
    ]
    NewsArticles = {'News': []}
    seen_urls = set() # To prevent duplicates if an article appears on multiple pages
    
    print("[Canon News] Starting Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True # --- DEBUGGING OFF ---
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
        )
        context.set_default_timeout(30000)
        page = context.new_page()

        try:
            for url in urls_to_check:
                print(f"[Canon News] Loading list page: {url}")
                page.goto(url, wait_until="domcontentloaded")
                print("[Canon News] No cookie banner, proceeding.")
                
                # --- START OF FIX: Using your new selectors ---
                # This is more specific: finds a div.col-sm-8 that *contains* a h2.header-link
                ARTICLE_CARD_SELECTOR = "div.col-sm-8:has(h2.header-link)" 
                TITLE_LINK_SELECTOR = "h2.header-link a"
                DATE_SELECTOR = "p:first-of-type"
                # --- END OF FIX ---
                
                articleElements = page.locator(ARTICLE_CARD_SELECTOR).all()
                print(f"[Canon News] Found {len(articleElements)} article cards on this page.")

                for element in articleElements:
                    try:
                        titleEl = element.locator(TITLE_LINK_SELECTOR).first 
                        headline = (titleEl.text_content() or "").strip()
                        articleUrl = (titleEl.get_attribute("href") or "").strip()
                        
                        if not articleUrl or articleUrl in seen_urls:
                            continue # Skip if no URL or already seen

                        dateEl = element.locator(DATE_SELECTOR).first 
                        raw_date = (dateEl.text_content() or "").strip()
                        date_str = _normalize_date(raw_date)

                        if headline and articleUrl:
                            try:
                                if not date_str:
                                    continue
                                dt_item = datetime.fromisoformat(date_str.split("T")[0])
                                if since_dt is not None:
                                    # Incremental mode: only include items on/after cutoff date
                                    if dt_item.date() < since_dt.date():
                                        continue
                                else:
                                    # Full mode: do not hard-cap by year.
                                    pass
                            except Exception:
                                # If parsing fails, skip to keep guarantees
                                continue

                            NewsArticles['News'].append({
                                'Headline': headline,
                                'URL': articleUrl,  # URLs are already absolute
                                'Date': date_str
                            })
                            seen_urls.add(articleUrl)
                    except Exception as e:
                        # This will no longer hang, but might fail if an element is weird
                        print(f"[Canon News] Failed to parse an article card: {e}")
                        continue
                
            print(f"[Canon News] Successfully scraped {len(NewsArticles['News'])} total articles.")

        except PlaywrightTimeoutError:
            print("[Canon News] Page timed out. Returning partial results.")
        except Exception as e:
            print(f"[Canon News] A critical error occurred: {e}")
        finally:
            browser.close()
            print("[Canon News] Browser closed.")

    if log:
        for article in NewsArticles['News']:
            print(f"Article on {article['Date']}: {article['Headline']}. URL: {article['URL']}")

    return NewsArticles


def runJobs(log=False, since_dt: Optional[datetime] = None):
    """
    Fetches jobs from LinkedIn, rewritten with Playwright.
    """
    jobsUrl = "https://www.linkedin.com/jobs/search/?f_C=27157455&geoId=92000000"
    JobPostings = {'Jobs': []}

    print("[Canon Jobs] Starting Playwright for LinkedIn...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) # Jobs can run headless
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
            java_script_enabled=True,
            accept_downloads=False,
            locale="en-US", # Anti-geolocation fix
            timezone_id="America/New_York"
        )
        context.set_default_timeout(30000)
        page = context.new_page()

        try:
            print(f"[Canon Jobs] Loading LinkedIn page: {jobsUrl}")
            page.goto(jobsUrl, wait_until="domcontentloaded")

            try:
                page.locator(
                    '[data-tracking-control-name="public_jobs_contextual-sign-in-modal_modal_dismiss"]'
                ).click(timeout=5000)
                print("[Canon Jobs] Clicked modal dismiss button.")
            except PlaywrightTimeoutError:
                print("[Canon Jobs] No sign-in modal found, proceeding.")

            noResults = page.locator(".jobs-search-no-results-banner__image").count()
            if noResults > 0:
                print("[Canon Jobs] No jobs found.")
                browser.close()
                return JobPostings

            jobElements = page.locator(".base-search-card").all()
            print(f"[Canon Jobs] Found {len(jobElements)} job cards.")

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
            print("[Canon Jobs] Page timed out (Likely blocked by LinkedIn).")
        except Exception as e:
            print(f"[Canon Jobs] A critical error occurred: {e}")
        finally:
            browser.close()
            print("[Canon Jobs] Browser closed.")

    if log:
        for job in JobPostings['Jobs']:
            print(f"Job: {job['Job Title']}. URL: {job['URL']}")
    
    return JobPostings

if __name__ == "__main__":
    
    print("--- [TEST RUN] Starting CanonScraper.py directly ---")
    
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
