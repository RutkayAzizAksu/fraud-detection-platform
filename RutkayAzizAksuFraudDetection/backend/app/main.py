from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import asyncio
from sqlalchemy.orm import Session
from pydantic import BaseModel
import pika
import json
import uuid
import os
import redis.asyncio as aioredis
from datetime import datetime
from . import database

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = aioredis.from_url(redis_url)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://user:password@localhost:5672/")

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

class TransactionCreate(BaseModel):
    user_id: str
    amount: float
    location: str

@app.post("/api/transactions")
def create_transaction(tx: TransactionCreate):
    tx_id = str(uuid.uuid4())
    payload = {
        "id": tx_id,
        "user_id": tx.user_id,
        "amount": tx.amount,
        "location": tx.location,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    try:
        params = pika.URLParameters(RABBITMQ_URL)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue='transactions')
        channel.basic_publish(exchange='', routing_key='transactions', body=json.dumps(payload))
        connection.close()
    except Exception as e:
        print(f"Failed to publish to queue: {e}")
        raise HTTPException(status_code=500, detail="Message queue error")

    return {"status": "queued", "transaction_id": tx_id}

@app.get("/api/transactions/{user_id}")
def get_user_transactions(user_id: str, db: Session = Depends(get_db)):
    txs = db.query(database.Transaction).filter(database.Transaction.user_id == user_id).order_by(database.Transaction.timestamp.desc()).all()
    return txs

@app.get("/api/frauds")
def get_recent_frauds(db: Session = Depends(get_db)):
    frauds = db.query(database.Transaction).filter(database.Transaction.is_fraud == True).order_by(database.Transaction.timestamp.desc()).limit(50).all()
    return frauds

@app.get("/api/stream")
async def message_stream(request: Request):
    async def event_generator():
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("fraud_alerts", "new_transactions")
        try:
            while True:
                if await request.is_disconnected():
                    break
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    channel = message['channel'].decode('utf-8')
                    data = message['data'].decode('utf-8')
                    yield {"event": channel, "data": data}
                await asyncio.sleep(0.1)
        finally:
            await pubsub.unsubscribe("fraud_alerts", "new_transactions")
            await pubsub.close()
            
    return EventSourceResponse(event_generator())
