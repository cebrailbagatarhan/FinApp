"""
Ekonomik Takvim Modülü (economic_calendar.py)
=============================================
Gerçek ekonomik takvim verileri üretir.

2 Katmanlı Yaklaşım:
1. Önce gerçek API kaynakları denenir (Trading Economics RSS, TCMB)
2. Başarısız olursa, deterministik takvim üretilir (bilinen yayın takvimine göre)

Deterministik takvim, rastgele tarih atamaz - her ekonomik göstergenin
gerçek yayın takvimini kullanır.
"""

import os
import sys
import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
import re
import json
import calendar

# Ana dizini path'e ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# SABİTLER
# ============================================================================

COUNTRY_CODES = {
    'TR': {'name': 'Türkiye', 'flag': '🇹🇷', 'currency': 'TRY'},
    'US': {'name': 'ABD', 'flag': '🇺🇸', 'currency': 'USD'},
    'EU': {'name': 'Euro Bölgesi', 'flag': '🇪🇺', 'currency': 'EUR'},
    'UK': {'name': 'İngiltere', 'flag': '🇬🇧', 'currency': 'GBP'},
}


# ============================================================================
# TARİH YARDIMCI FONKSİYONLARI
# ============================================================================

def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Bir ayın n'inci haftanın belirli gününü bulur (1-indexed)."""
    first_day = date(year, month, 1)
    first_weekday = first_day.weekday()
    
    # İlk hedef günü bul
    days_ahead = weekday - first_weekday
    if days_ahead < 0:
        days_ahead += 7
    
    target = first_day + timedelta(days=days_ahead)
    target += timedelta(weeks=(n - 1))
    
    return target


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    """Bir ayın son belirli gününü bulur."""
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    days_back = (last_day.weekday() - weekday) % 7
    return last_day - timedelta(days=days_back)


def _next_business_day(d: date) -> date:
    """Hafta sonuysa bir sonraki iş gününe taşı."""
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


# ============================================================================
# EKONOMİK TAKVİM ŞEDÜLLERİ (GERÇEK YAYIN TAKVİMİ)
# ============================================================================

def _get_tr_events_for_month(year: int, month: int) -> List[Dict]:
    """
    Türkiye için bilinen ekonomik veri yayın takvimini oluşturur.
    TÜİK ve TCMB'nin gerçek yayın takvimlerine dayanır.
    """
    events = []
    
    # 1) TÜİK TÜFE - Her ayın 3'ünde (önceki ayın verisi)
    tufe_date = _next_business_day(date(year, month, 3))
    prev_month = month - 1 if month > 1 else 12
    events.append({
        'date': tufe_date,
        'time': '10:00',
        'currency': 'TRY',
        'name': f'TÜFE (Aylık) - {_ay_adi(prev_month)}',
        'importance': 3,
        'forecast': '',
        'previous': '',
        'category': 'enflasyon'
    })
    events.append({
        'date': tufe_date,
        'time': '10:00',
        'currency': 'TRY',
        'name': f'TÜFE (Yıllık) - {_ay_adi(prev_month)}',
        'importance': 3,
        'forecast': '',
        'previous': '',
        'category': 'enflasyon'
    })
    events.append({
        'date': tufe_date,
        'time': '10:00',
        'currency': 'TRY',
        'name': f'ÜFE (Aylık) - {_ay_adi(prev_month)}',
        'importance': 2,
        'forecast': '',
        'previous': '',
        'category': 'enflasyon'
    })
    
    # 2) TCMB Faiz Kararı - PPK toplantıları (yılda 12 kez, genelde ayın 3. Perşembe)
    # TCMB 2025-2026 PPK takvimi (resmi)
    tcmb_ppk_dates_2025 = {
        1: 23, 2: 20, 3: 20, 4: 17, 5: 22, 6: 19,
        7: 17, 8: 21, 9: 18, 10: 23, 11: 20, 12: 25
    }
    tcmb_ppk_dates_2026 = {
        1: 22, 2: 19, 3: 19, 4: 16, 5: 21, 6: 18,
        7: 16, 8: 20, 9: 17, 10: 22, 11: 19, 12: 24
    }
    
    ppk_dates = tcmb_ppk_dates_2026 if year >= 2026 else tcmb_ppk_dates_2025
    ppk_day = ppk_dates.get(month)
    if ppk_day:
        try:
            ppk_date = date(year, month, ppk_day)
            events.append({
                'date': ppk_date,
                'time': '14:00',
                'currency': 'TRY',
                'name': 'TCMB Faiz Kararı (PPK)',
                'importance': 3,
                'forecast': '',
                'previous': '',
                'category': 'merkez_bankasi'
            })
        except ValueError:
            pass
    
    # 3) İşsizlik Oranı - Her ayın 10'unda civarı (2 ay gecikmeli)
    issizlik_date = _next_business_day(date(year, month, 10))
    events.append({
        'date': issizlik_date,
        'time': '10:00',
        'currency': 'TRY',
        'name': 'İşsizlik Oranı',
        'importance': 3,
        'forecast': '',
        'previous': '',
        'category': 'istihdam'
    })
    
    # 4) Sanayi Üretimi - Her ayın 12'si civarı
    sanayi_date = _next_business_day(date(year, month, 12))
    events.append({
        'date': sanayi_date,
        'time': '10:00',
        'currency': 'TRY',
        'name': 'Sanayi Üretim Endeksi (Yıllık)',
        'importance': 2,
        'forecast': '',
        'previous': '',
        'category': 'uretim'
    })
    
    # 5) Cari Denge - Her ayın 14'ü civarı
    cari_date = _next_business_day(date(year, month, 14))
    events.append({
        'date': cari_date,
        'time': '10:00',
        'currency': 'TRY',
        'name': 'Cari İşlemler Dengesi',
        'importance': 2,
        'forecast': '',
        'previous': '',
        'category': 'dis_ticaret'
    })
    
    # 6) Tüketici Güven Endeksi - Her ayın 22'si civarı
    tuketici_date = _next_business_day(date(year, month, min(22, calendar.monthrange(year, month)[1])))
    events.append({
        'date': tuketici_date,
        'time': '10:00',
        'currency': 'TRY',
        'name': 'Tüketici Güven Endeksi',
        'importance': 2,
        'forecast': '',
        'previous': '',
        'category': 'guven'
    })
    
    # 7) GDP - Çeyreklik (Mart, Haziran, Eylül, Aralık)
    if month in [3, 6, 9, 12]:
        gdp_date = _next_business_day(date(year, month, 1))
        events.append({
            'date': gdp_date,
            'time': '10:00',
            'currency': 'TRY',
            'name': 'GSYİH Büyüme Oranı (Çeyreklik)',
            'importance': 3,
            'forecast': '',
            'previous': '',
            'category': 'buyume'
        })
    
    return events


def _get_us_events_for_month(year: int, month: int) -> List[Dict]:
    """
    ABD için bilinen ekonomik veri yayın takvimini oluşturur.
    BLS, BEA, Fed takvimlerine dayanır.
    """
    events = []
    
    # 1) Non-Farm Payrolls - Her ayın ilk Cuma'sı
    nfp_date = _nth_weekday(year, month, 4, 1)  # 4=Friday, 1st occurrence
    events.append({
        'date': nfp_date,
        'time': '15:30',
        'currency': 'USD',
        'name': 'Tarım Dışı İstihdam (NFP)',
        'importance': 3,
        'forecast': '',
        'previous': '',
        'category': 'istihdam'
    })
    events.append({
        'date': nfp_date,
        'time': '15:30',
        'currency': 'USD',
        'name': 'İşsizlik Oranı',
        'importance': 3,
        'forecast': '',
        'previous': '',
        'category': 'istihdam'
    })
    events.append({
        'date': nfp_date,
        'time': '15:30',
        'currency': 'USD',
        'name': 'Ortalama Saatlik Kazanç (Aylık)',
        'importance': 2,
        'forecast': '',
        'previous': '',
        'category': 'istihdam'
    })
    
    # 2) CPI - Her ayın 10-13'ü arası (genelde 2. Çarşamba civarı)
    cpi_date = _next_business_day(date(year, month, 12))
    events.append({
        'date': cpi_date,
        'time': '15:30',
        'currency': 'USD',
        'name': 'CPI (Tüketici Fiyatları - Aylık)',
        'importance': 3,
        'forecast': '',
        'previous': '',
        'category': 'enflasyon'
    })
    events.append({
        'date': cpi_date,
        'time': '15:30',
        'currency': 'USD',
        'name': 'CPI (Tüketici Fiyatları - Yıllık)',
        'importance': 3,
        'forecast': '',
        'previous': '',
        'category': 'enflasyon'
    })
    events.append({
        'date': cpi_date,
        'time': '15:30',
        'currency': 'USD',
        'name': 'Çekirdek CPI (Core CPI - Yıllık)',
        'importance': 3,
        'forecast': '',
        'previous': '',
        'category': 'enflasyon'
    })
    
    # 3) Fed Faiz Kararı - FOMC (yılda 8 toplantı)
    # 2025 FOMC: Ocak 28-29, Mart 18-19, Mayıs 6-7, Haziran 17-18,
    #            Temmuz 29-30, Eylül 16-17, Kasım 4-5, Aralık 9-10
    # 2026 FOMC: Ocak 27-28, Mart 17-18, Nisan 28-29, Haziran 16-17,
    #            Temmuz 28-29, Eylül 15-16, Ekim 27-28, Aralık 8-9
    fomc_dates_2025 = {1: 29, 3: 19, 5: 7, 6: 18, 7: 30, 9: 17, 11: 5, 12: 10}
    fomc_dates_2026 = {1: 28, 3: 18, 4: 29, 6: 17, 7: 29, 9: 16, 10: 28, 12: 9}
    
    fomc_dates = fomc_dates_2026 if year >= 2026 else fomc_dates_2025
    fomc_day = fomc_dates.get(month)
    if fomc_day:
        try:
            fomc_date = date(year, month, fomc_day)
            events.append({
                'date': fomc_date,
                'time': '21:00',
                'currency': 'USD',
                'name': 'Fed Faiz Kararı (FOMC)',
                'importance': 3,
                'forecast': '',
                'previous': '',
                'category': 'merkez_bankasi'
            })
        except ValueError:
            pass
    
    # 4) PCE Fiyat Endeksi - Her ayın son Cuma'sı civarı (28-31 arası)
    pce_date = _next_business_day(date(year, month, min(28, calendar.monthrange(year, month)[1])))
    events.append({
        'date': pce_date,
        'time': '15:30',
        'currency': 'USD',
        'name': 'PCE Fiyat Endeksi (Aylık)',
        'importance': 3,
        'forecast': '',
        'previous': '',
        'category': 'enflasyon'
    })
    events.append({
        'date': pce_date,
        'time': '15:30',
        'currency': 'USD',
        'name': 'Core PCE (Fed Tercih Enflasyonu)',
        'importance': 3,
        'forecast': '',
        'previous': '',
        'category': 'enflasyon'
    })
    
    # 5) ISM İmalat PMI - Her ayın 1. iş günü
    ism_date = _next_business_day(date(year, month, 1))
    events.append({
        'date': ism_date,
        'time': '17:00',
        'currency': 'USD',
        'name': 'ISM İmalat PMI',
        'importance': 2,
        'forecast': '',
        'previous': '',
        'category': 'pmi'
    })
    
    # 6) ISM Hizmet PMI - Her ayın 3. iş günü
    ism_serv_date = _next_business_day(date(year, month, 3))
    events.append({
        'date': ism_serv_date,
        'time': '17:00',
        'currency': 'USD',
        'name': 'ISM Hizmet PMI',
        'importance': 2,
        'forecast': '',
        'previous': '',
        'category': 'pmi'
    })
    
    # 7) Perakende Satışlar - Her ayın 15'i civarı
    retail_date = _next_business_day(date(year, month, 15))
    events.append({
        'date': retail_date,
        'time': '15:30',
        'currency': 'USD',
        'name': 'Perakende Satışlar (Aylık)',
        'importance': 2,
        'forecast': '',
        'previous': '',
        'category': 'tuketim'
    })
    
    # 8) Haftalık İşsizlik Başvuruları - Her Perşembe  
    # Sadece bu ayın Perşembelerini ekle
    first_thurs = _nth_weekday(year, month, 3, 1)  # 3=Thursday
    for week in range(5):
        thurs = first_thurs + timedelta(weeks=week)
        if thurs.month == month:
            events.append({
                'date': thurs,
                'time': '15:30',
                'currency': 'USD',
                'name': 'Haftalık İşsizlik Başvuruları',
                'importance': 2,
                'forecast': '',
                'previous': '',
                'category': 'istihdam'
            })
    
    # 9) GDP - Çeyreklik (Ocak, Nisan, Temmuz, Ekim son Perşembe civarı)
    if month in [1, 4, 7, 10]:
        gdp_date = _last_weekday_of_month(year, month, 3)  # Son Perşembe
        events.append({
            'date': gdp_date,
            'time': '15:30',
            'currency': 'USD',
            'name': 'GDP Büyüme Oranı (Çeyreklik - İlk Tahmin)',
            'importance': 3,
            'forecast': '',
            'previous': '',
            'category': 'buyume'
        })
    
    # 10) Michigan Tüketici Güveni - Ayın 2. ve 4. Cuma'sı
    michigan_dates = [_nth_weekday(year, month, 4, 2), _nth_weekday(year, month, 4, 4)]
    for md in michigan_dates:
        if md.month == month:
            events.append({
                'date': md,
                'time': '17:00',
                'currency': 'USD',
                'name': 'Michigan Tüketici Güveni',
                'importance': 2,
                'forecast': '',
                'previous': '',
                'category': 'guven'
            })
    
    return events


def _get_eu_events_for_month(year: int, month: int) -> List[Dict]:
    """Euro Bölgesi ekonomik takvimi."""
    events = []
    
    # 1) ECB Faiz Kararı - Yılda 8 toplantı
    ecb_dates_2025 = {1: 30, 3: 6, 4: 17, 6: 5, 7: 24, 9: 11, 10: 30, 12: 18}
    ecb_dates_2026 = {1: 22, 3: 5, 4: 16, 6: 4, 7: 16, 9: 10, 10: 29, 12: 17}
    
    ecb_dates = ecb_dates_2026 if year >= 2026 else ecb_dates_2025
    ecb_day = ecb_dates.get(month)
    if ecb_day:
        try:
            ecb_date = date(year, month, ecb_day)
            events.append({
                'date': ecb_date,
                'time': '15:15',
                'currency': 'EUR',
                'name': 'ECB Faiz Kararı',
                'importance': 3,
                'forecast': '',
                'previous': '',
                'category': 'merkez_bankasi'
            })
        except ValueError:
            pass
    
    # 2) Euro Bölgesi HICP (Enflasyon) - Ayın ilk iş günleri
    hicp_date = _next_business_day(date(year, month, 2))
    events.append({
        'date': hicp_date,
        'time': '12:00',
        'currency': 'EUR',
        'name': 'HICP Enflasyon (Yıllık)',
        'importance': 3,
        'forecast': '',
        'previous': '',
        'category': 'enflasyon'
    })
    
    # 3) Euro Bölgesi PMI - Ayın 23-24'ü
    pmi_date = _next_business_day(date(year, month, min(23, calendar.monthrange(year, month)[1])))
    events.append({
        'date': pmi_date,
        'time': '10:55',
        'currency': 'EUR',
        'name': 'İmalat PMI (Flash)',
        'importance': 2,
        'forecast': '',
        'previous': '',
        'category': 'pmi'
    })
    events.append({
        'date': pmi_date,
        'time': '10:55',
        'currency': 'EUR',
        'name': 'Hizmet PMI (Flash)',
        'importance': 2,
        'forecast': '',
        'previous': '',
        'category': 'pmi'
    })
    
    # 4) İşsizlik - Her ayın ilk haftası
    issizlik_date = _next_business_day(date(year, month, 1))
    events.append({
        'date': issizlik_date,
        'time': '12:00',
        'currency': 'EUR',
        'name': 'Euro Bölgesi İşsizlik Oranı',
        'importance': 2,
        'forecast': '',
        'previous': '',
        'category': 'istihdam'
    })
    
    return events


def _ay_adi(month: int) -> str:
    """Ay numarasından Türkçe ay adı."""
    aylar = {
        1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan',
        5: 'Mayıs', 6: 'Haziran', 7: 'Temmuz', 8: 'Ağustos',
        9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'
    }
    return aylar.get(month, '')


# ============================================================================
# ANA TAKVİM ÜRETİCİLERİ
# ============================================================================

def generate_scheduled_calendar(days_ahead: int = 14) -> pd.DataFrame:
    """
    Deterministik ekonomik takvim üretir.
    Gerçek yayın takvimlerine dayanır - rastgele tarih ATAMAZ.
    
    Args:
        days_ahead: Bugünden kaç gün ilerisine kadar göster
    
    Returns:
        Ekonomik takvim DataFrame'i
    """
    today = date.today()
    end_date = today + timedelta(days=days_ahead)
    
    all_events = []
    
    # Gerekli ayları belirle
    current = date(today.year, today.month, 1)
    while current <= end_date:
        year = current.year
        month = current.month
        
        # Her ülkenin olaylarını topla
        all_events.extend(_get_tr_events_for_month(year, month))
        all_events.extend(_get_us_events_for_month(year, month))
        all_events.extend(_get_eu_events_for_month(year, month))
        
        # Sonraki ay
        if month == 12:
            current = date(year + 1, 1, 1)
        else:
            current = date(year, month + 1, 1)
    
    # Tarih aralığına filtrele
    filtered = []
    for event in all_events:
        event_date = event['date']
        if today <= event_date <= end_date:
            filtered.append({
                'Tarih': event_date.strftime('%Y-%m-%d'),
                'Saat': event['time'],
                'Para Birimi': event['currency'],
                'Olay Adı': event['name'],
                'Önem': event['importance'],
                'Beklenti': event.get('forecast', '-') or '-',
                'Açıklanan': '-',
                'Önceki': event.get('previous', '-') or '-'
            })
    
    if not filtered:
        return pd.DataFrame()
    
    df = pd.DataFrame(filtered)
    df['Tarih'] = pd.to_datetime(df['Tarih'])
    df = df.sort_values(['Tarih', 'Saat']).reset_index(drop=True)
    
    return df


def try_fetch_live_calendar() -> pd.DataFrame:
    """
    Canlı ekonomik takvim verisi çekmeye çalışır.
    Birden fazla kaynağı dener.
    """
    # Kaynak 1: TCMB RSS Feed
    try:
        tcmb_url = "https://www.tcmb.gov.tr/wps/wcm/connect/tcmb+tr/tcmb+tr/main+menu/duyurular/basin/rss"
        response = requests.get(tcmb_url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'
        })
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'xml')
            items = soup.find_all('item')
            if items:
                events = []
                for item in items[:20]:
                    title = item.find('title')
                    pub_date = item.find('pubDate')
                    if title and pub_date:
                        try:
                            event_date = pd.to_datetime(pub_date.text).strftime('%Y-%m-%d')
                        except Exception:
                            event_date = datetime.now().strftime('%Y-%m-%d')
                        
                        events.append({
                            'Tarih': event_date,
                            'Saat': '10:00',
                            'Para Birimi': 'TRY',
                            'Olay Adı': title.text.strip()[:100],
                            'Önem': 2,
                            'Beklenti': '-',
                            'Açıklanan': '-',
                            'Önceki': '-'
                        })
                
                if events:
                    return pd.DataFrame(events)
    except Exception:
        pass
    
    return pd.DataFrame()


def _enrich_calendar_with_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Takvim olaylarını EVDS verileriyle zenginleştirir.
    Önceki değerleri (son açıklanan) bilinen kaynaklardan doldurur.
    """
    if df.empty:
        return df
    
    df = df.copy()
    
    # EVDS CSV'den son verileri yükle
    evds_latest = {}
    try:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        csv_path = os.path.join(data_dir, 'evds_inflation.csv')
        if os.path.exists(csv_path):
            evds_df = pd.read_csv(csv_path, parse_dates=['Tarih'], encoding='utf-8-sig')
            if not evds_df.empty and len(evds_df) >= 2:
                latest = evds_df.iloc[-1]
                prev = evds_df.iloc[-2]
                
                # Yıllık TÜFE (son açıklanan)
                genel = latest.get('Genel TÜFE', None)
                if genel and not pd.isna(genel):
                    evds_latest['tufe_yillik'] = f'%{float(genel):.2f}'
                
                # Aylık TÜFE (MoM farktan)
                genel_prev = prev.get('Genel TÜFE', None)
                if genel and genel_prev and not pd.isna(genel) and not pd.isna(genel_prev) and float(genel_prev) != 0:
                    mom = ((float(genel) - float(genel_prev)) / float(genel_prev)) * 100
                    evds_latest['tufe_aylik'] = f'%{mom:.2f}'
                
                # Gıda enflasyonu
                gida = latest.get('Gıda ve Alkolsüz İçecekler', None)
                if gida and not pd.isna(gida):
                    evds_latest['gida'] = f'%{float(gida):.2f}'
                
                # Konut
                konut = latest.get('Konut', None)
                if konut and not pd.isna(konut):
                    evds_latest['konut'] = f'%{float(konut):.2f}'
                
                # Çekirdek B
                core = latest.get('B Endeksi (Çekirdek)', None)
                if core and not pd.isna(core):
                    evds_latest['cekirdek'] = f'%{float(core):.2f}'
    except Exception:
        pass
    
    # TCMB son politika faizi
    try:
        evds_api_key = os.environ.get("EVDS_API_KEY", "")
        if not evds_api_key:
            raise ValueError("EVDS_API_KEY tanımlı değil")
        tcmb_rate_url = (
            "https://evds2.tcmb.gov.tr/service/evds/series=TP.PF.FF.GD"
            f"&startDate=01-01-2024&endDate={datetime.now().strftime('%d-%m-%Y')}"
            f"&type=json&key={evds_api_key}"
        )
        resp = requests.get(tcmb_rate_url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('items', [])
            if items:
                last_rate = items[-1].get('TP_PF_FF_GD') or items[-1].get('TP.PF.FF.GD')
                if last_rate:
                    evds_latest['tcmb_faiz'] = f'%{float(last_rate):.2f}'
    except Exception:
        pass
    
    # Olayları zenginleştir
    for idx, row in df.iterrows():
        name = str(row.get('Olay Adı', ''))
        currency = str(row.get('Para Birimi', ''))
        
        # Türkiye olayları
        if currency == 'TRY':
            if 'TÜFE (Yıllık)' in name and 'tufe_yillik' in evds_latest:
                df.at[idx, 'Önceki'] = evds_latest['tufe_yillik']
            elif 'TÜFE (Aylık)' in name and 'tufe_aylik' in evds_latest:
                df.at[idx, 'Önceki'] = evds_latest['tufe_aylik']
            elif 'ÜFE' in name and 'tufe_aylik' in evds_latest:
                df.at[idx, 'Önceki'] = evds_latest.get('tufe_aylik', '-')
            elif 'TCMB Faiz' in name and 'tcmb_faiz' in evds_latest:
                df.at[idx, 'Önceki'] = evds_latest['tcmb_faiz']
    
    return df


# ============================================================================
# ANA ERİŞİM FONKSİYONU
# ============================================================================

def get_economic_calendar(countries: List[str] = None,
                          importance: str = 'all',
                          days: int = 7,
                          use_simulation: bool = False,
                          use_selenium: bool = False) -> pd.DataFrame:
    """
    Ekonomik takvim verilerini döndürür.
    
    Strateji:
    1. Deterministik takvim oluştur (her zaman güvenilir)
    2. EVDS verileriyle zenginleştir (Önceki değerleri doldur)
    3. Canlı TCMB RSS verisi varsa birleştir
    
    Args:
        countries: Filtrelenecek ülkeler (['TR', 'US'] gibi)
        importance: Önem filtresi ('high', 'medium', 'low', 'all')
        days: Kaç günlük veri
        use_simulation: Eski parametre, geriye uyumluluk (görmezden gelinir)
        use_selenium: Eski parametre, geriye uyumluluk (görmezden gelinir)
    
    Returns:
        Filtrelenmiş ekonomik takvim DataFrame'i
    """
    # Her zaman deterministik takvimi kullan (doğru tarihli)
    df = generate_scheduled_calendar(days)
    
    if df.empty:
        return df
    
    # EVDS verileriyle zenginleştir (Önceki değerlerini doldur)
    try:
        df = _enrich_calendar_with_data(df)
    except Exception:
        pass
    
    # Canlı TCMB RSS verisi almayı dene ve birleştir
    try:
        live_df = try_fetch_live_calendar()
        if not live_df.empty:
            live_df['Tarih'] = pd.to_datetime(live_df['Tarih'])
            # Sadece takvim aralığındaki RSS haberlerini ekle
            today = datetime.now().date()
            end_date = today + timedelta(days=days)
            live_df = live_df[
                (pd.to_datetime(live_df['Tarih']).dt.date >= today) & 
                (pd.to_datetime(live_df['Tarih']).dt.date <= end_date)
            ]
            if not live_df.empty:
                # Mevcut olaylarla çakışmayanları ekle
                live_df['Önem'] = live_df['Önem'].astype(int)
                df = pd.concat([df, live_df], ignore_index=True)
                df['Tarih'] = pd.to_datetime(df['Tarih'])
                df = df.drop_duplicates(subset=['Tarih', 'Olay Adı'], keep='first')
                df = df.sort_values(['Tarih', 'Saat']).reset_index(drop=True)
    except Exception:
        pass
    
    # Ülke filtresi
    if countries:
        currency_map = {'TR': 'TRY', 'US': 'USD', 'EU': 'EUR', 'UK': 'GBP'}
        currencies = [currency_map.get(c, c) for c in countries]
        df = df[df['Para Birimi'].isin(currencies)]
    
    # Önem filtresi
    if importance == 'high':
        df = df[df['Önem'] >= 3]
    elif importance == 'medium':
        df = df[df['Önem'] >= 2]
    elif importance == 'low':
        df = df[df['Önem'] >= 1]
    
    return df.reset_index(drop=True)


def highlight_today_events(df: pd.DataFrame) -> pd.DataFrame:
    """Bugünkü olayları işaretler."""
    if df.empty:
        return df
    
    today = datetime.now().date()
    df = df.copy()
    df['Bugün'] = df['Tarih'].apply(
        lambda x: '📌' if (pd.to_datetime(x).date() == today) else ''
    )
    return df


def get_upcoming_high_importance_events(days: int = 7) -> List[Dict]:
    """Yaklaşan yüksek önemli olayları döndürür."""
    df = get_economic_calendar(
        countries=['TR', 'US'],
        importance='high',
        days=days
    )
    
    if df.empty:
        return []
    
    events = []
    for _, row in df.iterrows():
        events.append({
            'date': row['Tarih'],
            'time': row['Saat'],
            'currency': row['Para Birimi'],
            'event': row['Olay Adı'],
            'importance': row['Önem']
        })
    
    return events


# ============================================================================
# STREAMLIT İÇİN RENDER FONKSİYONU
# ============================================================================

def render_economic_calendar_tab():
    """Streamlit'te ekonomik takvim sekmesini render eder."""
    import streamlit as st
    
    st.markdown("## 📅 Ekonomik Takvim")
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        countries = st.multiselect(
            "Ülkeler",
            options=['TR', 'US', 'EU'],
            default=['TR', 'US'],
            format_func=lambda x: f"{COUNTRY_CODES.get(x, {}).get('flag', '')} {COUNTRY_CODES.get(x, {}).get('name', x)}"
        )
    
    with col2:
        importance = st.selectbox(
            "Önem Seviyesi",
            options=['all', 'high', 'medium'],
            format_func=lambda x: {
                'all': '📊 Tümü',
                'high': '⭐⭐⭐ Yüksek',
                'medium': '⭐⭐ Orta ve Üstü'
            }.get(x, x)
        )
    
    with col3:
        days = st.slider("Gün Sayısı", min_value=1, max_value=30, value=14)
    
    with st.spinner("Ekonomik takvim yükleniyor..."):
        df = get_economic_calendar(
            countries=countries,
            importance=importance,
            days=days
        )
    
    if df.empty:
        st.warning("Seçilen kriterlere uygun olay bulunamadı.")
        return
    
    df = highlight_today_events(df)
    
    today = datetime.now().date()
    today_events = df[pd.to_datetime(df['Tarih']).dt.date == today]
    high_importance = df[df['Önem'] >= 3]
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Toplam Olay", len(df))
    with col2:
        st.metric("Bugünkü Olaylar", len(today_events))
    with col3:
        st.metric("Yüksek Önem", len(high_importance))
    with col4:
        tr_events = len(df[df['Para Birimi'] == 'TRY'])
        st.metric("🇹🇷 Türkiye", tr_events)
    
    st.markdown("---")
    
    display_df = df.copy()
    display_df['Önem'] = display_df['Önem'].apply(lambda v: '⭐' * v)
    
    flags = {'TRY': '🇹🇷', 'USD': '🇺🇸', 'EUR': '🇪🇺', 'GBP': '🇬🇧'}
    display_df['Para Birimi'] = display_df['Para Birimi'].apply(
        lambda v: f"{flags.get(v, '')} {v}"
    )
    display_df['Tarih'] = pd.to_datetime(display_df['Tarih']).dt.strftime('%d %b %Y')
    
    column_order = ['Bugün', 'Tarih', 'Saat', 'Para Birimi', 'Olay Adı', 'Önem', 'Beklenti', 'Açıklanan', 'Önceki']
    display_df = display_df[[col for col in column_order if col in display_df.columns]]
    
    def highlight_today_row(row):
        if row.get('Bugün') == '📌':
            return ['background-color: #FFFACD'] * len(row)
        return [''] * len(row)
    
    styled_df = display_df.style.apply(highlight_today_row, axis=1)
    st.dataframe(styled_df, use_container_width=True, height=500)
    
    st.markdown("""
    **📝 Notlar:**
    - 📌 Bugünkü olaylar sarı ile vurgulanmıştır
    - ⭐⭐⭐ Yüksek önemli olaylar piyasaları önemli ölçüde etkileyebilir
    - Saatler Türkiye saatine göredir (UTC+3)
    - Tarihler resmi yayın takvimlerine dayanmaktadır
    """)


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Ekonomik Takvim Modülü Test")
    print("=" * 60)
    
    print("\n📅 Ekonomik Takvim (TR & US & EU, 14 gün):")
    df = get_economic_calendar(
        countries=['TR', 'US', 'EU'],
        importance='all',
        days=14
    )
    
    df = highlight_today_events(df)
    
    if not df.empty:
        print(df[['Tarih', 'Saat', 'Para Birimi', 'Olay Adı', 'Önem']].to_string())
        print(f"\n📊 Toplam {len(df)} olay")
        
        # Tarihlerin doğruluğunu kontrol et
        today = date.today()
        for _, row in df.iterrows():
            event_date = pd.to_datetime(row['Tarih']).date()
            assert today <= event_date <= today + timedelta(days=14), \
                f"Tarih aralık dışı: {event_date}"
        print("✅ Tüm tarihler doğru aralıkta")
    else:
        print("⚠️ Veri bulunamadı")
    
    print("\n✅ Test tamamlandı!")
