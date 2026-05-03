#!/bin/bash
if [ "$#" -ne 3 ]; then
    echo "Usage: ./manual-input.sh <user_id> <amount> <location>"
    exit 1
fi
curl -X POST http://localhost:8000/api/transactions \
     -H "Content-Type: application/json" \
     -d "{\"user_id\":\"$1\", \"amount\":$2, \"location\":\"$3\"}"
echo ""
