# -*- coding: utf-8 -*-

#from builtins import str
import sys
PY3 = False
if sys.version_info[0] >= 3: PY3 = True; unicode = str; unichr = chr; long = int
from builtins import range

import os

from core import channeltools, jsontools
from core.item import Item
from platformcode import config, logger, platformtools, launcher
from time import sleep
from platformcode.config import get_setting

__channel__ = "autoplay"

PLAYED = False

autoplay_node = {}

colorKOD = '0xFF65B3DA'

quality_list = ['4k', '2k',
                'fullhd', 'fullhd 1080', 'fullhd 1080p', 'full hd', 'full hd 1080', 'full hd 1080p', 'hd1080', 'hd1080p', 'hd 1080', 'hd 1080p', '1080', '1080p',
                'hd', 'hd720', 'hd720p', 'hd 720', 'hd 720p', '720', '720p', 'hdtv',
                'sd', '480p', '480',
                '360p', '360',
                '240p', '240',
                'default']


def start(itemlist, item):
    '''
    Main method from which the links are automatically reproduced
    - In case the option to activate it will use the options defined by the user.
    - Otherwise it will try to reproduce any link that has the preferred language.

    :param itemlist: list (list of items ready to play, ie with action = 'play')
    :param item: item (the main item of the channel)
    :return: try to auto-reproduce, in case of failure it returns the itemlist that it received in the beginning
    '''
    if item.global_search:
        return itemlist
    logger.info()

    global PLAYED
    PLAYED = False

    base_item = item

    if not config.is_xbmc():
        return itemlist

    channel_id = item.channel
    if item.channel == 'videolibrary':
        channel_id = item.contentChannel


    if get_setting('autoplay'): 
        url_list_valid = []
        autoplay_list = []
        autoplay_b = []
        favorite_quality = []

        # Get Blacklisted Servers
        try: blacklisted_servers = config.get_setting('black_list', server='servers')
        except: blacklisted_servers = []
        # Get Favourite Servers
        try: favorite_servers = list(set(config.get_setting('favorites_servers_list', server='servers')) - set(blacklisted_servers))
        except: favorite_servers = []

        # Save the current value of "Action and Player Mode" in preferences
        user_config_setting_action = config.get_setting("default_action")
        user_config_setting_player = config.get_setting("player_mode")

        # Enable the "View in high quality" action (if the server returns more than one quality, eg gdrive)
        if not user_config_setting_action: config.set_setting("default_action", 2)

        if user_config_setting_player != 0: config.set_setting("player_mode", 0)

        # Priorities when ordering itemlist:
        #       0: Servers and qualities
        #       1: Qualities and servers
        #       2: Servers only
        #       3: Only qualities
        #       4: Do not order
        if config.get_setting('favorites_servers') and favorite_servers and config.get_setting('default_action'): # (settings_node['custom_servers'] and settings_node['custom_quality']) or get_setting('autoplay'):
            priority = 0  # 0: Servers and qualities or 1: Qualities and servers
        elif config.get_setting('favorites_servers') and favorite_servers: # settings_node['custom_servers']:
            priority = 2  # Servers only
        elif config.get_setting('default_action'): # settings_node['custom_quality']:
            priority = 3  # Only qualities
        else:
            priority = 4  # Do not order

        # from core.support import dbg;dbg()
        if get_setting('default_action') == 1:
            quality_list.reverse()
        favorite_quality = quality_list

        for item in itemlist:
            autoplay_elem = dict()
            b_dict = dict()

            # We check that it is a video item
            if 'server' not in item:
                continue

            # If it does not have a defined quality, it assigns a 'default' quality.
            if item.quality == '':
                item.quality = 'default'
            # The list for custom settings is created
            if priority < 2:  # 0: Servers and qualities or 1: Qualities and servers

                # if the server and the quality are not in the favorites lists or the url is repeated, we discard the item
                if item.server.lower() not in favorite_servers or item.quality.lower() not in favorite_quality or item.url in url_list_valid:
                    item.type_b = True
                    b_dict['videoitem']= item
                    autoplay_b.append(b_dict)
                    continue
                autoplay_elem["indice_server"] = favorite_servers.index(item.server.lower())
                autoplay_elem["indice_quality"] = favorite_quality.index(item.quality.lower())

            elif priority == 2:  # Servers only

                # if the server is not in the favorites list or the url is repeated, we discard the item
                if item.server.lower() not in favorite_servers or item.url in url_list_valid:
                    item.type_b = True
                    b_dict['videoitem'] = item
                    autoplay_b.append(b_dict)
                    continue
                autoplay_elem["indice_server"] = favorite_servers.index(item.server.lower())

            elif priority == 3:  # Only qualities

                # if the quality is not in the favorites list or the url is repeated, we discard the item
                if item.quality.lower() not in favorite_quality or item.url in url_list_valid:
                    item.type_b = True
                    b_dict['videoitem'] = item
                    autoplay_b.append(b_dict)
                    continue
                autoplay_elem["indice_quality"] = favorite_quality.index(item.quality.lower())

            else:  # Do not order

                # if the url is repeated, we discard the item
                if item.url in url_list_valid:
                    continue

            # If the item reaches here we add it to the list of valid urls and to autoplay_list
            url_list_valid.append(item.url)
            item.plan_b=True
            autoplay_elem['videoitem'] = item
            autoplay_list.append(autoplay_elem)

        # We order according to priority
        if priority == 0: autoplay_list.sort(key=lambda orden: (orden['indice_server'], orden['indice_quality'])) # Servers and qualities
        elif priority == 1: autoplay_list.sort(key=lambda orden: (orden['indice_quality'], orden['indice_server'])) # Qualities and servers
        elif priority == 2: autoplay_list.sort(key=lambda orden: (orden['indice_server'])) # Servers only
        elif priority == 3: autoplay_list.sort(key=lambda orden: (orden['indice_quality'])) # Only qualities

        # Plan b is prepared, in case it is active the non-favorite elements are added at the end
        try: plan_b = settings_node['plan_b']
        except: plan_b = True
        text_b = ''
        if plan_b: autoplay_list.extend(autoplay_b)
        # If there are elements in the autoplay list, an attempt is made to reproduce each element, until one is found or all fail.

        if autoplay_list or (plan_b and autoplay_b):

            # played = False
            max_intentos = 5
            max_intentos_servers = {}

            # If something is playing it stops playing
            if platformtools.is_playing():
                platformtools.stop_video()

            for autoplay_elem in autoplay_list:
                play_item = Item

                # If it is not a favorite element if you add the text plan b
                if autoplay_elem['videoitem'].type_b:
                    text_b = '(Plan B)'
                if not platformtools.is_playing() and not PLAYED:
                    videoitem = autoplay_elem['videoitem']
                    if videoitem.server.lower() not in max_intentos_servers:
                        max_intentos_servers[videoitem.server.lower()] = max_intentos

                    # If the maximum number of attempts of this server have been reached, we jump to the next
                    if max_intentos_servers[videoitem.server.lower()] == 0:
                        continue

                    lang = " "
                    if hasattr(videoitem, 'language') and videoitem.language != "":
                        lang = " '%s' " % videoitem.language

                    platformtools.dialog_notification("AutoPlay %s" %text_b, "%s%s%s" % (videoitem.server.upper(), lang, videoitem.quality.upper()), sound=False)

                    # Try to play the links If the channel has its own play method, use it
                    try: channel = __import__('channels.%s' % channel_id, None, None, ["channels.%s" % channel_id])
                    except: channel = __import__('specials.%s' % channel_id, None, None, ["specials.%s" % channel_id])
                    if hasattr(channel, 'play'):
                        resolved_item = getattr(channel, 'play')(videoitem)
                        if len(resolved_item) > 0:
                            if isinstance(resolved_item[0], list): videoitem.video_urls = resolved_item
                            else: videoitem = resolved_item[0]

                    # If not directly reproduce and mark as seen

                    # Check if the item comes from the video library
                    try:
                        if base_item.contentChannel == 'videolibrary':
                            # Mark as seen
                            from platformcode import xbmc_videolibrary
                            xbmc_videolibrary.mark_auto_as_watched(base_item)
                            # Fill the video with the data of the main item and play
                            play_item = base_item.clone(url=videoitem)
                            platformtools.play_video(play_item.url, autoplay=True)
                        else:
                            # If it doesn't come from the video library, just play
                            platformtools.play_video(videoitem, autoplay=True)
                    except:
                        pass
                    sleep(3)
                    try:
                        if platformtools.is_playing():
                            PLAYED = True
                            break
                    except:
                        logger.debug(str(len(autoplay_list)))

                    # If we have come this far, it is because it could not be reproduced
                    max_intentos_servers[videoitem.server.lower()] -= 1

                    # If the maximum number of attempts of this server has been reached, ask if we want to continue testing or ignore it.
                    if max_intentos_servers[videoitem.server.lower()] == 0:
                        text = config.get_localized_string(60072) % videoitem.server.upper()
                        if not platformtools.dialog_yesno("AutoPlay", text, config.get_localized_string(60073)):
                            max_intentos_servers[videoitem.server.lower()] = max_intentos

                    # If there are no items in the list, it is reported
                    if autoplay_elem == autoplay_list[-1]:
                         platformtools.dialog_notification('AutoPlay', config.get_localized_string(60072) % videoitem.server.upper())

        else:
            platformtools.dialog_notification(config.get_localized_string(60074), config.get_localized_string(60075))

        # Restore if necessary the previous value of "Action and Player Mode" in preferences
        if not user_config_setting_action: config.set_setting("default_action", user_config_setting_action)
        if user_config_setting_player != 0: config.set_setting("player_mode", user_config_setting_player)

    return itemlist


def play_multi_channel(item, itemlist):
    logger.info()
    global PLAYED
    video_dict = dict()

    for video_item in itemlist:
        if get_setting('autoplay'):
            if video_item.contentChannel not in video_dict.keys():
                video_dict[video_item.contentChannel] = [video_item]
            else:
                video_dict[video_item.contentChannel].append(video_item)

    for channel, videos in video_dict.items():
        item.contentChannel = channel
        if not PLAYED:
            start(videos, item)
        else:
            break
