import requests
from flask import Blueprint, request, jsonify

# Create a Flask Blueprint
imgur_upload_bp = Blueprint("imgur_upload_bp", __name__)

# Your Imgur API Client ID
IMGUR_CLIENT_ID = "8cc2c21f701f179"

@imgur_upload_bp.route("/api/v1.0/upload-image", methods=["POST"])
def upload_image():
    # Check if a file was uploaded
    if "image" not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    image = request.files["image"]
    
    if image.filename == "":
        return jsonify({"error": "No selected file"}), 400
    
    headers = {
        "Authorization": f"Client-ID {IMGUR_CLIENT_ID}"
    }
    
    # Prepare file for Imgur API
    image_data = {
        "image": image.read(),  # Read image in binary
        "type": "file"  # Set type to file
    }
    
    # Send request to Imgur to upload the image
    response = requests.post("https://api.imgur.com/3/upload", headers=headers, files=image_data)
    
    if response.status_code == 200:
        # Successfully uploaded image
        img_url = response.json()["data"]["link"]
        return jsonify({"message": "Image uploaded successfully!", "url": img_url}), 200
    else:
        return jsonify({"error": "Failed to upload image to Imgur"}), 500
