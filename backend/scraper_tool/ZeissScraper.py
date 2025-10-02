from datetime import datetime
from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
import time

def runNews(log=False) :

    ## Constants and Gubbins
    newsUrl = "https://www.zeiss.com/corporate/en/about-zeiss/present/newsroom/press-releases.html?f_page=1&"
    NewsArticles = { 'News' : [] }

    ## Setup the invisible chrome tab
    options = ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(options)
    
    ##Connet to the URL and find everything, then wait
    driver.get(newsUrl)
    driver.implicitly_wait(5)
    button = driver.find_element(By.ID, value="onetrust-reject-all-handler")
    time.sleep(2)
    button.click()
    time.sleep(2)

    articleElements = driver.find_elements(By.CLASS_NAME, value="article-teaser-item__content")

    for element in articleElements:
        articleName = element.find_element(By.CLASS_NAME, value="headline__main")
        articleDate = element.find_element(By.CLASS_NAME, value="article-teaser-item__eyebrow--sub-without-main ")
        dateString = datetime.strptime(articleDate.text, "%b %d, %Y")
        dateString = dateString.strftime("%d/%m/%Y")
        articleUrl = element.find_element(By.CSS_SELECTOR, '[href]').get_attribute("href")
        NewsArticles['News'].append({
            'Headline' : articleName.text,
            'URL' : articleUrl,
            'Date' : dateString
        })

    if(log):
        for article in NewsArticles['News']:
            print(f"Article on {article['Date']}: {article['Headline']}. URL: {article['URL']}")
    
    driver.quit()
    return NewsArticles

def runJobs(log=False):
    jobsUrl = "https://www.linkedin.com/jobs/search/?currentJobId=4298878773&f_C=6555&geoId=92000000&origin=JOB_SEARCH_PAGE_JOB_FILTER"

    JobPostings = { 'Jobs' : [] }

    ## Setup the invisible chrome tab
    options = ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(options)
    
    ##Connet to the URL and find everything, then wait
    driver.get(jobsUrl)
    driver.implicitly_wait(5)
    button = driver.find_element(By.CSS_SELECTOR, value='[data-tracking-control-name="public_jobs_contextual-sign-in-modal_modal_dismiss"]')
    button.click()

    noResults = driver.find_elements(By.CLASS_NAME, value="jobs-search-no-results-banner__image")

    if len(noResults) == 0:          
        jobElements = driver.find_elements(By.CLASS_NAME, value="base-search-card")

        for element in jobElements:
            jobTitle = element.find_element(By.CLASS_NAME, value="base-search-card__title")
            jobUrl = element.find_element(By.CSS_SELECTOR, '[href]').get_attribute("href")
            JobPostings['Jobs'].append({
                'Job Title' : jobTitle.text,
                'URL' : jobUrl,
            })

        if(log):
            for job in JobPostings['Jobs']:
                print(f"Job: {job['Job Title']}. URL: {job['URL']}")
    
    driver.quit()
    return JobPostings