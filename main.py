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


# @app.get("/index")
# def index(request: Request):
#     return templates.TemplateResponse("index.html", status_code=303)

# @app.get("/index")
# def index(request: Request):
#     stock_filter = request.query_params.get('filter', False)

#     # Fetch stocks from the database
#     if stock_filter == 'new_closing_highs':
#         # Find the highest closing price for each stock
#         pipeline = [
#             {"$group": {
#                 "_id": "$stock_id",
#                 "max_close": {"$max": "$close"},
#                 "date": {"$last": "$date"}
#             }},
#             {"$lookup": {
#                 "from": "stock",
#                 "localField": "_id",
#                 "foreignField": "id",
#                 "as": "stock_details"
#             }},
#             {"$unwind": "$stock_details"},
#             {"$sort": {"stock_details.symbol": 1}}
#         ]
#         rows = list(stock_price_collection.aggregate(pipeline))

#     elif stock_filter == 'new_closing_lows':
#         # Find the lowest closing price for each stock
#         pipeline = [
#             {"$group": {
#                 "_id": "$stock_id",
#                 "min_close": {"$min": "$close"},
#                 "date": {"$last": "$date"}
#             }},
#             {"$lookup": {
#                 "from": "stock",
#                 "localField": "_id",
#                 "foreignField": "id",
#                 "as": "stock_details"
#             }},
#             {"$unwind": "$stock_details"},
#             {"$sort": {"stock_details.symbol": 1}}
#         ]
#         rows = list(stock_price_collection.aggregate(pipeline))

#     else:
#         # Fetch all stocks without filter
#         rows = list(stock_collection.find({}, {"symbol": 1, "name": 1}))

#     # Fetch the latest closing price for each stock
#     latest_prices = stock_price_collection.aggregate([
#         {"$sort": {"date": -1}},
#         {"$group": {
#             "_id": "$stock_id",
#             "close": {"$first": "$close"}
#         }}
#     ])

#     # Map closing prices by symbol
#     closing_values = {}
#     for price in latest_prices:
#         stock = stock_collection.find_one({"id": price["_id"]})
#         if stock:
#             closing_values[stock['symbol']] = price['close']

#     print("closing_values:", closing_values)

#     # Return the template response
#     return templates.TemplateResponse("index.html", {
#         "request": request, 
#         "stocks": rows, 
#         "closing_values": closing_values
#     })

@app.get("/index")
def index(request: Request):
    stock_filter = request.query_params.get('filter', False)

    # ✅ Fetch stocks based on new closing highs
    if stock_filter == 'new_closing_highs':
        pipeline = [
            {"$sort": {"date": -1}},  # Sort by latest date
            {"$group": {
                "_id": "$stock_id",
                "max_close": {"$max": "$close"},
                "latest_date": {"$first": "$date"}
            }},
            {"$lookup": {
                "from": "stock",
                "localField": "_id",
                "foreignField": "id",
                "as": "stock_details"
            }},
            {"$unwind": "$stock_details"},
            {"$project": {
                "symbol": "$stock_details.symbol",
                "name": "$stock_details.name",
                "stock_id": "$_id",
                "max_close": 1,
                "date": "$latest_date"
            }},
            {"$sort": {"symbol": 1}}
        ]
        rows = list(stock_price_collection.aggregate(pipeline))

    # ✅ Fetch stocks based on new closing lows
    elif stock_filter == 'new_closing_lows':
        pipeline = [
            {"$sort": {"date": -1}},  # Sort by latest date
            {"$group": {
                "_id": "$stock_id",
                "min_close": {"$min": "$close"},
                "latest_date": {"$first": "$date"}
            }},
            {"$lookup": {
                "from": "stock",
                "localField": "_id",
                "foreignField": "id",
                "as": "stock_details"
            }},
            {"$unwind": "$stock_details"},
            {"$project": {
                "symbol": "$stock_details.symbol",
                "name": "$stock_details.name",
                "stock_id": "$_id",
                "min_close": 1,
                "date": "$latest_date"
            }},
            {"$sort": {"symbol": 1}}
        ]
        rows = list(stock_price_collection.aggregate(pipeline))

    # ✅ Fetch all stocks without any filter
    else:
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
        stock = stock_collection.find_one({"id": price["_id"]})
        print("stock:", stock)
        if stock:
            closing_values[stock['symbol']] = price['close']

    # ✅ Debugging (Optional)
    print("closing_values:", closing_values)

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