from tempfile import NamedTemporaryFile 
import playsound
import requests

import os

url = os.environ.get("SPARK_TTS_URL", "http://localhost:19099/synthesize")

class TTSEngine_with_Coqui_TTS_Server:
    def __init__(self, coqui_tts_server_url=url):
        self.coqui_tts_server_url = coqui_tts_server_url

    def tts(self, text, filename=None, play=False):
        response = requests.post(self.coqui_tts_server_url, data={'text': text})
        # Check if the request was successful
        if response.status_code == 200:
            # Define filename or create a temporary one if None
            filename = filename or NamedTemporaryFile(suffix='.wav').name

            try:
                # Write response content to the file
                with open(filename, 'wb') as f:
                    f.write(response.content)
            except OSError as e:
                # return f"An error occurred while writing the file: {e}"
                print(f"An error occurred while writing the file: {e}")

            # Play the WAV file if requested
            if play:
                playsound.playsound(filename, block=True)

        else:
            print("Failed to get the speech file:", response.json())
