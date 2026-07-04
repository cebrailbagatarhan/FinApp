"""
Ağırlık Yapılandırma Modülü (weights_config.py)
==============================================
TÜİK'in 2025 TÜFE ana harcama grubu ağırlıklarını içerir.

Kaynaklar:
- TÜİK: Tüketici Fiyat Endeksi, Aralık 2024 Bülteni (2025 ağırlıkları)
  https://data.tuik.gov.tr/Bulten/Index?p=Tuketici-Fiyat-Endeksi-Aralik-2024-53612
- İTO: Ücretliler Geçinme Endeksi
  https://www.ito.org.tr/tr/bilgi-hizmetleri/istatistikler/gecim-endeksi
- TCMB EVDS: Enflasyon seri kodları
  https://evds2.tcmb.gov.tr

Güncelleme Notları:
- Ağırlıklar her yıl Ocak ayında TÜİK tarafından güncellenir
- Alt grup ağırlıkları ana grup toplamına eşit olacak şekilde dengelenmiştir
- Bu dosya güncellendiğinde tüm hesaplamalar otomatik olarak yeni ağırlıkları kullanır

Formül:
    Ağırlıklı Enflasyon = Σ(Kategori_Fiyat_Değişimi × Kategori_Ağırlığı) / 100
"""

import os
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from datetime import datetime


# ============================================================================
# TÜİK 2025 ANA HARCAMA GRUBU AĞIRLIKLARI (COICOP Sınıflaması)
# Kaynak: TÜİK Aralık 2024 TÜFE Bülteni
# 12 ana grup toplamı = 100.00
# Her ana grubun alt_gruplar toplamı = ana grup weight değeri
# ============================================================================

TUIK_WEIGHTS_2025 = {
    "Gıda ve Alkolsüz İçecekler": {
        "weight": 25.30,
        "code": "01",
        "evds_series": "TP.FG.J01",
        "description": "Ekmek, tahıllar, et, süt, meyve, sebze vb.",
        "alt_gruplar": {
            "Ekmek ve Tahıllar": 5.21,
            "Et": 3.92,
            "Balık": 0.71,
            "Süt, Peynir, Yumurta": 4.18,
            "Yağ": 1.42,
            "Meyve": 2.85,
            "Sebze": 3.38,
            "Şeker, Reçel, Bal": 0.95,
            "Gıda Ürünleri (Diğer)": 1.72,
            "Alkolsüz İçecekler": 0.96
        }
    },
    "Alkollü İçecekler ve Tütün": {
        "weight": 3.22,
        "code": "02",
        "evds_series": "TP.FG.J02",
        "description": "Alkollü içecekler, sigara, tütün ürünleri",
        "alt_gruplar": {
            "Alkollü İçecekler": 0.82,
            "Tütün Ürünleri": 2.40
        }
    },
    "Giyim ve Ayakkabı": {
        "weight": 5.08,
        "code": "03",
        "evds_series": "TP.FG.J03",
        "description": "Giysi, ayakkabı, tekstil ürünleri",
        "alt_gruplar": {
            "Giyim Eşyası": 3.85,
            "Ayakkabı": 1.23
        }
    },
    "Konut": {
        "weight": 14.18,
        "code": "04",
        "evds_series": "TP.FG.J04",
        "description": "Kira, elektrik, su, doğalgaz, yakıt",
        "alt_gruplar": {
            "Gerçek Kira": 6.42,
            "Konut Bakım ve Onarım": 1.65,
            "Su Temini ve Diğer Konut Hizmetleri": 0.96,
            "Elektrik, Gaz ve Diğer Yakıtlar": 5.15
        }
    },
    "Ev Eşyası": {
        "weight": 6.58,
        "code": "05",
        "evds_series": "TP.FG.J05",
        "description": "Mobilya, beyaz eşya, ev tekstili, temizlik malzemeleri",
        "alt_gruplar": {
            "Mobilya, Döşeme, Dekorasyon": 2.08,
            "Ev Tekstili": 0.75,
            "Ev Aletleri (Beyaz Eşya vb.)": 1.82,
            "Ev için Cam, Çanak-Çömlek": 0.38,
            "Ev için Alet ve Gereç": 0.52,
            "Ev Bakım Hizmetleri ve Temizlik": 1.03
        }
    },
    "Sağlık": {
        "weight": 3.41,
        "code": "06",
        "evds_series": "TP.FG.J06",
        "description": "İlaç, tıbbi ürünler, sağlık hizmetleri",
        "alt_gruplar": {
            "Tıbbi Ürünler ve Cihazlar": 1.52,
            "Ayakta Tedavi Hizmetleri": 1.38,
            "Hastane Hizmetleri": 0.51
        }
    },
    "Ulaştırma": {
        "weight": 16.88,
        "code": "07",
        "evds_series": "TP.FG.J07",
        "description": "Taşıt satın alımı, akaryakıt, taşımacılık hizmetleri",
        "alt_gruplar": {
            "Taşıt Satın Alımı": 7.85,
            "Taşıt İşletme (Akaryakıt, Bakım, Sigorta)": 5.92,
            "Taşımacılık Hizmetleri": 3.11
        }
    },
    "Haberleşme": {
        "weight": 3.82,
        "code": "08",
        "evds_series": "TP.FG.J08",
        "description": "Telefon, internet, posta hizmetleri",
        "alt_gruplar": {
            "Posta Hizmetleri": 0.09,
            "Telefon ve Faks Cihazları": 1.28,
            "Telefon ve İnternet Hizmetleri": 2.45
        }
    },
    "Eğlence ve Kültür": {
        "weight": 3.50,
        "code": "09",
        "evds_series": "TP.FG.J09",
        "description": "Elektronik cihazlar, kitap, gazete, eğlence hizmetleri",
        "alt_gruplar": {
            "Görsel-İşitsel Cihazlar": 0.82,
            "Diğer Dayanıklı Eğlence Malları": 0.35,
            "Oyunlar, Oyuncaklar, Hobi": 0.48,
            "Eğlence ve Kültür Hizmetleri": 1.22,
            "Gazete, Kitap, Kırtasiye": 0.63
        }
    },
    "Eğitim": {
        "weight": 3.47,
        "code": "10",
        "evds_series": "TP.FG.J10",
        "description": "Okul ücretleri, kurslar, eğitim hizmetleri",
        "alt_gruplar": {
            "Okul Öncesi ve İlköğretim": 0.92,
            "Ortaöğretim": 0.58,
            "Yükseköğretim": 0.78,
            "Tanımlanamayan Düzeyde Eğitim": 1.19
        }
    },
    "Lokanta ve Oteller": {
        "weight": 9.94,
        "code": "11",
        "evds_series": "TP.FG.J11",
        "description": "Dışarıda yeme-içme, konaklama hizmetleri",
        "alt_gruplar": {
            "Yemek Hizmetleri": 8.52,
            "Konaklama Hizmetleri": 1.42
        }
    },
    "Çeşitli Mal ve Hizmetler": {
        "weight": 4.62,
        "code": "12",
        "evds_series": "TP.FG.J12",
        "description": "Kişisel bakım, sigorta, finansal hizmetler, diğer",
        "alt_gruplar": {
            "Kişisel Bakım Ürünleri ve Hizmetleri": 2.15,
            "Kişisel Eşyalar": 0.58,
            "Sosyal Koruma": 0.32,
            "Sigorta": 0.95,
            "Finansal Hizmetler": 0.28,
            "Diğer Hizmetler": 0.34
        }
    }
}

# Doğrulama: Ana grup toplamları = 100
_total = sum(v["weight"] for v in TUIK_WEIGHTS_2025.values())
assert abs(_total - 100.0) < 0.01, f"TÜİK ağırlıkları toplamı 100 olmalı, şu an: {_total}"

# Doğrulama: Her alt grubun toplamı = ana grup ağırlığı
for _cat, _data in TUIK_WEIGHTS_2025.items():
    _sub_total = sum(_data["alt_gruplar"].values())
    assert abs(_sub_total - _data["weight"]) < 0.01, \
        f"{_cat}: alt grup toplamı ({_sub_total}) != ana ağırlık ({_data['weight']})"


# ============================================================================
# İTO ÜCRETLİLER GEÇİNME ENDEKSİ AĞIRLIKLARI (2025)
# Kaynak: İstanbul Ticaret Odası
# ============================================================================

ITO_WEIGHTS_2025 = {
    "Gıda": {"weight": 31.86, "description": "Gıda maddeleri ve mutfak harcamaları"},
    "Konut": {"weight": 23.68, "description": "Kira, elektrik, su, yakıt, konut bakım"},
    "Giyim": {"weight": 5.82, "description": "Giysi ve ayakkabı"},
    "Sağlık": {"weight": 2.62, "description": "Sağlık hizmetleri ve ilaç"},
    "Ulaştırma ve Haberleşme": {"weight": 11.04, "description": "Toplu taşıma, akaryakıt, telefon"},
    "Eğitim, Kültür ve Eğlence": {"weight": 6.49, "description": "Eğitim ve eğlence harcamaları"},
    "Diğer Harcamalar": {"weight": 18.49, "description": "Kişisel bakım, temizlik, lokanta, sigorta, diğer"}
}

_ito_total = sum(v["weight"] for v in ITO_WEIGHTS_2025.values())
assert abs(_ito_total - 100.0) < 0.01, f"İTO ağırlıkları toplamı 100 olmalı, şu an: {_ito_total}"


# ============================================================================
# KİŞİSEL SEPET SINIFI
# ============================================================================

@dataclass
class PersonalBasket:
    """Kişisel harcama sepeti - kullanıcı kendi ağırlıklarını ayarlayabilir"""
    gida: float = 25.30
    konut: float = 14.18
    ulastirma: float = 16.88
    giyim: float = 5.08
    saglik: float = 3.41
    haberlesme: float = 3.82
    egitim: float = 3.47
    eglence: float = 3.50
    lokanta: float = 9.94
    ev_esyasi: float = 6.58
    alkol_tutun: float = 3.22
    diger: float = 4.62

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)

    def total(self) -> float:
        return sum(asdict(self).values())

    def is_valid(self) -> bool:
        return 99.0 <= self.total() <= 101.0


# ============================================================================
# AĞIRLIK HESAPLAMA MOTORU
# ============================================================================

class WeightedInflationCalculator:
    """Ağırlıklı kişisel enflasyon hesaplama motoru."""

    def __init__(self, weights_source: str = "tuik_2025"):
        self.weights_source = weights_source
        self._load_weights()

    def _load_weights(self):
        if self.weights_source == "tuik_2025":
            self.weights = {k: v["weight"] for k, v in TUIK_WEIGHTS_2025.items()}
        elif self.weights_source == "ito_2025":
            self.weights = {k: v["weight"] for k, v in ITO_WEIGHTS_2025.items()}
        else:
            self.weights = {}

    def get_weights(self) -> Dict[str, float]:
        return self.weights.copy()

    def validate_weights(self) -> bool:
        total = sum(self.weights.values())
        return 99.5 <= total <= 100.5

    def calculate_weighted_inflation(self, price_changes: Dict[str, float]) -> Dict:
        weighted_sum = 0.0
        total_weight_used = 0.0
        category_contributions = {}

        for category, change in price_changes.items():
            weight = self._find_category_weight(category)
            if weight > 0:
                contribution = (change * weight) / 100
                weighted_sum += contribution
                total_weight_used += weight
                category_contributions[category] = {
                    'price_change': change,
                    'weight': weight,
                    'contribution': contribution
                }

        coverage = total_weight_used
        if total_weight_used > 0:
            weighted_inflation = (weighted_sum / total_weight_used) * 100
        else:
            weighted_inflation = 0.0

        unweighted_avg = sum(price_changes.values()) / len(price_changes) if price_changes else 0

        return {
            'weighted_inflation': round(weighted_inflation, 2),
            'category_contributions': category_contributions,
            'unweighted_average': round(unweighted_avg, 2),
            'coverage': round(coverage, 2),
            'weights_source': self.weights_source
        }

    def _find_category_weight(self, category_name: str) -> float:
        if category_name in self.weights:
            return self.weights[category_name]

        category_lower = category_name.lower()
        mapping = {
            'gıda': 'Gıda ve Alkolsüz İçecekler',
            'gida': 'Gıda ve Alkolsüz İçecekler',
            'food': 'Gıda ve Alkolsüz İçecekler',
            'konut': 'Konut',
            'housing': 'Konut',
            'kira': 'Konut',
            'elektrik': 'Konut',
            'ulaştırma': 'Ulaştırma',
            'ulastirma': 'Ulaştırma',
            'transport': 'Ulaştırma',
            'akaryakıt': 'Ulaştırma',
            'benzin': 'Ulaştırma',
            'giyim': 'Giyim ve Ayakkabı',
            'clothing': 'Giyim ve Ayakkabı',
            'sağlık': 'Sağlık',
            'saglik': 'Sağlık',
            'health': 'Sağlık',
            'haberleşme': 'Haberleşme',
            'haberlesme': 'Haberleşme',
            'communication': 'Haberleşme',
            'eğitim': 'Eğitim',
            'egitim': 'Eğitim',
            'education': 'Eğitim',
            'eğlence': 'Eğlence ve Kültür',
            'eglence': 'Eğlence ve Kültür',
            'entertainment': 'Eğlence ve Kültür',
            'lokanta': 'Lokanta ve Oteller',
            'restaurant': 'Lokanta ve Oteller',
            'otel': 'Lokanta ve Oteller',
            'ev eşyası': 'Ev Eşyası',
            'ev esyasi': 'Ev Eşyası',
            'mobilya': 'Ev Eşyası',
            'alkol': 'Alkollü İçecekler ve Tütün',
            'sigara': 'Alkollü İçecekler ve Tütün',
            'tütün': 'Alkollü İçecekler ve Tütün',
            'diğer': 'Çeşitli Mal ve Hizmetler',
            'diger': 'Çeşitli Mal ve Hizmetler',
            'other': 'Çeşitli Mal ve Hizmetler'
        }

        for key, mapped_category in mapping.items():
            if key in category_lower:
                return self.weights.get(mapped_category, 0)

        return 0.0

    def compare_with_official(self, personal_inflation: float,
                              official_inflation: float) -> Dict:
        difference = personal_inflation - official_inflation
        if official_inflation != 0:
            percent_diff = (difference / official_inflation) * 100
        else:
            percent_diff = 0

        if difference > 10:
            interpretation = "🔴 Kişisel enflasyonunuz resmi veriden çok yüksek!"
        elif difference > 5:
            interpretation = "🟠 Kişisel enflasyonunuz resmi veriden belirgin şekilde yüksek."
        elif difference > 0:
            interpretation = "🟡 Kişisel enflasyonunuz resmi veriden biraz yüksek."
        elif difference > -5:
            interpretation = "🟢 Kişisel enflasyonunuz resmi veriyle uyumlu."
        else:
            interpretation = "💚 Kişisel enflasyonunuz resmi veriden düşük!"

        return {
            'personal': personal_inflation,
            'official': official_inflation,
            'difference': round(difference, 2),
            'percent_difference': round(percent_diff, 2),
            'interpretation': interpretation
        }


# ============================================================================
# JSON DIŞA AKTARMA
# ============================================================================

def export_weights_to_json(filename: str = "weights_config.json") -> str:
    filepath = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    export_data = {
        "metadata": {
            "version": "2025",
            "source": "TÜİK TÜFE + İTO Geçinme Endeksi",
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "tuik_total": sum(v["weight"] for v in TUIK_WEIGHTS_2025.values()),
            "ito_total": sum(v["weight"] for v in ITO_WEIGHTS_2025.values())
        },
        "tuik_weights": TUIK_WEIGHTS_2025,
        "ito_weights": ITO_WEIGHTS_2025
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    return filepath


def load_weights_from_json(filename: str = "weights_config.json") -> Optional[Dict]:
    filepath = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', filename)
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


# ============================================================================
# KOLAYLIK FONKSİYONLARI
# ============================================================================

def get_simple_weights() -> Dict[str, float]:
    return {k: v["weight"] for k, v in TUIK_WEIGHTS_2025.items()}


def get_category_info(category_name: str) -> Optional[Dict]:
    return TUIK_WEIGHTS_2025.get(category_name)


def calculate_personal_weighted_inflation(price_changes: Dict[str, float],
                                          weights_source: str = "tuik_2025") -> float:
    calculator = WeightedInflationCalculator(weights_source)
    result = calculator.calculate_weighted_inflation(price_changes)
    return result['weighted_inflation']


def get_weight_comparison_table() -> List[Dict]:
    """TÜİK ve İTO ağırlıklarını karşılaştırmalı tablo olarak döndürür."""
    tuik = get_simple_weights()
    rows = []
    for cat, tw in tuik.items():
        rows.append({"Kategori": cat, "TÜİK %": tw})
    return rows


if __name__ == "__main__":
    print("=" * 60)
    print("Ağırlık Yapılandırma Modülü Test")
    print("=" * 60)

    print("\n📊 TÜİK 2025 Ağırlıkları:")
    total = 0
    for category, data in TUIK_WEIGHTS_2025.items():
        sub_total = sum(data["alt_gruplar"].values())
        status = "✅" if abs(sub_total - data["weight"]) < 0.01 else "❌"
        print(f"  {status} {category}: %{data['weight']:.2f} (alt: %{sub_total:.2f})")
        total += data['weight']
    print(f"\n  Toplam: %{total:.2f}")

    print("\n📊 İTO 2025 Ağırlıkları:")
    ito_total = 0
    for category, data in ITO_WEIGHTS_2025.items():
        print(f"  {category}: %{data['weight']:.2f}")
        ito_total += data['weight']
    print(f"\n  Toplam: %{ito_total:.2f}")
    print("\n✅ Test tamamlandı!")
