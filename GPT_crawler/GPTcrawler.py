import GPT_crawler_utils as GPT_crawler
from Embedder import Embedder
from openai import OpenAI
from dotenv import load_dotenv
import json
import pandas as pd

GPT_MAX_TOKENS = 30000
load_dotenv()
client = OpenAI()
embedder = Embedder(use_api='jina')

#base_url = "https://storiestogrowby.org/"
base_url = "https://www.freechildrenstories.com/"
#base_url = "https://www.storyberries.com/"

## Chunks and merge the website snapshot
excluded_selectors = [
    # Advertisements
    ".ads", ".ad", ".advertisement", ".sponsored", ".promo", ".banner-ad", ".google-ad", ".ad-container",
    # Sidebar and widgets
    ".sidebar", ".widget", ".widget-container", ".sidebar-content", ".related-posts", ".recommendations",
    ".tag-cloud", ".sidebar-widget", ".right-sidebar", ".left-sidebar",
    # Popups and modals
    ".modal", ".popup", ".overlay", ".pop-up", ".cookie-banner", ".consent-banner", ".alert",
    # Social media and sharing
    ".social", ".share", ".share-buttons", ".follow-us", ".social-links", ".social-widget", ".social-icons",
    # Other common non-content elements
    ".search", ".search-bar", ".search-box", ".contact-form", ".newsletter", ".subscribe", ".logo",
    ".branding", ".terms", ".privacy-policy", ".faq", ".site-map"
]
snapshot = GPT_crawler.get_text_snapshot(base_url, exclude_selector=excluded_selectors, links_at_end=True) # put links at the end for better crawling
snapshot_links = snapshot[snapshot.find("Links/Buttons:"):]

completion_category = GPT_crawler.find_available_content(snapshot_links)
categories = json.loads(completion_category.choices[0].message.content).get('categories', {})

### check correctness of the categories url
for category, category_url in categories.copy().items():
    if GPT_crawler.GPT_boolean(category_url, "Does this website contain > 10 stories (with title and urls)?"):
        print(f"The category '{category}' contains stories for kids.")
    else:
        print(f"The category '{category}' does not contain stories for kids.")
        del categories[category] 
print()

for category, category_url in categories.items():
    print(category)
    print(category_url)

## Get the titles and urls of the stories of each category
print("\nFetching titles and urls of the stories of each category...\n")
titles_and_urls = {}  
excluded_selectors_title = excluded_selectors
send_full_page = False # whether send full page to the model
for category, category_url in categories.items():
    print(f"Category: {category}\nURL: {category_url}\n")
    page = 0
    next_page = category_url
    cached_snapshot = None  # Cache the valid snapshot

    while next_page:
        page += 1
        print(f"[Page: {page}]")

        # Fetch or reuse snapshot
        if cached_snapshot and cached_snapshot.get("url") == next_page:
            snapshot = cached_snapshot["snapshot"]
        else:
            snapshot = f"{GPT_crawler.get_text_snapshot(next_page, exclude_selector=excluded_selectors, links_at_end=True)}\nCurrent Page Number: {page}" # This might help the model to stop at the end of the page
            cached_snapshot = None  # Reset cache

        snapshot_links = snapshot[snapshot.find("Links/Buttons:"):]

        if not send_full_page:
            completion_titles = GPT_crawler.get_titles_and_urls(snapshot_links)
        else:
            completion_titles = GPT_crawler.get_titles_and_urls(snapshot)

        titles_and_urls_list = json.loads(completion_titles.choices[0].message.content).get('titles_and_urls', [])
        
        ## if the crawled content is empty, try to crawl the full page
        if not titles_and_urls_list and not send_full_page:
            print("Empty content. Setting send_full_page to True and retrying...")
            send_full_page = True
            page -= 1
            continue # restart the loop with full page mode

        for title_and_url in titles_and_urls_list:
            title = title_and_url.get('title', "")
            url = title_and_url.get('url', "")
            titles_and_urls[title] = (url, category)
            print(f"{title}: {titles_and_urls[title]}")

        next_page = json.loads(completion_titles.choices[0].message.content).get('next_page', "")
        ## validate the next page exists
        query = f"the current page is {page}, does this page have a link to next page or page {page+1}?"
        snapshot = f"{GPT_crawler.get_text_snapshot(next_page, exclude_selector=excluded_selectors, links_at_end=True)}\nCurrent Page Number: {page}" # This might help the model to stop at the end of the page
        if GPT_crawler.GPT_boolean(snapshot, query):
            cached_snapshot = {"url": next_page, "snapshot": snapshot}
        else:
            print(f"Next page does not exist.")
            next_page = ""

        print(f"Next page: {next_page}")

stories = {}

for title, (url, category) in titles_and_urls.items():
    print(f"Title: {title}")
    print(f"Category: {category}")
    print(f"URL: {url}")
    print("")
    completion = GPT_crawler.get_content(url)
    try:
        content = json.loads(completion.choices[0].message.content).get('content', {})
        next_page = json.loads(completion.choices[0].message.content).get('next_page', "") # should be empty
    except Exception as e:
        print(f"Error while fetching story content: {e}")
        print(completion)
        content = {}
        next_page = ""

    stories[title] = content

df = pd.DataFrame(stories).T
df.to_csv('stories.csv')
