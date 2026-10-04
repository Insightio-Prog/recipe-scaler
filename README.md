# Recipe Scaler

Photograph a kitchen recipe card, let AI read it, then scale it by **portions** or by **any one ingredient** ("I have 5 kg of beans, how much of everything else?"). Built for a working kitchen: phone first, grams and millilitres, big buttons.

**Live demo:** https://recipescaler.insightio.co.uk · Sample recipes are invented; no real company recipes are stored.

## How it works
1. **Photo → data.** Up to two photos (front and back of a card) go to Claude's vision model, which must answer through a strict `save_recipe` tool (name, portions, ingredients with quantity and unit, method). Supplier names, product codes and pack sizes are dropped.
2. **Check screen.** The person confirms every number. Anything the AI wasn't sure about (glare, blur) is highlighted yellow. Nothing is saved unchecked.
3. **Scaling is plain Python**, not AI: `app/scaling.py` converts everything to base units (g, ml, each), works out one scale factor, and formats results the way a kitchen reads them (1500 g → 1.5 kg). The AI never does the maths.

## Design decisions
- **AI reads, code calculates.** Wrong numbers in a kitchen matter, so arithmetic is deterministic and unit-tested.
- **Stateless server.** Recipes are saved in the browser (localStorage), so the server holds no user data.
- **Cost and abuse limits.** Daily per-IP and global caps on photo reads, image size checks and resizing, max two images.
- Photo text is treated as data, never instructions.

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
export ANTHROPIC_API_KEY=sk-ant-...                  # Windows: $env:ANTHROPIC_API_KEY="..."
uvicorn app.main:app --reload
pytest
```

## Deploy
`render.yaml` is included (Render free web service). Set `ANTHROPIC_API_KEY` as a secret environment variable.

## Stack
Python 3.11+, FastAPI, Anthropic SDK (tool use + vision), Pillow, vanilla JS front end, pytest (27 tests).
