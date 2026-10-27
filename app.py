from flask import Flask, request, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId

app = Flask(__name__)

# --- MongoDB Connection ---
client = MongoClient("mongodb://localhost:27017")
db = client['flask_db']
users_collection = db["users"]

@app.route("/")
def home():
    return "Flask is working!"

# --- 1. CREATE: Insert a New User ---
@app.route("/users", methods=["POST"])
def create_user():
    data = request.json
    
    new_user = {
        "name": data.get("name"),
        "email": data.get("email"),
        "age": data.get("age")
    }
    
    result = users_collection.insert_one(new_user)
    
    return jsonify({
        "status": "success",
        "message": "User created successfully!",
        "inserted_id": str(result.inserted_id)
    }), 201

# --- 2. READ: Get All Users ---
@app.route("/users", methods=["GET"])
def get_users():
    users = []
    for user in users_collection.find():
        user["_id"] = str(user["_id"])  # Convert ObjectId to string for JSON
        users.append(user)
    return jsonify(users), 200

# --- 3. READ: Get a Single User by ID ---
@app.route("/users/<user_id>", methods=["GET"])
def get_user_by_id(user_id):
    try:
        user = users_collection.find_one({"_id": ObjectId(user_id)})
        if user:
            user["_id"] = str(user["_id"])
            return jsonify(user), 200
        return jsonify({"error": "User not found"}), 404
    except Exception as e:
        return jsonify({"error": "Invalid User ID format"}), 400

# --- 4. UPDATE: Update a User by ID ---
@app.route("/users/<user_id>", methods=["PUT"])
def update_user(user_id):
    try:
        data = request.json
        updated_data = {
            "name": data.get("name"),
            "email": data.get("email"),
            "age": data.get("age")
        }
        
        result = users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": updated_data}
        )
        
        if result.matched_count > 0:
            return jsonify({"status": "success", "message": "User updated successfully!"}), 200
        return jsonify({"error": "User not found"}), 404
    except Exception as e:
        return jsonify({"error": "Invalid User ID format"}), 400

# --- 5. DELETE: Delete a User by ID ---
@app.route("/users/<user_id>", methods=["DELETE"])
def delete_user(user_id):
    try:
        result = users_collection.delete_one({"_id": ObjectId(user_id)})
        
        if result.deleted_count > 0:
            return jsonify({"status": "success", "message": "User deleted successfully!"}), 200
        return jsonify({"error": "User not found"}), 404
    except Exception as e:
        return jsonify({"error": "Invalid User ID format"}), 400

if __name__ == "__main__":
    app.run(debug=True)
