from flask import Blueprint, request, make_response, jsonify
import re
from bson import ObjectId
from decorators import jwt_required, admin_required
import globals
from blueprints.messages.messages import send_message

request_books_bp = Blueprint("request_books_bp", __name__)

requests = globals.db.requests
books = globals.db.books
users = globals.db.users

# BOOK REQUEST APIS
#------------------------------------------------------------------------------------------------------------------
@request_books_bp.route("/api/v1.0/add-requests", methods=["POST"])
@jwt_required
def add_new_book_request():
    token_data = request.token_data
    username = token_data['username']
    title = request.form.get('title')
    author = request.form.get('author')
    genres = request.form.get('genres')
    language = request.form.get('language')
    series = request.form.get('series', '')
    isbn = int(request.form.get('isbn', 0))

    if not title or not author or not genres or not language:
        return make_response(jsonify({"error": "You missed a required field"}), 400)

    if isinstance(genres, str):
        genres_list = [g.strip() for g in genres.split(",")]
    elif isinstance(genres, list):
        genres_list = [str(g).strip() for g in genres]
    else:
        genres_list = []

    if isinstance(author, str):
        author_list = [a.strip() for a in author.split(",")]
    elif isinstance(author, list):
        author_list = [str(a).strip() for a in author]
    else:
        author_list = []


    new_request = {
        '_id': ObjectId(),
        'title': title,
        'series': series,
        'author': author_list,
        'genres': genres_list,
        'language': language,
        'isbn': isbn,
        'username': username
    }

    new_request_id = requests.insert_one(new_request)

    request_link = f"http://localhost:4200/api/v1.0/requests/{new_request_id.inserted_id}"
    
    return make_response(jsonify({
        "message": "Your book request has been submitted and will be reviewed by our admins",
        "url": request_link
    }), 201)


@request_books_bp.route("/api/v1.0/requests", methods=["GET"])
@jwt_required
@admin_required
def show_all_book_requests():
    page_num, page_size = 1, 20
    if request.args.get('pn'):
        page_num = int(request.args.get('pn'))
    if request.args.get('ps'):
        page_size = int(request.args.get('ps'))
    page_start = page_size * (page_num - 1)

    all_requests = []
    for book_request in requests.find().skip(page_start).limit(page_size):
        book_request['_id'] = str(book_request['_id'])
        all_requests.append(book_request)
    return make_response(jsonify(all_requests), 200)

@request_books_bp.route("/api/v1.0/requests/<string:id>", methods=["GET"])
@jwt_required
def show_one_book_request(id):
    requested_book = requests.find_one({'_id': ObjectId(id)})
    if requested_book:
        requested_book['_id'] = str(requested_book['_id'])
        return make_response(jsonify(requested_book), 200)
    else:
        return make_response(jsonify({"error": "Invalid Book ID"}), 404)


@request_books_bp.route("/api/v1.0/requests/<string:id>/approve", methods=["POST"])
@jwt_required
@admin_required
def approve_book_request(id):
    book_request = requests.find_one({'_id': ObjectId(id)})
    if not book_request:
        return make_response(jsonify({"error": "Request not found"}), 404)
    
    approved_book_data = request.form.to_dict()
    
    def parse_comma_separated(value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value if isinstance(value, list) else []
    
    for field in ["author", "genres", "characters", "triggers", "awards"]:
        if field in approved_book_data:
            approved_book_data[field] = parse_comma_separated(approved_book_data[field])

    def extract_year(date_str):
        if date_str:
            try:
                return int(date_str[:4])
            except ValueError:
                return None
        return None

    publish_year = extract_year(approved_book_data['publishDate'])
    first_publish_year = extract_year(approved_book_data['firstPublishDate'])

    book_request_isbn = book_request.get('isbn', 0)
    approved_isbn = int(approved_book_data.get('isbn', 0))
    final_isbn = approved_isbn if book_request_isbn == 0 and approved_isbn != 0 else book_request_isbn

    approved_book_data.update({
        'title': book_request['title'],
        'author': book_request['author'],
        'genres': approved_book_data['genres'],
        'language': book_request['language'],
        'series': book_request['series'],
        'user_score': int(approved_book_data.get('user_score', 0)),
        'description': approved_book_data.get('description', ''),
        'user_reviews': [],
        'isbn': int(final_isbn),
        'characters': approved_book_data.get('characters', []), 
        'triggers': approved_book_data.get('triggers', []),
        'bookFormat': approved_book_data.get('bookFormat', ''),
        'edition': approved_book_data.get('edition', ''),
        'pages': int(approved_book_data.get('pages', 0)),
        'publisher': approved_book_data.get('publisher', ''),
        "publishDate": int(publish_year),
        "firstPublishDate": int(first_publish_year),
        'awards': approved_book_data.get('awards', []),
        'coverImg': approved_book_data.get('coverImg', ''),
        'price': int(approved_book_data.get('price', 0.0))
    })
    
    approved_book_id = books.insert_one(approved_book_data)
    approved_book_link = f"http://localhost:4200/api/v1.0/books/{approved_book_id.inserted_id}"

    send_message(
        recipient_name=book_request['username'],
        content=f"Dear '{book_request['username']}', your request for '{book_request['title']}' has been approved and added to our system. Here is the link to the book: {approved_book_link}. Thank you."
    )

    requests.delete_one({'_id': ObjectId(id)})

    return make_response(jsonify({"message": "Request has been approved", "url": approved_book_link}), 201)


@request_books_bp.route("/api/v1.0/requests/<string:id>/reject", methods=["POST"])
@jwt_required
@admin_required
def reject_book_request(id):
    book_request = requests.find_one({'_id': ObjectId(id)})
    if not book_request:
        return make_response(jsonify({"error": "Request not found"}), 404)
    
    recipient_name = book_request['username']
    title = book_request['title']
    
    send_message(
        recipient_name=recipient_name,
        content=f"Dear '{recipient_name}', we regret to inform you that your request for '{title}' has been rejected and will not be added to our system. Thank you."
    )
    rejected = requests.delete_one({'_id': ObjectId(id)})
    if rejected.deleted_count == 1:
        return make_response(jsonify({"message": "Request has been rejected"}), 201)
    else:
        return make_response(jsonify({"error": "Invalid Book ID"}), 404)
    
@request_books_bp.route("/api/v1.0/requests/<string:id>", methods=["DELETE"])
@jwt_required
@admin_required
def delete_request(id):
    result = requests.delete_one({"_id":ObjectId(id)})
    if result.deleted_count == 1:
        return make_response(jsonify({}), 204)
    else:
        return make_response(jsonify({"error": "Invalid request ID"}), 404)
