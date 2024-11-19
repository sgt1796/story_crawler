import GPT_crawler_utils as GPT_crawler
from openai import OpenAI
from dotenv import load_dotenv
import json
import pandas as pd

load_dotenv()
client = OpenAI()

base_url = "https://storiestogrowby.org/"

completion_category = GPT_crawler.find_available_content(base_url)
categories = json.loads(completion_category.choices[0].message.content).get('categories', {})

### check correctness of the categories url
for category, category_url in categories.copy().items():
    if GPT_crawler.GPT_boolean(category_url, "Does this website contain > 10 stories (with title and urls)?"):
        print(f"The category '{category}' contains stories for kids.")
    else:
        print(f"The category '{category}' does not contain stories for kids.")
        del categories[category]


for category, category_url in categories.items():
    print(category)
    print(category_url)


titles_and_urls = {}  

for category, category_url in categories.items():
    completion_titles = GPT_crawler.get_titles_and_urls(category_url)
    titles_and_urls_json = json.loads(completion_titles.choices[0].message.content).get('titles_and_urls', {})
    print(f"Category: {category}")
    
    for title, url in titles_and_urls_json.items():
        titles_and_urls[title] = (url, category)
        print(f"{title}: {titles_and_urls[title]}")
    print("")

stories = {}
for title, (url, category) in titles_and_urls.items():
    print(f"Title: {title}")
    print(f"Category: {category}")
    print(f"URL: {url}")
    print("")
    completion = GPT_crawler.get_content(url)
    content = json.loads(completion.choices[0].message.content).get('content', {})
    next_page = json.loads(completion.choices[0].message.content).get('next_page', "") # should be empty

    stories[title] = content

df = pd.DataFrame(stories).T
df.to_csv('stories.csv')