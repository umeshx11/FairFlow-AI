import google.generativeai as genai
import os
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

models = ["gemini-2.0-flash", "gemini-flash-latest", "gemini-2.0-flash-lite"]
for m in models:
    try:
        model = genai.GenerativeModel(m)
        response = model.generate_content("hi")
        print(f"{m} SUCCESS:", response.text)
        break
    except Exception as e:
        print(f"{m} ERROR:", str(e)[:100])
