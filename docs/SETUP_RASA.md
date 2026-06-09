# Rasa Setup

## Create environment

```bash
conda create -n spark python=3.9
conda activate spark
pip install -r requirements.txt
```

On macOS with Apple Silicon:

```bash
pip install 'rasa[metal]'
```

Install spaCy language model:

```bash
pip install -U spacy
python -m spacy download en_core_web_md
```

## Duckling server

Duckling extracts numbers and ordinals (e.g. "first", "block 3") used during program revision.

```bash
docker run -p 19999:8000 rasa/duckling
```

If port 19999 is taken, use another host port and update `DUCKLING_URL` in `.env` and `config.yml`:

```yaml
  - name: DucklingEntityExtractor
    url: http://localhost:19999
```

**Apple M1 note:** Duckling Docker images do not run natively on M1. Run Duckling on a remote Linux server and port-forward to your local machine.

## Use the pretrained model

A pretrained model is included at `models/20250131-150846-exhaustive-superset.tar.gz`. Pass it when starting the Rasa server:

```bash
rasa run --enable-api -p 15005 --model models/20250131-150846-exhaustive-superset.tar.gz
```

To retrain from scratch:

```bash
rasa train
```

## Run services

Three terminals (all from the project root, `conda activate spark`):

```bash
# Terminal 1 — Rasa server (NLU + dialogue)
rasa run --enable-api -p 15005 --model models/20250131-150846-exhaustive-superset.tar.gz

# Terminal 2 — Custom actions (LLM + web UI + robot)
rasa run actions -p 15055

# Terminal 3 — Duckling (if not already running)
docker run -p 19999:8000 rasa/duckling
```

## Verify

Send a test message:

```bash
curl -X POST http://localhost:15005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{"sender":"test","message":"hi spark"}'
```

Open the web UI at `http://localhost:9999`.

## Troubleshooting

**`ModuleNotFoundError: No module named 'chardet'`**

```bash
pip install chardet cchardet
```

**`ImportError: cannot import name '_plain_int' from 'werkzeug._internal'`**

```bash
pip install werkzeug==2.2.2
```

**Packaging import error during `rasa train`**

```bash
pip uninstall packaging && pip install packaging
```
