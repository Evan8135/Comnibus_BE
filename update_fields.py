from datetime import datetime, timedelta
import random
from pymongo import MongoClient
import ast

client = MongoClient("mongodb://127.0.0.1:27017")
db = client.comnibusDB
#books = db.books
users = db.users

def generate_random_date():
    # Random number of days in the past year
    random_days = random.randint(0, 365)
    random_date = datetime.utcnow() - timedelta(days=random_days)
    return random_date

#for book in books.find():
    #book["genres"] = ast.literal_eval(book.get("genres", "[]"))
    #book["awards"] = ast.literal_eval(book.get("awards", "[]"))
    #book["characters"] = ast.literal_eval(book.get("characters", "[]"))
    
    #author = book.get("author", "")
    #if author:
    #    book["author"] = [a.strip() for a in author.split(',')]  # Split by comma and strip spaces
    #else:
    #    book["author"] = []

    #books.update_one({ "_id" : book['_id'] },
    #                 {
    #                     "$set": {
                         #    "user_score": 0,
                         #    "user_reviews": [],
                         #    "triggers": []
                         #    "genres": book["genres"],
                         #    "awards": book["awards"],
                         #    "characters": book["characters"]
                         #    "author": book["author"]
                         #},
                         #"$unset": {
                         #    "rating": ""
    #                     }
    #                 })

for user in users.find():
    random_creation_date = generate_random_date()
    users.update_one({"_id": user['_id']},
                     {
                         "$set": {
                             #"favourite_genres": [],
                             #"favourite_authors": [],
                             #"favourite_books": [],
                             #"followers": [],
                             #"following": []
                             #"pronouns": ""
                             "created_at": random_creation_date
                             #"have_read": [],
                             #"want_to_read": [],
                             #"currently_reading": [],
                             #"user_type": "",
                             #"profile_pic": ""                        
                             }
                     })    