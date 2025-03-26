from flask import Blueprint, request, make_response, jsonify, redirect, url_for
from bson import ObjectId
from bson.regex import Regex
from datetime import datetime
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

@books_bp.route("/api/v1.0/add-book", methods=["POST"])
@jwt_required
@author_required
@admin_required
def add_book():
    # Helper function to parse comma-separated values into a list
    def parse_comma_separated(value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value if isinstance(value, list) else []

    # Get form data
    title = request.form.get("title")
    series = request.form.get("series", "")
    author = request.form.get("author")
    description = request.form.get("description")
    language = request.form.get("language")
    isbn = request.form.get("isbn")
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

    # Ensure required fields are present
    if not title or not author:
        return make_response(jsonify({"error": "Title and Author are required fields"}), 400)

    # Apply the parsing logic to the fields (genres, author, characters, triggers, awards)
    genres_list = parse_comma_separated(genres)
    author_list = parse_comma_separated(author)
    characters_list = parse_comma_separated(characters)
    triggers_list = parse_comma_separated(triggers)
    award_list = parse_comma_separated(awards)

    # Book data structure to insert into DB
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
        "publishDate": publish_date,
        "firstPublishDate": first_publish_date,
        "awards": award_list,
        "coverImg": cover_img,
        "price": price
    }

    # Insert the book into the database
    inserted_book = books.insert_one(book_data)
    
    return make_response(jsonify({"message": "Book added successfully", "book_id": str(inserted_book.inserted_id)}), 201)




@books_bp.route("/api/v1.0/books/<string:id>", methods=["PUT"])
@jwt_required
@admin_required
def edit_book(id):
    # Parse the request JSON
    update_data = request.get_json()
    if not update_data:
        return make_response(jsonify({"error": "No data provided"}), 400)
    
    # Ensure the book exists
    book = books.find_one({'_id': ObjectId(id)})
    if not book:
        return make_response(jsonify({"error": "Invalid Book ID"}), 404)
    
    # Update the book
    result = books.update_one({'_id': ObjectId(id)}, {'$set': update_data})
    
    if result.modified_count == 0:
        return make_response(jsonify({"message": "No changes made"}), 200)
    
    # Fetch the updated book
    updated_book = books.find_one({'_id': ObjectId(id)})
    updated_book['_id'] = str(updated_book['_id'])
    
    return make_response(jsonify(updated_book), 200)

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

    # Check if the user is authorized to delete the review
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

    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 10))
    skip = (page - 1) * page_size

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
        genre_books = list(books.find(genre_query, {"_id": 1, "title": 1, "author": 1, "coverImg": 1, "genres": 1}).limit(100))
        recommended_books.extend(genre_books)

    # Query for books based on authors
    if fav_authors:
        author_books = list(books.find(author_query, {"_id": 1, "title": 1, "author": 1, "coverImg": 1, "genres": 1}).limit(50))
        recommended_books.extend(author_books)

    rated_books = user.get("have_read", [])
    for rated_book in rated_books:
        if rated_book["stars"] > 3.5:  # Only if rated above half a star
            # Check if the author is in an array of authors, hence using `$in` operator
            same_author_books = list(books.find({
                "author": {"$in": [rated_book["author"]]},  # Check if the rated book's author is in the author array
                "_id": {"$ne": ObjectId(rated_book["_id"])}  # Exclude the rated book itself
            }))

            # Add the books by the same author
            for book in same_author_books:
                recommended_books.append({
                    "_id": str(book["_id"]),
                    "title": book["title"],
                    "author": book["author"],
                    "coverImg": book["coverImg"],
                    "genres": book["genres"]
                })


    # Ensure no duplicates (if a book is found in both genres and authors)
    recommended_books = list({str(book["_id"]): book for book in recommended_books}.values())

    # Convert ObjectId to string for serialization
    for book in recommended_books:
        book["_id"] = str(book["_id"])

    # Return the recommended books along with user's preferences
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
        all_book_data.append(book_info)
    return make_response(jsonify(all_book_data), 200)


#------------------------------------------------------------------------------------------------------------------
# 5. BOOKSHELVES
@books_bp.route("/api/v1.0/books/<string:id>/have-read", methods=["POST"])
@jwt_required
def have_read_book(id):
    token_data = request.token_data
    username = token_data["username"]
    date_read = request.form.get('date_read')

    # Find the user
    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    # Find the book
    book = books.find_one({"_id": ObjectId(id)})
    if not book:
        return make_response(jsonify({"error": "Invalid Book ID"}), 404)
    
    

    # Retrieve 'stars' from form data
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
    
    

    # Prepare book data
    book_data = {
        "_id": id,
        "title": book.get("title"),
        "coverImg": book.get("coverImg"),
        "author": book.get("author"),
        "genres": book.get("genres"),
        "stars": stars,
        "date_read": date_read
    }

    # Check if the book is already marked as read
    if "have_read" in user and any(b["_id"] == id for b in user["have_read"]):
        return make_response(jsonify({"message": "Book already marked as read"}), 200)

    # Add book to 'have_read' list
    users.update_one({"_id": user["_id"]}, {"$addToSet": {"have_read": book_data}})

    return make_response(jsonify({"message": "Book added to have_read list"}), 200)

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

    # Find the user
    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    # Find the book in the user's "have_read" list
    book_index = next((i for i, b in enumerate(user.get("have_read", [])) if b["_id"] == id), None)
    if book_index is None:
        return make_response(jsonify({"error": "Book not found in have read list"}), 404)

    # Get JSON data from request
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

    # If no valid updates, return an error
    if not updates:
        return make_response(jsonify({"error": "No valid fields to update"}), 400)

    # Update the specific book in the user's "have_read" list
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

    # Retrieve the user from the database
    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    # Remove all followers from the user's followers list
    users.update_one({"_id": user["_id"]}, {"$set": {"have_read": []}})

    

    return make_response(jsonify({"message": "All books removed successfully"}), 200)

@books_bp.route("/api/v1.0/books/<string:id>/have-read", methods=["DELETE"])
@jwt_required
def remove_have_read_book(id):
    token_data = request.token_data
    username = token_data["username"]

    # Find the user
    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    # Check if the book is in have_read
    if "have_read" not in user or not any(b["_id"] == id for b in user["have_read"]):
        return make_response(jsonify({"error": "Book not found in have_read list"}), 404)

    # Remove the book from have_read
    users.update_one({"_id": user["_id"]}, {"$pull": {"have_read": {"_id": id}}})




    return make_response(jsonify({
        "message": "Book removed from have_read list",
    }), 200)


@books_bp.route("/api/v1.0/books/<string:id>/want-to-read", methods=["POST"])
@jwt_required
def want_to_read_book(id):
    token_data = request.token_data
    username = token_data["username"]
    
    # Find the user
    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)
    
    # Find the book
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
    
    
    
    # Add book to have_read list
    users.update_one({"_id": user["_id"]}, {"$addToSet": {"want_to_read": book_data}})
    
    
    return make_response(jsonify({"message": "Book added to tbr list"}), 200)

@books_bp.route("/api/v1.0/books/<string:id>/current-read", methods=["POST"])
@jwt_required
def start_to_read_book(id):
    token_data = request.token_data
    username = token_data["username"]
    
    # Find the user
    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)
    
    # Find the book
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
    
    # Check if the book is already in the 'currently_reading' list
    if "currently_reading" in user and any(b["_id"] == id for b in user["currently_reading"]):
        return make_response(jsonify({"message": "Book already in currently reading list"}), 200)

    # Remove the book from 'want_to_read' if it exists
    if "want_to_read" in user:
        users.update_one(
            {"_id": user["_id"]},
            {"$pull": {"want_to_read": {"_id": id}}}
        )

    
    # Add book to have_read list
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
    
    # Find the user
    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)
    
    # Find the book in the user's currently reading list
    currently_reading = user.get("currently_reading", [])
    book = next((b for b in currently_reading if str(b["_id"]) == book_id), None)
    
    if not book:
        return make_response(jsonify({"error": "Book not found in currently reading list"}), 404)
    
    total_pages = book.get("total_pages", 0)
    
    if new_page > total_pages:
        return make_response(jsonify({"error": "Page number exceeds total pages"}), 400)
    
    # Update the current page in the user's currently reading list
    users.update_one(
        {"_id": user["_id"], "currently_reading._id": book_id},
        {"$set": {"currently_reading.$.current_page": new_page, "currently_reading.$.reading_time": datetime.now()}}
    )
    
    # Recalculate progress
    progress = user_progress_aggregation(user["_id"])
    
    # Update progress in the currently reading list
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

    # Find the user
    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    # Check if the book is in have_read
    if "currently_reading" not in user or not any(b["_id"] == id for b in user["currently_reading"]):
        return make_response(jsonify({"error": "Book not found in currently_reading list"}), 404)

    # Remove the book from have_read
    users.update_one({"_id": user["_id"]}, {"$pull": {"currently_reading": {"_id": id}}})

    return make_response(jsonify({
        "message": "Book removed from current reads",
    }), 200)

@books_bp.route("/api/v1.0/books/<string:id>/add-to-favourites", methods=["POST"])
@jwt_required
def add_to_favourites(id):
    token_data = request.token_data
    username = token_data["username"]
    
    # Find the user
    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)
    
    # Find the book
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
    
    # Check if the book is already in the 'currently_reading' list
    if "favourite_books" in user and any(b["_id"] == id for b in user["favourite_books"]):
        return make_response(jsonify({"message": "Book already in favourites"}), 200)


    
    # Add book to have_read list
    users.update_one({"_id": user["_id"]}, {"$addToSet": {"favourite_books": book_data}})
    
    
    return make_response(jsonify({"message": "Book added to favourites"}), 200)

@books_bp.route("/api/v1.0/favourites", methods=["GET"])
@jwt_required
def get_all_favourite_reads():
    token_data = request.token_data
    username = token_data['username']
    user = users.find_one({"username": username}, {"favourite_books": 1})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)
    return make_response(jsonify({"favourite_books": user.get("favourite_books", [])}), 200)


@books_bp.route("/api/v1.0/publish-book", methods=["POST"])
@jwt_required
@author_required
def publish_book():
    token_data = request.token_data
    username = token_data["username"]

    # Find user and get their preferences
    user = users.find_one({"username": username}, {"password": 0})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    

    title = request.form.get("title")
    series = request.form.get("series", "")
    author = user.get("name")
    description = request.form.get("description")
    language = request.form.get("language")
    isbn = request.form.get("isbn")
    genres = request.form.getlist("genres")
    characters = request.form.getlist("characters", [])
    triggers = request.form.getlist("triggers", [])
    book_format = request.form.get("bookFormat")
    edition = request.form.get("edition", "")
    pages = int(request.form.get("pages", 0))
    publisher = request.form.get("publisher", "")
    publish_date = request.form.get("publishDate")
    first_publish_date = request.form.get("firstPublishDate")
    awards = request.form.getlist("awards", [])
    cover_img = request.form.get("coverImg")
    price = int(request.form.get("price", 0))
    
    if not title or not author:
        return make_response(jsonify({"error": "Title and Author are required fields"}), 400)
    
    if isinstance(genres, str):
        genres_list = [g.strip() for g in genres.split(",")]
    elif isinstance(genres, list):
        genres_list = [str(g).strip() for g in genres]
    else:
        genres_list = []
    
    if isinstance(triggers, str):
        triggers_list = [t.strip() for t in triggers.split(",")]
    elif isinstance(triggers, list):
        triggers_list = [str(t).strip() for t in triggers]
    else:
        triggers_list = []

    if isinstance(characters, str):
        character_list = [c.strip() for c in characters.split(",")]
    elif isinstance(characters, list):
        character_list = [str(c).strip() for c in characters]
    else:
        character_list = []

    if isinstance(awards, str):
        award_list = [a.strip() for a in awards.split(",")]
    elif isinstance(awards, list):
        award_list = [str(a).strip() for a in awards]
    else:
        award_list = []

    book_data = {
        "title": title,
        "series": series,
        "author": author,
        "user_score": 0,
        "user_reviews": [],
        "description": description,
        "language": language,
        "isbn": isbn,
        "genres": genres_list,
        "characters": character_list,
        "triggers": triggers_list,
        "bookFormat": book_format,
        "edition": edition,
        "pages": pages,
        "publisher": publisher,
        "publishDate": publish_date,
        "firstPublishDate": first_publish_date,
        "awards": award_list,
        "coverImg": cover_img,
        "price": price
    }
    
    inserted_book = books.insert_one(book_data)
    return make_response(jsonify({"message": "Book successfully published", "book_id": str(inserted_book.inserted_id)}), 201)