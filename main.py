import config
from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from pymongo import MongoClient

from models.stock import Stock
from models.user import User
from models.stock_price import StockPrice
from models.stock_holding import StockHolding
from models.transaction import Transaction

from routes.stock_routes import stock_router
from routes.user_routes import user_router
from routes.login_routes import login_router
from routes.signup_routes import signup_router

from fastapi.templating import Jinja2Templates
import requests

app = FastAPI()

# Connect to MongoDB
client = MongoClient("mongodb+srv://dharmikparmarpd:dhp12345@cluster0.v5pxg.mongodb.net/stock_market?retryWrites=true&w=majority&appName=Cluster0")
db = client['stock_market']   
stock_collection = db['stock']
stock_price_collection = db['stock_price']

app.add_middleware(SessionMiddleware, secret_key=config.SPECIAL_KEY)


# Include Routers
app.include_router(stock_router)
app.include_router(user_router)
app.include_router(login_router)
app.include_router(signup_router)

templates = Jinja2Templates(directory="templates")

@app.get("/")
def root():
    return RedirectResponse(url="/login")

@app.get("/index")
def index(request: Request):
    stock_filter = request.query_params.get('filter', False)

    rows = list(stock_collection.find({}, {"symbol": 1, "name": 1}))

    # ✅ Fetch latest closing prices for each stock
    latest_prices = stock_price_collection.aggregate([
        {"$sort": {"date": -1}},
        {"$group": {
            "_id": "$stock_id",
            "close": {"$first": "$close"}
        }}
    ])

    # ✅ Map closing prices to stock symbols
    closing_values = {}
    for price in latest_prices:
        print(price)
        stock = stock_collection.find_one({"symbol": price["_id"]})
        # print(stock)
        if stock:
            closing_values[stock['symbol']] = price['close']

    # ✅ Return the template response
    return templates.TemplateResponse("index.html", {
        "request": request,
        "stocks": rows,
        "closing_values": closing_values
    })


@app.get("/search_stocks")
def search_stocks(query: str = Query("")):
    # Use MongoDB regex to match stocks starting with 'query'
    stocks = stock_collection.find(
        {"symbol": {"$regex": f"^{query}", "$options": "i"}},  # Case-insensitive search
        {"_id": 0, "symbol": 1, "name": 1}  # Return only symbol and name
    ).sort("symbol", 1)

    # Convert MongoDB cursor to a list of dictionaries
    result = list(stocks)
    
    return JSONResponse(result)