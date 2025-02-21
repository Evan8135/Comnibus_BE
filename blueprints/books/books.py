from flask import Blueprint, request, make_response, jsonify, redirect, url_for
from bson import ObjectId
from bson.regex import Regex
from decorators import jwt_required, admin_required
import globals

books_bp = Blueprint("books_bp", __name__)
users = globals.db.users
books = globals.db.books

# BOOK APIS
@books_bp.route("/api/v1.0/books", methods=['GET'])
def show_all_books():
    page_num, page_size = 1, 10
    title_filter = request.args.get('title')
    author_filter = request.args.get('author')
    genre_filter = request.args.get('genres')

    if request.args.get('pn'):
        page_num = int(request.args.get('pn'))
    if request.args.get('ps'):
        page_size = int(request.args.get('ps'))
    page_start = (page_size * (page_num - 1))

    query = {}
    if title_filter:
        query["title"] = {"$regex": Regex(title_filter, 'i')}
    if author_filter:
        query["author"] = {"$regex": Regex(author_filter, 'i')}
    if genre_filter:
        query["genres"] = {"$regex": Regex(genre_filter, 'i')}

    all_book_data = []
    for book in books.find(query).skip(page_start).limit(page_size):
        book['_id'] = str(book['_id'])
        book_info = {
            "_id": book['_id'],
            "title": book['title'],
            "series": book['series'],
            "author": book['author'],
            "user_score": book['user_score'],
            "description": book['description'],
            "user_reviews": book['user_reviews'],
            "language": book['language'],
            "isbn": book['isbn'],
            "genres": book['genres'],
            "characters": book['characters'],
            "triggers": book['triggers'],
            "bookFormat": book['bookFormat'],
            "edition": book['edition'],
            "pages": book['pages'],
            "publisher": book['publisher'],
            "publishDate": book['publishDate'],
            "firstPublishDate": book['firstPublishDate'],
            "awards": book['awards'],
            "coverImg": book['coverImg'],
            "price": book['price']
        }
        for review in book['user_reviews']:
            review['_id'] = str(review['_id'])
        all_book_data.append(book_info)
    return make_response(jsonify(all_book_data), 200)

@books_bp.route("/api/v1.0/books/<string:id>", methods=["GET"])
def show_one_book(id):
    book = books.find_one({'_id': ObjectId(id)})
    if book is None:
        return make_response(jsonify({"error": "Invalid Book ID"}), 404)

    author = book.get('author', None)

    query = {"_id": {"$ne": ObjectId(id)}}
    if author:
        query["author"] = {"$in": author}

    same_author_books = []
    for same_author_book in books.find(query).limit(3):
        same_author_book['_id'] = str(same_author_book['_id'])
        same_author_books.append({
            "_id": same_author_book['_id'],
            "title": same_author_book['title'],
            "author": same_author_book['author'],
            "coverImg": same_author_book['coverImg'],
        })

    book['_id'] = str(book['_id'])
    for review in book['user_reviews']:
        review['_id'] = str(review['_id'])
    response_data = {
        "book": book,
        "same_author_books": same_author_books
    }

    return make_response(jsonify(response_data), 200)

@books_bp.route("/api/v1.0/books/<string:id>", methods=["DELETE"])
@jwt_required
@admin_required
def delete_request(id):
    result = books.delete_one({"_id":ObjectId(id)})
    if result.deleted_count == 1:
        return make_response(jsonify({}), 204)
    else:
        return make_response(jsonify({"error": "Invalid book ID"}), 404)

@books_bp.route("/api/v1.0/recommendations", methods=["GET"])
@jwt_required
def get_recommendations():
    # Get user info from token
    token_data = request.token_data
    username = token_data["username"]

    # Find user and get their preferences
    user = users.find_one({"username": username}, {"password": 0})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    # Get the user's favorite genres and authors
    fav_genres = user.get("favourite_genres", [])
    fav_authors = user.get("favourite_authors", [])

    # Prepare a list to hold recommended books
    recommended_books = []

    # Fetch books based on genres
    genre_query = {}
    if fav_genres:
        genre_query["genres"] = {"$in": fav_genres}

    # Fetch books based on authors
    author_query = {}
    if fav_authors:
        author_query["author"] = {"$in": fav_authors}

    # Query for books based on genres
    if fav_genres:
        genre_books = list(books.find(genre_query, {"_id": 1, "title": 1, "author": 1, "coverImg": 1, "genres": 1}).limit(50))
        recommended_books.extend(genre_books)

    # Query for books based on authors
    if fav_authors:
        author_books = list(books.find(author_query, {"_id": 1, "title": 1, "author": 1, "coverImg": 1, "genres": 1}).limit(15))
        recommended_books.extend(author_books)

    # Ensure no duplicates (if a book is found in both genres and authors)
    recommended_books = list({str(book["_id"]): book for book in recommended_books}.values())

    # Convert ObjectId to string for serialization
    for book in recommended_books:
        book["_id"] = str(book["_id"])

    # Return the recommended books along with user's preferences
    return make_response(jsonify({
        "recommended_books": recommended_books,
        "favorite_genres": fav_genres,
        "favorite_authors": fav_authors
    }), 200)


