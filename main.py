import os
import requests
import psycopg2
import urllib.parse
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv

# 🔹 Load environment variables
load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# 🔹 Validate environment variables
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL or SUPABASE_KEY is not set in environment variables.")

# 🔹 Parse Supabase URL
parsed_url = urllib.parse.urlparse(SUPABASE_URL)

# 🔹 Database connection function
def get_db_connection():
    return psycopg2.connect(
        dbname=parsed_url.path[1:],
        user=parsed_url.username,
        password=SUPABASE_KEY,
        host=parsed_url.hostname,
        port=parsed_url.port,
        sslmode="require"
    )

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
        print(f"Database error: {e}")
    finally:
        cur.close()
        conn.close()  # Ensure the connection is closed

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
        return f"Erro na API Mistral: {str(e)}"

# 🔹 API endpoint
@app.post("/focusbot")
async def chatbot(input_text: InputText):
    resposta = get_mistral_response(input_text.message)
    salvar_mensagem(input_text.user_id, input_text.message, resposta)
    return {"resposta": resposta}

# 🚀 Removed the Uvicorn `if __name__ == "__main__"` block
# Railway will handle running Uvicorn with the command:
# uvicorn main:app --host 0.0.0.0 --port $PORT
