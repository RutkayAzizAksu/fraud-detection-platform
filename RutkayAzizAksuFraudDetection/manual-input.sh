#!/bin/bash

# manual-input.sh
# Usage: ./manual-input.sh <user_id> <amount> <location>

if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <user_id> <amount> <location>"
    echo "Example: $0 user_123 45.50 'New York'"
    exit 1
fi

USER_ID=$1
AMOUNT=$2
LOCATION=$3
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "Sending transaction for User: $USER_ID, Amount: $AMOUNT, Location: $LOCATION..."

curl -X 'POST' \
  'http://localhost:8080/transaction' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_id": "'"$USER_ID"'",
  "amount": '"$AMOUNT"',
  "location": "'"$LOCATION"'",
  "timestamp": "'"$TIMESTAMP"'"
}'
echo "" # Add a new line after curl output
