# Spotify Playlist İndirici

## 📋 Proje Açıklaması

Bu proje, Spotify'dan şarkı bilgilerini alıp YouTube'dan MP3 formatında indirmenizi sağlayan bir web uygulamasıdır. Kişisel kullanım amacıyla geliştirilmiştir ve Flask framework'ü ile oluşturulmuştur.

## 🚀 Özellikler

### 🎵 İndirme Yöntemleri
- **Manuel Şarkı Girişi**: Şarkı adı ve sanatçı adı girerek indirme
- **Spotify Link İşleme**: Spotify şarkı linklerini otomatik olarak analiz etme
- **Toplu Link İşleme**: Birden fazla Spotify linkini aynı anda işleme
- **Dosyadan Link Yükleme**: README.md dosyasından linkleri otomatik okuma

### 🔍 Gelişmiş Arama ve Filtreleme
- **YouTube Music Önceliği**: YouTube Music'ten indirme önceliği
- **Akıllı Video Filtreleme**: 
  - YouTube Shorts'ları otomatik reddetme
  - 60 saniye - 15 dakika arasında süre filtresi
  - Remix, cover, live, karaoke versiyonlarını filtreleme
  - Yüksek kalite önceliği

### 🎨 Kullanıcı Arayüzü
- **Modern Tasarım**: Spotify temalı gradient arayüz
- **Gerçek Zamanlı İlerleme**: Yüzdelik indirme göstergesi  
- **Animasyonlu Durumlar**: Pulse efekti ile görsel geri bildirim
- **Responsive Design**: Mobil ve masaüstü uyumlu

### 📁 Dosya Yönetimi
- **Organize Klasör Yapısı**: Tarih/saat damgalı klasörler
- **Güvenli Dosya İsimleri**: Özel karakterleri temizleme
- **ZIP İndirimi**: Tüm dosyaları tek seferde indirme

## 🛠️ Kurulum

### Sistem Gereksinimleri
- Python 3.7+
- macOS, Linux veya Windows
- İnternet bağlantısı

### Adım 1: Projeyi Klonlama
```bash
git clone [repo-url]
cd spotifylisteindir
```

### Adım 2: Bağımlılıkları Yükleme
```bash
pip3 install -r requirements.txt
```

### Adım 3: Uygulamayı Çalıştırma
```bash
python3 app.py
```

Uygulama `http://localhost:5001` adresinde çalışacaktır.

## 📋 Bağımlılıklar (requirements.txt)

```
flask==2.3.3
yt-dlp==2023.10.13
requests==2.31.0
beautifulsoup4==4.12.2
lxml==4.9.3
```

## 📖 Kullanım Kılavuzu

### 1. Manuel Şarkı İndirme
1. Ana sayfada "Şarkı Adı" ve "Sanatçı" alanlarını doldurun
2. "İndir" butonuna tıklayın
3. İndirme işlemi tamamlandığında dosya downloads klasörüne kaydedilir

### 2. Spotify Link İndirme
1. "Spotify Link" alanına tam Spotify URL'sini yapıştırın
   - Örnek: `https://open.spotify.com/track/2ROzkwkMWynZllbxcktMqB`
2. "Spotify Linkini İşle" butonuna tıklayın
3. Şarkı bilgileri otomatik olarak çekilir ve indirme başlar

### 3. Toplu Link İşleme
ctrl+ a ile hepsini seç müzikleri !
1. "Spotify Linkleri" alanına her satıra bir link olmak üzere birden fazla link yapıştırın
2. "Spotify Linklerini İşle" butonuna tıklayın
3. Tüm linkler sırayla işlenir

### 4. Dosyadan Link Yükleme
1. "README.md Linklerini Yükle" butonuna tıklayın
2. README.md dosyasındaki Spotify linkleri otomatik olarak okunur ve işlenir

## 🔧 Teknik Detaylar

### Uygulama Mimarisi

#### Backend (Flask)
- **Framework**: Flask 2.3.3
- **Port**: 5001 (macOS'ta AirPlay Receiver çakışmasını önlemek için)
- **Threading**: Çoklu indirme desteği

#### Frontend (HTML/CSS/JavaScript)
- **Responsive Design**: Bootstrap benzeri grid sistem
- **Real-time Updates**: AJAX ile anlık güncelleme
- **Progress Tracking**: Görsel ilerleme çubuğu

### Spotify Metadata Çıkarma

Uygulama, Spotify API kullanmak yerine web scraping yöntemi kullanır:

```python
def parse_spotify_url(url):
    # Birden fazla yöntem dener:
    # 1. og:title meta etiketi
    # 2. og:description meta etiketi  
    # 3. JSON-LD structured data
    # 4. Sayfa başlığı analizi
```

#### Çıkarma Yöntemleri
1. **OpenGraph Tags**: `og:title`, `og:description`
2. **JSON-LD**: Structured data parsing
3. **Meta Tags**: Description ve keywords
4. **Title Parsing**: Sayfa başlığından bilgi çıkarma

### YouTube İndirme Sistemi

#### yt-dlp Konfigürasyonu
```python
ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'outtmpl': '%(title)s.%(ext)s',
}
```

#### Video Filtreleme Algoritması
```python
def filter_videos(entries):
    filtered = []
    for entry in entries:
        # Süre kontrolü (60s - 15dk)
        if not (60 <= entry.get('duration', 0) <= 900):
            continue
            
        # İstenmeyen içerik filtresi
        title_lower = entry.get('title', '').lower()
        if any(term in title_lower for term in EXCLUDED_TERMS):
            continue
            
        # YouTube Shorts filtresi
        if entry.get('duration', 0) < 60:
            continue
            
        filtered.append(entry)
    
    return filtered
```

### Dosya Organizasyonu

#### Klasör Yapısı
```
downloads/
├── 20231201_143022/          # Tarih-saat damgalı klasör
│   ├── Song1 - Artist1.mp3
│   ├── Song2 - Artist2.mp3
│   └── download_20231201_143022.zip
└── 20231201_150315/
    └── ...
```

#### Güvenli Dosya İsimlendirme
```python
def safe_filename(filename):
    # Özel karakterleri temizle
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Uzunluk sınırla
    return filename[:100]
```

## 🔄 İş Akışı

### 1. Spotify Link İşleme Süreci
```
Spotify URL → Web Scraping → Metadata Extraction → 
Song Title & Artist → YouTube Search → Video Filtering → 
MP3 Download → File Organization → ZIP Creation
```

### 2. İndirme Süreci Detayları
1. **Bağlantı Kontrolü**: Spotify URL formatı doğrulama
2. **Metadata Çıkarma**: Şarkı ve sanatçı bilgisi alma
3. **YouTube Arama**: Optimized search query oluşturma
4. **Video Filtreleme**: Kalite ve içerik filtreleri
5. **İndirme**: yt-dlp ile MP3 dönüştürme
6. **Dosya Yönetimi**: Organize klasör yapısı
7. **Hız Kontrolü**: 2 saniye gecikme (rate limiting)

### 3. Hata Yönetimi
- **HTTP 403 Errors**: User-agent rotation
- **Video Bulunamadı**: Alternative search terms
- **İndirme Hataları**: Retry mekanizması
- **Dosya Çakışmaları**: Otomatik yeniden adlandırma

## 🎛️ Konfigürasyon

### Uygulama Ayarları
```python
# app.py içinde
app.config['DOWNLOAD_FOLDER'] = 'downloads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
```

### İndirme Ayarları
```python
# Video süre limitleri
MIN_DURATION = 60      # 1 dakika
MAX_DURATION = 900     # 15 dakika

# Kalite ayarları
AUDIO_QUALITY = '192'  # 192 kbps MP3

# Rate limiting
DOWNLOAD_DELAY = 2     # 2 saniye
```

## 🛡️ Güvenlik ve Yasal Uyarılar

### Kişisel Kullanım
- Bu uygulama **sadece kişisel kullanım** için tasarlanmıştır
- Telif hakkı korumalı içeriklerin indirilmesi yasal sorumluluk doğurabilir
- Kullanıcılar, yerel yasalara uygun davranmakla yükümlüdür

### Güvenlik Önlemleri
- **Rate Limiting**: Aşırı istek önleme
- **Input Validation**: URL format kontrolü
- **File Sanitization**: Güvenli dosya isimleri
- **Error Handling**: Güvenli hata yönetimi

## 🐛 Sorun Giderme

### Yaygın Sorunlar

#### Port 5000 Kullanımda
**Semptom**: `OSError: [Errno 48] Address already in use`
**Çözüm**: macOS'ta AirPlay Receiver'ı kapatın veya port 5001 kullanın

#### Python Modülü Bulunamadı
**Semptom**: `ModuleNotFoundError`
**Çözüm**: 
```bash
pip3 install -r requirements.txt
```

#### YouTube İndirme Hataları
**Semptom**: HTTP 403 errors
**Çözüm**: yt-dlp'yi güncelleyin:
```bash
pip3 install --upgrade yt-dlp
```

#### Spotify Link Parse Edememe
**Semptom**: Şarkı bilgisi çıkarılamıyor
**Çözüm**: 
- Link formatını kontrol edin
- İnternet bağlantınızı kontrol edin
- Spotify'ın site yapısı değişmiş olabilir

### Debug Modu
```python
# Detaylı log için
app.run(debug=True, host='0.0.0.0', port=5001)
```

## 📊 Performans Optimizasyonları

### Implemented Optimizations
1. **Video Filtering**: İstenmeyen içeriği erkenden filtrele
2. **Smart Search**: Optimized YouTube search queries
3. **Rate Limiting**: Sunucu yükünü azalt
4. **Progress Tracking**: Kullanıcı deneyimi iyileştirme
5. **Parallel Processing**: Çoklu indirme desteği

### Performance Metrics
- **Average Download Time**: 30-60 saniye per song
- **Success Rate**: %85-95 (content availability dependent)
- **File Size**: Typically 3-8 MB per song (192 kbps)

## 🔮 Gelecek Geliştirmeler

### Planned Features
- [ ] Playlist toplu indirme
- [ ] Kalite seçenekleri (128/192/320 kbps)
- [ ] İndirme geçmişi
- [ ] Kullanıcı ayarları
- [ ] Mobil uygulama

### Technical Improvements
- [ ] Database integration
- [ ] User authentication
- [ ] Cloud storage options
- [ ] API rate limiting
- [ ] Caching system

## 📞 Destek

Herhangi bir sorun yaşarsanız:
1. Önce "Sorun Giderme" bölümünü kontrol edin
2. Konsol loglarını inceleyin
3. GitHub Issues'da arama yapın

## 📄 Lisans

Bu proje kişisel kullanım amaçlıdır. Ticari kullanım yasaktır.

---

*Son güncelleme: 2023-12-01*
*Versiyon: 1.0.0*

