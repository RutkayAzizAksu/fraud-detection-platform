# Kartaca E-Ticaret Fraud Tespit Platformu

E-ticaret sistemlerindeki sahtecilik (fraud) tespitini gerçek zamanlı ve ölçeklenebilir bir şekilde çözmek için geliştirdiğim, mikroservis mimarisine dayanan bir platformdur. Sistem, Docker Compose ile tek komutla ayağa kalkar.

---

## Projenin Amacı ve Kapsamı

Bu projeyi geliştirirken kendime şu soruyu sordum: *"Bir SOC analisti, yüksek hacimli bir işlem trafiği içinde şüpheli hareketi saniyeler içinde nasıl görebilir?"* Cevabım bu platform oldu.

Sistem; hız (velocity), tutar (amount) ve coğrafi imkansızlık (location/haversine) bazlı üç kural üzerinden her işlemi değerlendirir. Birden fazla kural ihlal edildiğinde sistem işlemi otomatik olarak reddeder ve analiste gerçek zamanlı bildirim gönderir. Dashboard üzerindeki XSOAR War Room paneli ise analistin terminal komutlarıyla (örn: `/block user1`) müdahale edebilmesini sağlar.

---

## Sistem Mimarisi ve Komponentlerin Açıklaması

Tüm sistemi 4 bağımsız servise böldüm. Her biri kendi Docker konteynerinde koşar, birbirleriyle Kafka üzerinden konuşurlar:

```
[Frontend / React]
       │ SSE (canlı veri)
       ▼
[API Servisi / FastAPI]  ──POST──▶  [Kafka: raw-transactions]
                                              │
                                              ▼
                                   [Worker Servisi / Python]
                                        │         │
                                    Redis        PostgreSQL
                                        │
                                        ▼
                               [Kafka: processed-transactions]
                                        │
                                        ▼
                              [API] ──SSE──▶ [Frontend]

[MCP Servisi] ──────────────────────────────▶ PostgreSQL
(AI modellerinin sisteme erişim kapısı)
```

1. **API Servisi (FastAPI):** REST endpoint'lerini yönetir, işlemleri Kafka'ya kuyruğa alır, frontend'e SSE ile canlı veri pompalar.
2. **Worker Servisi (Python):** Kafka kuyruğundan ham veriyi okur, anomali tespit algoritmalarını çalıştırır, kararı PostgreSQL'e yazar ve sonucu tekrar Kafka'ya basar.
3. **MCP Servisi (FastMCP):** AI modellerinin (Claude, GPT vb.) sistemi sorgulaması için açık bir arayüz sunar. `get_recent_frauds` ve `check_user_status` tool'larını dışa açar.
4. **Frontend (React + Vite):** Canlı işlem akışı, fraud uyarıları, Cortex XSOAR simülasyonu ve kullanıcı risk profili panelini içerir.

---

## Teknoloji Seçimleri ve Gerekçeleri

**Kafka:** İşlemlerin kaybolmaması gerekiyordu. Kafka'nın log-based mimarisi, bir servis çökse bile mesajların kaybolmadığını garanti ediyor. RabbitMQ'yu da düşündüm ama yeniden oynatma (replay) ihtiyacı olmasa da Kafka'nın partition yapısı ileride yatay ölçekleme için çok daha uygun olduğunu gördüm.

**Redis:** Velocity kuralı için "son 1 dakikadaki işlem sayısı" anlık olarak tutulması gerekiyordu. Bunu PostgreSQL'de sorgulamak hem yavaş hem de çok pahalı olurdu. Redis'in Sorted Set yapısı (`ZRANGEBYSCORE`) bu iş için biçilmiş kaftan; O(log n) karmaşıklıkla milisaniyede cevap veriyor. Tutar ortalaması ve son konum bilgisi de aynı şekilde Redis'te cache'leniyor.

**PostgreSQL:** Kalıcı, ilişkisel veri için. `transactions` ve `frauds` tabloları arasındaki JOIN sorgusu ile kullanıcı risk profili çok temiz çalışıyor.

**FastAPI + asyncio:** Worker ve API tamamen asenkron yazıldı. `asyncpg`, `aiokafka`, `aioredis` — hepsi event loop üzerinde. Bu sayede thread bloğu olmadan yüksek eşzamanlılık sağlandı.

---

## Kurulum Adımları

### Gereksinimler
- Docker Desktop (v4.0+)
- Docker Compose (v2.0+)

### Tek Komutla Başlat

```bash
git clone <repo-url>
cd kartaca-fraud-platform
docker compose up -d --build
```

Sistem sırasıyla şu servisleri ayağa kaldırır:

| Servis | Port | Açıklama |
|--------|------|----------|
| Frontend | `3000` | React dashboard |
| API | `8080` | FastAPI REST + SSE |
| MCP | `8000` | AI tool server |
| Kafka UI | `8081` | Mesaj kuyruğu monitörü |
| PostgreSQL | `5432` | Veritabanı |
| Redis | `6379` | Cache |

> **Not:** Kafka ayağa kalması ~20-30 saniye sürer. `api` ve `worker` servisleri bu süreçte otomatik olarak yeniden bağlanmayı dener.

---

## Kullanım Rehberi

**Dashboard:** `http://localhost:3000` — Giriş ekranında herhangi bir kullanıcı adı ve şifre yazabilirsiniz (simülasyon).

**Canlı İzleme:** Giriş sonrası dashboard'da işlemler gerçek zamanlı akar. Fraud işaretli satırlar kırmızıyla vurgulanır. Satırın üzerine gelindiğinde çıkan **XSOAR** butonuna tıklamak War Room'u açar ve fraud kullanıcısını otomatik olarak engeller.

**War Room Komutları:**
```
/help                  → Tüm komutları listele
/analyze <user_id>     → Kullanıcı risk taraması
/block <user_id>       → Kullanıcıyı engelle
/unblock <user_id>     → Engeli kaldır
/status <user_id>      → Kullanıcı durumunu kontrol et
/clear                 → Terminali temizle
```

**Kafka UI:** `http://localhost:8081` — `raw-transactions`, `processed-transactions`, `detected-frauds` topic'lerini canlı izleyebilirsiniz.

---

## API ve MCP Dokümantasyonu

### REST API (`http://localhost:8080`)

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| `GET` | `/` | Servis durumu |
| `POST` | `/transaction` | Yeni işlem gönder |
| `GET` | `/dashboard` | Son işlemler + grafik verisi |
| `GET` | `/users/{user_id}` | Kullanıcı işlem geçmişi + fraud kayıtları |
| `GET` | `/events` | SSE canlı veri akışı |

**Swagger UI:** `http://localhost:8080/docs`

**Örnek istek:**
```bash
curl -X POST http://localhost:8080/transaction \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user1", "amount": 9500, "location": "Tokyo"}'
```

### MCP Server (`http://localhost:8000`)

AI modellerinin sistemi sorgulaması için iki tool dışa açılmıştır:

- `get_recent_frauds()` — Son 1 saatte yakalanan fraud işlemlerini listeler
- `check_user_status(user_id: str)` — Kullanıcının tüm işlem ve risk geçmişini döner

**MCP Inspector ile test:**
```bash
npx @modelcontextprotocol/inspector python ./backend/mcp/main.py
```

---

## Script'lerin Kullanımı ve Parametreleri

### Manuel İşlem Gönderme

```bash
./scripts/manual-input.sh <user_id> <amount> <location>

# Örnek:
./scripts/manual-input.sh user1 9500 "Tokyo"
```

### Otomatik Test (Yük + Anomali Simülasyonu)

```bash
./scripts/auto-test.sh --duration=60 --rate=5 --anomaly-chance=30
```

| Parametre | Açıklama | Varsayılan |
|-----------|----------|------------|
| `--duration` | Kaç saniye çalışsın | `60` |
| `--rate` | Saniyede kaç istek | `5` |
| `--anomaly-chance` | Anomali ihtimali (%) | `10` |

Script iki farklı anomali senaryosu üretir:
1. **Yüksek tutar:** $5.000-$10.000 arası işlemler → Amount Rule tetikler
2. **Velocity burst:** Aynı kullanıcıya 6 ardışık istek → Velocity Rule tetikler

---

## Geliştirme Notları

Bu bölümü projeyi geliştirirken gerçekten karşılaştığım sorunlar için açıyorum.

**Kafka + Docker Network Sorunu:** Geliştirme sürecinde en çok zaman harcadığım nokta buydu. `api` ve `worker` servisleri Kafka'ya bağlanmaya çalışırken sürekli `NoBrokersAvailable` hatası alıyordum. Sorun, Kafka'nın iki farklı listener tanımlamasından (iç ve dış ağ) kaynaklanıyordu. Docker compose içi servisler `kafka:29092` adresini, dışarıdan erişimler ise `localhost:9092` adresini kullanmalı. `KAFKA_ADVERTISED_LISTENERS` ve `KAFKA_LISTENER_SECURITY_PROTOCOL_MAP` ayarlarını düzgün yapılandırarak bu sorunu çözdüm.

**Datetime Timezone Uyumsuzluğu:** Dashboard grafiği başta hiç veri göstermiyordu. Sebebini araştırdığımda şunu gördüm: Worker, işlemleri UTC-aware (`datetime.now(timezone.utc)`) olarak kaydediyordu ama API tarafındaki sorgu tz-naive (`datetime.utcnow()`) bir parametre kullanıyordu. PostgreSQL bu iki formatı kıyaslayamadığı için sorgu boş dönüyordu. Sorguyu `WHERE timestamp >= NOW() - INTERVAL '1 hour'` olarak değiştirerek PostgreSQL'in kendi timestamp yönetimine bıraktım ve sorun çözüldü.

**Redis Sorted Set ile Velocity Yönetimi:** Başlangıçta velocity kontrolü için basit bir counter tutmayı düşünmüştüm. Ancak bu yaklaşım "sliding window" değil "fixed window" olacaktı ve 1 dakikanın sıfırlanma anında yanlış sonuçlar üretebilirdi. Redis'in `ZADD`/`ZREMRANGEBYSCORE` kombinasyonuyla gerçek sliding window implementasyonu yapınca hem doğruluk hem de performans problemini aynı anda çözdüm.

---

## Sorun Giderme (Troubleshooting)

**Konteynerler açılmıyor:**
```bash
docker compose logs -f
# veya belirli bir servis için:
docker compose logs -f api
```
Kafka'nın tamamen ayağa kalkması 20-30 saniye sürebilir. Servisler `restart: always` ile yapılandırıldığı için kendi kendine yeniden bağlanır.

**Dashboard boş geliyor:**
```bash
curl http://localhost:8080/dashboard
# transactions ve stats dizileri doluysa API çalışıyor demektir.
# Boşsa worker'ın Kafka'ya bağlanıp bağlanmadığını kontrol edin:
docker compose logs worker
```

**Veriler gelmiyor (SSE kesildi):**
Tarayıcı konsolunda (`F12`) Network sekmesinden `/events` bağlantısının `pending` durumda olup olmadığını kontrol edin. Eğer `failed` ise API servisini yeniden başlatın:
```bash
docker compose restart api
```

**Script çalışmıyor (permission denied):**
```bash
chmod +x scripts/auto-test.sh scripts/manual-input.sh
```

---

*Rutkay Aziz Aksu*
