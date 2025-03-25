from flask import Flask
from blueprints.books.books import books_bp
from blueprints.requests.request_books import request_books_bp
from blueprints.genres.genres import genres_bp
from blueprints.authors.authors import authors_bp
from blueprints.triggers.triggers import triggers_bp
from blueprints.reviews.reviews import reviews_bp
from blueprints.auth.auth import auth_bp
from blueprints.messages.messages import messages_bp
from blueprints.imgur_uploader.imgur_uploader import imgur_upload_bp
from blueprints.thoughts.thoughts import thoughts_bp
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins="http://localhost:4200")

app.register_blueprint(books_bp)
app.register_blueprint(request_books_bp)
app.register_blueprint(genres_bp)
app.register_blueprint(authors_bp)
app.register_blueprint(triggers_bp)
app.register_blueprint(reviews_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(messages_bp)
app.register_blueprint(imgur_upload_bp)
app.register_blueprint(thoughts_bp)



if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
