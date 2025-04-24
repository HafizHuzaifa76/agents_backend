import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google.adk.cli.fast_api import get_fast_api_app

# Path setup
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SESSION_DB_URL = f"sqlite:///{os.path.join(BASE_DIR, 'sessions.db')}"

app: FastAPI = get_fast_api_app(
    agent_dir=BASE_DIR,
    session_db_url=SESSION_DB_URL,
    allow_origins=["*"],
    web=True,
)


@app.get("/health")
async def health_check():
    return {"status": "Api is running"}


@app.get("/agent-info")
async def agent_info():
    try:
        from sub_agents import root_agent

        return {
            "name": root_agent.name,
            "description": root_agent.description,
            "model": root_agent.model,
            "tools": [t.__name__ for t in root_agent.tools],
        }
    except ImportError:
        return {
            "name": "Agent",
            "description": "Default agent description",
            "model": "Unknown",
            "tools": [],
        }


if __name__ == "__main__":
    # App Runner expects port 8080
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)


# http://0.0.0.0:9999/apps/sub_agents/users/user/sessions

# http://0.0.0.0:9999/run_sse

# {
#   "app_name": "sub_agents",
#   "user_id": "user",
#   "session_id": "54fbdbce-c815-432a-b133-f9d89940f105",
#   "new_message": {
#     "role": "user",
#     "parts": [
#       {
#         "text": "Hey...?"
#       }
#     ]
#   },
#   "streaming": false
# }
