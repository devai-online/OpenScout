import os
from dotenv import load_dotenv

load_dotenv()

# Groq API
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Database
DB_PATH = os.getenv("DB_PATH", "leads.db")
DB_URL = f"sqlite:///{DB_PATH}"

# Server
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
