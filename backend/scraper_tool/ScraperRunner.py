import os
import ZeissScraper, OptoVueScraper, TopConScraper, CanonScraper, NidekScraper
import PatentScraper
import json

log = False
filename = "outputData.json"

CompetitorDataArray = { 'Competitor' : [] }

CompetitorDataArray['Competitor'].append(
    {
        'Name' : 'TopCon',
        'News' : TopConScraper.runNews(log)['News'],
        'Jobs' : TopConScraper.runJobs(log)['Jobs'],
        'Patents' : PatentScraper.runPatent("TopCon")['Patents']
    }
)

CompetitorDataArray['Competitor'].append(
    {
        'Name' : 'Zeiss',
        'News' : ZeissScraper.runNews(log)['News'],
        'Jobs' : ZeissScraper.runJobs(log)['Jobs'],
        'Patents' : PatentScraper.runPatent("Zeiss")['Patents']
    }
)

CompetitorDataArray['Competitor'].append(
    {
        'Name' : 'Canon',
        'News' : CanonScraper.runNews(log)['News'],
        'Jobs' : CanonScraper.runJobs(log)['Jobs'],
        'Patents' : PatentScraper.runPatent("Canon")['Patents']
    }
)

CompetitorDataArray['Competitor'].append(
    {
        'Name' : 'OptoVue',
        'News' : OptoVueScraper.runNews(log)['News'],
        'Jobs' : OptoVueScraper.runJobs(log)['Jobs'],
        'Patents' : PatentScraper.runPatent("OptoVue")['Patents']
    }
)

CompetitorDataArray['Competitor'].append(
    {
        'Name' : 'Nidek',
        'News' : NidekScraper.runNews(log)['News'],
        'Jobs' : NidekScraper.runJobs(log)['Jobs'],
        'Patents' : PatentScraper.runPatent("Nidek")['Patents']
    }
)

if os.path.exists(filename):
    os.remove(filename)
    
with open( filename , "w" ) as write:
    json.dump(CompetitorDataArray, write)