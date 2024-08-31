import requests
from bs4 import BeautifulSoup

url = 'http://www.wpwx.cn/news/tonghua/'
response = requests.get(url)
response.encoding = 'gbk'
soup = BeautifulSoup(response.text, 'html.parser')

stories = soup.find_all('a', href=lambda x: x and x.startswith('/news/tonghua/'))
ignore = ['童话故事', '中国童话故事']

titles = {}
index = {}
page_number = 1
while page_number == 1 or next_page is not None:
    print('Page:', page_number)

    isIndex = False
    for story in stories:
        text = story.get_text().strip()
        if text in ignore:
            print('Ignoring:', text)
            continue
        if text.isdigit():
            isIndex = True
            if text not in index:
                index[text] = 'http://www.wpwx.cn' + story['href']
        else:
            if text not in titles:
                titles[text] = 'http://www.wpwx.cn' + story['href']
    
        # exit after reading the indexes
        if isIndex and not text.isdigit():
            break

        #print(text)
        #print('http://www.wpwx.cn' + story['href'])

    # print(index.values())
    page_number += 1
    next_page = index.get(str(page_number))

    if next_page is None or page_number > 1000:
        break

    response = requests.get(next_page)
    response.encoding = 'gbk'
    soup = BeautifulSoup(response.text, 'html.parser')

    stories = soup.find_all('a', href=lambda x: x and x.startswith('/news/tonghua/'))