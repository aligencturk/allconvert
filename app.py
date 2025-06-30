from flask import Flask, request, render_template, jsonify, send_file
import yt_dlp
import os
import threading
import tempfile
import shutil
import zipfile
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import re
import time
import json

app = Flask(__name__)

# İndirme durumu takibi için
download_status = {}
downloaded_files = []

def get_artist_name_from_url(artist_url):
    """Spotify artist URL'sinden sanatçı adını çek"""
    try:
        if not artist_url or not artist_url.startswith('https://open.spotify.com/artist/'):
            return None
            
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        session = requests.Session()
        session.headers.update(headers)
        
        response = session.get(artist_url, timeout=8)
        
        if response.status_code != 200:
            print(f"Artist URL HTTP Error: {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Artist name çekme yöntemleri
        # Yöntem 1: og:title
        title_tag = soup.find('meta', property='og:title')
        if title_tag and title_tag.get('content'):
            title = title_tag['content']
            # "Artist Name | Spotify" formatını temizle
            clean_title = title.replace(' | Spotify', '').replace(' - Spotify', '').strip()
            if clean_title and len(clean_title) < 100:
                print(f"Artist URL'den bulunan: {clean_title}")
                return clean_title
        
        # Yöntem 2: page title
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text()
            clean_title = title.replace(' | Spotify', '').replace(' - Spotify', '').strip()
            if clean_title and len(clean_title) < 100:
                print(f"Artist page title'dan bulunan: {clean_title}")
                return clean_title
        
        # Yöntem 3: h1 tag (artist name usually in h1)
        h1_tag = soup.find('h1')
        if h1_tag:
            h1_text = h1_tag.get_text().strip()
            if h1_text and len(h1_text) < 100:
                print(f"Artist h1'den bulunan: {h1_text}")
                return h1_text
        
        return None
        
    except Exception as e:
        print(f"Artist URL çekme hatası: {e}")
        return None

def get_spotify_track_info(track_url):
    """Spotify track URL'sinden şarkı bilgilerini al - Geliştirilmiş sanatçı çekme"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        session = requests.Session()
        session.headers.update(headers)
        
        response = session.get(track_url, timeout=10)
        print(f"Response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"HTTP Error: {response.status_code}")
            return None, None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Farklı yöntemlerle şarkı bilgilerini bulmaya çalış
        song_name = None
        artist = None
        
        # ========== YENİ AGRESİF YÖNTEMLER ==========
        
        # Yöntem A: Tüm meta tag'leri tara ve artist anahtar kelimelerini ara
        all_meta_tags = soup.find_all('meta')
        for meta in all_meta_tags:
            content = meta.get('content', '').strip()
            name = meta.get('name', '').lower()
            prop = meta.get('property', '').lower()
            
            # Artist içeren tüm meta tag'leri kontrol et
            if ('artist' in name or 'musician' in name or 'creator' in name or 
                'artist' in prop or 'musician' in prop) and content and not artist:
                artist = content
                print(f"Meta artist bulundu ({name or prop}): {artist}")
            
            # Song/title içeren meta tag'leri kontrol et  
            if ('song' in name or 'title' in name or 'track' in name or
                'song' in prop or 'title' in prop) and content and not song_name:
                song_name = content
                print(f"Meta song bulundu ({name or prop}): {song_name}")
        
        # Yöntem B: DOM'da data-* attribute'leri ara
        try:
            elements_with_data = soup.find_all(attrs=lambda x: x and isinstance(x, dict) and any(key.startswith('data-') for key in x.keys()))
            for elem in elements_with_data:
                for attr, value in elem.attrs.items():
                    if attr.startswith('data-') and isinstance(value, str):
                        lower_attr = attr.lower()
                        if ('artist' in lower_attr or 'musician' in lower_attr or 'creator' in lower_attr) and not artist:
                            artist = value.strip()
                            print(f"Data attribute artist bulundu ({attr}): {artist}")
                        elif ('song' in lower_attr or 'track' in lower_attr or 'title' in lower_attr) and not song_name:
                            song_name = value.strip()
                            print(f"Data attribute song bulundu ({attr}): {song_name}")
        except Exception as e:
            print(f"Data attribute arama hatası: {e}")
            pass
        
        # Yöntem C: Sayfa içindeki tüm script tag'leri parse et ve değişken ara
        script_tags = soup.find_all('script')
        for script in script_tags:
            if script.string:
                script_content = script.string
                
                # JavaScript değişkenlerini ara
                patterns_for_artist = [
                    r'"artist":\s*"([^"]+)"',
                    r'"artist_name":\s*"([^"]+)"',
                    r'"creator":\s*"([^"]+)"',
                    r'"musician":\s*"([^"]+)"',
                    r'"by":\s*"([^"]+)"',
                    r'artist:\s*["\']([^"\']+)["\']',
                    r'creator:\s*["\']([^"\']+)["\']',
                    r'byArtist.*?"name":\s*"([^"]+)"'
                ]
                
                patterns_for_song = [
                    r'"name":\s*"([^"]+)"',
                    r'"title":\s*"([^"]+)"', 
                    r'"track_name":\s*"([^"]+)"',
                    r'"song":\s*"([^"]+)"',
                    r'name:\s*["\']([^"\']+)["\']',
                    r'title:\s*["\']([^"\']+)["\']'
                ]
                
                if not artist:
                    for pattern in patterns_for_artist:
                        match = re.search(pattern, script_content, re.IGNORECASE)
                        if match:
                            potential_artist = match.group(1).strip()
                            if len(potential_artist) > 1 and len(potential_artist) < 100:
                                artist = potential_artist
                                print(f"Script artist bulundu: {artist}")
                                break
                
                if not song_name:
                    for pattern in patterns_for_song:
                        match = re.search(pattern, script_content, re.IGNORECASE)
                        if match:
                            potential_song = match.group(1).strip()
                            if len(potential_song) > 1 and len(potential_song) < 150:
                                song_name = potential_song
                                print(f"Script song bulundu: {song_name}")
                                break
        
        # Yöntem D: CSS Selector'ları ile DOM arama
        css_selectors_for_artist = [
            '[data-testid*="artist"]',
            '[class*="artist"]',
            '[id*="artist"]',
            'a[href*="/artist/"]',
            '.artist-name',
            '.creator',
            '.musician'
        ]
        
        for selector in css_selectors_for_artist:
            if not artist:
                try:
                    elements = soup.select(selector)
                    for elem in elements:
                        text = elem.get_text().strip()
                        if text and len(text) > 1 and len(text) < 100 and not text.lower().startswith('http'):
                            artist = text
                            print(f"CSS selector artist bulundu ({selector}): {artist}")
                            break
                except:
                    continue
        
        # ========== MEVCUT YÖNTEMLER (İyileştirilmiş) ==========
        
        # Yöntem 1: og:title - Daha iyi parsing
        title_tag = soup.find('meta', property='og:title')
        if title_tag and title_tag.get('content'):
            title = title_tag['content']
            print(f"OG Title: {title}")
            
            # Daha fazla format denemesi
            formats_to_try = [
                r'(.+?)\s*-\s*song and lyrics by\s*(.+)',
                r'(.+?)\s*-\s*(.+?)(?:\s*\|\s*Spotify)?$',
                r'(.+?)\s*·\s*(.+)',
                r'(.+?)\s*by\s*(.+)',
                r'(.+?)\s*-\s*(.+)',
                r'(.+?)\s*\|\s*(.+)',
                r'(.+?)\s*/\s*(.+)'
            ]
            
            for fmt in formats_to_try:
                match = re.match(fmt, title, re.IGNORECASE)
                if match:
                    potential_song = match.group(1).strip()
                    potential_artist = match.group(2).strip()
                    
                    if not song_name and potential_song:
                        song_name = potential_song
                    if not artist and potential_artist:
                        artist = potential_artist
                    break
            
            # Eğer hala parse edemedik, başka dene
            if not song_name and not artist:
                if ' · ' in title:
                    parts = title.split(' · ')
                    song_name = parts[0].strip()
                    artist = parts[1].strip() if len(parts) > 1 else ""
                else:
                    song_name = title.strip()
        
        # Yöntem 1.5: og:description'dan sanatçı çıkar - Daha agresif
        if not artist:
            description_tag = soup.find('meta', property='og:description')
            if description_tag and description_tag.get('content'):
                description = description_tag['content']
                print(f"OG Description: {description}")
                
                # Daha fazla format denemesi
                desc_patterns = [
                    r'Song\s*·\s*([^·\n\r]+)',
                    r'Listen to .+ on Spotify\.\s*(.+?)[\.\n\r]',
                    r'by\s+(.+?)[\.\n\r]',
                    r'Artist:\s*(.+?)[\.\n\r]',
                    r'Performed by\s*(.+?)[\.\n\r]',
                    r'(.+?)\s*-\s*Spotify'
                ]
                
                for pattern in desc_patterns:
                    match = re.search(pattern, description, re.IGNORECASE)
                    if match:
                        potential_artist = match.group(1).strip()
                        if len(potential_artist) > 1 and len(potential_artist) < 100:
                            artist = potential_artist
                            print(f"Description pattern artist bulundu: {artist}")
                            break
        
        # Yöntem 2: page title - Daha iyi parsing
        if not song_name or not artist:
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text()
                print(f"Page Title: {title}")
                
                # Spotify'dan temizle
                clean_title = title.replace(' | Spotify', '').replace(' - Spotify', '').strip()
                
                # Farklı ayırıcılarla dene
                separators = [' - ', ' · ', ' by ', ' | ', ' / ']
                for sep in separators:
                    if sep in clean_title:
                        parts = clean_title.split(sep, 1)
                        if not song_name:
                            song_name = parts[0].strip()
                        if not artist and len(parts) > 1:
                            artist = parts[1].strip()
                        break
        
        # Yöntem 3: Meta tag'lerden daha kapsamlı arama
        if not artist or not song_name:
            # twitter:title dene
            twitter_title = soup.find('meta', attrs={'name': 'twitter:title'})
            if twitter_title and twitter_title.get('content'):
                title_content = twitter_title['content']
                if ' - ' in title_content:
                    parts = title_content.split(' - ', 1)
                    if not song_name:
                        song_name = parts[0].strip()
                    if not artist:
                        artist = parts[1].strip()
            
            # music:musician meta tag'i dene
            musician_tag = soup.find('meta', property='music:musician')
            if musician_tag and musician_tag.get('content') and not artist:
                artist = musician_tag['content']
            
            # music:song meta tag'i dene
            song_tag = soup.find('meta', property='music:song')
            if song_tag and song_tag.get('content') and not song_name:
                song_name = song_tag['content']
        
        # Yöntem 4: JSON-LD structured data - Geliştirilmiş
        if not song_name or not artist:
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    if script.string:
                        data = json.loads(script.string)
                        
                        # Recursive function to search through nested JSON
                        def extract_from_json(obj, song_found=None, artist_found=None):
                            if isinstance(obj, dict):
                                # Direct lookups
                                if not song_found and obj.get('name'):
                                    song_found = obj['name']
                                if not artist_found and obj.get('byArtist'):
                                    if isinstance(obj['byArtist'], dict):
                                        artist_found = obj['byArtist'].get('name')
                                    elif isinstance(obj['byArtist'], list) and len(obj['byArtist']) > 0:
                                        artist_found = obj['byArtist'][0].get('name', '')
                                
                                # Check for other artist fields
                                artist_fields = ['artist', 'creator', 'musician', 'performer']
                                for field in artist_fields:
                                    if not artist_found and obj.get(field):
                                        if isinstance(obj[field], str):
                                            artist_found = obj[field]
                                        elif isinstance(obj[field], dict):
                                            artist_found = obj[field].get('name', '')
                                        elif isinstance(obj[field], list) and len(obj[field]) > 0:
                                            first_artist = obj[field][0]
                                            if isinstance(first_artist, str):
                                                artist_found = first_artist
                                            elif isinstance(first_artist, dict):
                                                artist_found = first_artist.get('name', '')
                                
                                # Recurse into nested objects
                                for value in obj.values():
                                    song_found, artist_found = extract_from_json(value, song_found, artist_found)
                                    
                            elif isinstance(obj, list):
                                for item in obj:
                                    song_found, artist_found = extract_from_json(item, song_found, artist_found)
                            
                            return song_found, artist_found
                        
                        json_song, json_artist = extract_from_json(data, song_name, artist)
                        if not song_name and json_song:
                            song_name = json_song
                        if not artist and json_artist:
                            artist = json_artist
                            
                except Exception as e:
                    print(f"JSON-LD parse error: {e}")
                    continue
        
        # ========== TEMİZLEME VE SON İŞLEMLER ==========
        
        # Bilgileri temizle
        if song_name:
            # Gereksiz metinleri temizle
            song_name = song_name.replace('| Spotify', '').replace('- Spotify', '').strip()
            song_name = re.sub(r'\s+', ' ', song_name)  # Çoklu boşlukları temizle
            song_name = song_name.replace('"', '').replace("'", "")  # Tırnak işaretlerini kaldır
        
        if artist:
            # Gereksiz metinleri temizle
            artist = artist.replace('| Spotify', '').replace('- Spotify', '').strip()
            artist = re.sub(r'\s+', ' ', artist)  # Çoklu boşlukları temizle
            artist = artist.replace('"', '').replace("'", "")  # Tırnak işaretlerini kaldır
            
            # Eğer sanatçı Spotify URL'si ise, gerçek ismi çek
            if artist.startswith('https://open.spotify.com/artist/'):
                print(f"Artist URL tespit edildi, gerçek isim çekiliyor: {artist}")
                real_artist_name = get_artist_name_from_url(artist)
                if real_artist_name:
                    artist = real_artist_name
                else:
                    artist = "Bilinmeyen Sanatçı"
            
            # Eğer sanatçı adı çok uzunsa, muhtemelen yanlış parse edilmiştir
            if len(artist) > 100:
                artist = "Bilinmeyen Sanatçı"
                
            # Sanatçı adında yaygın sorunları düzelt
            if artist.lower().startswith('by '):
                artist = artist[3:].strip()
            if artist.lower().endswith(' - spotify'):
                artist = artist[:-10].strip()
        
        # Eğer song_name içinde hem sanatçı hem şarkı varsa, ayır
        if song_name and not artist and (' - ' in song_name or ' by ' in song_name):
            if ' - ' in song_name:
                parts = song_name.split(' - ', 1)
                song_name = parts[0].strip()
                artist = parts[1].strip()
            elif ' by ' in song_name:
                parts = song_name.split(' by ', 1)
                song_name = parts[0].strip()
                artist = parts[1].strip()
        
        # Varsayılan değerler
        if not song_name:
            track_id_match = re.search(r'/track/([a-zA-Z0-9]+)', track_url)
            if track_id_match:
                track_id = track_id_match.group(1)
                song_name = f"Track {track_id[:8]}"
            else:
                song_name = "Bilinmeyen Şarkı"
        
        if not artist:
            artist = "Bilinmeyen Sanatçı"
        
        print(f"✅ SONUÇ: {song_name} - {artist}")
        return song_name, artist
        
    except Exception as e:
        print(f"Hata: {e}")
        return None, None

def parse_spotify_links(text):
    """Metindeki Spotify linklerini bulup şarkı bilgilerini çek"""
    # Spotify track URL'lerini bul
    spotify_patterns = [
        r'https://open\.spotify\.com/track/([a-zA-Z0-9]+)',
        r'https://spotify\.com/track/([a-zA-Z0-9]+)',
        r'spotify:track:([a-zA-Z0-9]+)'
    ]
    
    tracks = []
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        for pattern in spotify_patterns:
            match = re.search(pattern, line)
            if match:
                track_id = match.group(1)
                track_url = f"https://open.spotify.com/track/{track_id}"
                
                song_name, artist = get_spotify_track_info(track_url)
                if song_name:
                    tracks.append({
                        'name': song_name,
                        'artist': artist or 'Bilinmeyen Sanatçı',
                        'url': track_url
                    })
                
                # Rate limiting için kısa bekleme
                time.sleep(0.5)
                break
    
    return tracks

def filter_videos(info_dict):
    """YouTube videolarını filtrele - shorts ve istenmeyen içerikleri atla"""
    if not info_dict:
        return "Video bilgisi bulunamadı"
    
    title = info_dict.get('title', '').lower()
    duration = info_dict.get('duration', 0)
    uploader = info_dict.get('uploader', '').lower()
    
    # Shorts'ları filtrele (60 saniyeden kısa)
    if duration and duration < 60:
        return "Video çok kısa (Shorts)"
    
    # Çok uzun videoları filtrele (15 dakikadan uzun)
    if duration and duration > 900:  # 15 dakika
        return "Video çok uzun"
    
    # Audio/Lyric versiyonlarını önceleyecek pozitif puanlama
    good_keywords = ['official audio', 'lyrics', 'lyric video', 'audio only', 'music only']
    has_good_keyword = any(keyword in title for keyword in good_keywords)
    
    # İstenmeyen video türleri - klip ve canlı performanslar
    bad_video_keywords = [
        'official video', 'music video', 'video clip', 'clip', 'mv',
        'live performance', 'live version', 'concert', 'live at',
        'reaction', 'review', 'tutorial', 'lesson', 'how to',
        'dance', 'choreography', 'tiktok', 'vine', 'meme',
        'cover version', 'acoustic version', 'remix', 'mashup'
    ]
    
    # Kötü anahtar kelimeler varsa filtrele (ama good keywords varsa geçir)
    for keyword in bad_video_keywords:
        if keyword in title and not has_good_keyword:
            return f"Video türü: {keyword}"
    
    # İstenmeyen genel içerik
    unwanted_keywords = [
        'shorts', 'short', 'karaoke', 'instrumental',
        'funny', 'parody', 'comedy', 'skit'
    ]
    
    for keyword in unwanted_keywords:
        if keyword in title:
            return f"İstenmeyen içerik: {keyword}"
    
    # Geçerli video
    return None

def get_best_music_result(search_query, song_name, artist):
    """En uygun müzik sonucunu bul - Audio/Lyric versiyonlarını önceleyerek"""
    try:
        # Öncelikli arama sorguları - Audio ve Lyric versiyonları önceleyerek
        priority_queries = [
            f"ytsearch5:{song_name} {artist} official audio",
            f"ytsearch5:{song_name} {artist} lyrics audio",
            f"ytsearch5:{song_name} {artist} lyric video",
            f"ytsearch5:{song_name} {artist} site:music.youtube.com",
            f"ytsearch5:{song_name} {artist} audio only",
            f"ytsearch5:{song_name} {artist} music only"
        ]
        
        # Alternatif arama sorguları
        fallback_queries = [
            f"ytsearch5:{song_name} {artist} -clip -video -live -remix -cover",
            f"ytsearch5:{search_query} official audio",
            f"ytsearch5:{search_query} lyrics",
            f"ytsearch3:{search_query} -remix -cover -live -video"
        ]
        
        all_queries = priority_queries + fallback_queries
        
        for query in all_queries:
            try:
                with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                    search_results = ydl.extract_info(query, download=False)
                    
                    if search_results and 'entries' in search_results:
                        # Sonuçları kalite skoruna göre sırala
                        scored_results = []
                        
                        for entry in search_results['entries']:
                            if entry:
                                # Video'yu filtrele
                                filter_result = filter_videos(entry)
                                if filter_result is None:  # Uygun video
                                    # Kalite skoru hesapla
                                    score = calculate_audio_quality_score(entry, song_name, artist)
                                    scored_results.append((score, entry))
                                else:
                                    print(f"Video filtrelendi: {filter_result}")
                        
                        # En yüksek skorlu sonucu döndür
                        if scored_results:
                            scored_results.sort(key=lambda x: x[0], reverse=True)
                            best_entry = scored_results[0][1]
                            print(f"✅ En iyi sonuç bulundu (skor: {scored_results[0][0]}): {best_entry.get('title', 'Bilinmeyen')}")
                            return best_entry['webpage_url']
                            
            except Exception as e:
                print(f"Arama hatası ({query}): {e}")
                continue
        
        return None
    except Exception as e:
        print(f"En iyi sonuç bulma hatası: {e}")
        return None

def calculate_audio_quality_score(entry, song_name, artist):
    """Video'nun audio kalitesi için skor hesapla"""
    score = 0
    title = entry.get('title', '').lower()
    uploader = entry.get('uploader', '').lower()
    duration = entry.get('duration', 0)
    view_count = entry.get('view_count', 0)
    
    # Pozitif audio indikatörleri
    audio_indicators = {
        'official audio': 50,
        'lyrics': 40,
        'lyric video': 40,
        'audio only': 45,
        'music only': 45,
        'original': 30,
        'official': 25
    }
    
    for indicator, points in audio_indicators.items():
        if indicator in title:
            score += points
    
    # YouTube Music kanalı bonus
    if 'music.youtube.com' in entry.get('webpage_url', ''):
        score += 60
    
    # Resmi sanatçı kanalı bonus
    if artist.lower() in uploader or 'official' in uploader:
        score += 30
    
    # Görüntülenme sayısı bonus (popüler şarkılar için)
    if view_count > 1000000:  # 1M+
        score += 20
    elif view_count > 100000:  # 100K+
        score += 10
    
    # Süre uygunluğu (2-8 dakika ideal)
    if 120 <= duration <= 480:  # 2-8 dakika
        score += 15
    elif 60 <= duration <= 600:  # 1-10 dakika
        score += 5
    
    # Şarkı ismi benzerliği
    if song_name.lower()[:10] in title:
        score += 25
    
    return score

def download_youtube_audio(search_query, output_path, song_id, song_name):
    """YouTube'dan şarkı indir"""
    
    def progress_hook(d):
        if d['status'] == 'downloading':
            percent_str = d.get('_percent_str', '0.0%').strip()
            download_status[song_id] = f"İndiriliyor... {percent_str}"
        elif d['status'] == 'finished':
            # İndirme bitti, şimdi FFmpeg ile dönüştürme başlayabilir
            download_status[song_id] = "İşleniyor..."

    try:
        download_status[song_id] = "Aranıyor..."
        
        # Güvenli dosya adı oluştur
        safe_filename = "".join(c for c in song_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        
        # Şarkı adı ve sanatçıyı ayır
        if ' - ' in song_name:
            parts = song_name.split(' - ', 1)
            clean_song = parts[0].strip()
            clean_artist = parts[1].strip()
        else:
            clean_song = song_name
            clean_artist = ""
        
        # En iyi müzik sonucunu bul
        download_status[song_id] = "En iyi sonuç aranıyor..."
        best_url = get_best_music_result(search_query, clean_song, clean_artist)
        
        if not best_url:
            download_status[song_id] = "Uygun şarkı bulunamadı"
            return False, "Uygun şarkı bulunamadı"
        
        # Bu satırı progress_hook'un hemen altına taşıdık
        # download_status[song_id] = "İndiriliyor..." 
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'progress_hooks': [progress_hook],
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(output_path, f'{safe_filename}.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Bulduğumuz en iyi URL'yi indir
            result = ydl.extract_info(best_url, download=True)
            
            if result:
                download_status[song_id] = "Tamamlandı"
                
                # Gerçek indirilen dosya yolunu bul
                # yt-dlp tarafından indirilen dosyanın gerçek adını al
                expected_mp3_path = os.path.join(output_path, f'{safe_filename}.mp3')
                
                # Klasördeki tüm dosyaları kontrol et ve en son oluşturulmuş mp3 dosyasını bul
                mp3_files = []
                for file in os.listdir(output_path):
                    if file.endswith('.mp3') and safe_filename.lower() in file.lower():
                        full_path = os.path.join(output_path, file)
                        mp3_files.append((full_path, os.path.getctime(full_path)))
                
                if mp3_files:
                    # En son oluşturulan dosyayı al
                    actual_file_path = max(mp3_files, key=lambda x: x[1])[0]
                    actual_filename = os.path.basename(actual_file_path)
                    
                    # İndirilen dosya yolunu kaydet
                    downloaded_files.append({
                        'song_id': song_id,
                        'filename': actual_filename,
                        'path': actual_file_path
                    })
                    print(f"✅ İndirildi: {song_name} -> {actual_filename}")
                else:
                    # Beklenen yolda dosya varsa onu kullan
                    if os.path.exists(expected_mp3_path):
                        downloaded_files.append({
                            'song_id': song_id,
                            'filename': f'{safe_filename}.mp3',
                            'path': expected_mp3_path
                        })
                        print(f"✅ İndirildi: {song_name} -> {safe_filename}.mp3")
                    else:
                        print(f"⚠️ Dosya bulunamadı: {song_name}")
                
                return True, "Başarılı"
            else:
                download_status[song_id] = "İndirme başarısız"
                return False, "İndirme başarısız"
                
    except Exception as e:
        error_msg = str(e)
        print(f"❌ İndirme hatası ({song_name}): {error_msg}")
        download_status[song_id] = f"Hata: {error_msg}"
        return False, error_msg

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/parse_spotify_links', methods=['POST'])
def parse_links():
    """Spotify linklerini parse et"""
    data = request.get_json()
    text = data.get('links_text', '')
    
    if not text.strip():
        return jsonify({'error': 'Link metni boş'}), 400
    
    try:
        tracks = parse_spotify_links(text)
        return jsonify({'tracks': tracks})
    except Exception as e:
        return jsonify({'error': f'Link parse hatası: {str(e)}'}), 400

@app.route('/download_songs', methods=['POST'])
def download_songs():
    """Şarkı listesini indir"""
    data = request.get_json()
    songs = data.get('songs', [])
    
    if not songs:
        return jsonify({'error': 'İndirilecek şarkı bulunamadı'}), 400
    
    # İndirme klasörü oluştur
    downloads_dir = os.path.join(os.getcwd(), 'downloads')
    if not os.path.exists(downloads_dir):
        os.makedirs(downloads_dir)
    
    # Bu session için alt klasör
    session_folder = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_dir = os.path.join(downloads_dir, session_folder)
    os.makedirs(temp_dir, exist_ok=True)
    
    # Dosya listesini temizle ve tüm durumları başlat
    global downloaded_files, download_status
    downloaded_files = []
    download_status = {f"song_{i}": "Bekleniyor" for i in range(len(songs))}
    
    # İndirme işlemini arka planda başlat
    def download_thread():
        for i, song in enumerate(songs):
            song_id = f"song_{i}"
            song_name = song.get('name', f'Şarkı {i+1}')
            artist = song.get('artist', '')
            
            # Arama sorgusu oluştur
            search_query = f"{song_name} {artist}".strip()
            
            download_youtube_audio(search_query, temp_dir, song_id, f"{song_name} - {artist}")
            
            # Rate limiting - şarkılar arası 2 saniye bekle
            time.sleep(2)
    
    thread = threading.Thread(target=download_thread)
    thread.start()
    
    return jsonify({'message': 'İndirme başlatıldı', 'temp_dir': temp_dir})

@app.route('/download_status')
def get_download_status():
    """İndirme durumunu kontrol et"""
    return jsonify({
        'status': download_status,
        'downloaded_files': downloaded_files
    })

@app.route('/download_zip')
def download_zip():
    """İndirilen dosyaları zip olarak indir"""
    if not downloaded_files:
        return jsonify({'error': 'İndirilmiş dosya bulunamadı'}), 400
    
    print(f"ZIP oluşturuluyor: {len(downloaded_files)} dosya bulundu")
    
    # Zip dosyası oluştur
    zip_path = tempfile.mktemp(suffix='.zip')
    
    files_added = 0
    with zipfile.ZipFile(zip_path, 'w') as zip_file:
        for file_info in downloaded_files:
            file_path = file_info['path']
            filename = file_info['filename']
            
            print(f"Kontrol ediliyor: {file_path}")
            
            if os.path.exists(file_path):
                try:
                    zip_file.write(file_path, filename)
                    files_added += 1
                    print(f"✅ ZIP'e eklendi: {filename}")
                except Exception as e:
                    print(f"❌ ZIP'e eklenirken hata: {filename} - {e}")
            else:
                print(f"❌ Dosya bulunamadı: {file_path}")
    
    print(f"ZIP tamamlandı: {files_added} dosya eklendi")
    
    if files_added == 0:
        return jsonify({'error': 'ZIP dosyasına hiçbir dosya eklenemedi. Dosya yolları kontrol edilsin.'}), 400
    
    return send_file(
        zip_path,
        as_attachment=True,
        download_name=f'spotify_songs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip',
        mimetype='application/zip'
    )

@app.route('/clear_status', methods=['POST'])
def clear_status():
    """İndirme durumunu temizle"""
    global download_status, downloaded_files
    download_status = {}
    downloaded_files = []
    return jsonify({'message': 'Durum temizlendi'})

@app.route('/load_readme_links', methods=['POST'])
def load_readme_links():
    """README.md dosyasından Spotify linklerini yükle"""
    try:
        if os.path.exists('README.md'):
            with open('README.md', 'r', encoding='utf-8') as f:
                content = f.read()
            
            tracks = parse_spotify_links(content)
            return jsonify({'tracks': tracks})
        else:
            return jsonify({'error': 'README.md dosyası bulunamadı'}), 404
    except Exception as e:
        return jsonify({'error': f'Dosya okuma hatası: {str(e)}'}), 400

def extract_track_ids_simple(text):
    """Basit yöntemle Spotify linklerinden track ID'lerini çıkar"""
    spotify_patterns = [
        r'https://open\.spotify\.com/track/([a-zA-Z0-9]+)',
        r'https://spotify\.com/track/([a-zA-Z0-9]+)',
        r'spotify:track:([a-zA-Z0-9]+)'
    ]
    
    track_ids = []
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        for pattern in spotify_patterns:
            match = re.search(pattern, line)
            if match:
                track_id = match.group(1)
                track_ids.append({
                    'track_id': track_id,
                    'url': f"https://open.spotify.com/track/{track_id}",
                    'name': f"Track {track_id[:8]}...",
                    'artist': 'Bilinmeyen Sanatçı'
                })
                break
    
    return track_ids

@app.route('/extract_track_ids', methods=['POST'])
def extract_track_ids():
    """Spotify linklerinden sadece track ID'lerini çıkar"""
    data = request.get_json()
    text = data.get('links_text', '')
    
    if not text.strip():
        return jsonify({'error': 'Link metni boş'}), 400
    
    try:
        track_ids = extract_track_ids_simple(text)
        return jsonify({'tracks': track_ids})
    except Exception as e:
        return jsonify({'error': f'Link çıkarma hatası: {str(e)}'}), 400

@app.route('/get_download_path')
def get_download_path():
    """İndirme klasörü yolunu döndür"""
    downloads_dir = os.path.join(os.getcwd(), 'downloads')
    return jsonify({'download_path': downloads_dir})

@app.route('/debug_files')
def debug_files():
    """İndirilen dosyaların durumunu kontrol et (debug amaçlı)"""
    debug_info = {
        'downloaded_files_count': len(downloaded_files),
        'files': []
    }
    
    for file_info in downloaded_files:
        file_path = file_info['path']
        debug_info['files'].append({
            'song_id': file_info['song_id'],
            'filename': file_info['filename'],
            'path': file_path,
            'exists': os.path.exists(file_path),
            'size': os.path.getsize(file_path) if os.path.exists(file_path) else 0
        })
    
    return jsonify(debug_info)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 