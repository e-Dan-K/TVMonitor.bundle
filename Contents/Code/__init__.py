import os
# TODO: Remove when Plex framework allows token in the header.
import urllib2

NAME = 'TVMonitor'
ART = 'art-default.jpg'
ICON = 'icon-default.jpg'
PREFIX = '/video/' + NAME.lower()

if 'PLEXTOKEN' in os.environ:
    PLEX_TOKEN = os.environ['PLEXTOKEN']
else:
    PLEX_TOKEN = None

PLEX_IP = '127.0.0.1'
PLEX_PORT = os.environ['PLEXSERVERPORT']

user_sorts = {}
SortOrder = ['by Air Date', 'Alphabetically', 'by Watched Date']
def SortOrderGet():
	global user_sorts
	user = Request.Headers.get('X-Plex-Token', '')
	if not user in user_sorts:
		user_sorts[user] = 0
	return user_sorts[user]
	
def SortOrderNext():
	global user_sorts
	user = Request.Headers.get('X-Plex-Token', '')
	if not user in user_sorts:
		user_sorts[user] = 0
	user_sorts[user] = user_sorts[user] + 1   # really, python?
	if user_sorts[user] >= len(SortOrder):
		user_sorts[user] = 0
	return user_sorts[user]

def SortOrderGetName():
	cur_sort = SortOrderGet()
	return SortOrder[cur_sort]
	

####################################################################################################
def Start():
	Log("Hello from TV Monitor!!!")
	ObjectContainer.title1 = NAME
	HTTP.CacheTime = 0

###################################################################################################
@handler(PREFIX, NAME, art=ART, thumb=ICON)
def MainMenu():
	try:
		#Check Token
		if PLEX_TOKEN == None:
			raise Exception('Cannot find Plex Media Server token')

		playlist = LoadPlaylist()
		if playlist == 0:
			return ObjectContainer(header="TVMonitor", message="To use TVMonitor, make a playlist 'TVM', and add one episode from each series that you wish to monitor.")
			
		tracked_shows = ParseShowsFromPlaylist(playlist)
		episode_list = FindNextEpisodeFromShowList(tracked_shows)
		return DisplayEpisodesData(episode_list)
	except Exception as error:
		Log("exception in MainMenu")
		err = repr(error)
		Log(err)
		return ObjectContainer(header="Empty", message=err)

def MakeURL(url):
	plex_url = "http://%s:%s%s" % (PLEX_IP, PLEX_PORT, url)
	return plex_url

def XMLFromURLforCurrentRequest(url):
	# TODO Change to native framework call, when Plex allows token in header...
	# Really, should just be "xml = XML.ElementFromURL(url, headers={'X-Plex-Token': Request.Headers.get('X-Plex-Token', '')})"
	# But PLEX library overrides X-Plex-Token and resets it to the Admin's token regardless.
	opener = urllib2.build_opener(urllib2.HTTPHandler)
	request = urllib2.Request(url)
	request.add_header('X-Plex-Token', Request.Headers.get('X-Plex-Token', ''))
	response = opener.open(request).read()
	xml = XML.ElementFromString(response)
	return xml

def LoadPlaylist():
	url = MakeURL('/playlists')
	Log(url)
	all_playlists_xml = XMLFromURLforCurrentRequest(url)
	all_playlists = all_playlists_xml.xpath("//Playlist")

	for playlist in all_playlists:
		if playlist.get('title') == "TVM":
			playlist_key = playlist.get('key')
			return playlist_key

	return 0
	
def ParseShowsFromPlaylist(playlist):
	url = MakeURL(playlist)
	Log(url)
	playlist_xml = XMLFromURLforCurrentRequest(url)
	playlist = playlist_xml.xpath("//Video")
	
	show_list = {}
	for playlist_item in playlist:
		type = playlist_item.get('type')
		# Only add TV shows!
		if type == "episode":
			key = playlist_item.get('grandparentRatingKey')
			if key not in show_list:
				title = playlist_item.get('grandparentTitle')
				show_list[key] = {"key": key, "title": title}
	Log("Number of Shows: %s" % (len(show_list)))
	
	show_list = AddDetailToShows(show_list)
	return show_list
	
def AddDetailToShows(show_list):
	for show_id in show_list:
		base_url = "/library/metadata/%s" % (show_id)
		url = MakeURL(base_url)
		Log(url)
		show_xml = XMLFromURLforCurrentRequest(url)
		show = show_xml.xpath("//Directory")[0]
		title = show.get('title')
		titleSort = SafeGet(show, "titleSort")
		if titleSort == '':
			titleSort = title
		summary = show.get('summary')
		last_viewed = Datetime.FromTimestamp(SafeGetAsInt(show, 'lastViewedAt'))
		num_episodes = SafeGetAsInt(show, 'leafCount')
		num_watched_episodes = SafeGetAsInt(show, 'viewedLeafCount')
		num_unwatched_episodes = num_episodes - num_watched_episodes
		air_date = Datetime.ParseDate(SafeGetAsDate(show, 'originallyAvailableAt'))
		art = SafeGet(show, 'art')
		thumb = SafeGet(show, 'thumb')
		banner = SafeGet(show, 'banner')
		add_keys = {
			"key_id": show_id,	# ie 365
			"key": base_url,	# ie '/library/metadata/365'
			"name": title,
			"title_sort": titleSort,
			"summary": summary,
			"last_viewed": last_viewed, 
			"num_episodes": num_episodes,
			"num_watched_episodes": num_watched_episodes,
			"num_unwatched_episodes": num_unwatched_episodes,
			"art": art,
			"thumb": thumb,
			"banner": banner,
			"air_date": air_date}
		show_list[show_id].update(add_keys)
		
	return show_list

def FindNextEpisodeFromShowList(show_list):
	episode_list = {}
	for show_id, show_details in show_list.items():
		base_url = "/library/metadata/%s/allLeaves" % (show_id)
		url = MakeURL(base_url)
		episodes_xml = XMLFromURLforCurrentRequest(url)
		Log(url)
		all_episodes = episodes_xml.xpath("//Video")
		for episode in all_episodes:
			viewed = SafeGetAsInt(episode, 'viewCount')
			if viewed == 0:
				episode_id = SafeGet(episode, "ratingKey")
				episode_list[show_id] = {
					"ratingKey": episode_id,
					"key": SafeGet(episode, "key"),
					"show": SafeGet(episode, "grandparentTitle"),
					"show_key": show_details["key"],
					"title": SafeGet(episode, "title"),
					"show_sort": show_details["title_sort"],
					"summary": SafeGet(episode, "summary"),
					"num_unwatched": show_details["num_unwatched_episodes"],
					"art": show_details["art"],
					"thumb": show_details["thumb"],
					"banner": show_details["banner"],
					"air_date": Datetime.ParseDate(SafeGetAsDate(episode, 'originallyAvailableAt')),
					"watched_date": show_details["last_viewed"]
				}
				break

	return episode_list
	
	
def SafeGetAsDate(item, key):
	val = SafeGet(item, key)
	if val == '':
		val = '1927-09-07'	# Date TV was invented :-)
	return val
	
def SafeGetAsInt(item, key):
	val = SafeGet(item, key)
	if val == '':
		val = 0
	else:
		val = int(val)
	return val

def SafeGet(item, key):
	val = item.get(key)
	if val is None:
		val = ''
	return val

def DisplayEpisodesData(episode_list):
	oc = ObjectContainer(
		title1="TVMonitor",
		no_history=True,
		)
	oc.add(DirectoryObject(
		key = Callback(DoNothing), 
		title = "Sorted %s (Help)" % (SortOrderGetName())))
	oc.add(DirectoryObject(
		key = Callback(ChangeSort), 
		title = "Change Sort"))
	
	episodes = sorted(episode_list.values(), key=EpisodeSort)
	for episode_details in episodes:
		episode_object = TVShowObject(
			key=Callback(RedirectToShow, media_id=episode_details['show_key']),
			rating_key=episode_details['show_key'],
			title="%s: (%d new)" % (episode_details["show"], episode_details["num_unwatched"]),
			summary="Unwatched: %d" % (episode_details["num_unwatched"]),
			thumb=episode_details["thumb"],
			art=episode_details["art"]
		)
		oc.add(episode_object)
	return oc

def EpisodeSort(episode):
	cur_sort = SortOrderGetName()
	if cur_sort == 'by Air Date':
		return Datetime.Now() - episode['air_date']
	elif cur_sort == 'Alphabetically':
		return episode['show_sort']
	else: # 'by Watched Date'
		return Datetime.Now() - episode['watched_date']


@route(PREFIX + '/tvshow')
def RedirectToShow(media_id):
	# This doesn't redirect in all clients... 
	library_url = "%s" % (media_id)
	return Redirect(library_url)

@route(PREFIX + '/changesort')
def ChangeSort():
	SortOrderNext()
	
	Log("Changed to "+SortOrderGetName())
	return Redirect(PREFIX)

@route(PREFIX + '/donothing')
def DoNothing():
	Log("Do Nothing")
	return ObjectContainer(header="TVMonitor", message=
		"Sorting can be:\n"+
		"'by Air Date': Newest Aired Unwatched Episode First\n"+
		"'Alphabetically': Duh...\n"+
		"'by Watched Date': Most Recently Watched Series First")
	
# https://us.v-cdn.net/6025034/uploads/editor/rg/jxvpxxxt63r6.pdf

