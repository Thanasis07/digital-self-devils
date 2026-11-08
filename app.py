import random
import streamlit as st
from google import genai

# 1. Ρύθμιση Σελίδας Streamlit
st.set_page_config(page_title="AI or Not", page_icon="🤖", layout="centered")

st.title("AI or Not")
st.caption("Μπορείς να καταλάβεις αν σου απαντάει ο αληθινός φοιτητής ή το AI;")

# 2. Ασφαλής Ανάγνωση του API Key
api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error("❌ Δεν βρέθηκε το GEMINI_API_KEY στο .streamlit/secrets.toml!")
    st.stop()

# 3. Αρχικοποίηση του Gemini Client
client = genai.Client(api_key=api_key)
