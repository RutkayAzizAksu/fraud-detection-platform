#!/usr/bin/env python3
import argparse
import time
import random
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

def send_transaction(user_id, amount, location):
    url = "http://localhost:8080/transaction"
    data = {
        "user_id": user_id,
        "amount": amount,
        "location": location,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    req = urllib.request.Request(
        url, 
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, response.read().decode('utf-8')
    except urllib.error.URLError as e:
        status_code = getattr(e, 'code', 500)
        return status_code, str(e)

def main():
    parser = argparse.ArgumentParser(description="Automated Transaction Generator for Fraud Testing")
    parser.add_argument("--duration", type=int, default=60, help="Duration to run the test in seconds")
    parser.add_argument("--rate", type=float, default=2.0, help="Number of normal transactions per second")
    parser.add_argument("--anomaly-chance", type=float, default=0.1, help="Probability (0.0 to 1.0) of generating an anomalous transaction each tick")
    
    args = parser.parse_args()
    
    start_time = time.time()
    sleep_interval = 1.0 / args.rate if args.rate > 0 else 1.0
    
    locations = ["New York", "London", "Istanbul", "Tokyo", "Berlin", "Paris", "Sydney", "Dubai"]
    normal_users = [f"user_{i}" for i in range(1, 101)]
    
    transactions_sent = 0
    anomalies_sent = 0
    
    print(f"Starting auto-test for {args.duration}s at {args.rate} req/s with {args.anomaly_chance*100}% anomaly chance.")
    print("Press Ctrl+C to stop early.\n")
    
    try:
        while time.time() - start_time < args.duration:
            is_anomaly = random.random() < args.anomaly_chance
            
            if is_anomaly:
                anomaly_type = random.choice(["high_amount", "rapid_succession"])
                user_id = random.choice(normal_users)
                
                if anomaly_type == "high_amount":
                    # Anomaly 1: Unusually high amount
                    amount = round(random.uniform(10000, 50000), 2)
                    loc = random.choice(locations)
                    print(f"[ANOMALY: High Amount] User: {user_id}, Amount: ${amount}, Loc: {loc}")
                    send_transaction(user_id, amount, loc)
                    transactions_sent += 1
                    anomalies_sent += 1
                    
                elif anomaly_type == "rapid_succession":
                    # Anomaly 2: Multiple transactions from different locations very quickly
                    amount = round(random.uniform(10, 100), 2)
                    loc1 = random.choice(locations)
                    loc2 = random.choice([l for l in locations if l != loc1]) 
                    
                    print(f"[ANOMALY: Rapid Succession] User: {user_id}, Amount: ${amount}, Loc1: {loc1}, Loc2: {loc2}")
                    send_transaction(user_id, amount, loc1)
                    time.sleep(0.05) # Simulate very fast successive transaction
                    send_transaction(user_id, amount, loc2)
                    transactions_sent += 2
                    anomalies_sent += 2
            else:
                # Normal transaction
                user_id = random.choice(normal_users)
                amount = round(random.uniform(5, 500), 2)
                loc = random.choice(locations)
                
                status, _ = send_transaction(user_id, amount, loc)
                if status == 200:
                    print(f"[NORMAL] User: {user_id}, Amount: ${amount}, Loc: {loc}")
                else:
                    print(f"[ERROR] Failed to send normal tx: HTTP {status}")
                transactions_sent += 1
                
            time.sleep(sleep_interval)
            
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
        
    print(f"\nTest completed.")
    print(f"Total transactions sent: {transactions_sent}")
    print(f"Anomalous transactions generated: {anomalies_sent}")

if __name__ == "__main__":
    main()
