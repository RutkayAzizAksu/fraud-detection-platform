#!/bin/bash
DURATION=60
RATE=5
ANOMALY=10

while [ $# -gt 0 ]; do
  case "$1" in
    --duration=*) DURATION="${1#*=}" ;;
    --rate=*) RATE="${1#*=}" ;;
    --anomaly-chance=*) ANOMALY="${1#*=}" ;;
    *) exit 1 ;;
  esac
  shift
done

echo "Running auto-test: $DURATION s, $RATE req/s, $ANOMALY% anomaly"

END=$((SECONDS+$DURATION))
USERS=("user1" "user2" "user3" "user4" "user5")
# Şehirleri worker koordinatları ile eşleştirdim.
LOCATIONS=("Istanbul" "Ankara" "Izmir" "Antalya" "Bursa" "London" "Tokyo" "New York")

while [ $SECONDS -lt $END ]; do
    for ((i=1; i<=RATE; i++)); do
        USER=${USERS[$RANDOM % ${#USERS[@]}]}
        LOC=${LOCATIONS[$RANDOM % ${#LOCATIONS[@]}]}
        
        # Rastgele yüksek tutarlı işlemler (anomali) oluşturdum.
        if [ $((RANDOM % 100)) -lt $ANOMALY ]; then
            AMOUNT=$(( (RANDOM % 5000) + 5000 ))
        else
            AMOUNT=$((RANDOM % 100 + 10))
        fi
        
        curl -s -X POST http://localhost:8080/transaction \
             -H "Content-Type: application/json" \
             -d "{\"user_id\":\"$USER\", \"amount\":$AMOUNT, \"location\":\"$LOC\"}" > /dev/null &
    done
    sleep 1
done
echo "Test tamamlandı."
