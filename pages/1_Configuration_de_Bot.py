import json
import streamlit as st

from app.db import get_creator_bot_id, get_bot, parse_persona_json, upsert_bot

st.set_page_config(page_title="Configuration créatrice", layout="wide")

st.title("Configuration créatrice")

creator_id = get_creator_bot_id()
creator_row = get_bot(int(creator_id)) if creator_id else None
persona = parse_persona_json(creator_row) if creator_row else {}

if "creator_saved" not in st.session_state:
    st.session_state["creator_saved"] = False

if st.session_state.get("creator_saved"):
    st.success("Créatrice enregistrée.")
    if st.button("OK"):
        st.session_state["creator_saved"] = False
        st.rerun()
    st.stop()

name = st.text_input(
    "Nom du bot",
    value=(persona.get("name") or "Créatrice"),
)

col1, col2, col3 = st.columns(3)
with col1:
    dominance = st.slider("dominance", 1, 5, int(persona.get("dominance", 3)))
    audacity = st.slider("audacity", 1, 5, int(persona.get("audacity", 3)))
    sales_tactic = st.slider("sales_tactic", 1, 5, int(persona.get("sales_tactic", 2)))
with col2:
    tone = st.slider("tone", 1, 5, int(persona.get("tone", 2)))
    emotion = st.slider("emotion", 1, 5, int(persona.get("emotion", 3)))
    initiative = st.slider("initiative", 1, 5, int(persona.get("initiative", 3)))
with col3:
    vocabulary = st.slider("vocabulary", 1, 5, int(persona.get("vocabulary", 3)))
    emojis = st.slider("emojis", 1, 5, int(persona.get("emojis", 3)))
    imperfection = st.slider("imperfection", 1, 5, int(persona.get("imperfection", 1)))

base_prompt = st.text_area("base_prompt", value=str(persona.get("base_prompt", "")), height=140)

persona_data = {
    "name": name.strip() or "Bot",
    "base_prompt": base_prompt,
    "dominance": dominance,
    "audacity": audacity,
    "sales_tactic": sales_tactic,
    "tone": tone,
    "emotion": emotion,
    "initiative": initiative,
    "vocabulary": vocabulary,
    "emojis": emojis,
    "imperfection": imperfection,
}

c1, c2, c3 = st.columns([1, 1, 3])
with c1:
    if st.button("Enregistrer", type="primary"):
        upsert_bot(int(creator_id) if creator_id else None, "Créatrice", persona_data)
        st.session_state["creator_saved"] = True
        st.rerun()
with c2:
    st.write("")
with c3:
    st.write("")

with st.expander("Voir JSON persona_data", expanded=False):
    st.code(json.dumps(persona_data, ensure_ascii=False, indent=2), language="json")
