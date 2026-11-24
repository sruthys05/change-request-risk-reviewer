# Change Request Risk Reviewer

Engineer submits a change -> AI drafts a risk summary -> human approves or rejects.
Flow: pending -> agent_reviewed -> approved / rejected

## Setup
    python -m venv .venv
    source .venv/bin/activate        # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    cp .env.example .env             # then put your Anthropic key inside

## Run
    uvicorn main:app --reload
Open http://127.0.0.1:8000/docs

## Log in (demo)
Send a header `X-User: alice` (engineer) or `X-User: bob` (approver).
In /docs click "Try it out" and fill in the `x-user` box.

## Try it
1. POST /changes as alice  {"title": "Add 20 servers to Rack B", "description": "..."}
2. POST /changes/1/review as alice  (AI writes risk_summary)
3. POST /changes/1/approve as bob   (alice would get 403)
4. GET /audit  to see everything that happened

## Test 
    pytest

## Files
- models.py   tables + RiskSummary schema
- agent.py    LLM call + validation (no database access)
- services.py status rules + audit log
- main.py     routes and roles
