import requests

SAMPLE_JD = """We are looking for a rockstar engineer who is aggressive about 
results and can dominate in a fast-paced environment. The ideal candidate is a 
young, energetic self-starter who works independently and crushes deadlines. 
Must be a wizard with React and a ninja with backend systems."""

res = requests.post(
    "http://localhost:8000/jd-audit/analyze",
    json={"job_description": SAMPLE_JD, "job_title": "Software Engineer"}
)
print("Status:", res.status_code)
try:
    print("Response:", res.json())
except Exception as e:
    print("Error:", e, res.text)
