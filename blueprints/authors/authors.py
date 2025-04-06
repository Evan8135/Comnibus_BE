from flask import Blueprint, jsonify, make_response, request
from bson import ObjectId
from bson.regex import Regex
from datetime import datetime
from decorators import jwt_required, admin_required, author_required
import globals

# Initialize Blueprint
authors_bp = Blueprint("authors_bp", __name__)
books = globals.db.books

# AUTHOR APIS
#------------------------------------------------------------------------------------------------------------------
@authors_bp.route("/api/v1.0/authors", methods=["GET"])
def get_all_authors():
    try:
        authors = books.distinct("author")
        return make_response(jsonify(authors), 200)
    except Exception as e:
        return make_response(jsonify({"error": str(e)}), 500)
    
