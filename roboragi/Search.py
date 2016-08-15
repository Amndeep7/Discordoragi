'''
Search.py
Returns a built comment created from multiple databases when given a search term.
'''

import MAL
import AnimePlanet as AniP
import AniDB
import Hummingbird
import Anilist
import MU
import NU
import LNDB

import CommentBuilder
import DatabaseHandler

import traceback
import time

import sqlite3
import json

import pprint

USERNAME = ''

try:
    import Config
    USERNAME = Config.username
except ImportError:
    pass

sqlConn = sqlite3.connect('synonyms.db')
sqlCur = sqlConn.cursor()

try:
    sqlCur.execute('SELECT dbLinks FROM synonyms WHERE type = "Manga" and lower(name) = ?', ["despair simulator"])
except sqlite3.Error as e:
    print(e)

#Builds a manga reply from multiple sources
def buildMangaReply(searchText, message, isExpanded, blockTracking=False):
    try:
        ani = None
        mal = None
        mu = None
        ap = None
        
        try:
            sqlCur.execute('SELECT dbLinks FROM synonyms WHERE type = "Manga" and lower(name) = ?', [searchText.lower()])
        except sqlite3.Error as e:
            print(e)

        alternateLinks = sqlCur.fetchone()

        if (alternateLinks):
            synonym = json.loads(alternateLinks[0])       
            
            if (synonym['mal']):
                mal = MAL.getMangaDetails(synonym['mal'][0], synonym['mal'][1])
            if (synonym['ani']):
                ani = Anilist.getMangaDetailsById(synonym['ani'])
            if (synonym['mu']):
                mu = MU.getMangaURLById(synonym['mu'])
            if (synonym['ap']):
                ap = AniP.getMangaURLById(synonym['ap'])

        else:
            #Basic breakdown:
            #If Anilist finds something, use it to find the MAL version.
            #If hits either MAL or Ani, use it to find the MU version.
            #If it hits either, add it to the request-tracking DB.
            ani = Anilist.getMangaDetails(searchText)
            
            if ani:
                try:
                    mal = MAL.getMangaDetails(ani['title_romaji'])
                except:
                    pass

                if not mal:
                    try:
                        mal = MAL.getMangaDetails(ani['title_english'])
                    except:
                        pass

                if not mal:
                    mal = MAL.getMangaDetails(searchText)

            else:
                mal = MAL.getMangaDetails(searchText)

                if mal:
                    ani = Anilist.getMangaDetails(mal['title'])    

        #----- Finally... -----#
        if ani or mal:
            try:
                titleToAdd = ''
                if mal:
                    titleToAdd = mal['title']
                else:
                    try:
                        titleToAdd = ani['title_english']
                    except:
                        titleToAdd = ani['title_romaji']

                
                if not alternateLinks:
                    #MU stuff
                    if mal:
                        mu = MU.getMangaURL(mal['title'])
                    else:
                        mu = MU.getMangaURL(ani['title_romaji'])

                    #Do the anime-planet stuff
                    if mal and not ap:
                        if mal['title'] and not ap:
                            ap = AniP.getMangaURL(mal['title'])
                        if mal['english'] and not ap:
                            ap = AniP.getMangaURL(mal['english'])
                        if mal['synonyms'] and not ap:
                            for synonym in mal['synonyms']:
                                if ap:
                                    break
                                ap = AniP.getMangaURL(synonym)

                    if ani and not ap:
                        if ani['title_english'] and not ap:
                            ap = AniP.getMangaURL(ani['title_english'])
                        if ani['title_romaji'] and not ap:
                            ap = AniP.getMangaURL(ani['title_romaji'])
                        if ani['synonyms'] and not ap:
                            for synonym in ani['synonyms']:
                                if ap:
                                    break
                                ap = AniP.getMangaURL(synonym)
                if not blockTracking:
                    DatabaseHandler.addRequest(titleToAdd, 'Manga', message.author.name, message.server)
            except:
                traceback.print_exc()
                pass
        
        return CommentBuilder.buildMangaComment(isExpanded, mal, ani, mu, ap)
        
    except Exception as e:
        traceback.print_exc()
        return None

#Builds a manga search for a specific series by a specific author
def buildMangaReplyWithAuthor(searchText, authorName, message, isExpanded, blockTracking=False):
    try:        
        ani = Anilist.getMangaWithAuthor(searchText, authorName)
        mal = None
        mu = None
        ap = None
        
        if ani:
            mal = MAL.getMangaCloseToDescription(searchText, ani['description'])
            ap = AniP.getMangaURL(ani['title_english'], authorName)
        else:
            ap = AniP.getMangaURL(searchText, authorName)

        mu = MU.getMangaWithAuthor(searchText, authorName)

        if ani:
            try:
                titleToAdd = ''
                if mal is not None:
                    titleToAdd = mal['title']
                else:
                    titleToAdd = ani['title_english']
				
                if not blockTracking:
                    DatabaseHandler.addRequest(titleToAdd, 'Manga', message.author.name, message.server)
            except:
                traceback.print_exc()
                pass
            
            return CommentBuilder.buildMangaComment(isExpanded, mal, ani, mu, ap)
    
    except Exception as e:
        traceback.print_exc()
        return None

#Builds an anime reply from multiple sources
def buildAnimeReply(searchText, message, isExpanded, blockTracking=False):
    try:
        mal = {'search_function': MAL.getAnimeDetails,
                'synonym_function': MAL.getSynonyms,
                'checked_synonyms': [],
                'result': None}
        hb = {'search_function': Hummingbird.getAnimeDetails,
                'synonym_function': Hummingbird.getSynonyms,
                'checked_synonyms': [],
                'result': None}
        ani = {'search_function': Anilist.getAnimeDetails,
                'synonym_function': Anilist.getSynonyms,
                'checked_synonyms': [],
                'result': None}
        ap = {'search_function': AniP.getAnimeURL,
                'result': None}
        adb = {'search_function': AniDB.getAnimeURL,
                'result': None}
        
        try:
            sqlCur.execute('SELECT dbLinks FROM synonyms WHERE type = "Anime" and lower(name) = ?', [searchText.lower()])
        except sqlite3.Error as e:
            print(e)

        alternateLinks = sqlCur.fetchone()

        if (alternateLinks):
            synonym = json.loads(alternateLinks[0])

            if synonym:
                malsyn = None
                if 'mal' in synonym and synonym['mal']:
                    malsyn = synonym['mal']

                hbsyn = None
                if 'hb' in synonym and synonym['hb']:
                    hbsyn = synonym['hb']

                anisyn = None
                if 'ani' in synonym and synonym['ani']:
                    anisyn = synonym['ani']

                apsyn = None
                if 'ap' in synonym and synonym['ap']:
                    apsyn = synonym['ap']

                adbsyn = None
                if 'adb' in synonym and synonym['adb']:
                    adbsyn = synonym['adb']

                mal['result'] = MAL.getAnimeDetails(malsyn[0],malsyn[1]) if malsyn else None
                hb['result'] = Hummingbird.getAnimeDetailsById(hbsyn) if hbsyn else None
                ani['result'] = Anilist.getAnimeDetailsById(anisyn) if anisyn else None
                ap['result'] = AniP.getAnimeURLById(apsyn) if apsyn else None
                adb['result'] = AniDB.getAnimeURLById(adbsyn) if adbsyn else None
                
        else:
            data_sources = [ani, hb, mal]
            #aux_sources = [ap, adb]
            aux_sources = [ap]

            synonyms = set([searchText])

            for x in range(len(data_sources)):
                for source in data_sources:
                    if source['result']:
                        break
                    else:
                        for synonym in synonyms:
                            if synonym in source['checked_synonyms']:
                                continue

                            source['result'] = source['search_function'](synonym)
                            source['checked_synonyms'].append(synonym)

                            if source['result']:
                                break

                    if source['result']:
                        synonyms.update([synonym.lower() for synonym in source['synonym_function'](source['result'])])

            for source in aux_sources:
                for synonym in synonyms:     
                    source['result'] = source['search_function'](synonym)

                    if source['result']:
                        break

        if ani['result'] or hb['result'] or mal['result']:
            try:
                titleToAdd = ''
                if mal['result']:
                    titleToAdd = mal['result']['title']
                if hb['result']:
                    titleToAdd = hb['result']['title']
                if ani['result']:
                    titleToAdd = ani['result']['title_romaji']

                if not blockTracking:
                    DatabaseHandler.addRequest(titleToAdd, 'Anime', message.author.name, message.server)
            except:
                traceback.print_exc()
                pass
        
        return CommentBuilder.buildAnimeComment(isExpanded, mal['result'], hb['result'], ani['result'], ap['result'], adb['result'])

    except Exception as e:
        traceback.print_exc()
        return None

#Builds an LN reply from multiple sources
def buildLightNovelReply(searchText, isExpanded, baseComment, blockTracking=False):
    try:
        mal = {'search_function': MAL.getLightNovelDetails,
                'synonym_function': MAL.getSynonyms,
                'checked_synonyms': [],
                'result': None}
        ani = {'search_function': Anilist.getLightNovelDetails,
                'synonym_function': Anilist.getSynonyms,
                'checked_synonyms': [],
                'result': None}
        nu = {'search_function': NU.getLightNovelURL,
                'result': None}
        lndb = {'search_function': LNDB.getLightNovelURL,
                'result': None}
        
        try:
            sqlCur.execute('SELECT dbLinks FROM synonyms WHERE type = "LN" and lower(name) = ?', [searchText.lower()])
        except sqlite3.Error as e:
            print(e)

        alternateLinks = sqlCur.fetchone()

        if (alternateLinks):
            synonym = json.loads(alternateLinks[0])

            if synonym:
                malsyn = None
                if 'mal' in synonym and synonym['mal']:
                    malsyn = synonym['mal']

                anisyn = None
                if 'ani' in synonym and synonym['ani']:
                    anisyn = synonym['ani']

                nusyn = None
                if 'nu' in synonym and synonym['nu']:
                    nusyn = synonym['nu']

                lndbsyn = None
                if 'lndb' in synonym and synonym['lndb']:
                    lndbsyn = synonym['lndb']

                mal['result'] = MAL.getLightNovelDetails(malsyn[0],malsyn[1]) if malsyn else None
                ani['result'] = Anilist.getMangaDetailsById(anisyn) if anisyn else None
                nu['result'] = NU.getLightNovelById(nusyn) if nusyn else None
                lndb['result'] = LNDB.getLightNovelById(lndbsyn) if lndbsyn else None
                
        else:
            data_sources = [ani, mal]
            aux_sources = [nu, lndb]

            synonyms = set([searchText])

            for x in range(len(data_sources)):
                for source in data_sources:
                    if source['result']:
                        break
                    else:
                        for synonym in synonyms:
                            if synonym in source['checked_synonyms']:
                                continue

                            source['result'] = source['search_function'](synonym)
                            source['checked_synonyms'].append(synonym)

                            if source['result']:
                                break

                    if source['result']:
                        synonyms.update([synonym.lower() for synonym in source['synonym_function'](source['result'])])

            for source in aux_sources:
                for synonym in synonyms:     
                    source['result'] = source['search_function'](synonym)

                    if source['result']:
                        break

        if ani['result'] or mal['result']:
            try:
                titleToAdd = ''
                if mal['result']:
                    titleToAdd = mal['result']['title']
                if ani['result']:
                    try:
                        titleToAdd = ani['result']['title_romaji']
                    except:
                        titleToAdd = ani['result']['title_english']

                if (str(baseComment.subreddit).lower is not 'nihilate') and (str(baseComment.subreddit).lower is not 'roboragi') and not blockTracking:
                    DatabaseHandler.addRequest(titleToAdd, 'LN', baseComment.author.name, baseComment.subreddit)
            except:
                traceback.print_exc()
                pass
        
        return CommentBuilder.buildLightNovelComment(isExpanded, mal['result'], ani['result'], nu['result'], lndb['result'])

    except Exception as e:
        traceback.print_exc()
        return None

#Checks if the bot is the parent of this comment.
def isBotAParent(comment, reddit):
    try:
        parentComment = reddit.get_info(thing_id=comment.parent_id)

        if (parentComment.author.name == USERNAME):
            return True
        else:
            return False
            
    except:
        #traceback.print_exc()
        return False

#Checks if the message is valid (i.e. not already seen, not a post by Roboragi and the parent commenter isn't Roboragi)
def isValidMessage(message):
    try:
        if (DatabaseHandler.messageExists(message.id)):
            return False

        try:
            if (message.author.name == USERNAME):
                DatabaseHandler.addMessage(message.id, message.author.name, message.server, False)
                return False
        except:
            pass

        return True
        
    except:
        traceback.print_exc()
        return False

#Checks if a submission is valid (i.e. not already seen, not a submission by Roboragi). This WAS used before, but I have since removed the functionality it was relevant to.
def isValidSubmission(submission):
    try:
        if (DatabaseHandler.messageExists(submission.id)):
            return False

        try:
            if (submission.author.name == 'Roboragi'):
                DatabaseHandler.addMessage(submission.id, submission.author.name, submission.subreddit, False)
                return False
        except:
            pass

        return True
        
    except:
        traceback.print_exc()
        return False
