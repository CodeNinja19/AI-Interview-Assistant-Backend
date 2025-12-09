from fastapi import FastAPI
from routes.test import app as test_router
from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from routes.authentication import router as auth_router
from ChatBot.llm import get_llm
from ChatBot.agent import get_agent
from langchain_core.messages import HumanMessage
from routes.chat import router as chat_router
from routes.websocketStream import router as websocket_router
import requests
import base64
import os
load_dotenv()
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.mongodb_client = AsyncIOMotorClient(os.getenv("MONGODB_URL"))
    app.database = app.mongodb_client["users"]  
    config = {"configurable": {"thread_id": "1"}}
    app.agent = get_agent()
    yield
    app.mongodb_client.close()

app = FastAPI(lifespan=lifespan)
app.include_router(test_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(websocket_router)
@app.get("/")
def default_route():
    return {"message": "Hello, World!"}