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

def get_spotify_track_info(track_url):
    """Spotify track URL'sinden şarkı bilgilerini al"""
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
        
        # Yöntem 1: og:title
        title_tag = soup.find('meta', property='og:title')
        if title_tag and title_tag.get('content'):
            title = title_tag['content']
            print(f"OG Title: {title}")
            
            # Çeşitli format denemeleri
            if ' - song and lyrics by ' in title.lower():
                parts = title.split(' - song and lyrics by ')
                song_name = parts[0].strip()
                artist = parts[1].strip()
            elif ' - ' in title:
                parts = title.split(' - ', 1)
                song_name = parts[0].strip()
                artist = parts[1].strip()
            elif ' · ' in title:
                parts = title.split(' · ')
                song_name = parts[0].strip()
                artist = parts[1].strip() if len(parts) > 1 else ""
            elif ' by ' in title:
                parts = title.split(' by ')
                song_name = parts[0].strip()
                artist = parts[1].strip()
            else:
                song_name = title.strip()
        
        # Yöntem 1.5: og:description'dan sanatçı çıkar
        if not artist:
            description_tag = soup.find('meta', property='og:description')
            if description_tag and description_tag.get('content'):
                description = description_tag['content']
                print(f"OG Description: {description}")
                
                # "Song · Artist" formatı
                if 'Song ·' in description:
                    match = re.search(r'Song · ([^·]+)', description)
                    if match:
                        artist = match.group(1).strip()
                # "Listen to SONG on Spotify. ARTIST" formatı
                elif 'Listen to' in description and 'on Spotify.' in description:
                    parts = description.split('on Spotify.')
                    if len(parts) > 1:
                        potential_artist = parts[1].strip()
                        # Nokta ile biten kısmı al
                        if '.' in potential_artist:
                            artist = potential_artist.split('.')[0].strip()
                        else:
                            artist = potential_artist
        
        # Yöntem 2: page title
        if not song_name:
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text()
                print(f"Page Title: {title}")
                if ' - ' in title and 'Spotify' in title:
                    title = title.replace(' | Spotify', '').replace(' - Spotify', '')
                    if ' - ' in title:
                        parts = title.split(' - ', 1)
                        song_name = parts[0].strip()
                        artist = parts[1].strip()
        
        # Yöntem 3: Meta tag'lerden daha kapsamlı arama
        if not artist or not song_name:
            # twitter:title dene
            twitter_title = soup.find('meta', attrs={'name': 'twitter:title'})
            if twitter_title and twitter_title.get('content'):
                title_content = twitter_title['content']
                if ' - ' in title_content and not song_name:
                    parts = title_content.split(' - ', 1)
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
        
        # Yöntem 4: JSON-LD structured data
        if not song_name or not artist:
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    if script.string:
                        data = json.loads(script.string)
                        if isinstance(data, dict):
                            if data.get('@type') == 'MusicRecording':
                                if not song_name:
                                    song_name = data.get('name')
                                if not artist and data.get('byArtist'):
                                    if isinstance(data['byArtist'], dict):
                                        artist = data['byArtist'].get('name')
                                    elif isinstance(data['byArtist'], list) and len(data['byArtist']) > 0:
                                        artist = data['byArtist'][0].get('name', '')
                            elif data.get('@type') == 'WebPage' and data.get('mainEntity'):
                                entity = data['mainEntity']
                                if entity.get('@type') == 'MusicRecording':
                                    if not song_name:
                                        song_name = entity.get('name')
                                    if not artist and entity.get('byArtist'):
                                        artist = entity['byArtist'].get('name')
                        break
                except Exception as e:
                    print(f"JSON-LD parse error: {e}")
                    continue
        
        # Bu kısmı kaldırdık - çünkü aşağıda daha iyi handle ediyoruz
        
        # Bilgileri temizle
        if song_name:
            # Gereksiz metinleri temizle
            song_name = song_name.replace('| Spotify', '').replace('- Spotify', '').strip()
            song_name = re.sub(r'\s+', ' ', song_name)  # Çoklu boşlukları temizle
        
        if artist:
            # Gereksiz metinleri temizle
            artist = artist.replace('| Spotify', '').replace('- Spotify', '').strip()
            artist = re.sub(r'\s+', ' ', artist)  # Çoklu boşlukları temizle
            
            # Eğer sanatçı adı çok uzunsa, muhtemelen yanlış parse edilmiştir
            if len(artist) > 100:
                artist = "Bilinmeyen Sanatçı"
        
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
        
        print(f"Found: {song_name} - {artist}")
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
        
        download_status[song_id] = "İndiriliyor..."
        
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best[duration>60][duration<900]',  # Audio öncelikli
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(output_path, f'{safe_filename}.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'extractaudio': True,  # Sadece ses çıkarımını zorla
            'audioformat': 'mp3',  # MP3 formatını zorla
            'audioquality': '192K',  # 192kbps kalite
            'prefer_free_formats': True,  # Özgür formatları tercih et
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Bulduğumuz en iyi URL'yi indir
            result = ydl.extract_info(best_url, download=True)
            
            if result:
                download_status[song_id] = "Tamamlandı"
                # İndirilen dosya yolunu kaydet
                downloaded_files.append({
                    'song_id': song_id,
                    'filename': f'{safe_filename}.mp3',
                    'path': os.path.join(output_path, f'{safe_filename}.mp3')
                })
                print(f"✅ İndirildi: {song_name}")
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
    import datetime
    session_folder = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_dir = os.path.join(downloads_dir, session_folder)
    os.makedirs(temp_dir, exist_ok=True)
    
    # Dosya listesini temizle
    global downloaded_files
    downloaded_files = []
    
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
    
    # Zip dosyası oluştur
    zip_path = tempfile.mktemp(suffix='.zip')
    
    with zipfile.ZipFile(zip_path, 'w') as zip_file:
        for file_info in downloaded_files:
            file_path = file_info['path']
            if os.path.exists(file_path):
                zip_file.write(file_path, file_info['filename'])
    
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001) 