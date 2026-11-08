import random
import time
import streamlit as st
from groq import Groq
from supabase import create_client

# 1. Ρύθμιση Σελίδας
st.set_page_config(page_title="AI or Not", layout="centered")
st.title("AI or Not - Online Multiplayer")

# 2. Ανάγνωση Secrets
groq_key = st.secrets.get("GROQ_API_KEY")
supabase_url = st.secrets.get("SUPABASE_URL")
supabase_key = st.secrets.get("SUPABASE_KEY")

if not groq_key or not supabase_url or not supabase_key:
    st.error("Λείπουν διαπιστευτήρια στο .streamlit/secrets.toml")
    st.stop()

groq_client = Groq(api_key=groq_key)
supabase = create_client(supabase_url, supabase_key)

# 3. AI Generation με καθυστέρηση & χωρίς απόκρυψη σφαλμάτων


def generate_ai_reply(prompt, system_instruction):
    # Τεχνητή καθυστέρηση για φυσική απόκριση (1.5 έως 3.5 δευτερόλεπτα)
    time.sleep(random.uniform(1.5, 3.5))

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


# 4. Lobby & Επιλογή Ρόλου
st.subheader("1. Δωμάτιο και Προφίλ")
col_role, col_room = st.columns(2)

with col_role:
    role = st.selectbox("Ρόλος:", ["Δημιουργός Προφίλ", "Ανακριτής"])

with col_room:
    room_code = st.text_input("Κωδικός Δωματίου:", value="DEV1").upper()

if role == "Δημιουργός Προφίλ":
    twin_name = st.text_input("Όνομα Προφίλ:", value="Θανάσης")
    twin_style = st.text_area("Στυλ και Χαρακτηριστικά:",
                              value="Μιλάω κοφτά, χρησιμοποιώ slang, πίνω πολύ καφέ.")

    if st.button("Δημιουργία / Ενημέρωση Δωματίου"):
        supabase.table("rooms").upsert({
            "room_code": room_code,
            "twin_name": twin_name,
            "twin_style": twin_style,
            "status": "waiting",
            "current_prompt": "",
            "current_reply": "",
            "real_source": ""
        }).execute()
        st.success(
            f"Το δωμάτιο {room_code} δημιουργήθηκε με το προφίλ: {twin_name}")

st.divider()

# 5. Live Ανακριτήριο (Ανανέωση κάθε 2 δευτερόλεπτα)


@st.fragment(run_every=2)
def render_game():
    st.subheader(f"2. Ανακριτήριο (Δωμάτιο: {room_code})")

    room_data = supabase.table("rooms").select(
        "*").eq("room_code", room_code).execute()

    if not room_data.data:
        st.info(
            "Το δωμάτιο δεν έχει δημιουργηθεί ακόμα. Ο Δημιουργός πρέπει να πατήσει 'Δημιουργία Δωματίου'.")
        return

    room = room_data.data[0]

    # --- ΟΨΗ ΑΝΑΚΡΙΤΗ ---
    if role == "Ανακριτής":
        st.caption(f"Εξετάζεις το προφίλ: {room.get('twin_name', 'Άγνωστος')}")

        # Αποστολή νέας ερώτησης
        if room.get("status") in ["waiting", "finished", None]:
            if prompt := st.chat_input("Γράψε την ερώτησή σου..."):
                responder = random.choice(["AI", "Human"])

                system_instruction = f"""
                Είσαι το Digital Twin του {room.get('twin_name')}.
                Στυλ και Χαρακτηριστικά: {room.get('twin_style')}.
                
                ΚΑΝΟΝΕΣ:
                1. Απάντα αυστηρά σε 1-2 προτάσεις στα ελληνικά.
                2. Μην αποκαλύψεις ΠΟΤΕ ότι είσαι AI.
                3. Αν σε ρωτήσουν αν είσαι άνθρωπος, επέμεινε ότι είσαι ο αληθινός {room.get('twin_name')}.
                """

                if responder == "AI":
                    reply = generate_ai_reply(prompt, system_instruction)
                    status = "answered"
                else:
                    reply = ""
                    status = "waiting_human"

                supabase.table("rooms").update({
                    "current_prompt": prompt,
                    "current_reply": reply,
                    "real_source": responder,
                    "status": status
                }).eq("room_code", room_code).execute()
                st.rerun()

        # Εμφάνιση εξέλιξης ερώτησης
        if room.get("current_prompt"):
            st.write(f"**Ερώτηση:** {room['current_prompt']}")

            if room.get("status") == "waiting_human":
                st.info("Ο αληθινός χρήστης πληκτρολογεί την απάντησή του...")

            elif room.get("status") == "answered":
                st.write(f"**Απάντηση:** {room['current_reply']}")
                st.write("**Ποιος απάντησε;**")

                col_b1, col_b2 = st.columns(2)
                if col_b1.button("AI / Twin", key="btn_ai"):
                    correct = (room.get("real_source") == "AI")
                    supabase.table("rooms").update({"status": "finished"}).eq(
                        "room_code", room_code).execute()
                    st.session_state["last_result"] = (
                        "success" if correct else "error", "Σωστά! Ήταν το AI." if correct else "Λάθος! Ήταν ο αληθινός χρήστης.")
                    st.rerun()

                if col_b2.button("Αληθινός Χρήστης", key="btn_human"):
                    correct = (room.get("real_source") == "Human")
                    supabase.table("rooms").update({"status": "finished"}).eq(
                        "room_code", room_code).execute()
                    st.session_state["last_result"] = (
                        "success" if correct else "error", "Σωστά! Ήταν ο αληθινός χρήστης." if correct else "Λάθος! Ήταν το AI.")
                    st.rerun()

            elif room.get("status") == "finished":
                st.write(f"**Απάντηση:** {room['current_reply']}")
                if "last_result" in st.session_state:
                    res_type, res_msg = st.session_state["last_result"]
                    if res_type == "success":
                        st.success(res_msg)
                    else:
                        st.error(res_msg)

                if st.button("Νέος Γύρος"):
                    supabase.table("rooms").update({
                        "status": "waiting",
                        "current_prompt": "",
                        "current_reply": "",
                        "real_source": ""
                    }).eq("room_code", room_code).execute()
                    st.session_state.pop("last_result", None)
                    st.rerun()

    # --- ΟΨΗ ΔΗΜΙΟΥΡΓΟΥ ΠΡΟΦΙΛ ---
    else:
        if room.get("status") == "waiting_human":
            st.warning(f"Ο Ανακριτής ρώτησε: {room.get('current_prompt')}")
            human_answer = st.text_input("Γράψε την απάντησή σου:")
            if st.button("Αποστολή Απάντησης"):
                supabase.table("rooms").update({
                    "current_reply": human_answer,
                    "status": "answered"
                }).eq("room_code", room_code).execute()
                st.rerun()
        elif room.get("status") == "answered":
            st.info("Ο Ανακριτής διαβάζει την απάντηση και μαντεύει...")
        elif room.get("status") == "finished":
            st.success(
                "Ο γύρος ολοκληρώθηκε! Αναμονή για νέο γύρο από τον Ανακριτή.")
        else:
            st.info("Αναμονή για νέα ερώτηση από τον Ανακριτή...")


# Εκτέλεση Live Render
render_game()
