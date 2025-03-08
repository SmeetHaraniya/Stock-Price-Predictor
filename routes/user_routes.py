from fastapi import APIRouter, HTTPException
from models.user import User
from pymongo import MongoClient

user_router = APIRouter()
client = MongoClient("mongodb+srv://dharmikparmarpd:dhp12345@cluster0.v5pxg.mongodb.net/stock_market?retryWrites=true&w=majority&appName=Cluster0")
db = client["stock_market"]

@user_router.post("/users/", response_model=User)
def create_user(user: User):
    if db.user.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    result = db.user.insert_one(user.dict())
    return {"id": str(result.inserted_id), **user.dict()}

@user_router.get("/users/")
def get_users():
    users = list(db.user.find())
    for user in users:
        user["id"] = str(user["_id"])
        del user["_id"]
    return users
