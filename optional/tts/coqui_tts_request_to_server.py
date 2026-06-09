# CUDA_VISIBLE_DEVICES=1 python coqui_tts_request_to_server.py

import torch
from TTS.api import TTS

import os
from flask import Flask, request, send_file

from tempfile import NamedTemporaryFile 

# Get device
device = "cuda" if torch.cuda.is_available() else "cpu"

# Init TTS
tts = TTS("tts_models/en/ljspeech/tacotron2-DDC_ph").to(device)
# tts = TTS("tts_models/en/ljspeech/tacotron2-DCA").to(device)

app = Flask(__name__)

@app.route('/synthesize', methods=['POST'])
def synthesize():
    text = request.form['text']
    
    # Create a named temporary file without immediately deleting it
    temp_file = NamedTemporaryFile(suffix='.wav', delete=False)
    temp_file_path = temp_file.name  # Store file name since temp_file will be closed later
    try:
        # Synthesize the text to a WAV file
        # if the text is longer than 100 characters, it will be split into multiple WAV files
        # then the multiple WAV files will be concatenated into a single WAV file
        if len(text) > 150:
            # Split the text into serveral sentences while preserving whole words
            # split by space is not a good idea since it may split a word into two parts
            # split by space will also break the punctuation marks
            sentences = []
            sentence = ''
            for word in text.replace('_', ' ').split(' '):
                if len(sentence) + len(word) + 1 > 150:
                    sentences.append(sentence)
                    sentence = ''
                sentence += ' ' + word
            if sentence != '':
                sentences.append(sentence)

            # Synthesize each sentence and save the result to a temporary file
            # Then concatenate all the temporary files into a single WAV file
            temp_files = []
            for sentence in sentences:
                _temp_file = NamedTemporaryFile(suffix='.wav', delete=False)
                _temp_file_path = _temp_file.name
                tts.tts_to_file(sentence, file_path=_temp_file_path, split_sentences=False)
                temp_files.append(_temp_file_path)
            
            # Print the duration of each file
            # ffmpeg 
            for _temp_file_path in temp_files:
                os.system(f"ffprobe -i {_temp_file_path} -show_entries format=duration -v quiet -of csv=\"p=0\"")
            
            # Concatenate the temporary files into a single WAV file
            # os.system(f"sox {' '.join(temp_files)} {temp_file_path}")
            # sox not installed on server, use ffmpeg instead
            # ffmpeg was installed by conda install -c conda-forge ffmpeg
            # os.system(f"ffmpeg -y -i \"concat:{'|'.join(temp_files)}\" -acodec copy {temp_file_path}") # this does not work
            os.system(f"ffmpeg -y {' '.join(['-i ' + _temp_file_path for _temp_file_path in temp_files])} -filter_complex \"[0:0][1:0]concat=n={len(temp_files)}:v=0:a=1[out]\" -map \"[out]\" {temp_file_path}")
            
            # Remove the temporary files
            for _temp_file_path in temp_files:
                os.unlink(_temp_file_path)

        else:
            tts.tts_to_file(text.replace('_', ' '), file_path=temp_file_path)

        # tts.tts_to_file(text.replace('_', ' '), file_path=temp_file_path)

        # Close the file descriptor for proper sending
        temp_file.close()
        
        # Send the file back to the client
        return send_file(
            temp_file_path,
            as_attachment=True,
            download_name='speech.wav',
            mimetype='audio/wav'
        )
    except Exception as e:  # Replace with more specific exceptions
        # Handle any errors that occur during TTS generation or file sending
        print(e)
        return "An error occurred while processing your request.", 500
    finally:
        # Clean up the temporary file after the send_file operation has completed
        # Check if the file exists before trying to remove it
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9099)
