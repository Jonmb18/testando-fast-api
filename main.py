import os
import requests
import psycopg2
import urllib.parse
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv

# 🔹 Carregar variáveis de ambiente
load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# 🔹 Parseando a URL do Supabase para formato correto
parsed_url = urllib.parse.urlparse(SUPABASE_URL)

conn = psycopg2.connect(
    dbname=parsed_url.path[1:],
    user=parsed_url.username,
    password=SUPABASE_KEY,
    host=parsed_url.hostname,
    port=parsed_url.port,
    sslmode="require"
)

# 🔹 Inicializar o FastAPI
app = FastAPI()

# 🔹 Estrutura da requisição
class InputText(BaseModel):
    user_id: str
    message: str

# 🔹 Função para salvar conversa no Supabase
def salvar_mensagem(user_id, mensagem, resposta):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO conversations (user_id, message, response) VALUES (%s, %s, %s)",
        (user_id, mensagem, resposta)
    )
    conn.commit()
    cur.close()

# 🔹 Função para conectar-se à API do Mistral AI
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
    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        return response.json()["choices"][0]["text"]
    else:
        return "Erro ao conectar com a API do Mistral AI."

# 🔹 Criar endpoint da API
@app.post("/focusbot")
async def chatbot(input_text: InputText):
    resposta = get_mistral_response(input_text.message)
    salvar_mensagem(input_text.user_id, input_text.message, resposta)
    return {"resposta": resposta}

# 🔹 Rodar o servidor localmente
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
