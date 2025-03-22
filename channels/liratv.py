# -*- coding: utf-8 -*-
# ------------------------------------------------------------
# Canale per La7
# ------------------------------------------------------------

import sys
from core import support, httptools
from platformcode import logger
from datetime import datetime, timezone, timedelta
import html
import json
import ssl

if sys.version_info[0] >= 3:
    from concurrent import futures
    from urllib.parse import urlencode
    import urllib.request as urllib_request
else:
    from concurrent_py2 import futures
    from urllib import urlencode
    import urllib2 as urllib_request  # urllib2 is used in Python 2

host = 'https://www.liratv.it'

@support.menu
def mainlist(item):
    top =  [('Diretta {bold}', ['', 'live']),
            ('Replay {bold}', ['', 'replay_channels'])]

    menu = [('Programmi TV {bullet bold}', ['/', 'peliculas', '', 'tvshow'])]

    search = ''
    return locals()

def live(item):
    liratv_live = item.clone(title=support.typo('LiraTV', 'bold'), fulltitle='LiraTV', url= host + '/streaming', action='findvideos', forcethumb = True, no_return=True)
    liratv_live.plot = "Diretta streaming live"
    liratv_live.fanart = "https://webtools-a928c0678d284da5b383f29ecc5dfeec.msvdn.net/image/8kTBWibNteJA/poster"
    
    itemlist = [liratv_live]
    return support.thumb(itemlist, live=True)

def replay_channels(item):
    program_dict = [
        ("Programmi", "/programmi", "Ultimi programmi in replay"),
        ("News", "/news", "Ultime notizie"),
        ("Cronaca", "/news/cronaca", "Ultime notizie di cronaca"),
        ("Sport", "/news/sport", "Ultime notizie di sport"),
        ("Politica", "/news/politica", "Ultime notizie di politica"),
        ("Cultura", "/news/cultura-e-spettacolo", "Ultime notizie di cultura e spettacolo"),
    ]

    itemlist = [
            item.clone(
                title = support.typo(title, 'bold'),
                fulltitle = title,
                url = host + path,
                plot = plot,
                action = 'replay_menu',
                forcethumb = True,
                fanart = "https://webtools-a928c0678d284da5b383f29ecc5dfeec.msvdn.net/image/8kTBWibNteJA/poster"
            ) 
        for title, path, plot in program_dict]

    return support.thumb(itemlist, live=True)


def replay_menu(item):
    return global_scraper(item)

def peliculas(item):
    html_content = httptools.downloadpage(item.url).data
    html_content = html_content.split('<ul class="sub-menu">')[1].split('</ul>')[0]
    patron = r'<li[^>]*>\s*<a href="(?P<url>[^"]+)">(?P<title>[^<]+)</a>'

    match = support.match(html_content, patron=patron)
    matches = match.matches
    # url_splits = item.url.split('?')

    itemlist = []
    for n, key in enumerate(matches):
        programma_url, titolo = key
        if not programma_url.startswith('https://www.liratv.it/programmi'): continue
        titolo = html.unescape(titolo)

        it = item.clone(title=support.typo(titolo, 'bold'),
                        data='',
                        fulltitle=titolo,
                        show=titolo,
                        thumbnail= "https://webtools-a928c0678d284da5b383f29ecc5dfeec.msvdn.net/image/8kTBWibNteJA/poster",
                        fanart = "https://webtools-a928c0678d284da5b383f29ecc5dfeec.msvdn.net/image/8kTBWibNteJA/poster",
                        url=programma_url,
                        video_url=programma_url,
                        order=n)
        it.action = 'episodios'
        it.contentSerieName = it.fulltitle

        itemlist.append(it)

    return itemlist


def episodios(item):
    return global_scraper(item)

def global_scraper(item):
    html_content = httptools.downloadpage(item.url).data

    itemlist = []
    if 'penci-layout-masonry' in html_content:
        patron = r'<article[^>]*>.*?<div class="thumbnail">.*?<a href="(?P<url>[^"]+)"[^>]*>.*?<img[^>]*src="(?P<image>[^"]+)"[^>]*>.*?</a>.*?<h2[^>]*class="[^"]*entry-title[^"]*"[^>]*>.*?<a[^>]*>(?P<title>[^<]+)</a>'
    elif 'penci-layout-list' in html_content:
        patron = r'<article[^>]*>.*?<div class="thumbnail">.*?data-bgset="(?P<image>[^"]+)"\s*?href="(?P<url>[^"]+)"\s*?title="(?P<title>[^"]+)">\s*?</a>\s*?<a.*?<div class="item-content entry-content">.*?<p>(?P<description>.*?)</p>'
    
    match = support.match(html_content, patron=patron)
    matches = match.matches

    itemlist = []
    for n, key in enumerate(matches):
        if 'penci-layout-masonry' in html_content:
            programma_url, image, titolo = key
            plot = ''
        elif 'penci-layout-list' in html_content:
            image, programma_url, titolo, plot = key

        titolo = html.unescape(titolo)
        plot = html.unescape(plot)

        it = item.clone(title=support.typo(titolo, 'bold'),
                        data='',
                        fulltitle=titolo,
                        show=titolo,
                        plot = plot,
                        thumbnail= image,
                        fanart = image,
                        url=programma_url,
                        video_url=programma_url,
                        order=n)
        it.action = 'findvideos'
        it.contentSerieName = it.fulltitle

        itemlist.append(it)

    if 'page-numbers' in html_content:
        if item.url.split('/')[-2] != 'page':
            next_page = f'{item.url}/page/2'
        else:
            next_page = item.url.split('page')[0] + f'page/{int(item.url.split("page/")[1]) + 1}'
            
        itemlist.append(
            item.clone(title=support.typo('Next', 'bold'),
                        url= next_page,
                        order=len(itemlist),
                        video_url='',
                        thumbnail=''
                )
            )

    return itemlist

def findvideos(item):
    support.info()
    if item.livefilter:
        for it in live(item):
            if it.fulltitle == item.livefilter:
                item = it
                break
    data = support.match(item).data
    if item.url.endswith('/streaming'):
        playlist_url = support.match(data, patron=r'"video":"(?P<url>https?://[^"]+)"').matches[0]
        item = item.clone(title='Direct', server='directo', url=playlist_url, action='play')
    else:
        playlist_url = support.match(data, patron=r'"sd":"(?P<url>https?://[^"]+)"').matches[0]
        item = item.clone(title='Direct', server='directo', url=playlist_url, action='play')

    return support.server(item, itemlist=[item], Download=False, Videolibrary=False)
