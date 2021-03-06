
import xbmc
import xbmcplugin
import xbmcgui
import xbmcaddon
import urllib
import datetime
import time
import json as json
import inspect
import sys

from DownloadUtils import DownloadUtils
from PlayUtils import PlayUtils
from ReadKodiDB import ReadKodiDB
from ReadEmbyDB import ReadEmbyDB
import Utils as utils
from API import API
import Utils as utils
import os
import xbmcvfs

addon = xbmcaddon.Addon(id='plugin.video.emby')
addondir = xbmc.translatePath(addon.getAddonInfo('profile'))

WINDOW = xbmcgui.Window( 10000 )

class PlaybackUtils():
    
    settings = None
    language = addon.getLocalizedString
    logLevel = 0
    downloadUtils = DownloadUtils()
    
    def __init__(self, *args):
        pass    

    def PLAY(self, id):
        xbmc.log("PLAY Called")
        WINDOW = xbmcgui.Window(10000)

        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        
        url = "{server}/mediabrowser/Users/{UserId}/Items/%s?format=json&ImageTypeLimit=1" % id
        result = self.downloadUtils.downloadUrl(url)     
        

        userData = result[u'UserData']
        resume_result = 0
        seekTime = 0
        
        #get the resume point from Kodi DB for a Movie
        kodiItem = ReadKodiDB().getKodiMovie(id)
        if kodiItem != None:
            seekTime = int(round(kodiItem['resume'].get("position")))
        else:
            #get the resume point from Kodi DB for an episode
            episodeItem = ReadEmbyDB().getItem(id)
            if episodeItem != None and str(episodeItem["Type"]) == "Episode":
                kodiItem = ReadKodiDB().getKodiEpisodeByMbItem(id,episodeItem["SeriesId"])
                if kodiItem != None:
                    seekTime = int(round(kodiItem['resume'].get("position")))                  
        
        playurl = PlayUtils().getPlayUrl(server, id, result)
        
        isStrmFile = False
        thumbPath = API().getArtwork(result, "Primary")
        
        #workaround for when the file to play is a strm file itself
        if playurl.endswith(".strm"):
            isStrmFile = True
            tempPath = os.path.join(addondir,"library","temp.strm")
            xbmcvfs.copy(playurl, tempPath)
            sfile = open(tempPath, 'r')
            playurl = sfile.readline()
            sfile.close()
            xbmcvfs.delete(tempPath)
            WINDOW.setProperty("virtualstrm", id)
            WINDOW.setProperty("virtualstrmtype", result.get("Type"))

        listItem = xbmcgui.ListItem(path=playurl, iconImage=thumbPath, thumbnailImage=thumbPath)
        self.setListItemProps(server, id, listItem, result)    

        # Can not play virtual items
        if (result.get("LocationType") == "Virtual"):
          xbmcgui.Dialog().ok(self.language(30128), self.language(30129))

        watchedurl = "%s/mediabrowser/Users/%s/PlayedItems/%s" % (server, userid, id)
        positionurl = "%s/mediabrowser/Users/%s/PlayingItems/%s" % (server, userid, id)
        deleteurl = "%s/mediabrowser/Items/%s" % (server, id)

        # set the current playing info
        WINDOW.setProperty(playurl+"watchedurl", watchedurl)
        WINDOW.setProperty(playurl+"positionurl", positionurl)
        WINDOW.setProperty(playurl+"deleteurl", "")
        WINDOW.setProperty(playurl+"deleteurl", deleteurl)
        
        if seekTime != 0:
            displayTime = str(datetime.timedelta(seconds=seekTime))
            display_list = [ self.language(30106) + ' ' + displayTime, self.language(30107)]
            resumeScreen = xbmcgui.Dialog()
            resume_result = resumeScreen.select(self.language(30105), display_list)
            if resume_result == 0:
                WINDOW.setProperty(playurl+"seektime", str(seekTime))
            else:
                WINDOW.clearProperty(playurl+"seektime")
        else:
            WINDOW.clearProperty(playurl+"seektime")

        if result.get("Type")=="Episode":
            WINDOW.setProperty(playurl+"refresh_id", result.get("SeriesId"))
        else:
            WINDOW.setProperty(playurl+"refresh_id", id)
            
        WINDOW.setProperty(playurl+"runtimeticks", str(result.get("RunTimeTicks")))
        WINDOW.setProperty(playurl+"type", result.get("Type"))
        WINDOW.setProperty(playurl+"item_id", id)

        if PlayUtils().isDirectPlay(result) == True:
            playMethod = "DirectPlay"
        else:
            playMethod = "Transcode"

        WINDOW.setProperty(playurl+"playmethod", playMethod)
            
        mediaSources = result.get("MediaSources")
        if(mediaSources != None):
            if mediaSources[0].get('DefaultAudioStreamIndex') != None:
                WINDOW.setProperty(playurl+"AudioStreamIndex", str(mediaSources[0].get('DefaultAudioStreamIndex')))  
            if mediaSources[0].get('DefaultSubtitleStreamIndex') != None:
                WINDOW.setProperty(playurl+"SubtitleStreamIndex", str(mediaSources[0].get('DefaultSubtitleStreamIndex')))

        #this launches the playback
        #artwork only works with both resolvedurl and player command
        if isStrmFile:
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listItem)
        else:
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listItem)
            if(addon.getSetting("addExtraPlaybackArt") == "true"):
                utils.logMsg("PLAY", "Doing second xbmc.Player().play to add extra art")
                xbmc.Player().play(playurl,listItem)

    def setArt(self, list,name,path):
        if name=='thumb' or name=='fanart_image' or name=='small_poster' or name=='tiny_poster'  or name == "medium_landscape" or name=='medium_poster' or name=='small_fanartimage' or name=='medium_fanartimage' or name=='fanart_noindicators':
            list.setProperty(name, path)
        else:
            list.setArt({name:path})
        return list
    
    def setListItemProps(self, server, id, listItem, result):
        # set up item and item info
        thumbID = id
        eppNum = -1
        seasonNum = -1
        tvshowTitle = ""
        
        if(result.get("Type") == "Episode"):
            thumbID = result.get("SeriesId")
            seasonNum = result.get("ParentIndexNumber")
            eppNum = result.get("IndexNumber")
            tvshowTitle = result.get("SeriesName")
            
        self.setArt(listItem,'poster', API().getArtwork(result, "Primary"))
        self.setArt(listItem,'tvshow.poster', API().getArtwork(result, "SeriesPrimary"))
        self.setArt(listItem,'clearart', API().getArtwork(result, "Art"))
        self.setArt(listItem,'tvshow.clearart', API().getArtwork(result, "Art"))    
        self.setArt(listItem,'clearlogo', API().getArtwork(result, "Logo"))
        self.setArt(listItem,'tvshow.clearlogo', API().getArtwork(result, "Logo"))    
        self.setArt(listItem,'discart', API().getArtwork(result, "Disc"))  
        self.setArt(listItem,'fanart_image', API().getArtwork(result, "Backdrop"))
        self.setArt(listItem,'landscape', API().getArtwork(result, "Thumb"))   
        
        listItem.setProperty('IsPlayable', 'true')
        listItem.setProperty('IsFolder', 'false')
        
        # Process Studios
        studios = API().getStudios(result)
        if studios == []:
            studio = ""
        else:
            studio = studios[0]
        listItem.setInfo('video', {'studio' : studio})    

        # play info
        playinformation = ''
        if PlayUtils().isDirectPlay(result) == True:
            playinformation = self.language(30165)
        else:
            playinformation = self.language(30166)
            
        details = {
                 'title'        : result.get("Name", "Missing Name") + ' - ' + playinformation,
                 'plot'         : result.get("Overview")
                 }
                 
        if(eppNum > -1):
            details["episode"] = str(eppNum)
            
        if(seasonNum > -1):
            details["season"] = str(seasonNum)  

        if tvshowTitle != None:
            details["TVShowTitle"] = tvshowTitle    
        
        listItem.setInfo( "Video", infoLabels=details )

        people = API().getPeople(result)

        # Process Genres
        genre = API().getGenre(result)
        
        listItem.setInfo('video', {'director' : people.get('Director')})
        listItem.setInfo('video', {'writer' : people.get('Writer')})
        listItem.setInfo('video', {'mpaa': result.get("OfficialRating")})
        listItem.setInfo('video', {'genre': genre})
    
    def seekToPosition(self, seekTo):
    
        #Set a loop to wait for positive confirmation of playback
        count = 0
        while not xbmc.Player().isPlaying():
            count = count + 1
            if count >= 10:
                return
            else:
                xbmc.sleep(500)
            
        #Jump to resume point
        jumpBackSec = 10#int(self.settings.getSetting("resumeJumpBack"))
        seekToTime = seekTo - jumpBackSec
        count = 0
        while xbmc.Player().getTime() < (seekToTime - 5) and count < 11: # only try 10 times
            count = count + 1
            #xbmc.Player().pause
            #xbmc.sleep(100)
            xbmc.Player().seekTime(seekToTime)
            xbmc.sleep(100)
            #xbmc.Player().play()
    
    def PLAYAllItems(self, items, startPositionTicks):
        utils.logMsg("PlayBackUtils", "== ENTER: PLAYAllItems ==")
        utils.logMsg("PlayBackUtils", "Items : " + str(items))
        WINDOW = xbmcgui.Window(10000)

        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        playlist.clear()        
        started = False
        
        for itemID in items:
        
            utils.logMsg("PlayBackUtils", "Adding Item to Playlist : " + itemID)
            item_url = "{server}/mediabrowser/Users/{UserId}/Items/%s?format=json" % itemID
            jsonData = self.downloadUtils.downloadUrl(item_url)

            item_data = jsonData
            added = self.addPlaylistItem(playlist, item_data, server, userid)
            if(added and started == False):
                started = True
                utils.logMsg("PlayBackUtils", "Starting Playback Pre")
                xbmc.Player().play(playlist)
        
        if(started == False):
            utils.logMsg("PlayBackUtils", "Starting Playback Post")
            xbmc.Player().play(playlist)
        
        #seek to position
        seekTime = 0
        if(startPositionTicks != None):
            seekTime = (startPositionTicks / 1000) / 10000
            
        if seekTime > 0:
            self.seekToPosition(seekTime)
            
    def PLAYAllEpisodes(self, items):
        WINDOW = xbmcgui.Window(10000)

        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        playlist.clear()        
        
        for item in items:
        
            item_url = "{server}/mediabrowser/Users/{UserId}/Items/%s?format=json&ImageTypeLimit=1" % item["Id"]
            jsonData = self.downloadUtils.downloadUrl(item_url)
            
            item_data = jsonData
            self.addPlaylistItem(playlist, item_data, server, userid)
        
        xbmc.Player().play(playlist)
    
    def AddToPlaylist(self, itemIds):
        utils.logMsg("PlayBackUtils", "== ENTER: PLAYAllItems ==")
        WINDOW = xbmcgui.Window(10000)

        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)     
        
        for itemID in itemIds:
        
            utils.logMsg("PlayBackUtils", "Adding Item to Playlist : " + itemID)
            item_url = "{server}/mediabrowser/Users/{UserId}/Items/%s?format=json" % itemID
            jsonData = self.downloadUtils.downloadUrl(item_url)
            
            item_data = jsonData
            self.addPlaylistItem(playlist, item_data, server, userid)
    
        return playlist
    
    def addPlaylistItem(self, playlist, item, server, userid):

        id = item.get("Id")
        
        playurl = PlayUtils().getPlayUrl(server, id, item)
        utils.logMsg("PlayBackUtils", "Play URL: " + playurl)    
        thumbPath = API().getArtwork(item, "Primary")
        listItem = xbmcgui.ListItem(path=playurl, iconImage=thumbPath, thumbnailImage=thumbPath)
        self.setListItemProps(server, id, listItem, item)

        WINDOW = xbmcgui.Window(10000)

        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)

        # Can not play virtual items
        if (item.get("LocationType") == "Virtual") or (item.get("IsPlaceHolder") == True):
        
            xbmcgui.Dialog().ok(self.language(30128), self.language(30129))
            return False
            
        else:
        
            watchedurl = "%s/mediabrowser/Users/%s/PlayedItems/%s" % (server, userid, id)
            positionurl = "%s/mediabrowser/Users/%s/PlayingItems/%s" % (server, userid, id)
            deleteurl = "%s/mediabrowser/Items/%s" % (server, id)

            # set the current playing info
            WINDOW = xbmcgui.Window( 10000 )
            WINDOW.setProperty(playurl + "watchedurl", watchedurl)
            WINDOW.setProperty(playurl + "positionurl", positionurl)
            WINDOW.setProperty(playurl + "deleteurl", "")
            
            if item.get("Type") == "Episode" and addon.getSetting("offerDelete")=="true":
               WINDOW.setProperty(playurl + "deleteurl", deleteurl)
        
            WINDOW.setProperty(playurl + "runtimeticks", str(item.get("RunTimeTicks")))
            WINDOW.setProperty(playurl+"type", item.get("Type"))
            WINDOW.setProperty(playurl + "item_id", id)
            
            if (item.get("Type") == "Episode"):
                WINDOW.setProperty(playurl + "refresh_id", item.get("SeriesId"))
            else:
                WINDOW.setProperty(playurl + "refresh_id", id)            
            
            utils.logMsg("PlayBackUtils", "PlayList Item Url : " + str(playurl))
            
            playlist.add(playurl, listItem)
            
            return True