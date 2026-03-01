import os

SECRET_KEY = os.getenv("SECRET_KEY", "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0")
DATABASE_NAME = os.getenv("DATABASE_NAME", "car_management")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "carcorrection")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Aarif6382")
# mongodb+srv://<db_username>:<db_password>@cluster0.mpgvf66.mongodb.net/