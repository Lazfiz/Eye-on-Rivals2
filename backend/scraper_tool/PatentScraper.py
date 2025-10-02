from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
import time
from datetime import datetime

def runPatent(companyString):
    # Setup headless Chrome
    options = ChromeOptions()
    options.add_argument("--headless=new")
    driver = webdriver.Chrome(options)
    
    Patents = {'Patents': []}

    try:
        url = "https://patentscope.wipo.int/search/en/advancedSearch.jsf"
        driver.get(url)

        wait = WebDriverWait(driver, 15)

        # Search input
        searchBar = wait.until(EC.element_to_be_clickable((By.ID, "advancedSearchForm:advancedSearchInput:input")))
        searchBar.click()
        searchString = f"FP:{companyString} AND EN_AB:(Optometry OR Ophthalmology)"
        searchBar.send_keys(searchString)

        # Submit search
        button = driver.find_element(By.ID, "advancedSearchForm:searchButton")
        button.click()

        # Try to adjust sorting and per-page, but ignore failures if DOM differs
        try:
            filterDate = wait.until(EC.presence_of_element_located((By.ID, "resultListCommandsForm:sort:input")))
            Select(filterDate).select_by_value("-DP")
        except Exception:
            pass

        try:
            filterPerPage = wait.until(EC.presence_of_element_located((By.ID, "resultListCommandsForm:perPage:input")))
            Select(filterPerPage).select_by_value("100")
        except Exception:
            pass

        # Wait for results and collect a few
        wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "ps-patent-result--first-row")))
        elements = driver.find_elements(By.CLASS_NAME, "ps-patent-result--first-row")

        for element in elements[:5]:
            try:
                patentName = element.find_element(By.CLASS_NAME, "needTranslation-title")
                patentUrl = element.find_element(By.CSS_SELECTOR, "[href]").get_attribute("href")
                patentDateEl = element.find_element(By.CSS_SELECTOR, "[id$=resultListTableColumnPubDate]")

                date_text = patentDateEl.text.strip()
                date_dt = None
                for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
                    try:
                        date_dt = datetime.strptime(date_text, fmt)
                        break
                    except ValueError:
                        continue
                if date_dt is None:
                    date_string = date_text
                else:
                    date_string = date_dt.strftime("%d/%m/%Y")

                Patents['Patents'].append({
                    'Title': patentName.text,
                    'URL': patentUrl,
                    'Date': date_string,
                })
            except Exception:
                continue
    finally:
        driver.quit()

    return Patents