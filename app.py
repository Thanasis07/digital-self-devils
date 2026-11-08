import random
import time
import streamlit as st
from groq import Groq
from supabase import create_client

# 1. Ρύθμιση Σελίδας
st.set_page_config(page_title="AI or Not", layout="centered")
st.title("AI or Not - Online Multiplayer")

# Εξαφάνιση του default μενού, του Deploy button και του footer του Streamlit
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# 2. Ανάγνωση Secrets & Init
groq_key = st.secrets.get("GROQ_API_KEY")
supabase_url = st.secrets.get("SUPABASE_URL")
supabase_key = st.secrets.get("SUPABASE_KEY")

if not groq_key or not supabase_url or not supabase_key:
    st.error("Λείπουν διαπιστευτήρια στο .streamlit/secrets.toml")
    st.stop()

groq_client = Groq(api_key=groq_key)
supabase = create_client(supabase_url, supabase_key)


def generate_ai_reply(prompt, system_instruction):
    time.sleep(random.uniform(1.5, 3.0))
    completion = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=150
    )
    return completion.choices[0].message.content


# --- ΒΗΜΑ 1: Αρχική Είσοδος (Όνομα & Ρόλος) ---
if "user_name" not in st.session_state:
    st.subheader("1. Καλώς ήρθες!")
    name_input = st.text_input("Το όνομά σου:")
    role_input = st.selectbox("Επίλεξε το ρόλο σου:", [
                              "Ανακριτής", "Δημιουργός Προφίλ"])

    if st.button("Είσοδος"):
        if name_input.strip():
            st.session_state["user_name"] = name_input.strip()
            st.session_state["user_role"] = role_input
            st.rerun()
        else:
            st.warning("Πρέπει να βάλεις ένα όνομα για να συνεχίσεις.")
    st.stop()

# Εμφάνιση του προφίλ στο Sidebar
with st.sidebar:
    st.write(f"**Παίκτης:** {st.session_state['user_name']}")
    st.write(f"**Ρόλος:** {st.session_state['user_role']}")
    if st.button("Αλλαγή Λογαριασμού"):
        st.session_state.clear()
        st.rerun()

# --- ΒΗΜΑ 2: Διαχείριση Lobby ---
if "current_room" not in st.session_state:
    st.subheader("2. Διαχείριση Lobby")

    # 2A. Αν είναι Δημιουργός Προφίλ -> Φτιάχνει Lobby
    if st.session_state["user_role"] == "Δημιουργός Προφίλ":
        st.write("### Δημιουργία Νέου Lobby")
        style_input = st.text_area("Στυλ & Χαρακτηριστικά του AI σου:",
                                   value="Μιλάω κοφτά, χρησιμοποιώ slang, πίνω πολύ καφέ.")
        room_code_input = st.text_input(
            "Κωδικός Δωματίου:", value=f"ROOM{random.randint(1000, 9999)}").upper()
        is_priv = st.checkbox(
            "Ιδιωτικό Δωμάτιο (Δεν θα φαίνεται στη δημόσια λίστα)")

        if st.button("Δημιουργία Lobby"):
            if not style_input.strip():
                st.warning("Γράψε λίγα χαρακτηριστικά για το προφίλ.")
            else:
                supabase.table("rooms").upsert({
                    "room_code": room_code_input,
                    "host_name": st.session_state["user_name"],
                    "host_style": style_input.strip(),
                    "is_private": is_priv,
                    "status": "waiting_guest",
                    "turn_status": "waiting_prompt"
                }).execute()
                st.session_state["current_room"] = room_code_input
                st.rerun()

    # 2Β. Αν είναι Ανακριτής -> Ψάχνει / Μπαίνει σε Lobby
    else:
        st.write("### Εύρεση Lobby")
        tab_pub, tab_priv = st.tabs(["Δημόσια Lobbies", "Ιδιωτικό Lobby"])

        with tab_pub:
            public_rooms = supabase.table("rooms").select(
                "*").eq("is_private", False).eq("status", "waiting_guest").execute()
            if public_rooms.data:
                for r in public_rooms.data:
                    col_info, col_btn = st.columns([3, 1])
                    col_info.write(
                        f"**Δωμάτιο:** {r['room_code']} (Δημιουργός: {r['host_name']})")
                    if col_btn.button("Σύνδεση", key=f"join_{r['room_code']}"):
                        supabase.table("rooms").update({
                            "guest_name": st.session_state["user_name"],
                            "status": "active"
                        }).eq("room_code", r['room_code']).execute()
                        st.session_state["current_room"] = r['room_code']
                        st.rerun()
            else:
                st.info("Δεν βρέθηκαν διαθέσιμα δημόσια lobbies.")

            if st.button("Ανανέωση Λίστας"):
                st.rerun()

        with tab_priv:
            priv_code = st.text_input(
                "Βάλε τον κωδικό του δωματίου:").strip().upper()
            if st.button("Σύνδεση σε Ιδιωτικό"):
                if priv_code:
                    res = supabase.table("rooms").select(
                        "*").eq("room_code", priv_code).execute()
                    if res.data and res.data[0]["status"] == "waiting_guest":
                        supabase.table("rooms").update({
                            "guest_name": st.session_state["user_name"],
                            "status": "active"
                        }).eq("room_code", priv_code).execute()
                        st.session_state["current_room"] = priv_code
                        st.rerun()
                    else:
                        st.error("Το lobby δεν υπάρχει ή είναι ήδη γεμάτο.")
    st.stop()

# --- ΒΗΜΑ 3: Το Παιχνίδι (Live Refresh) ---


@st.fragment(run_every=2)
def play_game():
    room_code = st.session_state["current_room"]
    role = st.session_state["user_role"]

    res = supabase.table("rooms").select(
        "*").eq("room_code", room_code).execute()

    # Έλεγχος αν το lobby έκλεισε (π.χ. αν ο άλλος πάτησε Exit)
    if not res.data:
        st.warning("Το lobby έκλεισε ή διαγράφηκε (Exit).")
        if st.button("Επιστροφή στο Μενού"):
            st.session_state.pop("current_room", None)
            st.rerun()
        return

    room = res.data[0]

    # Αναμονή για Ανακριτή (Αν είσαι ο Host)
    if room["status"] == "waiting_guest":
        st.info(f"Αναμονή για Ανακριτή στο Lobby: **{room_code}**...")
        if st.button("Ακύρωση & Έξοδος"):
            supabase.table("rooms").delete().eq(
                "room_code", room_code).execute()
            st.session_state.pop("current_room", None)
            st.rerun()
        return

    st.subheader(
        f"Lobby: {room_code} | Δημιουργός: {room['host_name']} vs Ανακριτής: {room['guest_name']}")

    # Κουμπί Exit πάντα διαθέσιμο πάνω δεξιά
    col_empty, col_exit = st.columns([4, 1])
    with col_exit:
        if st.button("Exit Lobby"):
            supabase.table("rooms").delete().eq(
                "room_code", room_code).execute()
            st.session_state.pop("current_room", None)
            st.rerun()

    st.divider()

    # --- ΟΨΗ ΑΝΑΚΡΙΤΗ ---
    if role == "Ανακριτής":
        st.caption(f"Εξετάζεις το προφίλ του: {room['host_name']}")

        if room["turn_status"] == "waiting_prompt":
            if prompt := st.chat_input("Γράψε την ερώτησή σου..."):
                responder = random.choice(["AI", "Human"])
                system_instruction = f"Είσαι το Digital Twin του {room['host_name']}. Στυλ: {room['host_style']}. Απάντα σε 1-2 προτάσεις στα ελληνικά."

                if responder == "AI":
                    reply = generate_ai_reply(prompt, system_instruction)
                    t_status = "answered"
                else:
                    reply = ""
                    t_status = "waiting_human"

                supabase.table("rooms").update({
                    "current_prompt": prompt,
                    "current_reply": reply,
                    "real_source": responder,
                    "turn_status": t_status
                }).eq("room_code", room_code).execute()
                st.rerun()

        if room.get("current_prompt"):
            st.write(f"**Ερώτηση:** {room['current_prompt']}")

            if room["turn_status"] == "waiting_human":
                st.info("Το προφίλ πληκτρολογεί την απάντησή του...")
            elif room["turn_status"] == "answered":
                st.write(f"**Απάντηση:** {room['current_reply']}")
                st.write("**Ποιος νομίζεις ότι απάντησε;**")

                col_ai, col_hu = st.columns(2)
                if col_ai.button("AI / Twin"):
                    correct = (room["real_source"] == "AI")
                    supabase.table("rooms").update({"turn_status": "finished"}).eq(
                        "room_code", room_code).execute()
                    st.session_state["res_msg"] = (
                        "success" if correct else "error", "Σωστά! Ήταν το AI." if correct else "Λάθος! Ήταν ο αληθινός άνθρωπος.")
                    st.rerun()
                if col_hu.button("Αληθινός Άνθρωπος"):
                    correct = (room["real_source"] == "Human")
                    supabase.table("rooms").update({"turn_status": "finished"}).eq(
                        "room_code", room_code).execute()
                    st.session_state["res_msg"] = (
                        "success" if correct else "error", "Σωστά! Ήταν ο αληθινός άνθρωπος." if correct else "Λάθος! Ήταν το AI.")
                    st.rerun()
            elif room["turn_status"] == "finished":
                st.write(f"**Απάντηση:** {room['current_reply']}")
                if "res_msg" in st.session_state:
                    tp, msg = st.session_state["res_msg"]
                    st.success(msg) if tp == "success" else st.error(msg)

                if st.button("Rematch (Νέος Γύρος)"):
                    supabase.table("rooms").update({
                        "turn_status": "waiting_prompt",
                        "current_prompt": "",
                        "current_reply": "",
                        "real_source": ""
                    }).eq("room_code", room_code).execute()
                    st.session_state.pop("res_msg", None)
                    st.rerun()

    # --- ΟΨΗ ΔΗΜΙΟΥΡΓΟΥ ΠΡΟΦΙΛ ---
    else:
        st.caption(f"Παίζεις απέναντι στον Ανακριτή: {room['guest_name']}")

        if room["turn_status"] == "waiting_human":
            st.warning(f"Ερώτηση Ανακριτή: {room['current_prompt']}")
            h_ans = st.text_input("Γράψε την απάντησή σου:")
            if st.button("Αποστολή"):
                supabase.table("rooms").update({
                    "current_reply": h_ans,
                    "turn_status": "answered"
                }).eq("room_code", room_code).execute()
                st.rerun()
        elif room["turn_status"] == "answered":
            st.info("Ο Ανακριτής διαβάζει την απάντηση και μαντεύει...")
        elif room["turn_status"] == "finished":
            st.success(
                "Ο γύρος ολοκληρώθηκε! Αναμονή για Rematch από τον Ανακριτή.")
        elif room["turn_status"] == "waiting_prompt":
            st.info("Αναμονή για ερώτηση από τον Ανακριτή...")


# Εκτέλεση του Παιχνιδιού
play_game()
