"""
Haber Akışı ve AI Yorum Motoru
================================
Çeşitli RSS kaynaklarından ekonomi/finans haberlerini çeker,
kategorize eder ve yapay zeka ile yorumlar.

Kaynaklar:
- TCMB Duyurular
- Bloomberg HT RSS
- Dünya Gazetesi RSS
- Para Analiz RSS
- AA Ekonomi RSS
"""

import sys
import os
import re
import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import requests
import numpy as np
import pandas as pd

# ============================================================================
# VERİ MODELLERİ
# ============================================================================

@dataclass
class NewsItem:
    """Tek bir haber öğesi."""
    title: str
    link: str
    source: str
    published: datetime
    summary: str = ""
    category: str = "Genel"
    importance: str = "Normal"  # Düşük, Normal, Yüksek, Kritik
    sentiment: str = "Nötr"     # Pozitif, Negatif, Nötr
    ai_comment: str = ""
    
    @property
    def id(self) -> str:
        return hashlib.md5(f"{self.link}{self.title}".encode()).hexdigest()[:12]


# ============================================================================
# RSS HABERLERİ ÇEKİCİ
# ============================================================================

# RSS kaynakları
RSS_FEEDS = {
    'bloomberght': {
        'url': 'https://www.bloomberght.com/rss',
        'name': 'Bloomberg HT',
        'category': 'Piyasa'
    },
    'dunya': {
        'url': 'https://www.dunya.com/rss',
        'name': 'Dünya Gazetesi',
        'category': 'Ekonomi'
    },
    'paraanaliz': {
        'url': 'https://www.paraanaliz.com/feed/',
        'name': 'Para Analiz',
        'category': 'Piyasa'
    },
    'aa_ekonomi': {
        'url': 'https://www.aa.com.tr/tr/rss/default?cat=ekonomi',
        'name': 'Anadolu Ajansı',
        'category': 'Ekonomi'
    },
    'bigpara': {
        'url': 'https://bigpara.hurriyet.com.tr/rss/',
        'name': 'Bigpara',
        'category': 'Piyasa'
    },
}


def _parse_rss_date(date_str: str) -> Optional[datetime]:
    """RSS tarihini parse eder (çeşitli formatları destekler)."""
    formats = [
        '%a, %d %b %Y %H:%M:%S %z',
        '%a, %d %b %Y %H:%M:%S %Z',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%d %H:%M:%S',
        '%d.%m.%Y %H:%M',
        '%d %b %Y %H:%M:%S',
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            if dt.tzinfo:
                dt = dt.replace(tzinfo=None)
            return dt
        except ValueError:
            continue
    
    return None


def _extract_text(element_text: str) -> str:
    """HTML etiketlerini temizler."""
    if not element_text:
        return ""
    # Basit HTML tag temizleme
    clean = re.sub(r'<[^>]+>', '', element_text)
    clean = re.sub(r'&[a-z]+;', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()[:500]


def _parse_simple_xml(xml_text: str) -> List[Dict]:
    """Basit XML/RSS parser (lxml/feedparser olmadan çalışır)."""
    items = []
    
    # <item> veya <entry> blokları bul
    item_pattern = re.compile(
        r'<(?:item|entry)[\s>](.*?)</(?:item|entry)>',
        re.DOTALL | re.IGNORECASE
    )
    
    for match in item_pattern.finditer(xml_text):
        block = match.group(1)
        
        # Title
        title_m = re.search(r'<title[^>]*>(.*?)</title>', block, re.DOTALL)
        title = _extract_text(title_m.group(1)) if title_m else ""
        
        # Link
        link = ""
        link_m = re.search(r'<link[^>]*>(.*?)</link>', block, re.DOTALL)
        if link_m:
            link = link_m.group(1).strip()
        else:
            link_m = re.search(r'<link[^>]+href=["\']([^"\']+)', block)
            if link_m:
                link = link_m.group(1).strip()
        
        # Date
        date_str = ""
        for tag in ['pubDate', 'published', 'updated', 'dc:date']:
            date_m = re.search(rf'<{tag}[^>]*>(.*?)</{tag}>', block, re.DOTALL)
            if date_m:
                date_str = date_m.group(1).strip()
                break
        
        # Description/Summary
        desc = ""
        for tag in ['description', 'summary', 'content:encoded', 'content']:
            desc_m = re.search(rf'<{tag}[^>]*>(.*?)</{tag}>', block, re.DOTALL)
            if desc_m:
                raw = desc_m.group(1)
                # CDATA temizle
                cdata_m = re.search(r'<!\[CDATA\[(.*?)\]\]>', raw, re.DOTALL)
                if cdata_m:
                    raw = cdata_m.group(1)
                desc = _extract_text(raw)
                break
        
        if title:
            items.append({
                'title': title,
                'link': link,
                'date_str': date_str,
                'description': desc
            })
    
    return items


def fetch_rss_news(feed_key: str = None, max_items: int = 20, 
                    timeout: int = 10) -> List[NewsItem]:
    """
    Belirtilen RSS kaynağından veya tüm kaynaklardan haberleri çeker.
    
    Args:
        feed_key: Belirli kaynak anahtarı (None ise hepsi)
        max_items: Kaynak başına maksimum haber
        timeout: HTTP timeout saniye
    """
    all_news = []
    
    feeds = {feed_key: RSS_FEEDS[feed_key]} if feed_key and feed_key in RSS_FEEDS else RSS_FEEDS
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/rss+xml, application/xml, text/xml, */*',
    }
    
    for key, feed_info in feeds.items():
        try:
            resp = requests.get(
                feed_info['url'],
                headers=headers,
                timeout=timeout,
                allow_redirects=True
            )
            
            if resp.status_code != 200:
                continue
            
            items = _parse_simple_xml(resp.text)
            
            for item in items[:max_items]:
                pub_date = _parse_rss_date(item.get('date_str', ''))
                if pub_date is None:
                    pub_date = datetime.now()
                
                news = NewsItem(
                    title=item['title'],
                    link=item.get('link', ''),
                    source=feed_info['name'],
                    published=pub_date,
                    summary=item.get('description', '')[:300],
                    category=feed_info.get('category', 'Genel')
                )
                all_news.append(news)
                
        except Exception:
            continue
    
    # Tarihe göre sırala (en yeni ilk)
    all_news.sort(key=lambda x: x.published, reverse=True)
    
    return all_news


# ============================================================================
# HABER SINIFLANDIRMA VE ÖNEMLİLİK
# ============================================================================

# Anahtar kelime bazlı kategorizasyon
KEYWORD_CATEGORIES = {
    'Merkez Bankası': {
        'keywords': ['tcmb', 'merkez bankası', 'faiz kararı', 'politika faizi', 
                     'ppk', 'para politikası', 'fed', 'ecb', 'boj'],
        'importance': 'Kritik'
    },
    'Enflasyon': {
        'keywords': ['enflasyon', 'tüfe', 'üfe', 'cpi', 'ppi', 'fiyat artışı',
                     'hayat pahalılığı', 'tuik', 'tüik'],
        'importance': 'Yüksek'
    },
    'Borsa': {
        'keywords': ['borsa', 'bist', 'hisse', 'endeks', 'ipo', 'halka arz',
                     'nasdaq', 's&p', 'dow jones', 'rally', 'çöküş'],
        'importance': 'Yüksek'
    },
    'Döviz': {
        'keywords': ['dolar', 'euro', 'eurousd', 'usdtry', 'döviz', 'kur',
                     'altın', 'ons', 'gram altın', 'petrol', 'brent'],
        'importance': 'Yüksek'
    },
    'Büyüme': {
        'keywords': ['gsyh', 'gdp', 'büyüme', 'daralma', 'resesyon', 'istihdam',
                     'işsizlik', 'sanayi üretimi', 'pmi'],
        'importance': 'Yüksek'
    },
    'Maliye': {
        'keywords': ['bütçe', 'vergi', 'hazine', 'ihale', 'borçlanma', 
                     'maliye bakanlığı', 'kamu harcaması'],
        'importance': 'Normal'
    },
    'Dış Ticaret': {
        'keywords': ['ihracat', 'ithalat', 'cari açık', 'dış ticaret', 
                     'gümrük', 'ticaret dengesi'],
        'importance': 'Normal'
    },
    'Enerji': {
        'keywords': ['enerji', 'doğalgaz', 'elektrik', 'güneş enerjisi',
                     'rüzgar', 'opec', 'petrol'],
        'importance': 'Normal'
    },
    'Şirket Haberleri': {
        'keywords': ['bilanço', 'kâr', 'zarar', 'temettü', 'yönetim kurulu',
                     'satın alma', 'birleşme', 'sermaye artırımı'],
        'importance': 'Normal'
    },
}

# Sentiment anahtar kelimeleri
POSITIVE_KEYWORDS = [
    'artış', 'yükseliş', 'rekor', 'büyüme', 'olumlu', 'iyileşme',
    'güçlenme', 'toparlanma', 'pozitif', 'beklenti üstü', 'sürpriz',
    'al sinyali', 'ralli', 'rally', 'kâr', 'talep artışı', 'atılım'
]

NEGATIVE_KEYWORDS = [
    'düşüş', 'gerileme', 'kayıp', 'daralma', 'kriz', 'risk',
    'endişe', 'panik', 'çöküş', 'zarar', 'iflas', 'beklenti altı',
    'sat sinyali', 'çökme', 'yavaşlama', 'tehdit', 'zayıflama',
    'kötüleşme', 'belirsizlik'
]


def classify_news(news: NewsItem) -> NewsItem:
    """Haberi kategorize eder, önem ve duygu analizi yapar."""
    text = f"{news.title} {news.summary}".lower()
    
    # Kategori ve önem
    best_match_count = 0
    for category, info in KEYWORD_CATEGORIES.items():
        match_count = sum(1 for kw in info['keywords'] if kw in text)
        if match_count > best_match_count:
            best_match_count = match_count
            news.category = category
            news.importance = info['importance']
    
    # Birden fazla kritik kelime varsa önemi yükselt
    if best_match_count >= 3 and news.importance == 'Normal':
        news.importance = 'Yüksek'
    
    # Sentiment analizi
    pos_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
    neg_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text)
    
    if pos_count > neg_count + 1:
        news.sentiment = "Pozitif"
    elif neg_count > pos_count + 1:
        news.sentiment = "Negatif"
    else:
        news.sentiment = "Nötr"
    
    return news


def generate_news_ai_comment(news: NewsItem) -> str:
    """
    Haber için AI yorumu üretir.
    Kural tabanlı sistem: haberin kategorisi, duygusu ve anahtar kelimelerini
    kullanarak anlamlı ve kapsamlı yorum oluşturur.
    """
    text = f"{news.title} {news.summary}".lower()
    parts = []
    
    # Kategori bazlı yorum
    if news.category == 'Merkez Bankası':
        if 'faiz' in text and ('artır' in text or 'yüksel' in text):
            parts.append("Faiz artışı TL'yi destekleyici, hisse senetleri üzerinde baskı yaratabilir.")
            parts.append("Sabit gelirli yatırımlar göreceli olarak cazip hale gelir.")
        elif 'faiz' in text and ('indir' in text or 'düşür' in text or 'gevşe' in text):
            parts.append("Faiz indirimi hisse senetleri ve emtia için olumlu.")
            parts.append("TL üzerinde aşağı yönlü baskı oluşabilir, döviz pozisyonları dikkatle izlenmeli.")
        elif 'faiz' in text and ('sabit' in text or 'değiştir' in text or 'bekle' in text):
            parts.append("Faizin sabit tutulması piyasa beklentilerini yansıtıyor.")
            parts.append("İleriye dönük açıklamalar (forward guidance) yakından takip edilmeli.")
        else:
            parts.append("Merkez bankası kararları tüm piyasaları doğrudan etkiler.")
            parts.append("Detaylı açıklamayı ve enflasyon raporunu takip edin.")
    
    elif news.category == 'Enflasyon':
        if 'beklenti üstü' in text or 'yüksel' in text or 'artış' in text:
            parts.append("Yüksek enflasyon verisi faiz artış beklentilerini güçlendirir.")
            parts.append("Reel getiri hesaplarını gözden geçirin, enflasyona endeksli araçları değerlendirin.")
        elif 'düşüş' in text or 'gerileme' in text or 'iyileş' in text:
            parts.append("Enflasyondaki gerileme faiz indirim beklentilerini destekler.")
            parts.append("Risk iştahı artabilir, büyüme hisselerine yönelim olabilir.")
        else:
            parts.append("Enflasyon verileri para politikası yönelimini belirleyen kritik göstergedir.")
    
    elif news.category == 'Borsa':
        if news.sentiment == 'Pozitif':
            parts.append("Olumlu gelişme: Piyasada alıcılar ağırlık kazanabilir.")
            parts.append("Sektörel dönüşümü ve hacmi takip edin, tepki alımlarına dikkat.")
        elif news.sentiment == 'Negatif':
            parts.append("Dikkat: Olumsuz sinyal, kar realizasyonu veya panik satışı tetikleyebilir.")
            parts.append("Stop-loss seviyelerini kontrol edin, çeşitlendirme yapın.")
        else:
            parts.append("Borsa haberleri yakından izlenmeli, sektörel etki analiz edilmeli.")
    
    elif news.category == 'Döviz':
        if 'dolar' in text or 'usdtry' in text or 'kur' in text:
            if news.sentiment == 'Negatif':
                parts.append("TL'de değer kaybı enflasyon yoluyla tüm varlık sınıflarını etkiler.")
                parts.append("İthalat ağırlıklı şirketlerin maliyetleri artabilir.")
            elif news.sentiment == 'Pozitif':
                parts.append("TL değer kazanması enflasyon açısından olumlu.")
                parts.append("İhracatçılar üzerinde baskı yaratabilir, iç tüketime yönelik şirketler avantajlı.")
        if 'altın' in text or 'ons' in text:
            parts.append("Altın fiyatları küresel risk algısıyla yakından ilişkilidir.")
    
    elif news.category == 'Büyüme':
        if news.sentiment == 'Pozitif':
            parts.append("Güçlü büyüme verisi şirket kârlarını olumlu etkiler, borsayı destekler.")
        elif news.sentiment == 'Negatif':
            parts.append("Zayıf büyüme resesyon endişelerini artırır, savunmacı sektörlere yönelim olabilir.")
        parts.append("İstihdam ve sanayi üretimi verilerini de birlikte değerlendirin.")
    
    elif news.category == 'Enerji':
        parts.append("Enerji fiyatları enflasyonu ve üretim maliyetlerini doğrudan etkiler.")
        if 'petrol' in text and news.sentiment == 'Negatif':
            parts.append("Yükselen petrol fiyatları cari açığı olumsuz etkiler.")
    
    elif news.category == 'Şirket Haberleri':
        if 'temettü' in text:
            parts.append("Temettü dağıtımı hissenin gelir yatırımcıları için çekiciliğini artırır.")
        elif 'bilanço' in text or 'kâr' in text:
            parts.append("Bilanço sonuçları şirketin gerçek performansını gösterir, beklenti/gerçekleşme farkını izleyin.")
        else:
            parts.append("Şirket haberleri ilgili sektör ve rakip hisseleri de etkileyebilir.")
    
    else:
        # Genel yorum
        if news.sentiment == 'Pozitif':
            parts.append("Olumlu gelişme, piyasa performansını destekleyebilir.")
        elif news.sentiment == 'Negatif':
            parts.append("Dikkat gerektiren bir gelişme, risk yönetimine önem verin.")
        else:
            parts.append("Gelişmeleri yakından takip edin.")
    
    # Genel uyarı
    if news.importance in ('Kritik', 'Yüksek'):
        parts.append("📌 Bu haber yüksek öneme sahip, piyasa etkisi yakından izlenmeli.")
    
    return " ".join(parts)


# ============================================================================
# ANA FONKSİYONLAR
# ============================================================================

def get_latest_news(max_per_source: int = 10) -> List[NewsItem]:
    """Tüm kaynaklardan haberleri çeker, sınıflandırır ve AI yorumu ekler."""
    
    raw_news = fetch_rss_news(max_items=max_per_source)
    
    processed = []
    seen_titles = set()
    
    for news in raw_news:
        # Tekrar kontrolü (benzer başlıklar)
        title_key = news.title.lower()[:50]
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        
        # Sınıflandır
        news = classify_news(news)
        
        # AI yorum ekle
        news.ai_comment = generate_news_ai_comment(news)
        
        processed.append(news)
    
    return processed


def get_filtered_news(category: str = None, importance: str = None,
                       sentiment: str = None, max_results: int = 50) -> List[NewsItem]:
    """Filtrelenmiş haber listesi."""
    all_news = get_latest_news()
    
    filtered = all_news
    
    if category and category != "Tümü":
        filtered = [n for n in filtered if n.category == category]
    
    if importance and importance != "Tümü":
        filtered = [n for n in filtered if n.importance == importance]
    
    if sentiment and sentiment != "Tümü":
        filtered = [n for n in filtered if n.sentiment == sentiment]
    
    return filtered[:max_results]


def get_market_summary_from_news(news_list: List[NewsItem] = None) -> Dict:
    """Haberlerin genel özetini çıkarır."""
    if news_list is None:
        news_list = get_latest_news()
    
    if not news_list:
        return {
            'total': 0,
            'sentiment_summary': 'Veri yok',
            'dominant_categories': [],
            'critical_news': [],
            'ai_summary': 'Haber verisi bulunamadı.'
        }
    
    # Sentiment dağılımı
    sentiments = [n.sentiment for n in news_list]
    pos = sentiments.count('Pozitif')
    neg = sentiments.count('Negatif')
    neu = sentiments.count('Nötr')
    total = len(sentiments)
    
    if pos > neg * 1.5:
        sentiment_summary = "Genel Olumlu"
    elif neg > pos * 1.5:
        sentiment_summary = "Genel Olumsuz"
    else:
        sentiment_summary = "Karışık"
    
    # Kategori dağılımı
    cat_counts = {}
    for n in news_list:
        cat_counts[n.category] = cat_counts.get(n.category, 0) + 1
    dominant = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    
    # Kritik haberler
    critical = [n for n in news_list if n.importance in ('Kritik', 'Yüksek')][:5]
    
    # Genel AI özet
    summary_parts = [f"📰 Son haberlerin genel tonu: **{sentiment_summary}**"]
    summary_parts.append(f"Toplam {total} haber incelendi: {pos} olumlu, {neg} olumsuz, {neu} nötr.")
    
    if dominant:
        top_cats = [f"{c[0]} ({c[1]})" for c in dominant]
        summary_parts.append(f"En çok haber: {', '.join(top_cats)}")
    
    if critical:
        summary_parts.append(f"⚠️ {len(critical)} yüksek önemli haber tespit edildi:")
        for c in critical[:3]:
            summary_parts.append(f"  • **{c.title}** [{c.source}]")
    
    return {
        'total': total,
        'positive': pos,
        'negative': neg,
        'neutral': neu,
        'sentiment_summary': sentiment_summary,
        'dominant_categories': dominant,
        'critical_news': critical,
        'ai_summary': "\n".join(summary_parts)
    }


# ============================================================================
# STREAMLIT RENDER
# ============================================================================

def render_news_tab():
    """Streamlit haber sekmesini render eder."""
    import streamlit as st
    
    st.markdown("## 📰 Haber Akışı ve AI Yorumları")
    st.markdown("*Ekonomi ve finans haberlerini yapay zeka destekli analiz ile takip edin*")
    st.markdown("---")
    
    # Filtreler
    col1, col2, col3, col4 = st.columns(4)
    
    categories = ["Tümü", "Merkez Bankası", "Enflasyon", "Borsa", "Döviz",
                   "Büyüme", "Maliye", "Dış Ticaret", "Enerji", "Şirket Haberleri", "Genel"]
    importances = ["Tümü", "Kritik", "Yüksek", "Normal", "Düşük"]
    sentiments = ["Tümü", "Pozitif", "Negatif", "Nötr"]
    
    with col1:
        sel_category = st.selectbox("📂 Kategori", categories, key="news_cat")
    with col2:
        sel_importance = st.selectbox("⚡ Önem", importances, key="news_imp")
    with col3:
        sel_sentiment = st.selectbox("💭 Duygu", sentiments, key="news_sent")
    with col4:
        refresh_btn = st.button("🔄 Yenile", type="primary", use_container_width=True)
    
    # Haberleri çek
    with st.spinner("📡 Haberler çekiliyor..."):
        all_news = get_latest_news()
    
    if not all_news:
        st.warning("⚠️ Haber kaynakları şu an ulaşılabilir değil. Lütfen tekrar deneyin.")
        return
    
    # Özet panel
    summary = get_market_summary_from_news(all_news)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📰 Toplam", summary['total'])
    with col2:
        st.metric("🟢 Olumlu", summary['positive'])
    with col3:
        st.metric("🔴 Olumsuz", summary['negative'])
    with col4:
        st.metric("💭 Genel Ton", summary['sentiment_summary'])
    
    # AI Özet
    with st.expander("🤖 AI Piyasa Ozeti", expanded=True):
        st.markdown(summary['ai_summary'])
    
    st.markdown("---")
    
    # Filtrele
    filtered = all_news
    if sel_category != "Tümü":
        filtered = [n for n in filtered if n.category == sel_category]
    if sel_importance != "Tümü":
        filtered = [n for n in filtered if n.importance == sel_importance]
    if sel_sentiment != "Tümü":
        filtered = [n for n in filtered if n.sentiment == sel_sentiment]
    
    st.markdown(f"### 📋 Haberler ({len(filtered)} sonuç)")
    
    # Haber kartları
    for news in filtered[:30]:
        # Renk ve ikon
        imp_colors = {
            'Kritik': '🔴',
            'Yüksek': '🟠',
            'Normal': '🔵',
            'Düşük': '⚪'
        }
        sent_icons = {
            'Pozitif': '📈',
            'Negatif': '📉',
            'Nötr': '➡️'
        }
        
        imp_icon = imp_colors.get(news.importance, '🔵')
        sent_icon = sent_icons.get(news.sentiment, '➡️')
        
        with st.container():
            st.markdown(f"""
            **{imp_icon} {news.title}**
            
            *{news.source} | {news.published.strftime('%d.%m.%Y %H:%M')} | 
            {news.category} | {sent_icon} {news.sentiment}*
            """)
            
            if news.summary:
                st.markdown(f"> {news.summary[:200]}{'...' if len(news.summary) > 200 else ''}")
            
            if news.ai_comment:
                st.info(f"🤖 **AI Yorum:** {news.ai_comment}")
            
            if news.link:
                st.markdown(f"[Haberin tamamını oku →]({news.link})")
            
            st.markdown("---")


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("📰 Haber Akışı Test")
    print("=" * 60)
    
    print("\n🔄 Haberler çekiliyor...")
    news = get_latest_news()
    
    print(f"\n📊 Toplam {len(news)} haber geldi\n")
    
    for n in news[:10]:
        print(f"  [{n.importance}] [{n.sentiment}] [{n.category}]")
        print(f"  📰 {n.title}")
        print(f"  📡 {n.source} | {n.published.strftime('%d.%m.%Y %H:%M')}")
        if n.ai_comment:
            print(f"  🤖 {n.ai_comment[:100]}...")
        print()
    
    # Özet
    summary = get_market_summary_from_news(news)
    print("\n📊 Piyasa Özeti:")
    print(summary['ai_summary'])
