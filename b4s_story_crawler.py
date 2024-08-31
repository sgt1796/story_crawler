import requests
from bs4 import BeautifulSoup

url = 'http://www.wpwx.cn/news/tonghua/'
response = requests.get(url)
response.encoding = 'gbk'
soup = BeautifulSoup(response.text, 'html.parser')

stories = soup.find_all('a', href=lambda x: x and x.startswith('/news/tonghua/'))
ignore = ['童话故事', '中国童话故事']
isIndex = False

title = {}
index = {}
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
        if text not in title:
            title[text] = 'http://www.wpwx.cn' + story['href']
    
    # exit after reading the indexes
    if text.isdigit() and isIndex:
        break

    print(text)
    print('http://www.wpwx.cn' + story['href'])
