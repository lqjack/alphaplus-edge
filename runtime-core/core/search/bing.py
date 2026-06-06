import requests
from bs4 import BeautifulSoup
import json
import logging
logger = logging.getLogger(__name__)
# 设置请求头
headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Sec-Fetch-Site': 'same-origin',
    'Cookie': 'SNRHOP=I=&TS=; MUIDB=2A5F21D302E860DB214732DD033A6161; _RwBf=r=0&ilt=2763&ihpd=1&ispd=11&rc=200&rb=200&gb=0&rg=0&pc=200&mtu=0&rbb=0&g=0&cid=&clo=0&v=4&l=2025-02-20T08:00:00.0000000Z&lft=0001-01-01T00:00:00.0000000&aof=0&o=0&p=&c=&t=0&s=0001-01-01T00:00:00.0000000+00:00&ts=2025-02-20T15:08:18.7249396+00:00&rwred=0&wls=&wlb=&lka=0&lkt=0&TH=&aad=0&ccp=&wle=&ard=0001-01-01T00:00:00.0000000&rwdbt=0&rwflt=0&cpt=&mta=0&e=&A=5F4D81B3177B2A64C5BA5D4BFFFFFFFF&rwaul2=0; SRCHHPGUSR=SRCHLANG=zh-Hans&IG=01E05CD4D22448E79421C775249F552D&DM=1&BRW=N&BRH=S&CW=1247&CH=339&SCW=1247&SCH=339&DPR=2.0&UTC=480&EXLTT=31&HV=1740064099&WTS=63875619414&BZA=0&PRVCW=1247&PRVCH=695&WEBTHEME=1&HVE=CfDJ8GtUudZcSi1Enm88WwQKtCfPclU4l8FSRv7IuGb6U8wajsDV1X82Xr66sA-FJB_pLPHW9BhJtdE646hZmPE3i1Zqxje7isBj7LprfceelMU1mGM0PtV5jkBIn_3z0orXrTQL3vz-w6EKko1Nc7BDgcEloqCwdc6sTJKI_OC4G8XI; _Rwho=u=d&ts=2025-02-20; _SS=PC=APMC&SID=0D07063EAF34690034D313A7AEE66833&R=200&RB=200&GB=0&RG=0&RP=200; ipv6=hit=1740067697771&t=4; SRCHUSR=DOB=20250212&T=1740064092000&POEX=W; _HPVN=CS=eyJQbiI6eyJDbiI6OSwiU3QiOjAsIlFzIjowLCJQcm9kIjoiUCJ9LCJTYyI6eyJDbiI6OSwiU3QiOjAsIlFzIjowLCJQcm9kIjoiSCJ9LCJReiI6eyJDbiI6OSwiU3QiOjAsIlFzIjowLCJQcm9kIjoiVCJ9LCJBcCI6dHJ1ZSwiTXV0ZSI6dHJ1ZSwiTGFkIjoiMjAyNS0wMi0yMFQwMDowMDowMFoiLCJJb3RkIjowLCJHd2IiOjAsIlRucyI6MCwiRGZ0IjpudWxsLCJNdnMiOjAsIkZsdCI6MCwiSW1wIjoyOSwiVG9ibiI6MH0=; _UR=QS=0&TQS=0&Pn=0; USRLOC=HS=1&ELOC=LAT=22.510589599609375|LON=113.90779113769531|N=%E5%8D%97%E5%B1%B1%E5%8C%BA%EF%BC%8C%E5%B9%BF%E4%B8%9C%E7%9C%81|ELT=4|; ANON=A=5F4D81B3177B2A64C5BA5D4BFFFFFFFF&E=1edd&W=1; KievRPSSecAuth=FABKBRRaTOJILtFsMkpLVWSG6AN6C/svRwNmAAAEgAAACBaxlrwE7VscCAUxfrHhSD47KgGRZBd0df602Vv8V17Y6D5TAJluYnAqTS8A+5ge8V64CF7p+LkVA2+FIUVPmlRouGiAWQbkfQf9t00Tyizgu5lotVHMD46FLa2xHnyB8b9M9lAwSBeaMk2E87zQY48DN5nt4tjgHpxXWZt9svUn/AGSht5+DXTVQ/h1m3WBfOYYW/ovK0whePHQTQnSVCd1H2GC8dmrqgKDnYLZSZ8V5PpbkLsdLFtFnA0Dxt3Tm+ocLG6T/8qOBMEAUdP3j9ZCP3kn5KI84XwYRxHdDtcbyAAkHOqE0Uj7vJnCg/yUitm8dWHTL5KCuKKgzrEwhexvcKKCExPsaGm2i952jDJTilPbL72kxOrmNFWd1PhxQ6o5EVGiyojRG055d9rT6oOG3DmkSC7cij/xW3vsTwFwn5blK16Qk0GC0UVh9Pl11Vv1ZmyE1decCuXZVlnJy1kgkE3kPdp9YS1Iq8JPWgDX+4xxmD2Ve7hzZR+UnkCHKP+FQwsDLaeD69HTTSgvuVGNjoES22kb6nqhkXZjphL0gMRcVGkfK47q69fOJLGx6Gdohg3PxJlGzSgYLRXdDBrNm4O53du6tGwd2T7A/UESvj2XX9cgxBj5qfM6ofIP27Xya1ZpQmNEbEl5fuc7pqOBLY6L5wt34ipnLMp0euI4cDLSoMfw0Iho/Yi8wFnaazrOtXIEUJbuW+Q2uw4KI0YsAKRrlQv+ZbLPSJnF8llBug3Wz3xekJhmnsuAv4DrH83Cm/XfPrQ4NpkLpMk5nR3Cdb879tiCkLna73SH1GX1Lkrm+KZbVNLqHfiKrkBUNcflH8M1eAPZq8Do7nmB5sw0z/FBtKVQMIbU2RXzGV07gvc4Z9bYQHARsmyYKgBym5vASQeSLvyLSnhmsTF1qt0PJ9B9+V8OUFWiuDVTrz7S3lRE/JpbiI0T2csWN3efkuMoQsd9ZJk+MDFJyhfYtPZxbyEhDSTeLLMINzE1RAM7/lMhtVvRkukB0GDgZrEBaB9Wzoe5Mr6TZA20xAw2ALVReUf5Nk0ZVzZXWEIDD8ru3grC4WPp+NGjBzB5soiWXnPbUnyxlWDv0nujcK3KzcKMyFV+LXsGcmdI+IEQZncNfzg3tloX3nGjmyTmi/gADpv/7ilvDzMITRX3bNmQ9nmV1wMyTOLHgF4QLwjC68q62/XaAlSFWT1R8eiMjvSZYYaB5MHPYI6nXMG8YEfOqSuEHwhtTo2/Xmu5DK36ER40QqjnUSOIcyQnAg7wEBZZq+DVVlB7n8rfgwWKWgpPkpIvNb3BUp5PqMl1YYFyRCsJP8V2wWj9RYonaFCsCNzU4azuXkJ7TV0pM+0ctFeiuiGISYHcWTMuQdMRcR1D7tOLaLMmxETweErgixRfYl9gbXU6xlc8tT87URrRSTX+Q8w99UxJr6n/+pNXB8BnTpoGXIzV4aA+yzzhSTwj8yX9aP3giMp/pPwORiRFncFLLxDOelJ9myIW7fb+7zjS6kYx6kJfLezAsO3Lo5j+/6limAx0XsBlii37n9hvC67rTbAryLqg3mk1EvdLsAzvXuyNHu66H1aic+8Er9DnW11BRSRekuwZ/LK6krbdjlsc0zAgvAkgAOUsSv+Vwbm9v3WUCtD4LApCV4+j/ns3NUlQbIw6vGlr4vW59+gf/Tz46c2o5OQCCby4ockHimeEM4KY6k8ARYUS301z2gEHlJ1d3bNkFACK6NR41zdab/Y7RLB5eGqvt1zeDg==; NAP=V=1.9&E=1e83&C=HkXk7cksfDpRRx33BiOdQMMg3iwVG97Egd40t1Od3KBQK0W_ri9-UA&W=1; PPLState=1; WLID=YlMwJExwIN+//1UJf3YcRalX7rTLAgcrxzoiPfx8IIN6VNi5t1KDE34rVKBQ59zPCYpjS8O2Skl9Sjk1S0RMupDwiItunZUJNDCqNdYRQSA=; WLS=C=7824f0de35c71ced&N=lee; _U=1jVI9YZe16tZODxhuxFkWbrzMXBd-jjava2TWMTJdFyDQObjtqedH8yivyw0pVrUMpZUlLvXXjePtXYAo9bHuH_SMAAjqnYiAuTilUfe3gnXLQ86F7VZCgnvXib5qmZrJorg8NU8oiATsgABuGD_nPU1Bhkx6z9c8IYTgQX8WysWuUqNeTbzaeeme8RVUc4WTgRIWnJn8xv5xTNCwPJLChw; CSRFCookie=a6441b64-e95d-4995-973e-6e9667fc84dc; _EDGE_S=SID=0D07063EAF34690034D313A7AEE66833&mkt=zh-CN; MUID=2A5F21D302E860DB214732DD033A6161; MMCASM=ID=6487AEC8B3F941D7A8D97DD4734CAC50; SRCHD=AF=NOFORM; SRCHUID=V=2&GUID=4801BC17C3374D0C8D93FD65C68E87AC&dmnchg=1',
    'Sec-Fetch-Dest': 'document',
    'Accept-Language': 'zh-CN,zh-Hans;q=0.9',
    'Sec-Fetch-Mode': 'navigate',
    'Host': 'cn.bing.com',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15',
    'Referer': 'https://cn.bing.com/',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive'
}

def req(query):

# 发送请求
    url = f"https://cn.bing.com/search?q={query}&search=&form=QBLH&sp=-1&lq=0&pq=1&sc=12-1&qs=n&sk=&cvid=E89562EC89DD47DBBDC9323CD9FDA135&ghsh=0&ghacc=0&ghpl="
    response = requests.get(url, headers=headers)

    # 解析 HTML 内容
    soup = BeautifulSoup(response.content, 'html.parser')

    # 提取目标内容
    results = []
    for item in soup.find_all('li', class_='b_algo'):
        link = item.find('a')
        title = link.get_text()
        href = link.get('href')
        content = item.find('p').get_text() if item.find('p') else ''
        
        results.append({
            'url': href,
            'title': title,
            'content': content
        })
    return results

# 输出结果
# import json
# logger.info(json.dumps(results, ensure_ascii=False, indent=4))