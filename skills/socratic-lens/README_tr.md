# Socratic Lens - Bağlam Grameri Çıkarımı (CGI)

**Herhangi bir korpusta dönüştürücü soruları tespit etmek için dinamik bir yöntem.**

---

## Problem

Bir sorunun "iyi" olduğunu nasıl anlarsın?

Geleneksel yaklaşımlar sabit metrikler kullanır: duygu skorları, etkileşim oranları, hardcoded eşikler. Ama bunlar "iyi"nin ne demek olduğunu zaten bildiğimizi varsayar.

Bilmiyoruz.

Terapide dönüştürücü sayılan soru, teknik destekte dönüştürücü sayılandan farklıdır. Bir bağlamda derinlik açan soru, başka bir bağlamı raydan çıkarabilir.

**Asıl problem ölçmek değil. Tanımlamak.**

---

## Köken

Bu sistem, *Arrival* (2016) filmindeki bir gözlemle başladı:

İnsanlık uzaylılarla karşılaştığında, ordu sorar: *"Düşman mısınız?"*

Dilbilimci Louise sorar: *"Amacınız ne?"*

İlk soru mevcut bir çerçeve içinde işler (tehdit değerlendirmesi). İkinci soru **çerçevenin kendisini dönüştürür**.

Bu basit bir teze yol açtı:

> **Doğru soru, en iyi cevabı alan soru değildir.**
> **Doğru soru, bağlamı dönüştüren sorudur.**

Ama sonra: "bağlam" nedir? Ve dönüşümü nasıl tespit edersin?

---

## İçgörü

Bağlam evrensel değildir. **Korpusa özgüdür.**

Bir terapi veri setinde bağlam, duygusal derinlik demek olabilir.
Bir teknik veri setinde bağlam, problem kapsamı demek olabilir.
Bir felsefi veri setinde bağlam, soyutlama seviyesi demek olabilir.

Bunu hardcode edemezsin. **Keşfetmen** gerekir.

---

## Yöntem

CGI altı zincir çalıştırır:

| Zincir | Soru |
|--------|------|
| 1. Gramer | "Bu veri setinde *bağlam* ne demek?" |
| 2. Pozitif | "Burada *dönüşüm* neye benziyor?" |
| 3. Negatif | "Burada *durağanlık* neye benziyor?" |
| 4. Lens | "Bu korpus için karar çerçevesi ne?" |
| 5. Tarama | "Hangi sorular dönüştürücü?" |
| 6. Sokratik | "Ne öğrendik? İnsana ne kalıyor?" |

Anahtar: **hiçbir şey varsayılmıyor**. Sistem yargılamadan önce örneklerden öğreniyor.

---

## Ne Üretiyor

Bir **lens**: korpusa özgü yorumlama çerçevesi.

Test çalışmasından örnek çıktı:

```
Lens: "Yüzeyden-Anlama Yeniden Çerçeveleme Lensi"

Karar Sorusu: 
"Bu soru, konuşmayı görev yürütme/betimleme düzeyinden
içsel anlam, varsayımlar veya kendilik ilişkisini incelemeye mi yönlendiriyor?"

Dönüştürücü Sinyaller:
- Dış betimleme yerine içsel düşünüme davet eder
- Değer takasları sunar (para vs aidiyet, kayıp vs kazanç)
- Paydaşları kimlik veya anlam etrafında yeniden çerçeveler

Mekanik Sinyaller:
- Mevcut görevi netleştirir veya ilerletir
- Çerçeveyi sorgulamadan bilgi/detay ister
- Niyeti tamamen araçsal tutar
```

Bu lens programlanmadı. Veriden **ortaya çıktı**.

---

## Ne Olduğu

- Bir **keşif yöntemi**, skorlama algoritması değil
- Bir **ayna**, yargıç değil
- **Sokratik**: sorar, sonuçlandırmaz
- **Korpusa uyumlu**: "bağlam"ın yerel anlamını öğrenir
- **İnsan-final**: adayları gösterir, insan karar verir

---

## Ne Olmadığı

- İnsan yargısının yerini almıyor
- Evrensel bir metrik değil ("0.7 = iyi" yok)
- Sabit kategorili bir sınıflandırıcı değil
- "Doğru soru"yu global olarak tanımlamaya çalışmıyor
- Tüm korpusların aynı çalıştığını varsaymıyor

---

## Sokratik Uyum

Sokrates cevap vermedi. İnsanların **farklı görmesini** sağlayan sorular sordu.

CGI bunu takip eder:

| Prensip | Uygulama |
|---------|----------|
| "Bildiğim tek şey, hiçbir şey bilmediğim" | Zincir 1-3: Yargılamadan önce öğren |
| Elenchus (sorgulama) | Zincir 5: Lensi uygula, gerilimleri bul |
| Aporia (üretken kafa karışıklığı) | Zincir 6: Ne çözümsüz kalıyor? |
| İnsan nihai otorite | Sistem gösterir, insan karar verir |

---

## Testten Anahtar Keşif

Başlangıç varsayımı:
> Dönüştürücü = "duygular hakkında sorar"

Gerçek bulgu:
> Dönüştürücü = "paydaşların yeniden yorumlanmasını zorlayan değer takasları sunar"

Sistem Sokratik zincir aracılığıyla **kendi lensini düzeltti**.

Şu tür sorular:
- "Bunu kabul etsen neyi kaybederdin?"
- "O topluluk sana paranın veremeyeceği neyi veriyor?"

Bunlar sadece "derine inmiyor." **Neyin tehlikede olduğunu yeniden çerçeveliyor.**

---

## İnsana Kalan

Sistem karar veremez:

1. **Uygunluk** — Derinlik için doğru an mı?
2. **Güvenlik** — Bu kişi bu soruya hazır mı?
3. **Etik** — Bu çerçeve sorgulanmalı mı?
4. **Zamanlama** — Burada dönüşüm istenen şey mi?

Bunlar yargı, empati, rıza gerektirir. Hiçbir sistem aksini iddia etmemeli.

---

## Neden Önemli

LLM'ler giderek daha fazla soru üretmek için kullanılıyor: terapi botlarında, koçluk uygulamalarında, eğitim araçlarında, mülakatlarda.

Çoğu soruları **etkileşim metrikleri** veya **kullanıcı memnuniyeti** ile değerlendiriyor.

Ama bir soru tatmin edici olup yine de sığ olabilir.
Bir soru rahatsız edici olup yine de dönüştürücü olabilir.

CGI farklı bir lens sunuyor:

> "Beğendiler mi?" diye sorma.
> "Problemi nasıl gördüklerini değiştirdi mi?" diye sor.

---

## Meta-Soru

Test sırasında son Sokratik zincir sordu:

> "Bu analiz süreci kendi başına bir dönüştürücü soru muydu?"

Cevap:

> "Evet—analizin kendisi dönüştürücü bir sorgulama işlevi gördü.
> Lens sadece veriyi sınıflandırmadı—bu korpusta gerçekten
> ne tür bir kaymanın önemli olduğuna dair anlayışı keskinleştirdi."

Yöntem vaaz ettiğini uyguladı.

---

## Kullanım

```python
from cgi_runner import CGIRunner

runner = CGIRunner(llm_fn=your_llm)
results = runner.run(your_corpus)

print(results["lens"])        # Korpusa özgü çerçeve
print(results["candidates"])  # Dönüştürücü soru adayları
print(results["reflection"])  # Meta-analiz
```

---

## Dosyalar

```
socratic-context-analyzer/
├── chains/
│ ├── CGI-1-GRAMMAR.yaml
│ ├── CGI-2-POSITIVE.yaml
│ ├── CGI-3-NEGATIVE.yaml
│ ├── CGI-4-LENS.yaml
│ ├── CGI-5-SCAN.yaml
│ └── CGI-6-SOCRATIC.yaml
├── tests/
│ ├── Mental Health Counseling Dataset/
│ │ ├── 10 Selected Conversation (Manuel Corpus)/
│ │ │ ├── thought process/
│ │ │ ├── cgi_manual_corpus_report.md
│ │ │ ├── cgi_manual_corpus_report_TR.md
│ │ │ └── prompt and thought process.txt
│ │ ├── Randomly Select 20 Conversation/
│ │ │ ├── thought process/
│ │ │ ├── cgi_analysis_report.md
│ │ │ ├── cgi_analysis_report_TR.md
│ │ │ └── prompt and thought process.txt
│ │ ├── 0000.parquet
│ │ ├── cgi_complete_summary_EN.md
│ │ ├── cgi_complete_summary_TR.md
│ │ └── first-test-output.txt
├── cgi_runner.py
├── README_tr.md
├── README_en.md
├── chain-view.text
├── gpt-instructions.md
└── test-output.text
```

---

## Kapanış

Bu proje basit bir soruyla başladı:

> "Bir sorunun iyi olduğunu nasıl anlarım?"

Cevabın başka bir soru olduğu ortaya çıktı:

> "Ne için iyi? Hangi bağlamda? Kimin tanımına göre?"

CGI bunları cevaplamıyor. **Keşfetmene** yardım ediyor.

Mesele bu.

---

## Lisans

MIT

---