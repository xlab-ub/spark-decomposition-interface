import os

import requests

url = os.environ.get("SPARK_STT_URL", "http://localhost:9009/transcribe")

file_path = './sample-3.mp3'  # Replace this with the path to your MP3 file

with open(file_path, 'rb') as file:
    files = {'file': file}
    # print("Sending request to:", url)
    response = requests.post(url, files=files)

if response.status_code == 200:
    result = response.json()
    # print("Server response:", result)
    print("Transcription:", result['result'])
else:
    print("Request failed with status code:", response.status_code)
