import google.generativeai as genai
import os
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")
try:
    response = model.generate_content("hello")
    print("1.5-flash success:", response.text)
except Exception as e:
    print("1.5-flash error:", e)
