import os
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables from .env
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")

if not MONGODB_URI:
    raise ValueError("Please define the MONGODB_URI environment variable.")

# Global cache to reuse connection
cached_client = None

def connect_to_database():
    global cached_client

    if cached_client:
        return cached_client

    try:
        client = MongoClient(MONGODB_URI)
        cached_client = client
        print("MongoDB connected successfully!")
        return client
    except Exception as e:
        print("MongoDB connection failed:", e)
        raise
