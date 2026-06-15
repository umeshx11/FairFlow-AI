import os
import sys
import requests

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import SessionLocal
from models import User
from routers.auth import create_access_token

db = SessionLocal()
user = db.query(User).filter(User.email == "demo@fairflow.ai").first()
if not user:
    print("User not found!")
    sys.exit(1)

token = create_access_token({"sub": str(user.id)})
headers = {"Authorization": f"Bearer {token}"}

# Get an audit ID
res = requests.post("http://localhost:8000/demo/run")
data = res.json()
audit_id = data["audit"]["id"]
print(f"Audit ID: {audit_id}")

# Test Google Docs export
res = requests.post(f"http://localhost:8000/audit/{audit_id}/google-doc-report", headers=headers)
print("Status:", res.status_code)
print("Response:", res.json())
