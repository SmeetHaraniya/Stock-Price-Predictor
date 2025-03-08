import pandas as pd
from fastapi import APIRouter
from models.stock_data import StockData
from models.stock import Stock
from pymongo import MongoClient
import os
import joblib

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

@stock_router.post("/predict")
def predict(data: StockData):
    model_path = os.path.join(os.path.dirname(__file__), "..", "ml_model", "stock_prediction_model.pkl")
    model = joblib.load(model_path)
    # Convert input into DataFrame format for model
    df = pd.DataFrame([data.dict()])
    
    # Make prediction
    prediction = model.predict(df)[0]

    return {"prediction": "Up" if prediction == 1 else "Down"}