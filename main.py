from fastapi import FastAPI, HTTPException
from pymongo import MongoClient

from models.stock import Stock
from models.user import User
from models.stock_price import StockPrice
from models.stock_holding import StockHolding
from models.transaction import Transaction

from routes.stock_routes import stock_router
from routes.user_routes import user_router

app = FastAPI()

client = MongoClient("mongodb://localhost:27017")
db = client["stock_market"]

# Include Routers
app.include_router(stock_router)
app.include_router(user_router)

