# https://github.com/davabase/whisper_real_time/blob/master/transcribe_demo.py 

import io 
import speech_recognition as sr
# import whisper
# import torch

from datetime import datetime, timedelta
from queue import Queue
from tempfile import NamedTemporaryFile 
from sys import platform

import requests

import os

url = os.environ.get("SPARK_STT_URL", "http://localhost:9009/transcribe")

class STTEngine_with_Whisper_Server: 
    def __init__(self, energy_threshold=1000, record_timeout=2, phrase_timeout=3, default_microphone='pulse', whisper_server_url=url): 
        self.energy_threshold = energy_threshold 
        self.record_timeout = record_timeout 
        self.phrase_timeout = phrase_timeout 

        if 'linux' in platform: 
            self.default_microphone = default_microphone 
    
        # We use SpeechRecognizer to record our audio because it has a nice feauture where it can detect when speech ends.
        self.recorder = sr.Recognizer()
        self.recorder.energy_threshold = self.energy_threshold
        # Definitely do this, dynamic energy compensation lowers the energy threshold dramtically to a point where the SpeechRecognizer never stops recording.
        self.recorder.dynamic_energy_threshold = False
    
        # Important for linux users. 
        # Prevents permanent application hang and crash by using the wrong Microphone
        if 'linux' in platform:
            self.mic_name = default_microphone
            if not self.mic_name or self.mic_name == 'list':
                print("Available microphone devices are: ")
                for index, name in enumerate(sr.Microphone.list_microphone_names()):
                    print(f"Microphone with name \"{name}\" found")   
                raise RuntimeError('Wrong microphone name') 
            else:
                for index, name in enumerate(sr.Microphone.list_microphone_names()):
                    if self.mic_name in name:
                        self.source = sr.Microphone(sample_rate=16000, device_index=index)
                        break
        else:
            self.source = sr.Microphone(sample_rate=16000)
                
        with self.source:
            self.recorder.adjust_for_ambient_noise(self.source)

        self.whisper_server_url = whisper_server_url

    def stt(self): 
        # The last time a recording was retreived from the queue.
        phrase_time = None
        # Current raw audio bytes.
        last_sample = bytes()
        # Thread safe Queue for passing data from the threaded recording callback.
        data_queue = Queue()

        temp_file = NamedTemporaryFile().name 

        def record_callback(_, audio:sr.AudioData) -> None:
            """
            Threaded callback function to recieve audio data when recordings finish.
            audio: An AudioData containing the recorded bytes.
            """
            # Grab the raw bytes and push it into the thread safe queue.
            data = audio.get_raw_data()
            data_queue.put(data)

        # Create a background thread that will pass us raw audio bytes.
        # We could do this manually but SpeechRecognizer provides a nice helper.
        stop_listening = self.recorder.listen_in_background(self.source, record_callback, phrase_time_limit=self.record_timeout) 

        while True: 
            now = datetime.utcnow()
            # Pull raw recorded audio from the queue.
            if not data_queue.empty(): 
                # If enough time has passed between recordings, consider the phrase complete.
                # Clear the current working audio buffer to start over with the new data.
                if phrase_time and now - phrase_time > timedelta(seconds=self.phrase_timeout):
                    last_sample = bytes() 
                # This is the last time we received new audio data from the queue.
                phrase_time = now

                # Concatenate our current audio data with the latest audio data.
                while not data_queue.empty():
                    data = data_queue.get()
                    last_sample += data

                # Use AudioData to convert the raw data to wav data.
                audio_data = sr.AudioData(last_sample, self.source.SAMPLE_RATE, self.source.SAMPLE_WIDTH)
                # wav_data = io.BytesIO(audio_data.get_wav_data())

                # # Write wav data to the temporary file as bytes.
                # with open(temp_file, 'w+b') as f:
                #     f.write(wav_data.read())

                # # Send the temporary file to the whisper server.
                # with open(temp_file, 'rb') as file:
                #     files = {'file': file}
                #     response = requests.post(self.whisper_server_url, files=files)

                wav_data = audio_data.get_wav_data() # Directly get the WAV data as bytes.

                # Send the WAV data to the whisper server without writing to a local temp file.
                response = requests.post(self.whisper_server_url, files={'file': ('temp.wav', wav_data)})

                if response.status_code == 200:
                    result = response.json()
                    # print("Server response:", result)
                    # print("Transcription:", result['result'])
                    text = result['result'].strip()
                else:
                    print("Request failed with status code:", response.status_code)
                    text = ''

                # Read the transcription.
                # result = self.audio_model.transcribe(temp_file, fp16=torch.cuda.is_available())
                # text = result['text'].strip()

                stop_listening(wait_for_stop=False) 

                return text 