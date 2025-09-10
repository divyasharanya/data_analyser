
import os

# Aiven PostgreSQL connection settings
DB_HOST = "your_HOST"      # e.g., pg-12345.aivencloud.com
DB_PORT = "14586"                # check in console
DB_NAME = "defaultdb"            # usually defaultdb
DB_USER = "avnadmin"
DB_PASS = "YOUR_DB-PASS"

SQLALCHEMY_DATABASE_URI = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?sslmode=require"
)

SQLALCHEMY_TRACK_MODIFICATIONS = False
