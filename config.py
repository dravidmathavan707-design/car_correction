# import os

# SECRET_KEY = os.getenv("SECRET_KEY", "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0")
# DATABASE_NAME = os.getenv("DATABASE_NAME", "car_management")
# MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://dravidmathavan707_db_user:m99E606g5W1u6OBo@cluster0.4g0egls.mongodb.net/car_management?retryWrites=true&w=majority&appName=Cluster0")
# ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
# ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin@2026")
# # mongodb+srv://<db_username>:<db_password>@cluster0.mpgvf66.mongodb.net/
# # https://car-correction.onrender.com 
# # mongodb+srv://dravidmathavan707_db_user:m99E606g5W1u6OBo@cluster0.4g0egls.mongodb.net/car_management?retryWrites=true&w=majority&appName=Cluster0


# new version

import os

SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
DATABASE_NAME = os.getenv("DATABASE_NAME", "car_management")
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb+srv://dravidmathavan707_db_user:m99E606g5W1u6OBo@cluster0.4g0egls.mongodb.net/car_management?retryWrites=true&w=majority&appName=Cluster0"
)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin@2026")

# Repair photo upload settings
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.join("static", "uploads", "repairs"))
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 10 * 1024 * 1024))
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}