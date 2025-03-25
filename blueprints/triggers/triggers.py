from flask import Blueprint, request, jsonify, make_response
from bson import ObjectId
from decorators import jwt_required, admin_required
import globals

# Initialize Blueprint
triggers_bp = Blueprint("triggers_bp", __name__)
books = globals.db.books

@triggers_bp.route("/api/v1.0/triggers", methods=["GET"])
def get_all_trigger_warnings():
    try:
        triggers = books.distinct("triggers")
        return make_response(jsonify(triggers), 200)
    except Exception as e:
        return make_response(jsonify({"error": str(e)}), 500)
    

@triggers_bp.route("/api/v1.0/books/<string:id>/add-trigger", methods=["POST"])
@jwt_required
#@admin_required
def add_trigger_warnings(id):
    # Validate the input data
    triggers = request.form.get('triggers')

    # If triggers is a string, convert it to a list of individual triggers
    if isinstance(triggers, str):
        trigger_list = [t.strip() for t in triggers.split(",")]
    elif isinstance(triggers, list):
        trigger_list = [str(t).strip() for t in triggers]
    else:
        trigger_list = []

    # Create a dictionary for the trigger to be added
    trigger_warning = {'triggers': trigger_list}

    # Use the $push operator to add the new trigger(s) to the existing list in the MongoDB document
    books.update_one(
        {"_id": ObjectId(id)},  # Find the book by its ID
        {"$push": {"triggers": {"$each": trigger_warning['triggers']}}}  # Add new trigger(s)
    )

    # Return a success message
    return make_response(jsonify({"message": "Trigger added successfully"}), 201)