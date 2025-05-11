import streamlit as st
import pandas as pd
import requests
import time
import io
import json  # For safely parsing JSON responses

# ---------------------------
# UI CONFIGURATION
# ---------------------------
st.set_page_config(page_title="Meta Tag Translator", layout="wide")
st.title("🧾 Bulk Meta Tag Translator (EN → AR)")
st.markdown("""
Upload an Excel sheet containing English meta titles and descriptions.
Select a model via OpenRouter. The output will contain Arabic translations following Nahdi eCommerce guidelines.
""")

# ---------------------------
# USER INPUT
# ---------------------------
api_key = st.text_input("🔑 OpenRouter API Key", type="password")

model_options = [
    "google/gemini-2.5-flash-preview",
    "openai/gpt-4.1-nano",
    "google/gemini-2.0-flash-001",
    "openai/gpt-4o-mini",
    "google/gemini-flash-1.5"
]

selected_model = st.selectbox("🤖 Choose a Model", model_options)
uploaded_file = st.file_uploader("📤 Upload Excel File with 'Meta Title' and 'Meta Description' Columns", type=["xlsx"])

# ---------------------------
# TRANSLATION FUNCTION
# ---------------------------
def translate_meta_tags(title, description, model, api_key):
    prompt = f"""
You are a professional Arabic SEO translator for eCommerce.
Translate the following meta tags from English to Modern Standard Arabic, following these rules:
- Preserve brand names in Latin unless there's a well-known Arabic version.
- Translate only product types and descriptors.
- Use correct grammar and SEO-optimized Arabic.
- Return only the translated meta title and meta description as a JSON.

Meta Title: {title}
Meta Description: {description}

Return format:
{{
    "title": "...",
    "description": "..."
}}
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    body = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", json=body, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        result = response.json()
        if 'choices' in result and result['choices']:
            content = result['choices'][0]['message']['content']
            try:
                data = json.loads(content)
                return data.get("title", ""), data.get("description", "")
            except json.JSONDecodeError as e:
                st.error(f"Error decoding JSON response: {e} - Content: {content}")
                return None, None
        else:
            st.error(f"Unexpected response format: {result}")
            return None, None
    except requests.exceptions.RequestException as e:
        st.error(f"Request error: {e}")
        return None, None
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return None, None

# ---------------------------
# PROCESSING STATE
# ---------------------------
st.session_state.setdefault("stop_translation", False)
st.session_state.setdefault("translation_started", False)
st.session_state.setdefault("output_data", [])
st.session_state.setdefault("progress", 0)

translation_placeholder = st.empty()
progress_bar_placeholder = st.empty()
progress_text_placeholder = st.empty()

if uploaded_file and api_key:
    df = pd.read_excel(uploaded_file)

    if 'Meta Title' not in df.columns or 'Meta Description' not in df.columns:
        st.error("Excel file must contain 'Meta Title' and 'Meta Description' columns.")
    else:
        total_rows = len(df)

        if not st.session_state.translation_started:
            if st.button("🚀 Start Translation"):
                st.session_state.translation_started = True
                st.session_state.stop_translation = False
                st.session_state.output_data = []
                st.session_state.progress = 0
        else:
            if st.button("🛑 Stop Translation"):
                st.session_state.stop_translation = True

            progress_bar = progress_bar_placeholder.progress(st.session_state.progress / total_rows if total_rows > 0 else 0)
            progress_text_placeholder.markdown(f"**Progress:** {int(st.session_state.progress)} / {total_rows} translated")

            for i, row in df.iterrows():
                if st.session_state.stop_translation:
                    break

                title_en = row['Meta Title']
                desc_en = row['Meta Description']

                title_ar, desc_ar = translate_meta_tags(title_en, desc_en, selected_model, api_key)

                if title_ar is None or desc_ar is None:
                    translated_row = {
                        "Meta Title (EN)": title_en,
                        "Meta Description (EN)": desc_en,
                        "Meta Title (AR)": "❌ Skipped (error)",
                        "Meta Description (AR)": "❌ Skipped (error)"
                    }
                else:
                    translated_row = {
                        "Meta Title (EN)": title_en,
                        "Meta Description (EN)": desc_en,
                        "Meta Title (AR)": title_ar,
                        "Meta Description (AR)": desc_ar
                    }

                st.session_state.output_data.append(translated_row)
                translation_placeholder.write(pd.DataFrame([translated_row]))
                st.session_state.progress += 1
                progress_bar.progress(st.session_state.progress / total_rows)
                progress_text_placeholder.markdown(f"**Progress:** {st.session_state.progress} / {total_rows} translated")
                time.sleep(1.2) # Keep a small delay

            st.session_state.translation_started = False # Reset state after completion or stop

            result_df = pd.DataFrame(st.session_state.output_data)

            st.success("✅ Translation finished or stopped.")
            st.dataframe(result_df)

            def convert_df(df):
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                return output.getvalue()

            st.download_button(
                "📥 Download Current Translations",
                data=convert_df(result_df),
                file_name="translated_meta_tags_partial.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )