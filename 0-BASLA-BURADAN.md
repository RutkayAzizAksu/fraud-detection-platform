# Hızlı Başlangıç (Demo)

Asıl kod `RutkayAzizAksuFraudDetection/` klasöründe.

```bash
git clone https://github.com/RutkayAzizAksu/fraud-detection-platform.git
cd fraud-detection-platform/RutkayAzizAksuFraudDetection
docker compose up -d --build
```

Kafka'nın ayağa kalkması ~20-30 sn sürer; `api`/`worker` servisleri bu süreçte otomatik retry eder.

## Açılan servisler

| Servis | Adres |
|---|---|
| Frontend | http://localhost:3000 |
| API (Swagger) | http://localhost:8080/docs |
| MCP server | http://localhost:8000 |
| Kafka UI | http://localhost:8081 |
| Postgres | localhost:5432 |
| Redis | localhost:6379 |

## Demo akışı

- `localhost:3000`'e herhangi bir kullanıcı adı/şifre ile gir (simülasyon login).
- Dashboard'da canlı işlem akışını (SSE) izle.
- Yük/anomali üretmek için: `./scripts/auto-test.sh --duration=60 --rate=5 --anomaly-chance=30`
- Veya tek işlem göndermek için: `./scripts/manual-input.sh user1 9500 "Tokyo"`
- Fraud işaretli satırda **XSOAR** butonuna basarak War Room'u aç: `/help`, `/analyze user1`, `/block user1`, `/unblock user1`, `/status user1`

## Sorun çıkarsa

```bash
docker compose logs -f worker          # Kafka bağlantısı için
curl http://localhost:8080/dashboard   # API/worker çalışıyor mu
docker compose restart api             # SSE kesilirse
chmod +x scripts/*.sh                  # permission denied hatası için
```
