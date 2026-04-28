import streamlit as st
from google import genai
from google.genai import types
import json
import firebase_admin
from firebase_admin import credentials, firestore
import base64
import tempfile
import os

# ── Gemini Setup ──────────────────────────
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
MODEL = "gemini-2.5-flash"

# ── Firebase Setup ────────────────────────
if not firebase_admin._apps:
    cred = credentials.Certificate(
    json.loads(st.secrets["firebase_key"]))
    firebase_admin.initialize_app(cred)

db = firestore.client()


# ── Firebase Functions ────────────────────

def save_need(need_data):
    db.collection("needs").add(need_data)

def get_all_needs():
    docs = db.collection("needs").stream()
    needs = []
    for doc in docs:
        need = doc.to_dict()
        need["doc_id"] = doc.id
        needs.append(need)
    return needs

def resolve_need(doc_id):
    db.collection("needs").document(doc_id).update({"resolved": True})

def add_volunteer_to_need(doc_id, volunteer_name):
    doc_ref = db.collection("needs").document(doc_id)
    doc = doc_ref.get().to_dict()
    volunteers = doc.get("volunteers", [])
    if volunteer_name not in volunteers:
        volunteers.append(volunteer_name)
        doc_ref.update({"volunteers": volunteers})
        return True
    return False


# ── Gemini Functions ──────────────────────

def extract_need(free_text):
    prompt = f"""
    Extract information from this community need report.
    Return ONLY a raw JSON object. No markdown, no explanation, no backticks.

    Use this exact structure:
    {{
        "location": "village or area name",
        "category": "Water/Food/Medical/Infrastructure/Education",
        "affected_count": 0,
        "urgency_score": 0,
        "risk_flags": ["risk1", "risk2"],
        "crisis_brief": "2 sentence urgent summary",
        "lat": 0.0,
        "lng": 0.0,
        "resolved": false
    }}

    URGENCY SCORING RULES:
    - 80-100: People without food/water 2+ days, medical emergency, children/elderly at risk
    - 60-79: Large groups affected, essential services down, vulnerable people involved
    - 40-59: Moderate impact, some services affected
    - 0-39: Minor issues, infrastructure problems with no immediate human risk

    IMPORTANT for coordinates:
    - Use real accurate GPS coordinates for the location
    - Karnataka India coordinates are lat 11-18, lng 74-78
    - Hubballi: lat 15.3647, lng 75.1240
    - Dharwad: lat 15.4589, lng 75.0078
    - Gadag: lat 15.4166, lng 75.6167
    - Belagavi: lat 15.8497, lng 74.4977
    - Bengaluru: lat 12.9716, lng 77.5946
    - If unknown default to lat 15.3647, lng 75.1240

    Report: {free_text}
    """

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt
    )

    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def generate_volunteer_briefing(need, volunteer_name, volunteer_skill):
    prompt = f"""
    Write a short motivating task briefing for a volunteer.
    3 sentences maximum.
    Volunteer name: {volunteer_name}
    Volunteer skill: {volunteer_skill}
    Crisis: {need['crisis_brief']}
    Location: {need['location']}
    Make it warm, personal and urgent.
    Start with their name.
    """

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt
    )
    return response.text


def transcribe_audio(audio_bytes):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        f.write(audio_bytes)
        temp_path = f.name
    with open(temp_path, "rb") as f:
        audio_data = f.read()
    audio_b64 = base64.b64encode(audio_data).decode()
    os.unlink(temp_path)

    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part(text="Transcribe this audio accurately. Return only the spoken text, nothing else."),
            types.Part(inline_data=types.Blob(
                mime_type="audio/wav",
                data=audio_b64
            ))
        ]
    )
    return response.text.strip()