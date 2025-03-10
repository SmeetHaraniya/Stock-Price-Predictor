from datetime import datetime

from bson import ObjectId
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

users_collection = db["user"] 
stock_collection = db['stock']
stock_price_collection = db['stock_price']
stock_holding_collection = db['stock_holding']
transaction_collection = db['transaction']

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

    rows = stock_collection.find({}, {"symbol": 1, "name": 1})
    print(rows)

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
        stock = stock_collection.find_one({"symbol": price["_id"]})
        # print(stock)
        if stock:
            closing_values[stock['symbol']] = price['close']



    # # Apply filter logic for sorting based on closing price
    if stock_filter == 'new_closing_highs':
        # Sort by highest closing price (descending)
        closing_values = sorted(closing_values, key=lambda x: x['close'], reverse=True)

    elif stock_filter == 'new_closing_lows':
        # Sort by lowest closing price (ascending)
        closing_values = sorted(closing_values, key=lambda x: x['close'])


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

@app.get("/stock/{symbol}")
def stock_details(request: Request, symbol: str):
    # Fetch stock details using the symbol
    stock = stock_collection.find_one({"symbol": symbol})

    if stock is None:
        return {"error": "Stock not found"}

    # Fetch stock price history for the given stock_id, sorted by latest date
    prices = list(stock_price_collection.find({"stock_id": stock["symbol"]}).sort("date", -1))

    print(request.session)
    return templates.TemplateResponse("stock_details.html", {
        "request": request,
        "stock": stock,
        "bars": prices,
    })


# @app.get('/buy')
# def buy(request: Request):
    user = request.session.get('user_id')
    print('user:', user)
    return JSONResponse(user)
    

# @app.post("/buy")
# # def buy(request: Request):
# def buy(request: Request, symbol: str = Form(...), quantity: int = Form(...), price: float = Form(...)):
    user_id = request.session.get("user_id")
    print("post:",  request.session)
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    # user = user.to_list()[0]
    print("user",user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # request.body.user_id = user_id
    total_cost = quantity * price
    
    if user["cash"] < total_cost:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    # Deduct cash
    users_collection.update_one({"_id": user_id}, {"$inc": {"cash": -total_cost}})

    # Check existing stock holding
    existing_holding = stock_holding_collection.find_one({"user_id": user_id, "company_symbol": symbol})
    print(existing_holding)
    if existing_holding:
        new_quantity = existing_holding["number_of_shares"] + quantity
        new_avg_price = ((existing_holding["avg_price"] * existing_holding["number_of_shares"]) + total_cost) / new_quantity

        stock_holding_collection.update_one(
            {"_id": existing_holding["_id"]},
            {"$set": {"number_of_shares": new_quantity, "avg_price": new_avg_price}}
        )
    else:
        stock_holding_collection.insert_one({
            "user_id": user_id,
            "company_symbol": symbol,
            "number_of_shares": quantity,
            "avg_price": price
        })

    # Log transaction
    transaction_collection.insert_one({
        "user_id": user_id,
        "action": "BUY",
        "symbol": symbol,
        "quantity": quantity,
        "price": price,
        "timestamp": datetime.now()
    })
    print(-1)
    return {"message": "Stock purchased successfully"}

# @app.get("/portfolio")
# def portfolio(request: Request):
    user_id = request.session["user_id"]
    user = users_collection.find_one({"_id": user_id})
    
    return templates.TemplateResponse("/portfolio", {
        "portfolio": { user, }
    })