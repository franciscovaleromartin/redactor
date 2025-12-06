import requests
import json

url = "http://localhost:5000/"

payload = {
  "filas": [
    {
      "palabra_clave": "Test Batch Python 1", 
      "titulo_sugerido": "Guía Test Batch 1"
    },
    {
      "palabra_clave": "Test Batch Python 2", 
      "titulo_sugerido": "Guía Test Batch 2"
    }
  ]
}

headers = {
  'Content-Type': 'application/json'
}

try:
    print(f"Sending batch request to {url}...")
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    
    print(f"Status Code: {response.status_code}")
    print("Response:")
    print(json.dumps(response.json(), indent=2))
    
except Exception as e:
    print(f"Error: {e}")
    print("Make sure the Flask server is running on localhost:5000")
