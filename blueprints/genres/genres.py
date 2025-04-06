from flask import Blueprint, jsonify, make_response
import globals

# Initialize Blueprint
genres_bp = Blueprint("genres_bp", __name__)
books = globals.db.books

# GENRE APIS
#------------------------------------------------------------------------------------------------------------------
@genres_bp.route("/api/v1.0/genres", methods=["GET"])
def get_all_genres():
    try:
        # Aggregate unique genres from the books collection
        genres = books.distinct("genres")
        return make_response(jsonify(genres), 200)
    except Exception as e:
        return make_response(jsonify({"error": str(e)}), 500)
