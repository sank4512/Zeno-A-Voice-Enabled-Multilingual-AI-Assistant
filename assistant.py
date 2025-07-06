import streamlit as st
import os, whisper, sounddevice as sd, numpy as np
from datetime import datetime
import requests, wikipedia, tempfile, time, pygame
from langdetect import detect
from gtts import gTTS
import google.generativeai as genai
from translate import Translator
from sqlalchemy import create_engine, Column, String
from sqlalchemy.orm import sessionmaker, declarative_base

# --- Gemini & Whisper init (existing) ---
genai.configure(api_key="AIzaSyBGzLZFa0NkzSqrC7mymT2Nui5XpdWsnt8")
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

model = whisper.load_model("base")
pygame.init()
SUPPORTED_LANGUAGES = ['en','hi','mr',...]  # add more
LANGUAGE_MAP = {
    "en": "English",
    "hi": "Hindi",
    "mr": "Marathi",
    "gu": "Gujarati",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
    "bn": "Bengali",
    "ur": "Urdu",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "or": "Odia",
    "as": "Assamese",
    # add more if needed
}


# --- Neon DB setup using st.connection ---
conn = st.connection("neon", type="sql")  # automatically reads secrets
Session = sessionmaker(bind=conn.session.bind)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    username = Column(String, primary_key=True)
    password = Column(String, nullable=False)

# Ensure table exists
Base.metadata.create_all(bind=conn.session.bind)

# --- Auth logic ---
st.set_page_config(page_title="Zeno Assistant", layout="wide")

# Apply custom dark theme to entire app
st.markdown("""
    <style>
    body {
        background-color: #000000;
        color: #FFFFFF;
    }
    .stApp {
        background-color: #000000;
        color: #FFFFFF;
    }
    h1, h2, h3, h4, h5, h6, p, div {
        color: #FFFFFF;
    }
    input, textarea, .stTextInput > div > div > input {
        background-color: #1e1e1e;
        color: #ffffff;
        border: 1px solid #555555;
    }
    button[kind="primary"], .stButton > button {
        background-color: #FF0000 !important;
        color: white !important;
        border-radius: 5px;
        border: none;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)


if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.show_login = True

def login(username, password):
    session = Session()
    user = session.query(User).filter_by(username=username).first()
    session.close()
    return user and user.password == password

def signup(username, password):
    session = Session()
    if session.query(User).filter_by(username=username).first():
        session.close(); return False
    session.add(User(username=username,password=password))
    session.commit(); session.close(); return True


# --- UI: login/signup toggle ---
if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align:center;'>🔐 Login</h2>" if st.session_state.show_login else "<h2 style='text-align:center;'>📝 Sign Up</h2>", unsafe_allow_html=True)

    u = st.text_input("Username", key="username_input")
    p = st.text_input("Password", type="password", key="password_input")

    if st.button("Submit"):
        if st.session_state.show_login:
            if login(u, p):
                st.session_state.authenticated = True
            else:
                st.error("Invalid credentials")
        else:
            if signup(u, p):
                st.success("Account created!")
                st.session_state.show_login = True
            else:
                st.error("Username exists")

    if st.button("Switch to " + ("Sign Up" if st.session_state.show_login else "Login")):
        st.session_state.show_login = not st.session_state.show_login

    st.stop()


# --- Core chat UI below here ---
st.markdown("""
    <style>
    body, .stApp {
        background-color: #121212;
        color: white;
    }
    .stTextInput > div > div > input,
    .stButton > button {
        background-color: #1f1f1f;
        color: white;
    }
    .stMarkdown {
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

st.set_page_config(page_title="Zeno", layout="wide")
st.markdown("<h2 style='text-align:center;'>🤖 Zeno – AI Assistant</h2>", unsafe_allow_html=True)
if "chat_history" not in st.session_state: st.session_state.chat_history=[]

# Render chat bubbles
for ts, role, msg in st.session_state.chat_history:
    st.markdown(f"**{ts} | {role}**: {msg}")

# Input area
user_msg = st.text_input("Your Message", key="input", label_visibility="collapsed")

# Aligned buttons below
col1, col2 = st.columns([1, 1])
with col1:
    send = st.button("➡️ Send", use_container_width=True)
with col2:
    rec = st.button("🎤 Speak", use_container_width=True)


# Process send
def chat_reply(text, lang):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.chat_history.append((timestamp, "You", text))

    def reply(q):
        try:
            return gemini_model.generate_content(f"Answer in {LANGUAGE_MAP.get(lang, 'English')}: {q}").text.strip()
        except:
            return "Sorry, I couldn't generate a reply."

    answer = reply(text)
    st.session_state.chat_history.append((timestamp, "Zeno", answer))

    # speak
    if lang not in SUPPORTED_LANGUAGES: lang='en'
    tts = gTTS(text=Translator(to_lang=lang).translate(answer), lang=lang)
    path = os.path.join(tempfile.gettempdir(),f"{time.time()}.mp3")
    tts.save(path)
    pygame.mixer.music.load(path); pygame.mixer.music.play()

if send and user_msg:
    lang = detect(user_msg)
    chat_reply(user_msg, lang)
    # Reset using rerun-safe method
    st.rerun()


if rec:
    duration, sr = 5,16000
    recarr = sd.rec(int(duration*sr), samplerate=sr,channels=1,dtype='int16'); sd.wait()
    wavarr = tempfile.NamedTemporaryFile(delete=False,suffix=".wav")
    import scipy.io.wavfile as wav
    wav.write(wavarr.name,sr,recarr)
    text = model.transcribe(wavarr.name)["text"]
    lang = detect(text)
    chat_reply(text, lang)
    os.unlink(wavarr.name)

# PDF download

from fpdf import FPDF

# PDF Download button
if st.button("📄 Download PDF"):
    pdf = FPDF()
    pdf.add_page()

    # Add Unicode font (DejaVuSans)
    font_path = os.path.join(os.getcwd(), "DejaVuSans.ttf")
    pdf.add_font("DejaVu", "", font_path, uni=True)
    pdf.set_font("DejaVu", size=12)

    # Add chat history
    for ts, role, msg in st.session_state.chat_history:
        pdf.multi_cell(0, 10, f"{ts} | {role}: {msg}")

    pdf_path = os.path.join(tempfile.gettempdir(), "chat.pdf")
    pdf.output(pdf_path, "F")

    with open(pdf_path, "rb") as f:
        st.download_button("Download PDF", f, "chat.pdf", "application/pdf")

st.caption("🔊 Powered by Whisper, Gemini, Streamlit | Built with ❤️ by Sanket")


