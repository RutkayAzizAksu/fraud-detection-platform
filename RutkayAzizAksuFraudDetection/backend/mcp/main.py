import os
import asyncio
from datetime import datetime, timedelta, timezone

import asyncpg
import uvicorn
from mcp.server.fastmcp import FastMCP

PG_DSN = os.environ.get("PG_DSN", "postgresql://user:password@postgres:5432/fraud_db")


mcp = FastMCP("Fraud System MCP")


pg_pool = None

@mcp.tool()
async def get_recent_frauds() -> str:
    """Son 1 saat içinde yakalanan fraud işlemlerini listeler."""
    global pg_pool
    if not pg_pool:
        return "Veritabanı bağlantısı henüz hazır değil."
        
    async with pg_pool.acquire() as conn:
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        rows = await conn.fetch('''
            SELECT f.id, f.reason, f.risk_score, f.detected_at, t.user_id, t.amount 
            FROM frauds f 
            JOIN transactions t ON f.transaction_id = t.id 
            WHERE f.detected_at >= $1 
            ORDER BY f.detected_at DESC LIMIT 20
        ''', one_hour_ago)
        
        if not rows:
            return "Son 1 saat içinde fraud tespit edilmedi."
            
        res = "Yakın Zamandaki Fraudlar:\n" + "-"*30 + "\n"
        for r in rows:
            res += f"Kullanıcı: {r['user_id']} | Tutar: ${r['amount']} | Risk: {r['risk_score']}\nSebep: {r['reason']}\n" + "-"*15 + "\n"
        return res

@mcp.tool()
async def check_user_status(user_id: str) -> str:
    """Belirli bir kullanıcının risk durumunu ve son işlemlerini kontrol eder."""
    global pg_pool
    if not pg_pool:
        return "Veritabanı bağlantısı henüz hazır değil."
        
    async with pg_pool.acquire() as conn:
        txs = await conn.fetch('''
            SELECT amount, status, timestamp 
            FROM transactions 
            WHERE user_id = $1 
            ORDER BY timestamp DESC LIMIT 10
        ''', user_id)
        frs = await conn.fetch('''
            SELECT f.reason, f.risk_score 
            FROM frauds f 
            JOIN transactions t ON f.transaction_id = t.id 
            WHERE t.user_id = $1
        ''', user_id)
        
        res = f"Kullanıcı Raporu: {user_id}\n\nİşlemler:\n"
        for t in txs:
            res += f"- {t['timestamp']}: ${t['amount']} [{t['status']}]\n"
        
        res += "\nFraud Geçmişi:\n"
        if not frs:
            res += "Temiz kullanıcı."
        else:
            for f in frs:
                res += f"⚠️ Risk: {f['risk_score']} | Sebep: {f['reason']}\n"
        return res

async def main():
    global pg_pool
    
    print("Veritabanı bağlantısı başlatılıyor...")
    while True:
        try:
            pg_pool = await asyncpg.create_pool(PG_DSN)
            print("PostgreSQL bağlantısı başarılı.")
            break
        except Exception as e:
            print(f"PostgreSQL bağlantı hatası: {e}. 5 saniye içinde tekrar denenecek...")
            await asyncio.sleep(5)
            

    config = uvicorn.Config(mcp.sse_app(), host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    
    print("MCP Sunucusu başlatılıyor...")
    await server.serve()
    

    if pg_pool:
        await pg_pool.close()

if __name__ == "__main__":
    asyncio.run(main())
