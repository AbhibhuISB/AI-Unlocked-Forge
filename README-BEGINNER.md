# FORGE Beginner Guide (No Technical Background Needed)

This guide helps you run FORGE in the easiest way possible.

## What was recently updated (March 2026)
- Added two run modes:
	- Quick Run: AI runs everything automatically.
	- Guided Run: AI asks you for input while planning.
- Added Interrupt button:
	- You can stop a running request safely.
- Improved Guided Run experience:
	- AI asks clearer clarification questions.
	- Input box appears only in Guided Run.
	- Skip/Submit flow improved.
- Added better output viewing:
	- Output is now in a scrollable box.
	- “Open In New Tab” option added.
- Planner is now smarter:
	- Uses a Tree-of-Thoughts approach to compare multiple plan options and choose the best one.
- Added safety checks:
	- conflict source-priority selection
	- deadlock guard to stop repeated patch loops

## What is FORGE?
FORGE is a project with 3 AI roles working together:
- Planner (makes the plan)
- Retriever (finds information)
- Executor (creates the final output)

You will open a web page and click a button to run it.

## Before you start
You need:
1. A Windows laptop with Python installed
2. Your Azure OpenAI account ready
3. A model deployment created in Azure OpenAI
4. Your Azure OpenAI endpoint + key + deployment name

## Step 1: Get your Azure values
In Azure OpenAI, collect these 3 items:
- API Key
- Endpoint URL
- Deployment Name (exactly as shown)

If deployment is not approved yet, the app UI will open, but AI runs will fail until approval is complete.

## Step 2: Create your local settings file
Inside this project folder, there is a file named `.env.example`.

Do this:
1. Make a copy of `.env.example`
2. Rename the copy to `.env`
3. Open `.env` and fill your real Azure values

Important:
- Keep `.env.example` unchanged (template)
- Put secrets only in `.env`
- Never share `.env` publicly

## Step 3: Run the app (copy-paste commands)
Open PowerShell in this folder and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
```

## Step 4: Open the app in browser
Open this link:
- http://127.0.0.1:8000/

You should see the FORGE UI page.

## Step 5: If something is not working
Check these pages:
- Health check: http://127.0.0.1:8000/health
- API docs: http://127.0.0.1:8000/docs

If `/health` works but running AI fails, usually one of these is the issue:
- Deployment name in `.env` is wrong
- Azure deployment is not approved yet
- Endpoint URL is wrong
- API key is wrong or expired

## Which README should I use?
- If you are technical: use `README.md`
- If you want simple steps: use this file (`README-BEGINNER.md`)

## Safety reminder
A real Azure key was previously exposed during setup, so rotate your Azure OpenAI key if you have not already done so.
