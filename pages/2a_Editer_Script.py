import streamlit as st

st.switch_page("pages/2_Builder_de_Scripts.py")

from app.db import (
    add_step,
    delete_step,
    get_script,
    list_steps,
    move_step,
    update_step,
    upsert_script,
)

st.set_page_config(page_title="Éditer Script", layout="wide")

script_id = st.session_state.get("script_edit_id")
script_row = get_script(int(script_id)) if script_id else None

if "script_saved" not in st.session_state:
    st.session_state["script_saved"] = False

if st.session_state.get("script_saved"):
    st.success("Script enregistré.")
    c1, c2 = st.columns([1, 5])
    with c1:
        if st.button("OK", type="primary"):
            st.session_state["script_saved"] = False
            st.switch_page("pages/2_Builder_de_Scripts.py")
    st.stop()

st.title("Éditer Script")

name = st.text_input("Nom du script", value=(script_row["name"] if script_row else ""))
description = st.text_area("Description", value=(script_row["description"] if script_row else ""), height=90)

c1, c2, c3 = st.columns([1, 1, 3])
with c1:
    if st.button("Enregistrer", type="primary"):
        new_id = upsert_script(
            int(script_row["id"]) if script_row else None,
            name.strip() or "Script",
            description,
            None,
        )
        st.session_state["script_edit_id"] = int(new_id)
        st.session_state["script_saved"] = True
        st.rerun()
with c2:
    if st.button("Retour"):
        st.session_state["script_saved"] = False
        st.switch_page("pages/2_Builder_de_Scripts.py")

if not script_row:
    st.info("Enregistre d'abord le script pour gérer ses étapes.")
    st.stop()

steps = list_steps(int(script_row["id"]))

st.subheader("Étapes")

with st.expander("+ Ajouter une étape", expanded=(len(steps) == 0)):
    step_type = st.selectbox("Type", options=["text", "media_text"])
    is_paywall = st.checkbox("Paywall", value=False)
    script_text = st.text_area("Texte / phrase-modèle (script)", height=120)
    media_desc = None
    if step_type == "media_text":
        media_desc = st.text_area("Description du média (photo/vidéo)", height=80)

    if st.button("Ajouter", type="primary"):
        if not script_text.strip():
            st.error("Le texte de l'étape est requis.")
        else:
            add_step(int(script_row["id"]), step_type, script_text.strip(), media_desc, is_paywall)
            st.rerun()

for s in steps:
    with st.container(border=True):
        left, right = st.columns([4, 1])
        with left:
            st.markdown(f"### Étape {int(s['position'])}")
            st.caption(f"type={s['step_type']} | paywall={bool(int(s['is_paywall']))}")

            edit_type = st.selectbox(
                "Type",
                options=["text", "media_text"],
                index=["text", "media_text"].index(s["step_type"]),
                key=f"type_{s['id']}",
            )
            edit_paywall = st.checkbox(
                "Paywall",
                value=bool(int(s["is_paywall"])) ,
                key=f"paywall_{s['id']}",
            )
            edit_text = st.text_area(
                "Script",
                value=s["script_text"],
                height=100,
                key=f"text_{s['id']}",
            )
            edit_media = None
            if edit_type == "media_text":
                edit_media = st.text_area(
                    "Media desc",
                    value=s["media_desc"] or "",
                    height=70,
                    key=f"media_{s['id']}",
                )

        with right:
            if st.button("↑", key=f"up_{s['id']}"):
                move_step(int(script_row["id"]), int(s["id"]), "up")
                st.rerun()
            if st.button("↓", key=f"down_{s['id']}"):
                move_step(int(script_row["id"]), int(s["id"]), "down")
                st.rerun()
            if st.button("Sauver", key=f"save_{s['id']}", type="primary"):
                if not edit_text.strip():
                    st.error("Script vide.")
                else:
                    update_step(int(s["id"]), edit_type, edit_text.strip(), edit_media, edit_paywall)
                    st.rerun()
            if st.button("Supprimer", key=f"del_{s['id']}"):
                delete_step(int(s["id"]))
                st.rerun()
