from pymongo import MongoClient
import ast

client = MongoClient("mongodb://127.0.0.1:27017")
db = client.comnibusDB
books = db.books

for book in books.find():
    #book["genres"] = ast.literal_eval(book.get("genres", "[]"))
    #book["awards"] = ast.literal_eval(book.get("awards", "[]"))
    #book["characters"] = ast.literal_eval(book.get("characters", "[]"))
    
    author = book.get("author", "")
    if author:
        book["author"] = [a.strip() for a in author.split(',')]  # Split by comma and strip spaces
    else:
        book["author"] = []

    books.update_one({ "_id" : book['_id'] },
                     {
                         "$set": {
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
                         }
                     })
                     