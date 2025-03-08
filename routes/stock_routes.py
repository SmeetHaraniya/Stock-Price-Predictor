from fastapi import APIRouter
from models.stock import Stock
from pymongo import MongoClient

stock_router = APIRouter()
client = MongoClient("mongodb://localhost:27017")
db = client["stock_market"]

@stock_router.post("/stocks/", response_model=Stock)
def create_stock(stock: Stock):
    result = db.stocks.insert_one(stock.dict())
    return {"id": str(result.inserted_id), **stock.dict()}

@stock_router.get("/stocks/")
def get_stocks():
    stocks = list(db.stocks.find())
    for stock in stocks:
        stock["id"] = str(stock["_id"])
        del stock["_id"]
    return stocks
