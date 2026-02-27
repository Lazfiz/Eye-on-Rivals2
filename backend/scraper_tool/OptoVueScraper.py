import time
import re
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
    Parses a complex date string and returns YYYY-MM-DD.
    Handles "Sep 11, 2025 3:26:52 PM" and "2025-Sep-11".
    """
    if not date_text:
        return ""
    
    date_text = date_text.strip()
    
    # Format 1: "Sep 11, 2025 3:26:52 PM" (from text content)
    try:
        # We need to handle the time and AM/PM
        dt = datetime.strptime(date_text, "%b %d, %Y %I:%M:%S %p")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
        
    # Format 2: "2025-Sep-11" (from datetime attribute)
    try:
        dt = datetime.strptime(date_text, "%Y-%b-%d")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    
    # Format 3: ISO '2025-09-11...'
    try:
        # Handle the junk 'PT2M' by splitting at 'T'
        dt = datetime.fromisoformat(date_text.split("T")[0])
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    return "" # Return empty if nothing matched


def runNews(log=False, since_dt: Optional[datetime] = None) -> Dict[str, List[Dict[str, str]]]:
    """
    Fetches news from Visionix (OptoVue), rewritten with Playwright.
    This version uses the correct N+1 logic and date parsing.
    """
    url = "https://blog.visionix.com/en-us/visionix-news-blog"
    NewsArticles = {'News': []}
    articles_to_visit = []  # Store just the URLs
    seen_urls = set()  # Deduplicate appended results
    
    if log: print("[OptoVue News] Starting Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
        )
        context.set_default_timeout(30000)
        page = context.new_page()

        try:
            # --- Block the axept.io cookie banner ---
            if log: print("[OptoVue News] Setting up network block for axept.io...")
            page.route(re.compile(r".*axept\.io.*"), 
                       lambda route: route.abort())
            # ----------------------------------------

            if log: print(f"[OptoVue News] Loading list page: {url}")
            page.goto(url, wait_until="domcontentloaded")
            if log: print("[OptoVue News] Page loaded. Cookie banner should be blocked.")
            
            ARTICLE_CARD_SELECTOR = ".blog__listing-item"
            LINK_SELECTOR = "a.post__link"
            
            page.wait_for_selector(ARTICLE_CARD_SELECTOR, timeout=15000)
            
            articleElements = page.locator(ARTICLE_CARD_SELECTOR).all()
            if log: print(f"[OptoVue News] Found {len(articleElements)} article cards.")

            if not articleElements:
                if log: print("[OptoVue News] No articles found.")

            # --- LOOP 1: Get all the links ---
            for element in articleElements:
                try:
                    linkEl = element.locator(LINK_SELECTOR).first
                    href = (linkEl.get_attribute("href") or "").strip()
                    if href:
                        articles_to_visit.append(href)
                except Exception as e:
                    if log: print(f"[OptoVue News] Failed to find link in card: {e}")
                    
            if log: print(f"[OptoVue News] Found {len(articles_to_visit)} articles to visit.")

            # --- LOOP 2: Visit each page to get Title and Date ---
            for article_url in articles_to_visit:
                try:
                    if log: print(f"[OptoVue News] Visiting: {article_url}")
                    page.goto(article_url, wait_until="domcontentloaded")
                    
                    titleEl = page.locator("h1.post__title").first
                    headline = (titleEl.text_content() or "").strip()
                    
                    # --- THIS IS THE FIX ---
                    # Find the date <time> tag *inside* the .post__body
                    postBody = page.locator(".post__body").first
                    timeEl = postBody.locator("time").first
                    
                    # Prioritize the visible text, fall back to the attribute
                    raw_date = (timeEl.text_content() or timeEl.get_attribute("datetime") or "").strip()
                    # ---------------------
                    
                    date_str = _normalize_date(raw_date)

                    if headline and article_url:
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
                            # If the date cannot be parsed reliably, skip to keep guarantees
                            continue

                        if article_url not in seen_urls:
                            NewsArticles['News'].append({
                                'Headline': headline,
                                'URL': article_url,
                                'Date': date_str
                            })
                            seen_urls.add(article_url)
                except Exception as e:
                    if log: print(f"[OptoVue News] Failed to scrape article detail page: {e}")
                    continue # Skip this article
            
            if log: print(f"[OptoVue News] Successfully scraped {len(NewsArticles['News'])} articles.")

        except PlaywrightTimeoutError:
            print("[OptoVue News] Page timed out. Returning partial results.")
        except Exception as e:
            print(f"[OptoVue News] A critical error occurred: {e}")
        finally:
            browser.close()
            if log: print("[OptoVue News] Browser closed.")

    return NewsArticles


def runJobs(log=False, since_dt: Optional[datetime] = None):
    jobsUrl = "https://www.linkedin.com/jobs/search/?f_C=18006916&geoId=92000000"
    JobPostings = {'Jobs': []}

    if log: print("[OptoVue Jobs] Starting Playwright for LinkedIn...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
            java_script_enabled=True,
            accept_downloads=False,
            locale="en-US", 
            timezone_id="America/New_York"
        )
        context.set_default_timeout(30000) 
        page = context.new_page()

        try:
            if log: print(f"[OptoVue Jobs] Loading LinkedIn page: {jobsUrl}")
            page.goto(jobsUrl, wait_until="domcontentloaded")

            try:
                page.locator(
                    '[data-tracking-control-name="public_jobs_contextual-sign-in-modal_modal_dismiss"]'
                ).click(timeout=5000)
                if log: print("[OptoVue Jobs] Clicked modal dismiss button.")
            except PlaywrightTimeoutError:
                if log: print("[OptoVue Jobs] No sign-in modal found, proceeding.")

            noResults = page.locator(".jobs-search-no-results-banner__image").count()
            if noResults > 0:
                if log: print("[OptoVue Jobs] No jobs found.")
                browser.close()
                return JobPostings

            jobElements = page.locator(".base-search-card").all()
            if log: print(f"[OptoVue Jobs] Found {len(jobElements)} job cards.")

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
            print("[OptoVue Jobs] Page timed out (Likely blocked by LinkedIn).")
        except Exception as e:
            print(f"[OptoVue Jobs] A critical error occurred: {e}")
        finally:
            browser.close()
            if log: print("[OptoVue Jobs] Browser closed.")
    
    return JobPostings

if __name__ == "__main__":
    
    print("--- [TEST RUN] Starting OptoVueScraper.py directly ---")
    
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
