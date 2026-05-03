import os
from sqlalchemy import create_engine, Column, String, Float, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
import datetime
from fastapi import FastAPI
import uvicorn
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent, CallToolRequest

app = FastAPI()
mcp = Server("fraud-mcp")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/fraud_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True)
    amount = Column(Float)
    location = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    is_fraud = Column(Boolean, default=False)
    fraud_reason = Column(String, nullable=True)

@mcp.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_recent_frauds",
            description="Get a list of the most recent fraudulent transactions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of frauds to return (default 10)"}
                }
            }
        ),
        Tool(
            name="check_user_status",
            description="Check the risk status of a specific user based on transaction history.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "The ID of the user"}
                },
                "required": ["user_id"]
            }
        )
    ]

@mcp.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    db = SessionLocal()
    try:
        if name == "get_recent_frauds":
            limit = arguments.get("limit", 10)
            frauds = db.query(Transaction).filter(Transaction.is_fraud == True).order_by(Transaction.timestamp.desc()).limit(limit).all()
            if not frauds:
                return [TextContent(type="text", text="No recent frauds found.")]
            res = "Recent frauds:\n" + "\n".join([f"- [{f.timestamp}] User {f.user_id} amount {f.amount} at {f.location}. Reason: {f.fraud_reason}" for f in frauds])
            return [TextContent(type="text", text=res)]
            
        elif name == "check_user_status":
            user_id = arguments.get("user_id")
            txs = db.query(Transaction).filter(Transaction.user_id == user_id).order_by(Transaction.timestamp.desc()).limit(20).all()
            if not txs:
                return [TextContent(type="text", text=f"No transaction history found for user {user_id}.")]
            fraud_count = sum(1 for tx in txs if tx.is_fraud)
            status = "High Risk" if fraud_count > 0 else "Normal"
            res = f"User Status: {status}\nRecent Transactions:\n" + "\n".join([f"{'[FRAUD]' if t.is_fraud else '[OK]'} amount {t.amount} at {t.location} on {t.timestamp}" for t in txs])
            return [TextContent(type="text", text=res)]
        else:
            raise ValueError(f"Unknown tool: {name}")
    finally:
        db.close()

sse_transport = None

@app.get("/sse")
async def sse_endpoint():
    global sse_transport
    sse_transport = SseServerTransport("/message")
    return await sse_transport.handle_sse()

@app.post("/message")
async def message_endpoint(request):
    if sse_transport:
        await sse_transport.handle_post_message(await request.json())
        return {}
    return {"error": "SSE not initialized"}

async def run_mcp():
    # Tie the server to transport somehow or just run app
    pass

if __name__ == "__main__":
    import asyncio
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080)
