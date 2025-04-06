from flask import Blueprint, request, jsonify, make_response
from bson import ObjectId
from decorators import jwt_required, admin_required
import globals

triggers_bp = Blueprint("triggers_bp", __name__)
books = globals.db.books

# TRIGGER WARNING APIS
#------------------------------------------------------------------------------------------------------------------
@triggers_bp.route("/api/v1.0/triggers", methods=["GET"])
def get_all_trigger_warnings():
    try:
        triggers = books.distinct("triggers")
        return make_response(jsonify(triggers), 200)
    except Exception as e:
        return make_response(jsonify({"error": str(e)}), 500)
    

@triggers_bp.route("/api/v1.0/books/<string:id>/add-trigger", methods=["POST"])
@jwt_required
def add_trigger_warnings(id):
    triggers = request.form.getlist('triggers')

    trigger_list = [t.strip() for t in triggers if t.strip()]

    trigger_list = list(set(trigger_list))

    books.update_one(
        {"_id": ObjectId(id)},
        {"$addToSet": {"triggers": {"$each": trigger_list}}} 
    )

    return make_response(jsonify({"message": "Trigger(s) added successfully"}), 201)
