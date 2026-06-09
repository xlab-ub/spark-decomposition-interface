# Spark Decomposition Interface

Spark turns natural-language instructions from users into decomposed pseudo-code and robot actions. It uses Rasa for dialogue management, LiteLLM for LLM reasoning, and an optional Unitree Go1 robot backend.

## Quick start

### 1. Environment

```bash
conda create -n spark python=3.9
conda activate spark
cd spark-decomposition-interface
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your LLM API key or local vLLM endpoint (.env is loaded automatically by actions)
```

### 2. Duckling (entity extraction)

```bash
docker run -p 19999:8000 rasa/duckling
```

On Apple M1, Duckling may need to run on a remote Linux server with port forwarding. See `docs/SETUP_RASA.md`.

### 3. Train and run Rasa

```bash
# Use the included pretrained model, or run `rasa train` to retrain
rasa run --enable-api -p 15005 --model models/20250131-150846-exhaustive-superset.tar.gz  # terminal 1
rasa run actions -p 15055              # terminal 2 (from this directory)
```

### 4. Open the web UI

Visit `http://localhost:9999` after actions start. The default robot backend is **noop** (no hardware required).

## LLM backends

| Provider | `.env` settings |
|----------|-----------------|
| OpenAI (commercial) | `SPARK_LLM_PROVIDER=openai`, `OPENAI_API_KEY=...`, `SPARK_LLM_MODEL=gpt-4o-mini` |
| Local vLLM (Docker) | `SPARK_LLM_PROVIDER=vllm`, `SPARK_LLM_API_BASE=http://localhost:8000/v1`, `SPARK_LLM_MODEL=hosted_vllm/openai/gpt-oss-20b` — run `docker run --gpus all -p 8000:8000 vllm/vllm-openai:latest --model openai/gpt-oss-20b` |

## Robot backend

| Mode | Setting | Description |
|------|---------|-------------|
| No-op (default) | `SPARK_ROBOT_BACKEND=noop` | Validates and logs commands; no hardware |
| Go1 | `SPARK_ROBOT_BACKEND=go1` | Real Unitree Go1 via vendored free-dog-sdk |

See `docs/SETUP_GO1.md` for robot network configuration.

## Project layout

```
actions/actions.py     Core Rasa custom actions (user <-> LLM <-> robot)
actions/engine/        LiteLLM program generator
actions/prompts/       Decomposition prompt templates
actions/robot/         Robot backends + vendored free-dog-sdk
actions/web/           Flask chat UI
data/                  Rasa NLU training data
optional/              STT, TTS, vision, database (off by default)
docs/                  Setup and architecture guides
```

## Citation

The following publications report empirical work that **utilized the Spark decomposition framework**. If you use this codebase in your research, please cite:

> Changjae Lee, Qingxiao Zheng, and Jinjun Xiong. 2026. *From Visual to Multimodal Programming: Designing an Interface to Externalize Decomposition Thinking for Novice Learners.* In Proceedings of the 31st International Conference on Intelligent User Interfaces (IUI '26). Association for Computing Machinery, New York, NY, USA, 1202–1217. https://doi.org/10.1145/3742413.3789131

> Changjae Lee and Jinjun Xiong. 2024. *From Keyboard to Chatbot: An AI-powered Integration Platform with Large-Language Models for Teaching Computational Thinking for Young Children.* arXiv:2405.00750. https://arxiv.org/abs/2405.00750

```bibtex
@inproceedings{10.1145/3742413.3789131,
  author = {Lee, Changjae and Zheng, Qingxiao and Xiong, Jinjun},
  title = {From Visual to Multimodal Programming: Designing an Interface to Externalize Decomposition Thinking for Novice Learners},
  year = {2026},
  isbn = {9798400719844},
  publisher = {Association for Computing Machinery},
  address = {New York, NY, USA},
  url = {https://doi.org/10.1145/3742413.3789131},
  doi = {10.1145/3742413.3789131},
  abstract = {Decomposition, the process of breaking down complex problems into manageable parts, is a fundamental component of computational thinking (CT) but remains challenging for novice learners. We present Spark, a multimodal programming interface that supports the externalization of decomposition thinking by organizing user-articulated goals into structured steps and enacting them through a tangible robot, making decomposition visible and open to inspection. The design of Spark is theory-driven, with its user interface aligned to three decomposition rationales: substantive, relational, and functional decomposition. In a study with 20 adult novices, we compared Spark with Scratch, an educational block-based visual programming interface. While both systems were associated with improvements in participants' self-reported decomposition skills, only Spark was associated with measurable gains on objective assessments and significantly higher task success when experienced first, while maintaining comparable workload and completion times. Participants reported that externalizing the otherwise hidden process of decomposition made programming more tangible and motivating. These findings, highlighting the complementary roles of multimodal interaction in shaping novices' decomposition experiences, inform the design of interactive programming interfaces that aim to support the externalization of reasoning processes. More broadly, our work contributes to the field of human-AI interaction in learning, illustrating how multimodal interaction can be responsibly integrated to scaffold reasoning, support reflection, and promote equitable participation in computing.},
  booktitle = {Proceedings of the 31st International Conference on Intelligent User Interfaces},
  pages = {1202--1217},
  numpages = {16},
  keywords = {Decomposition, Vibe Coding, Computational Thinking, Novice Programming Learner, Robotics.},
  series = {IUI '26}
}

@misc{lee2024keyboardchatbotaipoweredintegration,
  title={From Keyboard to Chatbot: An AI-powered Integration Platform with Large-Language Models for Teaching Computational Thinking for Young Children},
  author={Changjae Lee and Jinjun Xiong},
  year={2024},
  eprint={2405.00750},
  archivePrefix={arXiv},
  primaryClass={cs.HC},
  url={https://arxiv.org/abs/2405.00750},
}
```

This repository is a public, configurable release of the decomposition interface. It is related to the Spark system described in those works, but should not be taken as a line-by-line reproduction of the exact study apparatus.

## Documentation

- [Rasa setup](docs/SETUP_RASA.md)
- [Go1 robot setup](docs/SETUP_GO1.md)
- [Architecture](docs/ARCHITECTURE.md)
