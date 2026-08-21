"""A deliberately small Streamlit client for the FastAPI query service."""

import os

import requests
import streamlit as st


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


st.set_page_config(page_title="Safe Text-to-SQL", page_icon="🛡️", layout="wide")
st.title("🛡️ Safe Text-to-SQL")
st.caption("Ask in plain English. Every query is schema-aware, read-only, bounded, and validated.")

with st.sidebar:
    st.subheader("Try these sample questions")
    st.code("Show gross revenue by month")
    st.code("Which customers have the highest net revenue?")
    st.code("How many paid orders are there?")
    st.code("Show sales by product category")
    st.divider()
    st.caption("Use `LLM_PROVIDER=ollama` for free local model-backed questions.")

question = st.text_area("Your business question", placeholder="Show gross revenue by month")
verify_alternative = st.checkbox("Validate with an independent SQL query", value=False)

if st.button("Generate and run safely", type="primary", disabled=not question.strip()):
    with st.spinner("Generating, checking, explaining, and running a read-only query…"):
        try:
            response = requests.post(
                f"{API_BASE_URL}/v1/query",
                json={"question": question, "verify_with_alternative": verify_alternative},
                timeout=60,
            )
            body = response.json()
        except requests.RequestException as error:
            st.error(f"Could not reach the API at {API_BASE_URL}: {error}")
            st.stop()

    if not response.ok:
        st.error(body.get("detail", "The API rejected this request."))
        st.stop()
    if body.get("needs_clarification"):
        st.warning(body["message"])
        for option in body["options"]:
            st.info(f"**{option['label']}** — {option['description']}  \nTry: {option['example_question']}")
        st.stop()

    left, right = st.columns([1, 2])
    left.metric("Confidence", f"{body['confidence']:.0%}")
    left.metric("Rows", body["row_count"])
    left.metric("Execution", f"{body['execution_ms']} ms")
    right.subheader("Generated SQL")
    right.code(body["generated"]["sql"], language="sql")
    right.caption(body["generated"]["explanation"])

    st.subheader("Results")
    st.dataframe(body["rows"], use_container_width=True, hide_index=True)

    with st.expander("Confidence breakdown"):
        st.dataframe(body["confidence_breakdown"], use_container_width=True, hide_index=True)
        if body["warnings"]:
            st.warning(body["warnings"])
    with st.expander("EXPLAIN plan"):
        st.code(body["explain_plan"], language="text")

    feedback_columns = st.columns(2)
    if feedback_columns[0].button("✓ Result is correct"):
        requests.post(
            f"{API_BASE_URL}/v1/feedback",
            json={"question": question, "sql": body["generated"]["sql"], "correct": True},
            timeout=10,
        )
        st.success("Thanks — saved as positive feedback.")
    if feedback_columns[1].button("✗ Result is incorrect"):
        requests.post(
            f"{API_BASE_URL}/v1/feedback",
            json={"question": question, "sql": body["generated"]["sql"], "correct": False},
            timeout=10,
        )
        st.info("Saved as a future evaluation case.")
