import os
import pymysql
from flask import Flask, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

def get_db_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        ssl={"ca": os.getenv("DB_SSL_CA")},
        cursorclass=pymysql.cursors.DictCursor
    )

@app.route("/")
def home():
    return {"status": "API rodando no Render 🚀"}

@app.route("/db-test")
def db_test():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT DATABASE() AS db, VERSION() AS version;")
            result = cursor.fetchone()
        conn.close()
        return jsonify({
            "conectado": True,
            "database": result["db"],
            "version": result["version"]
        })
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
