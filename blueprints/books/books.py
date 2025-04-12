from flask import Blueprint, request, make_response, jsonify, redirect, url_for
from bson import ObjectId
from bson.regex import Regex
from datetime import datetime
from blueprints.messages.messages import send_message
from decorators import jwt_required, admin_required, author_required
from aggregation import user_progress_aggregation
import globals

books_bp = Blueprint("books_bp", __name__)
users = globals.db.users
books = globals.db.books

# BOOK APIS
#------------------------------------------------------------------------------------------------------------------
# 1. BASIC CRUD FEATURES
@books_bp.route("/api/v1.0/books", methods=['GET'])
def show_all_books():
    page_num, page_size = 1, 10
    title_filter = request.args.get('title')
    author_filter = request.args.get('author')
    genre_filter = request.args.get('genres')
    character_filter = request.args.get('characters')

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
    if character_filter:
        query["characters"] = {"$regex": Regex(character_filter, 'i')}

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
            for reply in review['replies']:
                reply['_id'] = str(reply['_id'])

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
        for reply in review['replies']:
                reply['_id'] = str(reply['_id'])
    response_data = {
        "book": book,
        "same_author_books": same_author_books
    }

    return make_response(jsonify(response_data), 200)

@books_bp.route("/api/v1.0/add-book", methods=["POST"])
@jwt_required
@author_required
@admin_required
def add_book():
    token_data = request.token_data
    name = token_data['name']
    followers = token_data['followers']
    def parse_comma_separated(value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value if isinstance(value, list) else []

    title = request.form.get("title")
    series = request.form.get("series", "")
    author = request.form.get("author")
    description = request.form.get("description")
    language = request.form.get("language")
    isbn = int(request.form.get("isbn"))
    genres = request.form.get("genres")
    characters = request.form.get("characters")
    triggers = request.form.get("triggers")
    book_format = request.form.get("bookFormat")
    edition = request.form.get("edition", "")
    pages = int(request.form.get("pages", 0))
    publisher = request.form.get("publisher", "")
    publish_date = request.form.get("publishDate")
    first_publish_date = request.form.get("firstPublishDate")
    awards = request.form.get("awards")
    cover_img = request.form.get("coverImg")
    price = float(request.form.get("price", 0.0))

    if not title or not author:
        return make_response(jsonify({"error": "Title and Author are required fields"}), 400)

    genres_list = parse_comma_separated(genres)
    author_list = parse_comma_separated(author)
    characters_list = parse_comma_separated(characters)
    triggers_list = parse_comma_separated(triggers)
    award_list = parse_comma_separated(awards)

    def extract_year(date_str):
        if date_str:
            try:
                return int(date_str[:4])
            except ValueError:
                return None 
        return None

    publish_year = extract_year(publish_date)
    first_publish_year = extract_year(first_publish_date)

    book_data = {
        "title": title,
        "series": series,
        "author": author_list,
        "user_score": 0,
        "user_reviews": [],
        "description": description,
        "language": language,
        "isbn": isbn,
        "genres": genres_list,
        "characters": characters_list,
        "triggers": triggers_list,
        "bookFormat": book_format,
        "edition": edition,
        "pages": pages,
        "publisher": publisher,
        "publishDate": int(publish_year),
        "firstPublishDate": int(first_publish_year),
        "awards": award_list,
        "coverImg": cover_img,
        "price": price
    }

    inserted_book = books.insert_one(book_data)

    for author_name in author_list:
        if name == author_name:
            for follower in followers:
                send_message(
                    recipient_name=follower['username'],
                    content=f"{name}, published a new book called {title}"
                )
    
    return make_response(jsonify({"message": "Book added successfully", "book_id": str(inserted_book.inserted_id)}), 201)




@books_bp.route("/api/v1.0/books/<string:id>", methods=["PUT"])
@jwt_required
@author_required
@admin_required
def edit_book(id):
    token_data = request.token_data
    name = token_data['name']
    admin = token_data.get('admin', False)
    
    book = books.find_one({'_id': ObjectId(id)})
    if not book:
        return make_response(jsonify({"error": "Book not found"}), 404)
    
    author_name = book.get("author")
    
    if not admin and author_name != name:
        return make_response(jsonify({"error": "Unauthorized to delete this thought"}), 403)
    
    data = request.get_json()
    updates = {}
    
    if "title" in data:
        updates["title"] = data["title"]
    if "series" in data:
        updates["series"] = data["series"]
    if "description" in data:
        updates["description"] = data["description"]
    if "language" in data:
        updates["language"] = data["language"]
    if "isbn" in data:
        updates["isbn"] = data["isbn"]
    if "genres" in data:
        updates["genres"] = data["genres"]
    if "characters" in data:
        updates["characters"] = data["characters"]
    if "triggers" in data:
        updates["triggers"] = data["triggers"]
    if "bookFormat" in data:
        updates["bookFormat"] = data["bookFormat"]
    if "edition" in data:
        updates["edition"] = data["edition"]
    if "pages" in data:
        updates["pages"] = int(data["pages"])
    if "publisher" in data:
        updates["publisher"] = data["publisher"]
    if "publishDate" in data:
        updates["publishDate"] = int(data["publishDate"])
    if "firstPublishDate" in data:
        updates["firstPublishDate"] = int(data["firstPublishDate"])
    if "awards" in data:
        updates["awards"] = data["awards"]
    if "coverImg" in data:
        updates["coverImg"] = data["coverImg"]
    if "price" in data:
        updates["price"] = float(data["price"])
    
    books.update_one({"_id": ObjectId(id)}, {"$set": updates})
    
    return make_response(jsonify({"message": "Book updated successfully"}), 200)

@books_bp.route("/api/v1.0/books/<string:id>", methods=["DELETE"])
@jwt_required
@admin_required
@author_required
def delete_books(id):
    token_data = request.token_data
    admin = token_data.get('admin', False)
    name = token_data.get('name')

    book = books.find_one(
        {"_id": ObjectId(id)}
    )

    if not book:
        return make_response(jsonify({"error": "Book not found"}), 404)

    author_name = book.get("author")

    if not admin and author_name != name:
        return make_response(jsonify({"error": "Unauthorized to delete this thought"}), 403)

    result = books.delete_one({"_id":ObjectId(id)})

    if result.deleted_count == 1:
        return make_response(jsonify({}), 204)
    else:
        return make_response(jsonify({"error": "Invalid request ID"}), 404)


#------------------------------------------------------------------------------------------------------------------
# 3. RECOMMENDATION ALGORITHM
@books_bp.route("/api/v1.0/recommendations", methods=["GET"])
@jwt_required
def get_recommendations():
    token_data = request.token_data
    username = token_data["username"]

    user = users.find_one({"username": username}, {"password": 0})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    fav_genres = user.get("favourite_genres", [])
    fav_authors = user.get("favourite_authors", [])

    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 10))
    skip = (page - 1) * page_size

    recommended_books = []

    genre_query = {}
    if fav_genres:
        genre_query["genres"] = {"$in": fav_genres}

    author_query = {}
    if fav_authors:
        author_query["author"] = {"$in": fav_authors}

    if fav_genres:
        genre_books = list(books.find(genre_query, {"_id": 1, "title": 1, "author": 1, "coverImg": 1, "genres": 1}).limit(100))
        recommended_books.extend(genre_books)

    if fav_authors:
        author_books = list(books.find(author_query, {"_id": 1, "title": 1, "author": 1, "coverImg": 1, "genres": 1}).limit(50))
        recommended_books.extend(author_books)

    rated_books = user.get("have_read", [])
    for rated_book in rated_books:
        if rated_book["stars"] > 3.5: 
            same_author_books = list(books.find({
                "author": {"$in": [rated_book["author"]]},
                "_id": {"$ne": ObjectId(rated_book["_id"])}
            }))

            for book in same_author_books:
                recommended_books.append({
                    "_id": str(book["_id"]),
                    "title": book["title"],
                    "author": book["author"],
                    "coverImg": book["coverImg"],
                    "genres": book["genres"]
                })


    recommended_books = list({str(book["_id"]): book for book in recommended_books}.values())

    for book in recommended_books:
        book["_id"] = str(book["_id"])

    return make_response(jsonify({
        "recommended_books": recommended_books,
        "favorite_genres": fav_genres,
        "favorite_authors": fav_authors,
        "have_read": rated_books
    }), 200)


#------------------------------------------------------------------------------------------------------------------
# 4. TOP RATED BOOKS
@books_bp.route("/api/v1.0/top-books", methods=['GET'])
def show_high_rated_books():
    page_num, page_size = 1, 10
    title_filter = request.args.get('title')
    author_filter = request.args.get('author')
    genre_filter = request.args.get('genres')
    character_filter = request.args.get('characters')

    if request.args.get('pn'):
        page_num = int(request.args.get('pn'))
    if request.args.get('ps'):
        page_size = int(request.args.get('ps'))
    page_start = (page_size * (page_num - 1))

    query = {"user_score": {"$gt": 3.5}}  # Filter for user_score greater than 3.5
    if title_filter:
        query["title"] = {"$regex": Regex(title_filter, 'i')}
    if author_filter:
        query["author"] = {"$regex": Regex(author_filter, 'i')}
    if genre_filter:
        query["genres"] = {"$regex": Regex(genre_filter, 'i')}
    if character_filter:
        query["characters"] = {"$regex": Regex(character_filter, 'i')}

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
            for reply in review['replies']:
                reply['_id'] = str(reply['_id'])
        all_book_data.append(book_info)
    return make_response(jsonify(all_book_data), 200)

@books_bp.route("/api/v1.0/new-releases", methods=['GET'])
def show_newly_released_books():
    page_num, page_size = 1, 10
    title_filter = request.args.get('title')
    author_filter = request.args.get('author')
    genre_filter = request.args.get('genres')
    character_filter = request.args.get('characters')

    if request.args.get('pn'):
        page_num = int(request.args.get('pn'))
    if request.args.get('ps'):
        page_size = int(request.args.get('ps'))
    page_start = (page_size * (page_num - 1))

    current_year = datetime.now().year

    query = {
        "$or": [
            {
                "publishDate": current_year  # Match exact year for publishDate
            },
            {
                "firstPublishDate": current_year  # Match exact year for firstPublishDate
            }
        ]
    }
    if title_filter:
        query["title"] = {"$regex": Regex(title_filter, 'i')}
    if author_filter:
        query["author"] = {"$regex": Regex(author_filter, 'i')}
    if genre_filter:
        query["genres"] = {"$regex": Regex(genre_filter, 'i')}
    if character_filter:
        query["characters"] = {"$regex": Regex(character_filter, 'i')}

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
            for reply in review['replies']:
                reply['_id'] = str(reply['_id'])
        all_book_data.append(book_info)
    return make_response(jsonify(all_book_data), 200)


#------------------------------------------------------------------------------------------------------------------
# 5. BOOKSHELVES
# Helper function to check and assign awards
def check_and_assign_awards(user):
    read_count = len(user.get("have_read", []))
    current_awards = set(user.get("awards", []))  # ensure it's a set for quick lookup

    new_awards = []

    # Define milestones
    milestones = {
        1: "First Book Read",
        5: "5 Books Read",
        10: "10 Books Read",
        25: "25 Books Read",
        50: "50 Books Read",
        100: "100 Books Read"
    }

    for milestone, award in milestones.items():
        if read_count >= milestone and award not in current_awards:
            new_awards.append(award)

    if new_awards:
        users.update_one(
            {"_id": user["_id"]},
            {"$addToSet": {"awards": {"$each": new_awards}}}
        )

        return new_awards

    return []


@books_bp.route("/api/v1.0/books/<string:id>/have-read", methods=["POST"])
@jwt_required
def have_read_book(id):
    token_data = request.token_data
    username = token_data["username"]
    date_read = request.form.get('date_read')

    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    book = books.find_one({"_id": ObjectId(id)})
    if not book:
        return make_response(jsonify({"error": "Invalid Book ID"}), 404)

    if "stars" not in request.form:
        return make_response(jsonify({"error": "Missing 'stars' field"}), 400)

    try:
        stars = float(request.form["stars"])
        if stars < 0 or stars > 5:
            return make_response(jsonify({"error": "Stars must be between 0 and 5"}), 400)
    except ValueError:
        return make_response(jsonify({"error": "Invalid rating format"}), 400)

    if not date_read:
        return make_response(jsonify({"error": "Missing 'date_read' field"}), 400)

    book_data = {
        "_id": id,
        "title": book.get("title"),
        "coverImg": book.get("coverImg"),
        "author": book.get("author"),
        "genres": book.get("genres"),
        "stars": stars,
        "date_read": date_read
    }

    if "have_read" in user and any(b["_id"] == id for b in user["have_read"]):
        return make_response(jsonify({"message": "Book already marked as read"}), 200)

    users.update_one({"_id": user["_id"]}, {"$addToSet": {"have_read": book_data}})

    # Re-fetch user to ensure we have latest data
    user = users.find_one({"username": username})

    # Check for awards 🏆
    new_awards = check_and_assign_awards(user)

    response = {"message": "Book added to have_read list"}
    if new_awards:
        response["new_awards"] = new_awards

    return make_response(jsonify(response), 200)


@books_bp.route("/api/v1.0/have-read", methods=["GET"])
@jwt_required
def get_all_have_read_books():
    token_data = request.token_data
    username = token_data['username']
    user = users.find_one({"username": username}, {"have_read": 1})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)
    return make_response(jsonify({"have_read": user.get("have_read", [])}), 200)

@books_bp.route("/api/v1.0/have-read/<string:book_id>", methods=["GET"])
@jwt_required
def get_have_read_book(book_id):
    token_data = request.token_data
    username = token_data['username']
    user = users.find_one({"username": username}, {"have_read": 1})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)
    book = next((b for b in user.get("have_read", []) if b["_id"] == book_id), None)
    if not book:
        return make_response(jsonify({"error": "Book not found in have read list"}), 404)
    return make_response(jsonify({"book": book}), 200)


@books_bp.route("/api/v1.0/books/<string:id>/have-read", methods=["PUT"])
@jwt_required
def edit_have_read_book(id):
    token_data = request.token_data
    username = token_data["username"]

    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    book_index = next((i for i, b in enumerate(user.get("have_read", [])) if b["_id"] == id), None)
    if book_index is None:
        return make_response(jsonify({"error": "Book not found in have read list"}), 404)

    data = request.get_json()
    updates = {}

    if "stars" in data:
        try:
            stars = float(data["stars"])
            if stars < 0 or stars > 5:
                return make_response(jsonify({"error": "Stars must be between 0 and 5"}), 400)
            updates["stars"] = stars
        except ValueError:
            return make_response(jsonify({"error": "Invalid rating format"}), 400)

    if "date_read" in data:
        updates["date_read"] = data["date_read"]

    if not updates:
        return make_response(jsonify({"error": "No valid fields to update"}), 400)

    users.update_one(
        {"_id": user["_id"], f"have_read.{book_index}._id": id},
        {"$set": {f"have_read.{book_index}.{key}": value for key, value in updates.items()}}
    )

    return make_response(jsonify({"message": "Book details updated successfully"}), 200)


@books_bp.route('/api/v1.0/remove-all-have-read', methods=["POST"])
@jwt_required
def remove_all_have_read_books():
    token_data = request.token_data
    username = token_data['username']

    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    users.update_one({"_id": user["_id"]}, {"$set": {"have_read": []}})

    

    return make_response(jsonify({"message": "All books removed successfully"}), 200)

@books_bp.route("/api/v1.0/books/<string:id>/have-read", methods=["DELETE"])
@jwt_required
def remove_have_read_book(id):
    token_data = request.token_data
    username = token_data["username"]

    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    if "have_read" not in user or not any(b["_id"] == id for b in user["have_read"]):
        return make_response(jsonify({"error": "Book not found in have_read list"}), 404)

    users.update_one({"_id": user["_id"]}, {"$pull": {"have_read": {"_id": id}}})

    return make_response(jsonify({
        "message": "Book removed from have_read list",
    }), 200)


@books_bp.route("/api/v1.0/books/<string:id>/want-to-read", methods=["POST"])
@jwt_required
def want_to_read_book(id):
    token_data = request.token_data
    username = token_data["username"]
    
    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)
    
    book = books.find_one({"_id": ObjectId(id)})
    if not book:
        return make_response(jsonify({"error": "Invalid Book ID"}), 404)
    
    book_data = {
        "_id": id,
        "title": book.get("title"),
        "coverImg": book.get("coverImg"),
        "author": book.get("author"),
        "genres": book.get("genres"),
    }
    
    
    users.update_one({"_id": user["_id"]}, {"$addToSet": {"want_to_read": book_data}})
    
    
    return make_response(jsonify({"message": "Book added to tbr list"}), 200)

@books_bp.route("/api/v1.0/want-to-read", methods=["GET"])
@jwt_required
def get_all_tbr_books():
    token_data = request.token_data
    username = token_data['username']
    user = users.find_one({"username": username}, {"want_to_read": 1})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)
    return make_response(jsonify({"want_to_read": user.get("want_to_read", [])}), 200)

@books_bp.route("/api/v1.0/books/<string:id>/want-to-read", methods=["DELETE"])
@jwt_required
def remove_tbr_book(id):
    token_data = request.token_data
    username = token_data["username"]

    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    if "have_read" not in user or not any(b["_id"] == id for b in user["want_to_read"]):
        return make_response(jsonify({"error": "Book not found in tbr list"}), 404)

    users.update_one({"_id": user["_id"]}, {"$pull": {"want_to_read": {"_id": id}}})

    return make_response(jsonify({
        "message": "Book removed from tbr list",
    }), 200)

@books_bp.route("/api/v1.0/books/<string:id>/current-read", methods=["POST"])
@jwt_required
def start_to_read_book(id):
    token_data = request.token_data
    username = token_data["username"]
    
    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)
    
    book = books.find_one({"_id": ObjectId(id)})
    if not book:
        return make_response(jsonify({"error": "Invalid Book ID"}), 404)
    
    current_time = datetime.utcnow()

    book_data = {
        "_id": id,
        "title": book.get("title"),
        "coverImg": book.get("coverImg"),
        "author": book.get("author"),
        "genres": book.get("genres"),
        "reading_time": current_time,
        "total_pages": book.get("pages"),
        "current_page": 0,
        "progress": 0
    }
    
    if "currently_reading" in user and any(b["_id"] == id for b in user["currently_reading"]):
        return make_response(jsonify({"message": "Book already in currently reading list"}), 200)

    if "want_to_read" in user:
        users.update_one(
            {"_id": user["_id"]},
            {"$pull": {"want_to_read": {"_id": id}}}
        )

    
    users.update_one({"_id": user["_id"]}, {"$addToSet": {"currently_reading": book_data}})
    
    
    return make_response(jsonify({"message": "Book added to current reads"}), 200)




@books_bp.route("/api/v1.0/currently-reading", methods=["GET"])
@jwt_required
def get_all_current_reads():
    token_data = request.token_data
    username = token_data['username']
    user = users.find_one({"username": username}, {"currently_reading": 1})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)
    return make_response(jsonify({"currently_reading": user.get("currently_reading", [])}), 200)

@books_bp.route("/api/v1.0/currently-reading/<string:book_id>", methods=["GET"])
@jwt_required
def get_current_read(book_id):
    token_data = request.token_data
    username = token_data['username']
    user = users.find_one({"username": username}, {"currently_reading": 1})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)
    book = next((b for b in user.get("currently_reading", []) if b["_id"] == book_id), None)
    if not book:
        return make_response(jsonify({"error": "Book not found in currently reading list"}), 404)
    return make_response(jsonify({"book": book}), 200)




@books_bp.route("/api/v1.0/currently-reading/<string:book_id>", methods=["POST"])
@jwt_required
def update_reading_progress(book_id):
    token_data = request.token_data
    username = token_data["username"]
    new_page = request.form.get("current_page")
    
    if new_page is None or not new_page.isdigit() or int(new_page) < 0:
        return make_response(jsonify({"error": "Invalid page number"}), 400)
    
    new_page = int(new_page)
    
    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)
    
    currently_reading = user.get("currently_reading", [])
    book = next((b for b in currently_reading if str(b["_id"]) == book_id), None)
    
    if not book:
        return make_response(jsonify({"error": "Book not found in currently reading list"}), 404)
    
    total_pages = book.get("total_pages", 0)
    
    if new_page > total_pages:
        return make_response(jsonify({"error": "Page number exceeds total pages"}), 400)
    
    users.update_one(
        {"_id": user["_id"], "currently_reading._id": book_id},
        {"$set": {"currently_reading.$.current_page": new_page, "currently_reading.$.reading_time": datetime.now()}}
    )
    
    progress = user_progress_aggregation(user["_id"])
    
    users.update_one(
        {"_id": user["_id"], "currently_reading._id": book_id},
        {"$set": {"currently_reading.$.progress": progress}}
    )
    
    return make_response(jsonify({"message": "Progress updated", "progress": progress}), 200)


@books_bp.route("/api/v1.0/books/<string:id>/currently-reading", methods=["DELETE"])
@jwt_required
def remove_currently_reading_book(id):
    token_data = request.token_data
    username = token_data["username"]

    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    if "currently_reading" not in user or not any(b["_id"] == id for b in user["currently_reading"]):
        return make_response(jsonify({"error": "Book not found in currently_reading list"}), 404)

    users.update_one({"_id": user["_id"]}, {"$pull": {"currently_reading": {"_id": id}}})

    return make_response(jsonify({
        "message": "Book removed from current reads",
    }), 200)

@books_bp.route("/api/v1.0/books/<string:id>/add-to-favourites", methods=["POST"])
@jwt_required
def add_to_favourites(id):
    token_data = request.token_data
    username = token_data["username"]
    
    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)
    
    book = books.find_one({"_id": ObjectId(id)})
    if not book:
        return make_response(jsonify({"error": "Invalid Book ID"}), 404)
    
    book_data = {
        "_id": id,
        "title": book.get("title"),
        "coverImg": book.get("coverImg"),
        "author": book.get("author"),
        "genres": book.get("genres"),
        "pages": book.get("pages"),
    }
    
    if "favourite_books" in user and any(b["_id"] == id for b in user["favourite_books"]):
        return make_response(jsonify({"message": "Book already in favourites"}), 200)

    users.update_one({"_id": user["_id"]}, {"$addToSet": {"favourite_books": book_data}})

    return make_response(jsonify({"message": "Book added to favourites"}), 200)

@books_bp.route("/api/v1.0/books/<string:id>/favourites", methods=["DELETE"])
@jwt_required
def remove_favourite_book(id):
    token_data = request.token_data
    username = token_data["username"]

    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    if "have_read" not in user or not any(b["_id"] == id for b in user["favourite_books"]):
        return make_response(jsonify({"error": "Book not found in favourites list"}), 404)

    users.update_one({"_id": user["_id"]}, {"$pull": {"favourite_books": {"_id": id}}})

    return make_response(jsonify({
        "message": "Book removed from favourites list",
    }), 200)

@books_bp.route("/api/v1.0/favourites", methods=["GET"])
@jwt_required
def get_all_favourite_reads():
    token_data = request.token_data
    username = token_data['username']
    user = users.find_one({"username": username}, {"favourite_books": 1})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)
    return make_response(jsonify({"favourite_books": user.get("favourite_books", [])}), 200)
