# ============================================================================
# OpsMate UI (M4) — a Streamlit chat page over the RAG backend.
#
# It talks only to the app service (APP_URL): /ask for the grounded answer, and
# it shows the retrieved chunks in an expander so you can SEE what fed the
# answer — the whole point of RAG observability. The UI holds no model logic;
# retrieval and generation live in the app.
# ============================================================================
import os
import httpx
import streamlit as st

APP_URL = os.environ.get("APP_URL", "http://app:8001")

st.set_page_config(page_title="OpsMate v0.5", page_icon="🛠️", layout="centered")
st.title("OpsMate v0.5 — runbook assistant")
st.caption("Answers are grounded in the runbook corpus. Every answer shows the chunks that fed it.")

if "history" not in st.session_state:
    st.session_state.history = []

# Replay the conversation so far.
for turn in st.session_state.history:
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])
        if turn.get("sources"):
            with st.expander("Retrieved chunks (what fed this answer)"):
                for s in turn["sources"]:
                    st.markdown(
                        f"- **{s['source']}** · _{s['heading']}_ · distance `{s['distance']}`"
                    )

question = st.chat_input("Ask about an incident, e.g. 'website throwing 500 errors'")
if question:
    st.session_state.history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Retrieving runbooks and generating..."):
            try:
                resp = httpx.get(f"{APP_URL}/ask", params={"q": question}, timeout=180.0)
                resp.raise_for_status()
                data = resp.json()
                answer = data.get("answer", "(no answer)")
                sources = data.get("sources", [])
            except Exception as exc:  # keep the UI honest when the backend is down
                answer = f"Backend error: {exc}"
                sources = []
        st.markdown(answer)
        if sources:
            with st.expander("Retrieved chunks (what fed this answer)"):
                for s in sources:
                    st.markdown(
                        f"- **{s['source']}** · _{s['heading']}_ · distance `{s['distance']}`"
                    )
    st.session_state.history.append(
        {"role": "assistant", "content": answer, "sources": sources}
    )
