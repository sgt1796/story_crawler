import requests
from bs4 import BeautifulSoup
import pandas as pd

url_base = 'http://www.oesz.cn/'
categories = {'睡前故事': url_base + 'shuiqian/',
              '童话故事': url_base + 'tonghua/',
              '寓言故事': url_base + 'yuyan/',
              '成语故事': url_base + 'chengyu/',
              '哲理故事': url_base + 'zheli/',
              '故事大全': url_base + 'gushidaquan/',}

## 除了每个故事的链接，还需要保存每个故事的分类
## 所以格式为: {'story title': （'url/to/story', 'category') }
titles_dict = {}
recent_dict = {}
ignore = ['睡前小故事', '童话故事', '寓言故事', '成语故事', '哲理故事', '安徒生童话故事', '格林童话故事', '一千零一夜故事', '公主的故事', '随意分享小故事', '故事大全']

for category in categories:
    print(f"Category: {category}")
    
    url = categories[category]
    response = requests.get(url)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')

    suffix = url.strip('/').split('/')[-1]

    ## 如果是故事大全，则suffix为"a"
    if category == '故事大全':
        suffix = 'a'
    titles = soup.find_all('a', href=lambda x: x and x.startswith(f'/{suffix}/'))

    index = soup.find_all('a', href=lambda x: x and x.startswith(f'list_'))

    ## 爬取标题和链接
    for title in titles:
        if title.text.strip() in ignore:
            continue
        titles_dict[title.text.strip()] = (url_base + title['href'][1:], category)

    ## 爬取下一页链接
    next_page = None
    for i in index:
        if i.get_text().strip() == "下一页":
            next_page = i['href']
            break
    next_page = url + next_page

    # 如果最新发布区的故事已经在titles_dict里，则不再重复添加
    if not recent_dict:
        print("No recent stories")
        recent = soup.find('span', string='最新发布').find_all_next('a', href=lambda x: x and x.endswith('.html'))
        recent_dict = {}
        for title in recent:
            recent_suffix = title['href'].split('/')[-2]
            if title.text in ignore or recent_suffix != suffix:
                continue
            titles_dict[title.text.strip()] = (url_base + title['href'][1:], category)
            recent_dict[title.text.strip()] = (url_base + title['href'][1:], category)

    ## Step 4: 循环爬取下一页
    page_number = 2
    while True:
        if page_number % 10 == 0:
            print(f"Page {page_number}")
        ## 重复Step 1-3
        ## Step 1
        response = requests.get(next_page)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        ## Step 2.1
        suffix = url.strip('/').split('/')[-1]
        titles = soup.find_all('a', href=lambda x: x and x.startswith(f'/{suffix}/'))
        ## Step 2.2
        index = soup.find_all('a', href=lambda x: x and x.startswith(f'list_'))

        ## Step 3: crawling the titles and links
        for title in titles:
            ## 如果标题在ignore里或者在recent_dict里，则跳过
            if title.text.strip() in ignore or title.text.strip() in recent_dict.keys():
                continue
            titles_dict[title.text.strip()] = (url_base + title['href'][1:], category)

        next_page = None
        for i in index:
            if i.get_text().strip() == "下一页":
                next_page = i['href']
                break
        
        ## 当下一页为空时, 退出循环
        if not next_page:
            break
            
        next_page = url + next_page
        page_number += 1

print(f"Obtained {len(titles_dict)} story urls.")

print("Text crawling start.")
data = [(name, info[0], info[1]) for name, info in titles_dict.items()]
df = pd.DataFrame(data, columns=['name', 'url', 'category'])
empty_count = 0
for i, row in df.iterrows():
    if i % 20 == 0 and i != 0:
        print(f"{i} Stories processed")
    url = row["url"]
    response = requests.get(url)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')
    ## 从网页中提取故事内容
    content = soup.find('div', class_='content').text.rstrip().replace('\r', '').replace('\u3000', '')
    df.loc[i, 'content'] = content
print("Text crawling complete. Saving to file")

df.to_csv('stories_cn_oesz.csv', index=False)