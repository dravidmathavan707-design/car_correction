from flask import Flask, render_template, request, redirect, session, abort
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from functools import wraps
from datetime import datetime
from bson.objectid import ObjectId
import os
import uuid
from config import *

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', SECRET_KEY)
if os.path.isabs(UPLOAD_FOLDER):
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
else:
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

client = MongoClient(
    os.getenv('MONGO_URI', MONGO_URI),
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=5000,
    socketTimeoutMS=5000,
)
db = client[DATABASE_NAME]


def database_ready():
    try:
        client.admin.command("ping")
        return True
    except Exception:
        return False


@app.errorhandler(ServerSelectionTimeoutError)
@app.errorhandler(PyMongoError)
def handle_mongo_error(_error):
    return render_template(
        "login.html",
        error="Database connection failed. Verify Render MONGO_URI and MongoDB Atlas Network Access (0.0.0.0/0)."
    ), 503


@app.errorhandler(500)
def handle_internal_error(_error):
    return render_template(
        "login.html",
        error="Temporary server error. Please try again in a moment."
    ), 500


@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(_error):
    return render_template(
        "add_repair.html",
        error="Upload is too large. Please keep total photos under 10 MB."
    ), 413

# ---------------- ROLE DECORATOR ----------------
def roles_required(*roles):
    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "role" not in session:
                return redirect("/login")
            if session["role"] not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return wrapper

# ---------------- ROOT ROUTE ----------------
@app.route("/")
def index():
    if "user" in session:
        return redirect("/dashboard")
    return redirect("/login")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # Fixed Admin
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["user"] = ADMIN_USERNAME
            session["role"] = "admin"
            return redirect("/dashboard")

        if not database_ready():
            return render_template("login.html", error="Database connection failed. Check Render MONGO_URI and MongoDB Atlas Network Access.")

        # Staff
        try:
            user = db.users.find_one({"username": username, "role": "staff"})
        except PyMongoError:
            return render_template("login.html", error="Database query failed. Verify MongoDB username, password, and cluster settings.")

        if user and check_password_hash(user["password"], password):
            session["user"] = user["username"]
            session["role"] = "staff"
            return redirect("/dashboard")

        return render_template("login.html", error="Invalid credentials")

    return render_template("login.html", error=None)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
@roles_required("admin", "staff")
def dashboard():

    search = request.args.get("search")

    query_customer = {}
    query_repair = {}

    if search:
        query_customer = {
            "$or": [
                {"name": {"$regex": search, "$options": "i"}},
                {"phone": {"$regex": search, "$options": "i"}},
                {"vehicle": {"$regex": search, "$options": "i"}}
            ]
        }

        query_repair = {
            "$or": [
                {"customer": {"$regex": search, "$options": "i"}},
                {"service": {"$regex": search, "$options": "i"}},
                {"status": {"$regex": search, "$options": "i"}}
            ]
        }

    # Staff cannot see soft deleted
    if session["role"] == "staff":
        query_customer["is_deleted"] = False

    customers = list(db.customers.find(query_customer))
    repairs = list(db.repairs.find(query_repair))

    total_customers = db.customers.count_documents({"is_deleted": False})
    total_repairs = db.repairs.count_documents({})

    return render_template("dashboard.html",
                           customers=customers,
                           repairs=repairs,
                           total_customers=total_customers,
                           total_repairs=total_repairs,
                           search=search)
# ---------------- CUSTOMER ----------------
@app.route("/add_customer", methods=["GET", "POST"])
@roles_required("admin", "staff")
def add_customer():
    if request.method == "POST":
        db.customers.insert_one({
            "name": request.form["name"],
            "phone": request.form["phone"],
            "vehicle": request.form["vehicle"],
            "created_at": datetime.now(),
            "is_deleted": False
        })
        return redirect("/dashboard")

    return render_template("add_customer.html")

@app.route("/delete_customer/<id>")
@roles_required("admin", "staff")
def delete_customer(id):
    if session["role"] == "staff":
        db.customers.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"is_deleted": True}}
        )
    else:
        db.customers.delete_one({"_id": ObjectId(id)})
    return redirect("/dashboard")

# ---------------- REPAIR ----------------
@app.route("/add_repair", methods=["GET", "POST"])
@roles_required("admin", "staff")
def add_repair():
    if request.method == "POST":
        uploaded_photos = request.files.getlist("damage_photos")
        
        # Validate photo limit (max 13 photos per customer)
        valid_photos = [p for p in uploaded_photos if p and p.filename != ""]
        if len(valid_photos) > 13:
            return render_template(
                "add_repair.html",
                error="Maximum 13 photos allowed per customer. Please reduce the number of photos."
            )
        
        damage_photo_paths = []

        for photo in valid_photos:
            if not allowed_file(photo.filename):
                return render_template(
                    "add_repair.html",
                    error="Only image files are allowed (jpg, jpeg, png, webp)."
                )

            filename = secure_filename(photo.filename)
            extension = filename.rsplit(".", 1)[1].lower()
            unique_filename = f"{uuid.uuid4().hex}.{extension}"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            photo.save(save_path)
            damage_photo_paths.append(f"uploads/repairs/{unique_filename}")

        db.repairs.insert_one({
            "customer": request.form["customer"],
            "service": request.form["service"],
            "cost": request.form["cost"],
            "warranty": request.form["warranty"],
            "damage_photos": damage_photo_paths,
            "status": "Pending",
            "created_at": datetime.now()
        })
        return redirect("/dashboard")

    return render_template("add_repair.html", error=None)

@app.route("/delete_repair/<id>")
@roles_required("admin", "staff")
def delete_repair(id):
    repair = db.repairs.find_one({"_id": ObjectId(id)})

    # Best effort cleanup for previously uploaded damaged-part photos.
    if repair and repair.get("damage_photos"):
        for relative_path in repair.get("damage_photos", []):
            photo_path = os.path.join(app.static_folder, relative_path.replace("/", os.sep))
            if os.path.exists(photo_path):
                os.remove(photo_path)

    db.repairs.delete_one({"_id": ObjectId(id)})
    return redirect("/dashboard")

# ---------------- STAFF MANAGEMENT ----------------
@app.route("/staff_management")
@roles_required("admin")
def staff_management():
    staffs = list(db.users.find({"role": "staff"}))
    return render_template("staff_management.html", staffs=staffs)

@app.route("/add_staff", methods=["POST"])
@roles_required("admin")
def add_staff():
    username = request.form["username"]
    password = request.form["password"]

    if db.users.find_one({"username": username}):
        return "Username already exists"

    db.users.insert_one({
        "username": username,
        "password": generate_password_hash(password),
        "role": "staff",
        "created_at": datetime.now()
    })
    return redirect("/staff_management")

@app.route("/delete_staff/<id>")
@roles_required("admin")
def delete_staff(id):
    db.users.delete_one({"_id": ObjectId(id), "role": "staff"})
    return redirect("/staff_management")

if __name__ == "__main__":
    app.run(debug=True)


# mongodb+srv://<db_username>:<db_password>@cluster0.mpgvf66.mongodb.net/

