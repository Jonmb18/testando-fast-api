import os
import requests
import psycopg2
import urllib.parse
import time
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from psycopg2 import pool

# 🔹 Load environment variables
load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# 🔹 Validate environment variables
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ ERROR: SUPABASE_URL or SUPABASE_KEY is missing in environment variables!")

# 🔹 Parse Supabase URL
parsed_url = urllib.parse.urlparse(SUPABASE_URL)

# Ensure required database environment variables exist
DB_USER = os.getenv("SUPABASE_USER")
DB_PASSWORD = os.getenv("SUPABASE_PASSWORD")
DB_HOST = os.getenv("SUPABASE_HOST")
DB_PORT = os.getenv("SUPABASE_PORT")
DB_NAME = os.getenv("SUPABASE_DB")

if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    raise ValueError("❌ ERROR: One or more required database environment variables are missing!")

# Convert port to integer safely
try:
    DB_PORT = int(DB_PORT)
except ValueError:
    raise ValueError("❌ ERROR: SUPABASE_PORT must be an integer!")

# 🔹 Database Connection Pool with Improved Error Handling
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

def create_connection_pool():
    for attempt in range(MAX_RETRIES):
        try:
            print(f"🔄 Attempting to connect to database... (Try {attempt + 1}/{MAX_RETRIES})")
            return pool.SimpleConnectionPool(
                1, 10, 
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                connect_timeout=10  # Ensures quick failure instead of indefinite hanging
            )
        except psycopg2.OperationalError as e:
            print(f"⚠️ Connection attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise Exception("❌ ERROR: Database connection failed after multiple attempts. Check Supabase settings!")

# Initialize the connection pool
db_pool = create_connection_pool()

def get_db_connection():
    try:
        return db_pool.getconn()
    except Exception as e:
        raise Exception(f"❌ ERROR: Failed to retrieve a database connection. {e}")

def release_db_connection(conn):
    try:
        db_pool.putconn(conn)
    except Exception as e:
        print(f"⚠️ Warning: Failed to release connection: {e}")

# 🔹 Initialize FastAPI
app = FastAPI()

# 🔹 Request model
class InputText(BaseModel):
    user_id: str
    message: str

# 🔹 Function to save conversation to Supabase
def salvar_mensagem(user_id, mensagem, resposta):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO conversations (user_id, message, response) VALUES (%s, %s, %s)",
            (user_id, mensagem, resposta)
        )
        conn.commit()
    except Exception as e:
        print(f"❌ Database error: {e}")
    finally:
        cur.close()
        release_db_connection(conn)  # Properly release connection

# 🔹 Function to call Mistral AI API
def get_mistral_response(user_input):
    url = "https://api.mistral.ai/v1/completions"
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "mistral-medium",
        "prompt": user_input,
        "max_tokens": 200,
        "temperature": 0.7
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json().get("choices", [{}])[0].get("text", "No response received.")
    except requests.exceptions.RequestException as e:
        return f"❌ ERROR: Mistral API error: {str(e)}"

# 🔹 API endpoint
@app.post("/focusbot")
async def chatbot(input_text: InputText):
    resposta = get_mistral_response(input_text.message)
    salvar_mensagem(input_text.user_id, input_text.message, resposta)
    return {"resposta": resposta}

# 🚀 Railway automatically runs Uvicorn, so no need for a `__main__` block
