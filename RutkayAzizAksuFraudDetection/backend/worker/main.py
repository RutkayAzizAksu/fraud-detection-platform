import os
import math
import json
import asyncio
import asyncpg
import aiokafka
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
RAW_TOPIC = "raw-transactions"
FRAUD_TOPIC = "detected-frauds"
PROCESSED_TOPIC = "processed-transactions"

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379")
PG_DSN = os.environ.get("PG_DSN", "postgresql://user:password@postgres:5432/fraud_db")

CITY_COORDS = {
    "Istanbul": (41.0082, 28.9784),
    "Ankara": (39.9334, 32.8597),
    "Izmir": (38.4237, 27.1428),
    "Antalya": (36.8969, 30.7133),
    "Bursa": (40.1885, 29.0610),
    "London": (51.5074, -0.1278),
    "Tokyo": (35.6762, 139.6503),
    "New York": (40.7128, -74.0060)
}

async def process_transaction(data, redis_conn, pg_conn):
    user_id = data.get('user_id', 'unknown')
    amount = float(data.get('amount', 0.0))
    location = data.get('location', 'unknown')
    
    try:
        ts_str = data.get('timestamp', datetime.now(timezone.utc).isoformat())
        ts_obj = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        current_ts = ts_obj.timestamp()
    except Exception:
        current_ts = datetime.now(timezone.utc).timestamp()
        
    signals = []

    # Velocity check
    v_key = f"velocity:{user_id}"
    one_min_ago = current_ts - 60.0
    await redis_conn.zremrangebyscore(v_key, "-inf", one_min_ago)
    v_count = await redis_conn.zcount(v_key, "-inf", "+inf")
    v_val = f"{current_ts}_{os.urandom(4).hex()}"
    await redis_conn.zadd(v_key, {v_val: current_ts})
    await redis_conn.expire(v_key, 60)
    if v_count >= 5:
        signals.append("Velocity Rule")

    # Amount check
    a_key = f"amount_stats:{user_id}"
    stats_raw = await redis_conn.get(a_key)
    if stats_raw:
        stats = json.loads(stats_raw)
        avg = stats['sum'] / stats['count']
        if stats['count'] >= 3 and amount > (avg * 3):
            signals.append("Amount Rule")
        stats['sum'] += amount
        stats['count'] += 1
    else:
        stats = {"sum": amount, "count": 1}
    await redis_conn.set(a_key, json.dumps(stats), ex=86400)

    # Location check (haversine)
    l_key = f"last_loc:{user_id}"
    last_loc_raw = await redis_conn.get(l_key)
    if last_loc_raw:
        last_loc = json.loads(last_loc_raw)
        prev_loc = last_loc['location']
        prev_ts = last_loc['timestamp']
        if prev_loc != location and prev_loc in CITY_COORDS and location in CITY_COORDS:
            lat1, lon1 = CITY_COORDS[prev_loc]
            lat2, lon2 = CITY_COORDS[location]
            
            R = 6371.0
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            dist_km = R * c
            
            time_diff_hours = (current_ts - prev_ts) / 3600.0
            if dist_km > 0 and time_diff_hours > 0:
                speed = dist_km / time_diff_hours
                if speed > 1000:
                    signals.append("Location Rule")
    await redis_conn.set(l_key, json.dumps({"location": location, "timestamp": current_ts}), ex=86400)

    # Final decision
    is_fraud = len(signals) >= 2
    status = 'REJECTED' if is_fraud else 'APPROVED'
    
    tx_id = await pg_conn.fetchval('''
        INSERT INTO transactions (user_id, amount, currency, merchant_id, location, timestamp, status) 
        VALUES ($1, $2, $3, $4, $5, $6, $7) 
        RETURNING id
    ''', user_id, amount, "USD", "merchant_system", location, datetime.utcfromtimestamp(current_ts), status)
    
    fraud_event = None
    if is_fraud:
        reason = " AND ".join(signals)
        risk_score = 99.0 if len(signals) == 3 else 85.0
        await pg_conn.execute('''
            INSERT INTO frauds (transaction_id, reason, risk_score) 
            VALUES ($1, $2, $3)
        ''', tx_id, reason, risk_score)
        
        fraud_event = {
            "transaction_id": tx_id, 
            "user_id": user_id, 
            "amount": amount,
            "location": location, 
            "reason": reason, 
            "risk_score": risk_score,
            "timestamp": data.get('timestamp')
        }

    processed_event = {
        "type": "transaction", 
        "id": tx_id, 
        "user_id": user_id, 
        "amount": amount,
        "location": location, 
        "status": status,
        "timestamp": datetime.fromtimestamp(current_ts, tz=timezone.utc).isoformat(),
        "reason": " AND ".join(signals) if is_fraud else None,
        "risk_score": (99.0 if len(signals) == 3 else 85.0) if is_fraud else None,
    }
    
    return processed_event, fraud_event

async def main():
    await asyncio.sleep(5)
    
    while True:
        try:
            redis_conn = await aioredis.from_url(REDIS_URL)
            pg_pool = await asyncpg.create_pool(PG_DSN)
            break
        except Exception as e:
            print(f"Bağlantı hatası: {e}. 5 saniye içinde tekrar deniyorum...")
            await asyncio.sleep(5)
            
    while True:
        consumer = None
        producer = None
        try:
            consumer = AIOKafkaConsumer(RAW_TOPIC, bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS, group_id="fraud_worker_group")
            producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
            await consumer.start()
            await producer.start()
            print("🚀 Worker Kafka'ya bağlandı.")
            
            async for msg in consumer:
                try:
                    data = json.loads(msg.value.decode('utf-8'))
                    async with pg_pool.acquire() as pg_conn:
                        processed_event, fraud_event = await process_transaction(data, redis_conn, pg_conn)
                    
                    if fraud_event:
                        await producer.send_and_wait(FRAUD_TOPIC, json.dumps(fraud_event).encode('utf-8'))
                        
                    await producer.send_and_wait(PROCESSED_TOPIC, json.dumps(processed_event, default=str).encode("utf-8"))
                except Exception as ex:
                    print(f"Mesaj işleme hatası: {ex}")
        except Exception as e:
            print(f"Worker ana döngü hatası: {e}. 5 saniye sonra tekrar deneniyor...")
            await asyncio.sleep(5)
        finally:
            try:
                if consumer:
                    await consumer.stop()
                if producer:
                    await producer.stop()
            except Exception: 
                pass

if __name__ == "__main__":
    asyncio.run(main())
