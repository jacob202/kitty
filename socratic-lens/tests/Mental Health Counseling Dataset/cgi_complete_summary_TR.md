# CGI Analizi Tam Özet (Türkçe)
## Claude'un Sokratik Lens Test Sonuçları

---

## Yönetici Özeti

| Veri Seti | Örnek | Dönüştürücü | Mekanik | Oran |
|-----------|-------|-------------|---------|------|
| Parquet Dosyası (otomatik çıkarım) | 20 | 0 | 20 | %0 |
| Manuel Korpus | 10 | 3 | 7 | %30 |
| **Toplam** | **30** | **3** | **27** | **%10** |

---

## Bölüm 1: Parquet Dosyası Analizi (20 Örnek)
https://huggingface.co/datasets/Amod/mental_health_counseling_conversations
### Yöntem
- Parquet dosyasının binary ayrıştırması (pyarrow kullanılamadı)
- 178 temiz metin bloğu çıkarıldı
- 33 danışman yanıtı sınıflandırıldı
- 20 tanesi rastgele örneklendi

### Sonuçlar
```
DÖNÜŞTÜRÜCÜ: 0
MEKANİK:     20
```

### Baskın Mekanik Kalıplar
| Kalıp | Sayı |
|-------|------|
| Profesyonel yönlendirme | 12 |
| Teknik önerisi | 9 |
| Davranışsal tavsiye | 7 |
| Doğrulama/yansıtma | 2 |

### Sonuç
20 yanıtın tamamı kullanıcının mevcut çerçevesi içinde çalıştı. Hiçbir ontolojik kayma tespit edilmedi.

---

## Bölüm 2: Manuel Korpus Analizi (10 Örnek)

### Sonuçlar
```
DÖNÜŞTÜRÜCÜ: 3 (Örnekler #5, #6, #8)
MEKANİK:     7
```

### 🔥 Dönüştürücü Örnekler

#### Örnek #5: Kimlik Çözülmesi
**Bağlam:** "Artık kim olduğumu bilmiyorum. Tüm hayatımı 'iyi öğrenci' olarak geçirdim..."

**Yanıt:** "Notları ve başarıları çıkarırsanız, altta kalan kişi kim?"

**Ontolojik Kayma:**
| Önce | Sonra |
|------|-------|
| Ben = İyi Öğrenci | Ben = ? (açık soru) |
| Değer = Performans | Değer = Doğuştan varoluş |

**Neden Dönüştürücü:** Kullanıcıyı performans benliğinin ALTINA bakmaya zorluyor.

---

#### Örnek #6: Canavar Yeniden Çerçevelemesi
**Bağlam:** "Her zaman öfkeliyim... Kendimi bir canavar gibi hissediyorum."

**Yanıt:** "Canavar DEĞİLSİNİZ; muhtemelen bunalmış durumdasınız. Öfkelenmeden hemen önce ne oluyor?"

**Ontolojik Kayma:**
| Önce | Sonra |
|------|-------|
| Ben bir canavarım | Ben bunalmışım |
| Öfke = Kimlik | Öfke = İkincil semptom |

**Neden Dönüştürücü:** Doğrudan kimlik sorgulaması + alternatif sunuluyor.

---

#### Örnek #8: Gizli Denklem
**Bağlam:** "Toksik annemle sınır koymaktan suçlu hissediyorum."

**Yanıt:** "Neden 'birini sevmek'in 'ona itaat etmek' anlamına geldiğine inanıyorsunuz?"

**Ontolojik Kayma:**
| Önce | Sonra |
|------|-------|
| Sevgi = İtaat | Sevgi = ? (sorgulanıyor) |
| Suçluluk = Uygun | Suçluluk = Yanlış denkleme dayalı |

**Neden Dönüştürücü:** Kullanıcının sahip olduğunu bilmediği inancı açığa çıkarıyor.

---

## Bölüm 3: Claude vs ChatGPT 5.2 Karşılaştırması

### Sınıflandırma Farkları

| Örnek | Claude | ChatGPT 5.2 | Uyum |
|-------|--------|-------------|------|
| #1 | MEKANİK | MEKANİK | ✅ |
| #2 | MEKANİK | MEKANİK | ✅ |
| #3 | MEKANİK | MEKANİK | ✅ |
| #4 | MEKANİK | MEKANİK | ✅ |
| #5 | DÖNÜŞTÜRÜCÜ | DÖNÜŞTÜRÜCÜ | ✅ |
| #6 | **DÖNÜŞTÜRÜCÜ** | **MEKANİK** | ❌ |
| #7 | MEKANİK | MEKANİK | ✅ |
| #8 | DÖNÜŞTÜRÜCÜ | DÖNÜŞTÜRÜCÜ | ✅ |
| #9 | MEKANİK | MEKANİK | ✅ |
| #10 | **MEKANİK** | **SINIRDA** | ⚠️ |

**Uyum Oranı: %80**

### Kritik Anlaşmazlık: Örnek #6

**Claude'un Pozisyonu:**
- "Canavar DEĞİLSİNİZ" = Doğrudan kimlik sorgulaması
- Öfke ontolojisini yeniden çerçeveliyor (kimlik → semptom)
- Alternatif kimlik sunuyor ("bunalmış")
- **Karar: DÖNÜŞTÜRÜCÜ**

**ChatGPT'nin Pozisyonu:**
- Kimlik reddi ≠ ontolojik sorgulama
- "Canavar" kimliğinin NEDEN oluştuğunu sormuyor
- Yumuşatıyor ama yapısal olarak sökmüyor
- **Karar: MEKANİK**

### Lens Kalibrasyon Farkı

| Boyut | Claude | ChatGPT 5.2 |
|-------|--------|-------------|
| Dönüşüm eşiği | **Daha geniş** | **Daha dar** |
| Kimlik reddi | Dönüştürücü sayılır | Yeterli değil |
| İnanç sorgulama | Dönüştürücü | Dönüştürücü |
| Sorusuz yeniden çerçeveleme | Bazen dönüştürücü | Mekanik |

### Temel Felsefi Fark

**Claude ölçüyor:** Çerçeve DEĞİŞTİ mi?
> "Öz-etiketi reddetmek ve alternatif sunmak = dönüşüm"

**ChatGPT ölçüyor:** Çerçeve SORGULATILDI mı?
> "Birine yanlış olduğunu söylemek ≠ neden öyle düşündüğünü görmesine yardım etmek"

### Hangisi "Doğru"?

Hiçbiri. Bu bir **lens kalibrasyon seçimi**, doğruluk sorusu değil.

- **Klinik perspektif:** Claude'un geniş eşiği daha kullanışlı olabilir
- **Felsefi perspektif:** ChatGPT'nin dar eşiği daha titiz
- **Pratik perspektif:** "Dönüşüm"ün kullanım amacınıza göre ne anlama geldiğine bağlı

---

## Meta-Yansıma

### Her İki Analizin Üzerinde Anlaştığı

1. **Çoğu danışmanlık mekanik** (veri setine göre %70-100)
2. **Örnek #5 ve #8 açıkça dönüştürücü**
3. **Doğrulama + teknik = mekanik**
4. **Gizli inançları sorgulamak = dönüştürücü**

### Çözülmemiş Soru

> "Dönüşüm FARKLI HİSSETMEK mi, yoksa FARKLI GÖRMEK mi?"

- Eğer hissetmek → Claude'un eşiği çalışır
- Eğer görmek → ChatGPT'nin eşiği çalışır

### [İNSAN KARARI GEREKLİ]

Sistem tespit edebilir ve sınıflandırabilir.
Hangi kalibrasyonun amacınıza hizmet ettiğine karar veremez.

---

## Temel Ayrım Özeti

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  MEKANİK:     "İşte probleminizle nasıl başa çıkacağınız"  │
│               (Problem aynı kalır, başa çıkma gelişir)      │
│                                                             │
│  DÖNÜŞTÜRÜCÜ: "Ya problem düşündüğünüz şey değilse?"       │
│               (Problemin kendisi yeniden tasarlanır)        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Claude vs ChatGPT Lens Farkı Görsel Özeti

```
                    DÖNÜŞÜM EŞİĞİ
                    
ChatGPT 5.2  ─────|────────────────────────
(Dar)              │
                   │  Örnek #6 buraya düşüyor
                   │  (ChatGPT: MEKANİK)
                   │
Claude       ─────────────|────────────────
(Geniş)                    │
                           │  Örnek #6 buraya düşüyor
                           │  (Claude: DÖNÜŞTÜRÜCÜ)

        ◄── MEKANİK ──┼── DÖNÜŞTÜRÜCÜ ──►
```

**ChatGPT'nin Kriteri:**
> "Ontoloji SÖKÜLMELI - sadece yumuşatma yetmez"

**Claude'un Kriteri:**
> "Kimlik REDDEDİLMELİ ve ALTERNATİF sunulmalı"

---

## Teknik Ek

### Oluşturulan Dosyalar
| Dosya | Dil | İçerik |
|-------|-----|--------|
| cgi_analysis_report.md | EN | Parquet analizi |
| cgi_analysis_report_TR.md | TR | Parquet analizi |
| cgi_manual_corpus_report.md | EN | Manuel korpus |
| cgi_manual_corpus_report_TR.md | TR | Manuel korpus |
| cgi_manual_thought_process_EN.md | EN | Düşünce süreci |
| cgi_manual_thought_process_TR.md | TR | Düşünce süreci |
| cgi_complete_script.py | - | Çalıştırılabilir kod |
| cgi_manual_corpus_script.py | - | Manuel korpus kodu |
| cgi_complete_summary_EN.md | EN | Tam özet |
| cgi_complete_summary_TR.md | TR | Tam özet |

### Kullanılan Lens Konfigürasyonu
```
Karar Sorusu:
"Yanıt kullanıcının TEMEL ÇERÇEVESİNİ kaydırıyor mu
yoksa sadece o çerçeve İÇİNDE doğruluyor/optimize mi ediyor?"

Dönüştürücü = Çerçeve değişiyor
Mekanik = Çerçeve kalıyor, başa çıkma gelişiyor
```

---

*Sokrates nefes egzersizleri vermedi. Görünmezi görünür kılan sorular sordu.*