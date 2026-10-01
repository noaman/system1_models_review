# :test_tube: System 1 Playground

[![Python](https://img.shields.io/badge/Python-3-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-UI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![TypeSafe](https://img.shields.io/badge/TypeSafe-JEV-1F6FEB?style=for-the-badge)](https://docs.typesafe.ai/primitives)
[![Laya](https://img.shields.io/badge/Laya-local-6E7781?style=for-the-badge)](https://github.com/NandhaKishorM/laya)

![Choice](https://img.shields.io/badge/Choice-pick%20one%20option-9ebfff?style=flat-square)
![Score](https://img.shields.io/badge/Score-place%20on%20a%20scale-f0b429?style=flat-square)
![Noul](https://img.shields.io/badge/Noul-yes%20or%20no-5ee0b5?style=flat-square)
![Compare](https://img.shields.io/badge/Compare-before%20you%20ship-dff25a?style=flat-square&labelColor=1c2114)

Try a System 1 question on real models **before** you put it in production.

A live feature often starts as a fuzzy ask: route this ticket, score this risk, decide if the customer wants a refund. [System 1](https://docs.typesafe.ai/concepts/system-one) models do not answer that in prose. They return a typed judgment, and the shape of the question changes the answer you can act on. This playground is where you settle that shape, and which model to trust, on the same inputs you would send in production.

Paste the text or JSON a live request would see. Write it as a **Choice**, a **Score**, or a **Noul**. Run one model, or send that exact question to every model you are considering and read the answers side by side. When the probabilities, the disagreements, and the misses against your expected answers look right, copy the question into the live integration.

> [!IMPORTANT]
> Until the models agree on the cases you care about, nothing is shipped. A single friendly example is not a go-live check.

## :dart: What you test before go-live

| | Check | What "ready" looks like |
| --- | --- | --- |
| :blue_circle: | **Query type** | The live code can branch on the answer. "Which team?" is a Choice. "How urgent?" is a Score. "Will they cancel?" is a Noul. |
| :pencil: | **The question** | Options, levels, and yes/no wording are the contract. Change a label and run the same case again. |
| :scales: | **The model** | TypeSafe and Laya see the same state and the same questions. ![Agreed](https://img.shields.io/badge/Agreed-8fef9a?style=flat-square&labelColor=14301c) on the cases that matter. ![Split](https://img.shields.io/badge/Split-ff6b5a?style=flat-square&labelColor=3a1512) means stay in the playground. |
| :bookmark: | **Your labels** | An expected option, score, or yes/no marks a match or a miss. A miss means the question, the scale, or the model is not ready. |

:bulb: **Use sample** loads one support ticket with all three types filled in, so you can see a comparison before you bring your own cases.

## :robot: Models

| Model | Where it runs | What you need |
| --- | --- | --- |
| :cloud: [TypeSafe](https://docs.typesafe.ai/primitives) (JEV) | Hosted API | `JEV_APIKEY` in `.env` |
| :computer: [Laya](https://github.com/NandhaKishorM/laya) | On this machine | Checkpoints downloaded on first startup |

Both take the same request: a **state** (the text or record being judged) and one or more **questions**. Each question is one snap judgment.

## :art: Question types

| Type | Use it when the live code needs | What comes back |
| --- | --- | --- |
| ![Choice](https://img.shields.io/badge/Choice-9ebfff?style=flat-square&labelColor=152033) | One label from a fixed list, such as a route or a category | The selected option, a probability for every option, and a confidence |
| ![Score](https://img.shields.io/badge/Score-f0b429?style=flat-square&labelColor=2a2108) | A position on a scale you define, such as urgency or severity | A score that can fall between two levels, the nearest level, and probabilities |
| ![Noul](https://img.shields.io/badge/Noul-5ee0b5?style=flat-square&labelColor=0e2a22) | A yes or no you can threshold, such as "does this request a refund?" | A probability from 0 to 1. Near 1 is yes, near 0 is no, near 0.5 is uncertain |

Leave a type empty if you are not testing it. Only filled questions are sent.

> [!TIP]
> Score tolerance is how far a score can sit from the expected value, or from another model's score, and still count as a match. The default is `0.5`, half a level.

## :rocket: Quick start

You need Python 3 and `lsof`.

```bash
cp env.sample .env
# put your TypeSafe key in .env

./install.sh
./run.sh 8000
```

Open **http://127.0.0.1:8000**.

`./install.sh` deletes `.venv` and installs a fresh one from `requirements.txt`. `./run.sh` stops whatever is already listening on that port, then starts the app. The port is the first argument, or `8000` if you omit it:

```bash
./run.sh 8765
```

> [!WARNING]
> The first startup loads Laya's English and multilingual checkpoints into memory before the server accepts requests. That download can take several minutes. Wait until the terminal prints `Laya is in memory`. Later questions reuse those checkpoints. TypeSafe calls still need a network connection and a valid key.


## :white_check_mark: A run before you ship

1. Switch to **Compare** and select every model still in the running. Use **Single model** only after one of them has already won.
2. Paste a real case in **Text to judge**. Use **JSON** when the live payload is a record and the question should point at a field, such as `` `ticket.messages[0].text` ``.
3. Write the decision in the type you think production will call. Add a second type on the same text when you are not sure Choice, Score, or Noul is the right contract.
   - :blue_circle: **Choice:** the question, then each option and what it means.
   - :yellow_circle: **Score:** the question, then levels from lowest to highest. The first row is level 0.
   - :green_circle: **Noul:** the yes-or-no question. "Yes means" and "No means" are optional.
4. If you already know the right call, set the expected answer. That is the check you would regret getting wrong in production.
5. Run. Read the probabilities, not only the headline.
   - ![Agreed](https://img.shields.io/badge/Agreed-same%20call-8fef9a?style=flat-square&labelColor=14301c) the models made the same decision.
   - ![Split](https://img.shields.io/badge/Split-do%20not%20ship%20yet-ff6b5a?style=flat-square&labelColor=3a1512) change the wording or the scale and run the same case again.

Keep a few cases that should pass and a few that should fail. :x: A model that looks right on one friendly example is not ready.

## :file_folder: Layout

```
playground/          FastAPI app and the browser UI
  app.py             routes and startup
  runners.py         TypeSafe and Laya clients
  catalog.py         model list and the sample question
  static/            the page
experiments/         small scripts that call each model directly
tests/               checks for question validation and scoring
```

To add another System 1 model, add a `ModelSpec` in `playground/catalog.py` and a runner next to `TypeSafeRunner` and `LayaRunner` in `playground/runners.py`.

## :gear: Configuration

| Variable | Purpose |
| --- | --- |
| `JEV_APIKEY` | TypeSafe API key. Copy `env.sample` to `.env` and replace the placeholder. |
| `HOST` | Bind address for `./run.sh`. Defaults to `127.0.0.1`. |
| `PORT` | Port for `./run.sh` when you do not pass one as an argument. |

Laya reads its own Hugging Face settings if you need a token for the checkpoint download. See the [Laya repo](https://github.com/NandhaKishorM/laya) for `HF_TOKEN` and related options.
# system1_models_review
Try a System 1 question on real models before you put it in production. 
