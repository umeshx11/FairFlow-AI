import requests

print("Testing /demo/run endpoint")
res = requests.post("http://localhost:8000/demo/run")
print("Status Code:", res.status_code)
print("Response Text:", res.text)
