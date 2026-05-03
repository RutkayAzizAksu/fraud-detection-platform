import pika
import json
import os
import time
import redis
from datetime import datetime, timedelta
from . import database
from sqlalchemy.orm import sessionmaker

import math

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://user:password@localhost:5672/")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/fraud_db")

redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
engine = database.create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

CITY_COORDS = {
    "Istanbul": (41.0082, 28.9784),
    "Ankara": (39.9334, 32.8597),
    "Izmir": (38.4237, 27.1428),
    "Antalya": (36.8969, 30.7133),
    "Bursa": (40.1828, 29.0667)
}

def haversine(coord1, coord2):
    R = 6371 # Earth radius in km
    lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
    lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def check_anomaly(tx_data):
    user_id = tx_data['user_id']
    amount = float(tx_data['amount'])
    tx_id = tx_data['id']
    now = time.time()
    
    is_fraud = False
    reasons = []

    # 1. Velocity Check (5 transactions in 1 minute)
    velocity_key = f"velocity:{user_id}"
    redis_client.zadd(velocity_key, {tx_id: now})
    # Remove transactions older than 60 seconds
    redis_client.zremrangebyscore(velocity_key, 0, now - 60)
    tx_count = redis_client.zcard(velocity_key)
    
    if tx_count > 5:
        reasons.append(f"Velocity exceeded: {tx_count} txs in 1 min")

    # 2. Amount Check (3x the average of last 24h)
    # 3. Impossible Travel Check (Location)
    loc_key = f"location:{user_id}"
    last_loc_data = redis_client.get(loc_key)
    current_location = tx_data['location']
    
    if last_loc_data and current_location in CITY_COORDS:
        last_loc = json.loads(last_loc_data)
        if last_loc['city'] != current_location and last_loc['city'] in CITY_COORDS:
            time_diff_hours = (now - last_loc['timestamp']) / 3600.0
            if time_diff_hours > 0: # Avoid division by zero
                distance_km = haversine(CITY_COORDS[last_loc['city']], CITY_COORDS[current_location])
                speed_kmh = distance_km / time_diff_hours
                
                # If speed > 1000 km/h (faster than commercial plane) -> IMPOSSIBLE TRAVEL
                if speed_kmh > 1000:
                    reasons.append(f"Impossible Travel: {last_loc['city']} to {current_location} in {time_diff_hours*60:.1f} mins ({speed_kmh:.0f} km/h)")
    
    # Update last location
    redis_client.set(loc_key, json.dumps({"city": current_location, "timestamp": now}))

    db = SessionLocal()
    try:
        one_day_ago = datetime.utcnow() - timedelta(days=1)
        from sqlalchemy.sql import func
        avg_amount = db.query(func.avg(database.Transaction.amount)).filter(
            database.Transaction.user_id == user_id,
            database.Transaction.timestamp >= one_day_ago,
            database.Transaction.is_fraud == False
        ).scalar()
        
        if avg_amount and amount > (avg_amount * 3):
            reasons.append(f"Amount {amount} is > 3x average ({avg_amount:.2f})")

        # REQUIRE AT LEAST 2 RULES BROKEN FOR ANOMALY
        is_fraud = len(reasons) >= 2
            
        new_tx = database.Transaction(
            id=tx_id,
            user_id=user_id,
            amount=amount,
            location=tx_data['location'],
            timestamp=datetime.fromisoformat(tx_data['timestamp']),
            is_fraud=is_fraud,
            fraud_reason=", ".join(reasons) if reasons else None
        )
        db.add(new_tx)
        db.commit()
    finally:
        db.close()

    return is_fraud, reasons

def callback(ch, method, properties, body):
    data = json.loads(body)
    print(f"Processing transaction: {data['id']}")
    try:
        is_fraud, reasons = check_anomaly(data)
        
        data['is_fraud'] = is_fraud
        data['fraud_reason'] = ", ".join(reasons)
        
        redis_client.publish("new_transactions", json.dumps(data))
        if is_fraud:
            redis_client.publish("fraud_alerts", json.dumps(data))
            
    except Exception as e:
        print(f"Error processing {data['id']}: {e}")

def main():
    database.Base.metadata.create_all(bind=engine)
    
    for i in range(20):
        try:
            params = pika.URLParameters(RABBITMQ_URL)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue='transactions')
            channel.basic_consume(queue='transactions', on_message_callback=callback, auto_ack=True)
            print('Worker is waiting for messages. To exit press CTRL+C')
            channel.start_consuming()
            break
        except Exception as e:
            print(f"RabbitMQ not ready, waiting... ({e})")
            time.sleep(5)

if __name__ == '__main__':
    main()
