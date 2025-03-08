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

# Directory Structure
# - app
#   - main.py
#   - models
#     - stock.py
#     - user.py
#     - stock_price.py
#     - stock_holding.py
#     - transaction.py
#   - routes
#     - stock_routes.py
#     - user_routes.py

# Example: models/stock.py
from pydantic import BaseModel

class Stock(BaseModel):
    symbol: str
    name: str
    exchange: str
    shortable: bool

# Example: routes/stock_routes.py
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

# Example: routes/user_routes.py
from fastapi import APIRouter, HTTPException
from models.user import User
from pymongo import MongoClient

user_router = APIRouter()
client = MongoClient("mongodb://localhost:27017")
db = client["stock_market"]

@user_router.post("/users/", response_model=User)
def create_user(user: User):
    if db.users.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    result = db.users.insert_one(user.dict())
    return {"id": str(result.inserted_id), **user.dict()}

@user_router.get("/users/")
def get_users():
    users = list(db.users.find())
    for user in users:
        user["id"] = str(user["_id"])
        del user["_id"]
    return users
