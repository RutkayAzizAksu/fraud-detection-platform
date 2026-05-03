import os
import json
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Set

import redis.asyncio as aioredis
import asyncpg
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="Fraud Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "raw-transactions")
PROCESSED_TOPIC = "processed-transactions"
PG_DSN = os.environ.get("PG_DSN", "postgresql://user:password@postgres:5432/fraud_db")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379")

PG_POOL = None
producer = None
redis_client = None

class SSEManager:
    def __init__(self):
        self._clients: Set[asyncio.Queue] = set()

    async def connect(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._clients.add(q)
        return q

    def disconnect(self, q: asyncio.Queue) -> None:
        self._clients.discard(q)

    async def broadcast(self, data: dict) -> None:
        payload = json.dumps(data, default=str)
        for q in list(self._clients):
            try:
                q.put_nowait(payload)
            except Exception:
                self._clients.discard(q)

sse_manager = SSEManager()

async def kafka_sse_consumer():
    await asyncio.sleep(5)
    while True:
        try:
            consumer = AIOKafkaConsumer(
                PROCESSED_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id="api_sse_group"
            )
            await consumer.start()
            try:
                async for msg in consumer:
                    data = json.loads(msg.value.decode("utf-8"))
                    await sse_manager.broadcast(data)
            finally:
                await consumer.stop()
        except Exception as e:
            print(f"SSE Consumer hatası: {e}. 5 saniye içinde tekrar deniyorum...")
            await asyncio.sleep(5)

class Transaction(BaseModel):
    user_id: str
    amount: float
    location: str

@app.on_event("startup")
async def startup():
    global PG_POOL, producer, redis_client
    
    try:
        PG_POOL = await asyncpg.create_pool(PG_DSN)
        redis_client = await aioredis.from_url(REDIS_URL)
    except Exception as e:
        print(f"DB/Redis connection failed: {e}")

    connected = False
    while not connected:
        try:
            producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
            await producer.start()
            connected = True
            print("API Kafka Producer started.")
        except Exception as e:
            print(f"Kafka bağlantı hatası: {e}. Tekrar deniyorum...")
            await asyncio.sleep(3)

    asyncio.create_task(kafka_sse_consumer())

@app.on_event("shutdown")
async def shutdown():
    global PG_POOL, producer
    if producer:
        await producer.stop()
    if PG_POOL:
        await PG_POOL.close()

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "Fraud Detection API",
        "endpoints": {
            "dashboard": "/dashboard",
            "events": "/events",
            "swagger": "/docs"
        }
    }

@app.post("/transaction")
async def create_transaction(transaction: Transaction):
    try:
        tx_data = transaction.model_dump() if hasattr(transaction, 'model_dump') else transaction.dict()
        tx_data["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        if producer:
            await producer.send_and_wait(KAFKA_TOPIC, json.dumps(tx_data).encode("utf-8"))
        else:
            raise HTTPException(status_code=500, detail="Kafka producer is not available")
            
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/events")
async def sse_events(request: Request):
    queue = await sse_manager.connect()
    async def event_generator():
        yield 'data: {"type":"connected"}\n\n'
        try:
            while True:
                if await request.is_disconnected():
                    break
                payload = await asyncio.wait_for(queue.get(), timeout=20.0)
                yield f"data: {payload}\n\n"
        except asyncio.TimeoutError:
            yield ": heartbeat\n\n"
        finally:
            sse_manager.disconnect(queue)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/dashboard")
async def get_dashboard():
    if not PG_POOL:
        raise HTTPException(status_code=500, detail="Database pool not initialized")
    async with PG_POOL.acquire() as conn:
        transactions = await conn.fetch('''
            SELECT id, user_id, amount, status, timestamp, location 
            FROM transactions 
            ORDER BY timestamp DESC LIMIT 50
        ''')
        stats_rows = await conn.fetch('''
            SELECT date_trunc('minute', timestamp) AS minute, 
                   COUNT(CASE WHEN status = 'APPROVED' THEN 1 END) AS approved, 
                   COUNT(CASE WHEN status = 'REJECTED' THEN 1 END) AS rejected 
            FROM transactions 
            WHERE timestamp >= NOW() - INTERVAL '1 hour'
            GROUP BY minute 
            ORDER BY minute ASC
        ''')
        
        return {
            "transactions": [dict(t) for t in transactions],
            "stats": [
                {
                    "time": r["minute"].strftime("%H:%M"), 
                    "approved": r["approved"], 
                    "rejected": r["rejected"]
                } for r in stats_rows
            ]
        }

@app.get("/users/{user_id}")
async def get_user_details(user_id: str):
    if not PG_POOL:
        raise HTTPException(status_code=500, detail="Database pool not initialized")
    async with PG_POOL.acquire() as conn:
        transactions = await conn.fetch('''
            SELECT amount, status, timestamp, location 
            FROM transactions 
            WHERE user_id = $1 
            ORDER BY timestamp DESC LIMIT 10
        ''', user_id)
        frauds = await conn.fetch('''
            SELECT f.reason, f.risk_score, f.detected_at 
            FROM frauds f 
            JOIN transactions t ON f.transaction_id = t.id 
            WHERE t.user_id = $1 
            ORDER BY f.detected_at DESC
        ''', user_id)
        return {
            "transactions": [dict(t) for t in transactions], 
            "frauds": [dict(f) for f in frauds]
        }
