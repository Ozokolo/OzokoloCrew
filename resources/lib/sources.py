# -*- coding: utf-8 -*-

"""
    sources.py ---
    Copyright (C) 2017, Midraal

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import random

import nanscrapers
import requests
import xbmcaddon
import xbmcgui
import xbmc
import koding
from koding import route
import sys
import xbmcplugin


from resources.lib.util.xml import JenItem, JenList
from resources.lib.util.info import get_info

addon_name = xbmcaddon.Addon().getAddonInfo('name')

ADDON = xbmcaddon.Addon()
DIALOG = xbmcgui.Dialog()


class Sources(object):
    """interface to NaN scraper library and helper functions"""

    def __init__(self):
        """initialise class"""
        pass

    @staticmethod
    def get_sources(title, year, imdb, tvdb, season, episode, tvshowtitle,
                    premiered, timeout=30, preset="search", dialog=None,
                    exclude=None, scraper_title=False, listitem=None,
                    output_function=koding.Play_Video, skip_selector=False):
        """
        scrapes for video sources using NaN scraper library
        Args:
            title: movie or episode title
            year: year movie/episode came out
            imdb: imdb identifier
            tvdb:  tvdb identifier
            season: season number
            episode: episode number
            tvshowtitle: title of tv show
            premiered: year tv show premiered
            timeout: timeout for scraping link
            preset: preferred quality of stream
            dialog: dialog to use for displaying messages
            exclude: list of scrapers to exclude
            scraper_title: extra movie/tv show title to search first.
                           required if scrapers use an alternate spelling
        Returns:
            Boolean indicating playback success
        """
        year = str(year)
        content = 'movie' if tvshowtitle is None else 'episode'
        allow_debrid = ADDON.getSetting('allow_debrid') == "true"

        if ADDON.getSetting('use_link_dialog') == 'true' and not skip_selector:
            # use link selector
            if content == 'movie':
                scraper = nanscrapers.scrape_movie_with_dialog
                link, rest = scraper(title, year, imdb, timeout=timeout,
                                     exclude=exclude, extended=True,
                                     sort_function=Sources.sort_function,
                                     enable_debrid=allow_debrid)
            elif content == "episode":
                scraper = nanscrapers.scrape_episode_with_dialog
                link, rest = scraper(tvshowtitle, year, premiered,
                                     season, episode, imdb, tvdb,
                                     timeout=timeout, exclude=exclude,
                                     extended=True,
                                     sort_function=Sources.sort_function,
                                     enable_debrid=allow_debrid)
            else:
                return

            if type(link) == dict and "path" in link:
                link = link["path"]
            if link is None:
                return False
            url = link['url']
            if ADDON.getSetting('link_fallthrough') == 'true':
                played = False
                index = 0
                links = []
                for item in rest:
                    if type(item) == dict and "path" in item:
                        links.extend(item["path"][1])
                    else:
                        links.extend(item[1])
                index = links.index(link)
                links = links[index + 1:]
                num_results = len(rest) + 1
                while not played:
                    try:
                        if dialog is not None and dialog.iscanceled():
                            return
                        if dialog is not None:
                            index = index + 1
                            percent = int((index * 100) / num_results)
                            line = "%s - %s (%s)" % (link['scraper'],
                                                     link['source'],
                                                     link['quality'])
                            dialog.update(percent, line)
                        played = output_function(url, showbusy=False,
                                                 ignore_dp=True, item=listitem)
                        link = links[0]
                        links = links[1:]
                    except:
                        return False
                return played
            else:
                return output_function(url, showbusy=False,
                                       ignore_dp=True, item=listitem)
        else:
            if content == 'movie':
                title = title
                scraper = nanscrapers.scrape_movie
                links_scraper = scraper(title, year, imdb, timeout=timeout,
                                        exclude=exclude,
                                        enable_debrid=allow_debrid)

            elif content == 'episode':
                if scraper_title:
                    tvshowtitle = title
                tvshowtitle = tvshowtitle
                scraper = nanscrapers.scrape_episode
                links_scraper = scraper(tvshowtitle, year, premiered, season,
                                        episode, imdb, tvdb, timeout=timeout,
                                        exclude=exclude,
                                        enable_debrid=allow_debrid)
            else:
                return

        sd_links = []
        non_direct_links = []
        non_direct_sd_links = []
        num_scrapers = len(nanscrapers.relevant_scrapers())
        index = 0
        try:
            for scraper_links in links_scraper():
                if dialog is not None and dialog.iscanceled():
                    return
                if dialog is not None:
                    index = index + 1
                    percent = int((index * 100) / num_scrapers)
                    dialog.update(percent)
                if scraper_links is not None:
                    random.shuffle(scraper_links)
                    for scraper_link in scraper_links:
                        if dialog is not None and dialog.iscanceled():
                            return False

                        if Sources().__check_skip_pairing(scraper_link):
                            continue

                        quality = Sources.__determine_quality(
                            scraper_link["quality"])
                        preset = preset.lower()
                        if preset == 'searchsd':
                            if quality == "HD":
                                continue
                        elif preset == "search":
                            if quality == "SD":
                                sd_links.append(scraper_link)

                        if scraper_link["direct"]:
                            result = output_function(scraper_link["url"],
                                                     showbusy=False,
                                                     ignore_dp=True,
                                                     item=listitem)
                            if result:
                                return result
                        else:
                            non_direct_links.append(scraper_link)

            for scraper_link in non_direct_links:
                if dialog is not None and dialog.iscanceled():
                    return False
                result = output_function(scraper_link["url"], showbusy=False,
                                         ignore_dp=True, item=listitem)
                if result:
                    return result

            for scraper_link in sd_links:
                if dialog is not None and dialog.iscanceled():
                    return

                if scraper_link['direct']:
                    result = output_function(scraper_link["url"],
                                             showbusy=False,
                                             ignore_dp=True, item=listitem)
                    if result:
                        return result
                else:
                    non_direct_sd_links.append(scraper_link)

            for scraper_link in non_direct_sd_links:
                if dialog is not None and dialog.iscanceled():
                    return
                result = output_function(scraper_link["url"], showbusy=False,
                                         ignore_dp=True, item=listitem)
                if result:
                    return result

            return False
        except:
            return False

    @staticmethod
    def get_music_sources(title, artist, timeout=30, preset="search",
                          dialog=None, exclude=None, listitem=None,
                          output_function=koding.Play_Video):
        """
        scrapes for music sources using NaN scraper library
        Args:
            title: song title
            artist: song artist
            timeout: timeout for scraping link
            preset: preferred quality of stream
            dialog: dialog to use for displaying messages
            exclude: list of scrapers to exclude
        Returns:
            Boolean indicating playback success
        """
        title = title
        allow_debrid = ADDON.getSetting('allow_debrid') == "true"
        links_scraper = nanscrapers.scrape_song(
            title, artist, timeout=timeout, exclude=exclude,
            enable_debrid=allow_debrid)

        sd_links = []
        num_scrapers = len(nanscrapers.relevant_scrapers())
        index = 0
        for scraper_links in links_scraper():
            if dialog is not None and dialog.iscanceled():
                return
            if dialog is not None:
                index = index + 1
                percent = int((index * 100) / num_scrapers)
                dialog.update(percent)
            if scraper_links is not None:
                random.shuffle(scraper_links)
                for scraper_link in scraper_links:
                    if dialog is not None and dialog.iscanceled():
                        return

                    if Sources().__check_skip_pairing(scraper_link):
                        continue

                    quality = Sources.__determine_quality(
                        scraper_link["quality"])
                    preset = preset.lower()
                    if preset == 'searchsd':
                        if quality == "HD":
                            continue
                    elif preset == "search":
                        if quality == "SD":
                            sd_links.append(scraper_link)

                    result = output_function(scraper_link["url"],
                                             showbusy=False,
                                             ignore_dp=True,
                                             item=listitem)
                    if result:
                        return result

        for scraper_link in sd_links:
            if dialog is not None and dialog.iscanceled():
                return
            result = output_function(scraper_link["url"], showbusy=False,
                                     ignore_dp=True, item=listitem)
            if result:
                return result

            return False

    @staticmethod
    def youtube_resolve(url):
        """
        transform youtube url to link to youtube add-on
        Args:
            url: youtube url
        Returns:
            playable url
        """
        try:
            youtube_id = url.split(
                '?v=')[-1].split('/')[-1].split('?')[0].split('&')[0]
            result = requests.head(
                'http://www.youtube.com/watch?v=%s' % youtube_id)
            if result:
                return 'plugin://plugin.video.youtube/play/?video_id=%s' % (
                    youtube_id)
        except:
            return

    @staticmethod
    def sort_function(item):
        """
        transform items quality into a string that's sort-able
        Args:
            item: scraper link
        Returns:
            sortable quality string
        """
        if 'quality' in item[1][0]:
            quality = item[1][0]["quality"]
        else:
            quality = item[1][0]["path"]["quality"]

        if quality.startswith("1080"):
            quality = "HDa"
        elif quality.startswith("720"):
            quality = "HDb"
        elif quality.startswith("560"):
            quality = "HDc"
        elif quality == "HD":
            quality = "HDd"
        elif quality.startswith("480"):
            quality = "SDa"
        elif quality.startswith("360"):
            quality = "SDb"
        elif quality.startswith("SD"):
            quality = "SDc"
        return quality

    @staticmethod
    def __determine_quality(quality_string):
        try:
            quality = int(quality_string)
            if quality > 576:
                return "HD"
            else:
                return "SD"
        except ValueError:
            if quality_string not in ["SD", "CAM", "SCR"]:
                return "HD"
            else:
                return "SD"

    @staticmethod
    def __check_skip_pairing(scraper_link):
        if not ADDON.getSetting('allow_openload') == 'true' and\
           'openload' in scraper_link['url']:
            return True
        if not ADDON.getSetting('allow_the_video_me') == 'true' and\
           'thevideo.me' in scraper_link['url']:
            return True
        if not ADDON.getSetting('allow_the_vidup_me') == 'true' and\
           'vidup.me' in scraper_link['url']:
            return True
        return False


def choose_quality(link, name=None, selected_link=None):
    """
    choose quality for scraping

    Keyword Arguments:
    link -- Jenitem link with sublinks
    name -- Name to display in dialog (default None)
    """
    import re
    if name is None:
        name = xbmc.getInfoLabel('listitem.label')
    if link.startswith("http") or link.startswith("plugin"):
        sublinks = [link]
    else:
        jen_link = JenItem(link)
        sublinks = jen_link.getAll("sublink")
        if not sublinks:
            sublinks = [jen_link]
    links = []
    if selected_link is None:
        default_link = ADDON.getSetting("default_link")
    else:
        default_link = selected_link
    link_dialog = ADDON.getSetting("use_link_dialog") == "true"
    direct_links = False
    for sublink in sublinks:
        if link_dialog and "search" in sublink:
            continue
        if "searchsd" in sublink:
            if default_link == "SD":
                return sublink
            label = 'SD'
            new_item = (label, sublink)
        elif "search" in sublink:
            if default_link == "HD":
                return sublink
            label = 'HD'
            new_item = (label, sublink)
        else:
            direct_links = True
            match = re.findall("(.*?)\((.*?)\)", sublink)
            if match:
                new_item = ('%s' % match[0][1], match[0][0])
            else:
                new_item = ('Link %s' % (int(sublinks.index(sublink)) + 1),
                            sublink)
        links.append(new_item)
    if link_dialog and (not direct_links or len(sublinks) > 1):
        links.append(("Search", "search"))

    if len(links) == 1:
        url = links[0][1]
        return url

    select = xbmcgui.Dialog().select(name, [i[0] for i in links])
    if select == -1:
        return False
    else:
        url = links[select][1]
    return url


@route(mode="get_sources", args=["url"])
def get_sources(item):
    """
    get video_link and try to play it
    Keyword Arguments:
    item -- JenItem to try playing
    """
    if item.startswith("<plugin>"):
        # link to plugin
        link = JenItem(item)["link"]
        sublinks = JenItem(link).getAll("sublink")
        if sublinks:
            if len(sublinks) > 1:
                link = choose_quality(link)
            else:
                link = sublinks[0]
        link = link.replace("&amp;", "&")
        xbmc.executebuiltin('Container.update('+link+')')
        return
    item = JenItem(item)

    link = item["link"]
    if not link or link.replace("\t", "") == "":
        return
    meta = JenItem(item["meta"])
    title = meta["title"]
    year = meta["year"].split("-")[0].strip()
    imdb = meta["imdb"]
    tvdb = meta.get("tvdb", "")
    season = meta.get("season", "")
    episode = meta.get("episode", "")
    tvshowtitle = meta.get("tvshowtitle", None)
    premiered = meta.get("premiered", "")
    try:
        premiered = premiered.split("-")[0].strip()
    except:
        if len(premiered) == 4:
            pass
        else:
            xbmc.log("wrong premiered format")
    busy_dialog = xbmcgui.DialogProgress()
    dialog = xbmcgui.Dialog()
    icon = ADDON.getAddonInfo('icon')

    busy_dialog.create(addon_name, "Processing Link")
    preset = choose_quality(link)
    played = False
    infolabels = {}
    if preset:
        preset = preset.replace("&amp;", "&")
        busy_dialog.update(0, "")
        listitem = None
        fetch_meta = ADDON.getSetting("metadata") == "true"
        listitem = xbmcgui.ListItem(path=link,
                                    iconImage=item.get("thumbnail", icon),
                                    thumbnailImage=item.get("thumbnail",
                                                            icon))

        if fetch_meta and imdb != "0":  # only try valid items with imdb
            infolabels = {}
            try:
                info, created = get_info([item.item_string])
                if info and type(info) == dict:
                    infolabels = info
            except:
                pass
        if "plotoutline" not in infolabels:
            infolabels["plotoutline"] = infolabels.get("plot", "")
        listitem.setInfo(type="video", infoLabels=infolabels)
        listitem.setLabel(item.get("title", item.get("name", "")))
        if "search" in preset:
            exclude_scrapers_content = item.get("exclude_scrapers", "")
            if exclude_scrapers_content:
                exclude_scrapers = exclude_scrapers_content.split(";")
            else:
                exclude_scrapers = None
            # nanscraper link
            played = Sources.get_sources(
                title, year, imdb, tvdb, season, episode, tvshowtitle,
                premiered, preset=preset, dialog=busy_dialog,
                listitem=listitem, exclude=exclude_scrapers)
            if not played:
                dialog.notification(addon_name,
                                    "no link found",
                                    icon, 5)
        elif preset.startswith("http") or preset.startswith("plugin"):
            # direct link
            if "/playlist" in preset:
                busy_dialog.close()
                xbmc.executebuiltin('Container.update('+preset+')')
                return
            elif "plugin://plugin.video.youtube/play/?video_id=" in preset:
                xbmc.executebuiltin("PlayMedia(%s)" % preset)
                played = True
            elif item["content"] == "image":
                busy_dialog.close()
                xbmc.executebuiltin("ShowPicture(%s)" % preset)
                played = True
            else:
                played = koding.Play_Video(
                    preset, showbusy=False, ignore_dp=True, item=listitem)
            if not played:
                dialog.notification(addon_name,
                                    "no link found",
                                    icon, 5)
        else:
            # who knows
            busy_dialog.close()
            xbmc.log("unknown link type: " + repr(preset), xbmc.LOGDEBUG)
            raise Exception()
    busy_dialog.close()
    if played:
        is_playing = True
        while is_playing:
            is_playing = xbmc.Player().isPlaying()
            xbmc.sleep(1000)


@route(mode="queue", args=["url"])
def queue_source(item, depth=0):
    """
    queue item
    Keyword Arguments:
    item -- JenItem to try playing
    """
    from resources.lib.util.url import get_addon_url
    jen_item = JenItem(item)
    playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    if "<item>" in str(jen_item):
        play = False
        if xbmcaddon.Addon().getSetting("autostart_queue") == "true":
            if playlist.size() == 0:
                play = True
        playlist.add(get_addon_url("get_sources", str(item)),
                     xbmcgui.ListItem(jen_item["title"],
                                      iconImage=jen_item.get("thumbnail", "")))
        if play:
            play_queue()
    else:
        link = jen_item.get("url", jen_item.get("link", ""))
        jenlist = JenList(link).get_raw_list()
        for list_item in jenlist:
            queue_source(str(list_item), depth + 1)
    if depth == 0:
        xbmcgui.Dialog().notification(addon_name,
                                      "Finished Queueing".encode('utf-8'),
                                      ADDON.getAddonInfo("icon"))
        xbmc.executebuiltin("Container.Refresh")


@route(mode="clear_queue")
def clear_queue():
    xbmc.PlayList(xbmc.PLAYLIST_VIDEO).clear()
    xbmcgui.Dialog().notification(ADDON.getAddonInfo("name"),
                                  "Queue cleared".encode('utf-8'),
                                  ADDON.getAddonInfo("icon"))
    xbmc.executebuiltin('Container.Refresh')


@route(mode="play_queue")
def play_queue():
    playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    if playlist.size() > 0:
        item = playlist[0]
        xbmc.Player().play(playlist, item)
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)
    else:
        xbmcgui.Dialog().notification(ADDON.getAddonInfo("name"),
                                      "Queue is empty".encode('utf-8'),
                                      ADDON.getAddonInfo("icon"))

#  LocalWords:  searchsd HD