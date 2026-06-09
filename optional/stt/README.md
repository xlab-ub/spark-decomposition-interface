# Speech-to-Text (optional)

Off by default. Set `SPARK_STT_URL` in `.env` to point at a Whisper server.

- `whisper_server.py` — client that posts audio to a remote Whisper endpoint
- `sttengine_with_whisper_server.py` — STT engine wrapper

Enable by integrating these modules into your client; they are not imported by default actions.
