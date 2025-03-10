from datetime import datetime
import asyncio
import yfinance as yf

from bson import ObjectId
from fastapi.staticfiles import StaticFiles
import config
from fastapi import FastAPI, WebSocket, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from pymongo import MongoClient

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

app.mount("/static", StaticFiles(directory="static"), name="static")


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
    print('Index:', request.session.get('user_id'))
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

    for price in prices:
        if "_id" in price:
            price["_id"] = str(price["_id"])
    print(type(prices[0]))
    return templates.TemplateResponse("stock_details.html", {
        "request": request,
        "stock": stock,
        "bars": prices,
    })


@app.get("/trade_stocks")
def trade_stocks(request:Request):
    return templates.TemplateResponse("trade_stocks.html",{"request":request})
    
@app.get("/get-stock-price/{symbol}")
def get_stock_price(request: Request, symbol:str):
    # Find the stock ID based on the symbol
    stock = stock_collection.find_one({"symbol": symbol.upper()})
    print(stock)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock symbol not found")
    
    # Get the latest stock price based on the stock ID
    stock_price = stock_price_collection.find(
        {"stock_id": stock["symbol"]}, 
        sort=[("date", -1)]  # Sort by date DESCENDING to get the latest price
    )

    latest_price = next(stock_price, None)
    print(latest_price)
    if not stock_price:
        raise HTTPException(status_code=404, detail="Stock price not available")
    

    # Return the latest stock price
    return {"price": round(latest_price['close'], 2) }

@app.post("/buy")
def buy(request: Request, symbol: str = Form(...), quantity: int = Form(...), price: float = Form(...)):
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
    users_collection.update_one({"_id": ObjectId(user_id)}, {"$inc": {"cash": -total_cost}})

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
        "timestamp": datetime.now(),
        "profit_loss": "-"
    })
    print(-1)
    return {"message": "Stock purchased successfully"}

@app.post("/sell")
def sell(request: Request, symbol: str = Form(...), quantity: int = Form(...), price: float = Form(...)):
    user_id = request.session.get("user_id")
    print("post:", request.session)
    
    # Fetch the user from the database
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check for existing stock holdings
    existing_holding = stock_holding_collection.find_one({"user_id": user_id, "company_symbol": symbol})
    if not existing_holding:
        raise HTTPException(status_code=400, detail="You do not own any shares of this stock")

    # Ensure the user has enough shares to sell
    if existing_holding["number_of_shares"] < quantity:
        raise HTTPException(status_code=400, detail="Insufficient shares to sell")

    # Calculate the total revenue from the sale
    total_revenue = quantity * price

     # Calculate the profit or loss for the transaction
    avg_price = existing_holding["avg_price"]
    profit_loss = (price - avg_price) * quantity  # Profit if positive, loss if negative

    # Add the revenue to the user's cash balance
    users_collection.update_one({"_id": ObjectId(user_id)}, {"$inc": {"cash": total_revenue}})

    # Update the stock holding after selling
    new_quantity = existing_holding["number_of_shares"] - quantity

    if new_quantity > 0:
        # If the user still has shares left, update the holding
        stock_holding_collection.update_one(
            {"_id": existing_holding["_id"]},
            {"$set": {"number_of_shares": new_quantity}}
        )
    else:
        # If no shares are left, remove the holding
        stock_holding_collection.delete_one({"_id": existing_holding["_id"]})

    # Log the transaction
    transaction_collection.insert_one({
        "user_id": user_id,
        "action": "SELL",
        "symbol": symbol,
        "quantity": quantity,
        "price": price,
        "timestamp": datetime.now(),
        "profit_loss": str(profit_loss)
    })

    return {"message": "Stock sold successfully"}

@app.get("/portfolio")
def portfolio(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Fetch user details
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Fetch stock holdings for the user
    stock_holdings = stock_holding_collection.find({"user_id": user_id})
    portfolio_stocks = {}
    for holding in stock_holdings:
        symbol = holding["company_symbol"]
        portfolio_stocks[symbol] = {
            "quantity": holding["number_of_shares"],
            "avg_price": holding["avg_price"]
        }

    # Fetch transaction history for the user
    transaction_history = transaction_collection.find({"user_id": user_id}).sort("timestamp", -1)

    portfolio_data = {
        "funds": user.get("cash", 0),  # User's available cash
        "stocks": portfolio_stocks,
        "history": [
            {
                "action": transaction["action"],
                "stock": transaction["symbol"],
                "quantity": transaction["quantity"],
                "price": transaction["price"]
            }
            for transaction in transaction_history
        ]
    }

    return templates.TemplateResponse("portfolio.html", {"request": request, "portfolio": portfolio_data})
    
@app.route("/transaction-history", methods=["GET"])
def stock_transaction_history(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Fetch user details
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Fetch transaction history for the user
    transaction_history = transaction_collection.find({"user_id": user_id}).sort("timestamp", -1)

    portfolio_data = {
        "history": [
            {
                "timestamp": transaction["timestamp"],
                "action": transaction["action"],
                "stock": transaction["symbol"],
                "quantity": transaction["quantity"],
                "price": transaction["price"],
                "profit_loss": transaction["profit_loss"]
            }
            for transaction in transaction_history
        ]
    }

    return templates.TemplateResponse("transaction_history.html", {"request": request, "portfolio": portfolio_data})
    

@app.route("/profit_loss_chart")
def profit_loss_chart_data(request: Request):
    user_id = request.session.get("user_id")

    # Fetch all SELL transactions with profit/loss from MongoDB
    # transactions = transaction_collection.find(
    #     {"user_id": user_id, "action": "SELL"},
    #     {"timestamp": 1, "profit_loss": 1}  # Only select timestamp and profit_loss
    # ).sort("timestamp", 1)  # Sort by timestamp in ascending order

    # Ensure at least 5 dummy data points if no transactions are found
    # if not transactions or len(transactions) < 5:
        # transactions = [
        #     {"timestamp": "2025-02-27", "profit_loss": 100},
        #     {"timestamp": "2025-02-28", "profit_loss": -50},
        #     {"timestamp": "2025-02-29", "profit_loss": 75},
        #     {"timestamp": "2025-03-01", "profit_loss": -20},
        #     {"timestamp": "2025-03-02", "profit_loss": 120},
        #     {"timestamp": "2025-04-27", "profit_loss": 150},
        #     {"timestamp": "2025-04-28", "profit_loss": 110},
        #     {"timestamp": "2025-04-29", "profit_loss": 75},
        #     {"timestamp": "2025-04-01", "profit_loss": -20},
        #     {"timestamp": "2025-04-02", "profit_loss": -10},
        #     {"timestamp": "2025-04-27", "profit_loss": 5},
        #     {"timestamp": "2025-05-28", "profit_loss": 0},
        #     {"timestamp": "2025-05-29", "profit_loss": 15},
        #     {"timestamp": "2025-05-01", "profit_loss": -50},
        #     {"timestamp": "2025-05-02", "profit_loss": 10},
        #     {"timestamp": "2025-06-27", "profit_loss": 30},
        #     {"timestamp": "2025-06-28", "profit_loss": 60},
        #     {"timestamp": "2025-06-29", "profit_loss": 75},
        #     {"timestamp": "2025-06-01", "profit_loss": 40},
        #     {"timestamp": "2025-06-02", "profit_loss": 120},
        #     {"timestamp": "2025-07-27", "profit_loss": 100},
        #     {"timestamp": "2025-07-28", "profit_loss": -50},
        #     {"timestamp": "2025-07-29", "profit_loss": 75},
        #     {"timestamp": "2025-07-01", "profit_loss": -20},
        #     {"timestamp": "2025-07-02", "profit_loss": 120}
        # ]

    transactions = [
            {"timestamp": "2025-02-27", "profit_loss": 100},
            {"timestamp": "2025-02-28", "profit_loss": -50},
            {"timestamp": "2025-02-29", "profit_loss": 75},
            {"timestamp": "2025-03-01", "profit_loss": -20},
            {"timestamp": "2025-03-02", "profit_loss": 120},
            {"timestamp": "2025-04-27", "profit_loss": 150},
            {"timestamp": "2025-04-28", "profit_loss": 110},
            {"timestamp": "2025-04-29", "profit_loss": 75},
            {"timestamp": "2025-04-01", "profit_loss": -20},
            {"timestamp": "2025-04-02", "profit_loss": -10},
            {"timestamp": "2025-04-27", "profit_loss": 5},
            {"timestamp": "2025-05-28", "profit_loss": 0},
            {"timestamp": "2025-05-29", "profit_loss": 15},
            {"timestamp": "2025-05-01", "profit_loss": -50},
            {"timestamp": "2025-05-02", "profit_loss": 10},
            {"timestamp": "2025-06-27", "profit_loss": 30},
            {"timestamp": "2025-06-28", "profit_loss": 60},
            {"timestamp": "2025-06-29", "profit_loss": 75},
            {"timestamp": "2025-06-01", "profit_loss": 40},
            {"timestamp": "2025-06-02", "profit_loss": 120},
            {"timestamp": "2025-07-27", "profit_loss": 100},
            {"timestamp": "2025-07-28", "profit_loss": -50},
            {"timestamp": "2025-07-29", "profit_loss": 75},
            {"timestamp": "2025-07-01", "profit_loss": -20},
            {"timestamp": "2025-07-02", "profit_loss": 120}
        ]

    # Convert to JSON format for charting
    chart_data = {
        "timestamps": [str(t["timestamp"]) for t in transactions],
        "profit_losses": [t["profit_loss"] for t in transactions]
    }

    # Close the MongoDB connection
    client.close()

    return JSONResponse(content=chart_data)

# async def fetch_stock_price(symbols):
#     stock = yf.Ticker(symbols)
#     return stock.history(period="1d", interval="1m")["Close"].iloc[-1]

# @app.websocket("/ws/stocks/")
# async def stock_price_ws(websocket: WebSocket):
#     await websocket.accept()
#     while True:
#         symbols = ["AAPL", "AMZN", "MSFT", "META", "TSLA"]
#         latest_price = await fetch_stock_price()
#         await websocket.send_json({"symbols": symbols, "price": latest_price})
#         await asyncio.sleep(5)  # Fetch every 5 seconds
