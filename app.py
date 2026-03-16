from flask import Flask, render_template, request, redirect, session, abort, send_from_directory, url_for
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
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

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def normalize_photo_path(photo_path):
    if not photo_path:
        return ""
    normalized_path = str(photo_path).replace("\\", "/").strip()
    normalized_path = normalized_path.lstrip("/")

    if normalized_path.startswith("static/"):
        normalized_path = normalized_path[len("static/"):]

    if "/" not in normalized_path:
        normalized_path = f"uploads/repairs/{normalized_path}"

    return normalized_path


def extract_photo_filename(photo_path):
    normalized_path = normalize_photo_path(photo_path)
    return os.path.basename(normalized_path)


def get_photo_storage_dirs():
    return [
        app.config['UPLOAD_FOLDER'],
        os.path.join(app.root_path, "uploads", "repairs")
    ]

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

    for repair in repairs:
        normalized_photos = []
        photo_urls = []
        for photo in repair.get("damage_photos", []):
            normalized_photo = normalize_photo_path(photo)
            if normalized_photo:
                normalized_photos.append(normalized_photo)
                photo_urls.append(url_for("repair_photo", photo_path=normalized_photo))
        repair["damage_photos"] = normalized_photos
        repair["damage_photo_urls"] = photo_urls

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
        uploaded_photos = request.files.getlist("damage_photos")

        valid_photos = [p for p in uploaded_photos if p and p.filename != ""]

        damage_photo_paths = []

        for photo in valid_photos:
            if not allowed_file(photo.filename):
                return render_template(
                    "add_customer.html",
                    error="Only image files are allowed (jpg, jpeg, png, webp)."
                )

            filename = secure_filename(photo.filename)
            extension = filename.rsplit(".", 1)[1].lower()
            unique_filename = f"{uuid.uuid4().hex}.{extension}"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            photo.save(save_path)
            damage_photo_paths.append(f"uploads/repairs/{unique_filename}")

        customer_name = request.form["name"]
        created_at = datetime.now()

        db.customers.insert_one({
            "name": customer_name,
            "phone": request.form["phone"],
            "vehicle": request.form["vehicle"],
            "created_at": created_at,
            "created_date": created_at.strftime("%d-%m-%Y"),
            "created_time": created_at.strftime("%I:%M %p"),
            "is_deleted": False
        })

        db.repairs.insert_one({
            "customer": customer_name,
            "service": request.form["service"],
            "cost": request.form["cost"],
            "notes": request.form.get("notes", "").strip(),
            "damage_photos": damage_photo_paths,
            "status": "Pending",
            "created_at": created_at,
            "created_date": created_at.strftime("%d-%m-%Y"),
            "created_time": created_at.strftime("%I:%M %p")
        })

        return redirect("/dashboard")

    return render_template("add_customer.html", error=None)

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


@app.route("/edit_customer/<id>", methods=["GET", "POST"])
@roles_required("admin", "staff")
def edit_customer(id):
    customer = db.customers.find_one({"_id": ObjectId(id)})
    if not customer:
        abort(404)

    if request.method == "POST":
        old_name = customer.get("name", "")
        new_name = request.form["name"].strip()

        db.customers.update_one(
            {"_id": ObjectId(id)},
            {
                "$set": {
                    "name": new_name,
                    "phone": request.form["phone"].strip(),
                    "vehicle": request.form["vehicle"].strip(),
                    "updated_at": datetime.now()
                }
            }
        )

        if old_name and new_name and old_name != new_name:
            db.repairs.update_many(
                {"customer": old_name},
                {"$set": {"customer": new_name, "updated_at": datetime.now()}}
            )

        return redirect("/dashboard")

    return render_template("edit_customer.html", customer=customer, error=None)

# ---------------- REPAIR ----------------
@app.route("/add_repair", methods=["GET"])
@roles_required("admin", "staff")
def add_repair():
    return redirect("/add_customer")

@app.route("/delete_repair/<id>")
@roles_required("admin", "staff")
def delete_repair(id):
    repair = db.repairs.find_one({"_id": ObjectId(id)})

    # Best effort cleanup for previously uploaded damaged-part photos.
    if repair and repair.get("damage_photos"):
        for relative_path in repair.get("damage_photos", []):
            filename = extract_photo_filename(relative_path)
            for folder in get_photo_storage_dirs():
                photo_path = os.path.join(folder, filename)
                if os.path.exists(photo_path):
                    os.remove(photo_path)
                    break

    db.repairs.delete_one({"_id": ObjectId(id)})
    return redirect("/dashboard")


@app.route("/edit_repair/<id>", methods=["GET", "POST"])
@roles_required("admin", "staff")
def edit_repair(id):
    repair = db.repairs.find_one({"_id": ObjectId(id)})
    if not repair:
        abort(404)

    if request.method == "POST":
        db.repairs.update_one(
            {"_id": ObjectId(id)},
            {
                "$set": {
                    "customer": request.form["customer"].strip(),
                    "service": request.form["service"].strip(),
                    "cost": request.form["cost"].strip(),
                    "notes": request.form.get("notes", "").strip(),
                    "status": request.form["status"],
                    "updated_at": datetime.now()
                }
            }
        )
        return redirect("/dashboard")

    return render_template("edit_repair.html", repair=repair, error=None)


@app.route("/repair-photo/<path:photo_path>")
@roles_required("admin", "staff")
def repair_photo(photo_path):
    filename = extract_photo_filename(photo_path)
    for folder in get_photo_storage_dirs():
        file_path = os.path.join(folder, filename)
        if os.path.exists(file_path):
            return send_from_directory(folder, filename)
    abort(404)

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

