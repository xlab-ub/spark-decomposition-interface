# Text-to-Speech (optional)

Off by default. Set `SPARK_TTS_ON=true` and `SPARK_TTS_URL` in `.env`.

- `ttsengine_with_coqui_tts_server.py` — TTS client
- `coqui_tts_request_to_server.py` — Coqui TTS server reference

Requires a separate Coqui TTS server when using the real Go1 audio path.
