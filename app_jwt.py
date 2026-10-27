import os
from datetime import timedelta

from flask import Flask, request, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson.errors import InvalidId
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# --- Security Configuration ---
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")

if not app.config["JWT_SECRET_KEY"]:
    raise RuntimeError("JWT_SECRET_KEY is missing from the .env file")

app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(
    minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", "30"))
)

jwt = JWTManager(app)

# --- MongoDB Connection ---
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)

db = client["flask_db"]
users_collection = db["users"]clear

# --- Home Route ---
@app.route("/")
def home():
    return "Flask API is working!"

# --- 1. REGISTER A USER ---
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A valid JSON body is required"}), 400

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    age = data.get("age")

    if not all(isinstance(value, str) and value.strip()
               for value in (name, email, password)):
        return jsonify({
            "error": "Name, email and password are required"
        }), 400

    name = name.strip()
    email = email.strip().lower()

    if len(password) < 8:
        return jsonify({
            "error": "Password must be at least 8 characters long"
        }), 400

    if len(password) > 128:
        return jsonify({"error": "Password is too long"}), 400

    if "@" not in email or len(email) > 254:
        return jsonify({"error": "Enter a valid email address"}), 400

    if age is not None and (
        isinstance(age, bool) or not isinstance(age, int)
        or age < 0 or age > 130
    ):
        return jsonify({"error": "Age must be between 0 and 130"}), 400

    if users_collection.find_one({"email": email}):
        return jsonify({"error": "Email is already registered"}), 409

    new_user = {
        "name": name,
        "email": email,
        "password": generate_password_hash(password),
        "age": age
    }

    try:
        result = users_collection.insert_one(new_user)
    except Exception:
        app.logger.exception("User registration failed")
        return jsonify({"error": "Unable to register user"}), 500

    return jsonify({
        "status": "success",
        "message": "User registered successfully",
        "user_id": str(result.inserted_id)
    }), 201

# --- 2. LOGIN AND GENERATE JWT ---
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A valid JSON body is required"}), 400

    email = data.get("email")
    password = data.get("password")

    if not isinstance(email, str) or not isinstance(password, str):
        return jsonify({"error": "Email and password are required"}), 400

    user = users_collection.find_one({
        "email": email.strip().lower()
    })

    if not user or not check_password_hash(
        user.get("password", ""), password
    ):
        return jsonify({
            "error": "Invalid email or password"
        }), 401

    # The JWT identity must be a string
    access_token = create_access_token(
        identity=str(user["_id"])
    )

    return jsonify({
        "status": "success",
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in_minutes": int(
            os.getenv("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", "30")
        )
    }), 200

# --- 3. CREATE: Insert a New User (Protected) ---
@app.route("/users", methods=["POST"])
@jwt_required()
def create_user():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A valid JSON body is required"}), 400

    name = data.get("name")
    email = data.get("email")
    age = data.get("age")

    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "Name is required"}), 400

    if not isinstance(email, str) or not email.strip():
        return jsonify({"error": "Email is required"}), 400

    email = email.strip().lower()

    if users_collection.find_one({"email": email}):
        return jsonify({"error": "Email is already in use"}), 409

    if age is not None and (
        isinstance(age, bool) or not isinstance(age, int)
        or age < 0 or age > 130
    ):
        return jsonify({"error": "Invalid age"}), 400

    new_user = {
        "name": name.strip(),
        "email": email,
        "age": age
    }

    try:
        result = users_collection.insert_one(new_user)
    except Exception:
        app.logger.exception("User creation failed")
        return jsonify({"error": "Unable to create user"}), 500

    return jsonify({
        "status": "success",
        "message": "User created successfully",
        "inserted_id": str(result.inserted_id)
    }), 201

# --- 4. READ: Get All Users (Protected) ---
@app.route("/users", methods=["GET"])
@jwt_required()
def get_users():
    users = []

    for user in users_collection.find(
        {},
        {"password": 0}
    ):
        user["_id"] = str(user["_id"])
        users.append(user)

    return jsonify(users), 200

# --- 5. READ: Get One User by ID (Protected) ---
@app.route("/users/<user_id>", methods=["GET"])
@jwt_required()
def get_user_by_id(user_id):
    try:
        user = users_collection.find_one(
            {"_id": ObjectId(user_id)},
            {"password": 0}
        )
    except InvalidId:
        return jsonify({"error": "Invalid User ID format"}), 400

    if not user:
        return jsonify({"error": "User not found"}), 404

    user["_id"] = str(user["_id"])
    return jsonify(user), 200

# --- 6. UPDATE: Update a User by ID (Protected) ---
@app.route("/users/<user_id>", methods=["PUT"])
@jwt_required()
def update_user(user_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A valid JSON body is required"}), 400

    updated_data = {}

    if "name" in data:
        if not isinstance(data["name"], str) or not data["name"].strip():
            return jsonify({"error": "Invalid name"}), 400
        updated_data["name"] = data["name"].strip()

    if "email" in data:
        if not isinstance(data["email"], str) or not data["email"].strip():
            return jsonify({"error": "Invalid email"}), 400
        updated_data["email"] = data["email"].strip().lower()

    if "age" in data:
        age = data["age"]
        if age is not None and (
            isinstance(age, bool) or not isinstance(age, int)
            or age < 0 or age > 130
        ):
            return jsonify({"error": "Invalid age"}), 400
        updated_data["age"] = age

    if not updated_data:
        return jsonify({"error": "No valid fields supplied"}), 400

    try:
        object_id = ObjectId(user_id)

        if "email" in updated_data:
            existing = users_collection.find_one({
                "email": updated_data["email"],
                "_id": {"$ne": object_id}
            })
            if existing:
                return jsonify({"error": "Email is already in use"}), 409

        result = users_collection.update_one(
            {"_id": object_id},
            {"$set": updated_data}
        )
    except InvalidId:
        return jsonify({"error": "Invalid User ID format"}), 400

    if result.matched_count == 0:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "status": "success",
        "message": "User updated successfully"
    }), 200

# --- 7. DELETE: Delete a User by ID (Protected) ---
@app.route("/users/<user_id>", methods=["DELETE"])
@jwt_required()
def delete_user(user_id):
    try:
        result = users_collection.delete_one({
            "_id": ObjectId(user_id)
        })
    except InvalidId:
        return jsonify({"error": "Invalid User ID format"}), 400

    if result.deleted_count == 0:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "status": "success",
        "message": "User deleted successfully"
    }), 200

# --- JWT Error Responses ---
@jwt.unauthorized_loader
def missing_token(reason):
    return jsonify({"error": "Authorization token is required"}), 401

@jwt.invalid_token_loader
def invalid_token(reason):
    return jsonify({"error": "Invalid authentication token"}), 401

@jwt.expired_token_loader
def expired_token(jwt_header, jwt_payload):
    return jsonify({"error": "Authentication token has expired"}), 401

if __name__ == "__main__":
    # Debug is disabled
    app.run(debug=False)
