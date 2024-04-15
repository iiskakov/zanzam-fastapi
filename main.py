from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
from supabase import create_client, Client
import os
import logging
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

origins = [
    "http://localhost:3000",
    "https://localhost:3000",
    "http://localhost:8080",
    "http://localhost:4200",
    "http://localhost:8000",
    "https://zanzam.kz"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    )


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
AUTH_TOKEN = os.getenv("AUTH_TOKEN")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

logging.basicConfig(level=logging.DEBUG)


class Submission(BaseModel):
    bio: str


@app.post("/submit/")
async def submit_gpt4(submission: Submission):
    url = "https://canopy-gpt4-production.up.railway.app/v1/chat/completions"
    logging.debug(f"Received submission with bio: {submission.bio}")

    payload = {
        "messages": [{"role": "user", "content": submission.bio}]
    }
    headers = {
        "Content-Type": "application/json",
        "X-Auth-Token": AUTH_TOKEN
    }

    timeout = httpx.Timeout(50.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(
                url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
            logging.debug("API call successful")

            # Save full response to Supabase
            response_data = jsonable_encoder(result)
            supabase.table("api_logs").insert({
                "request_bio": submission.bio,
                "response_data": response_data
            }).execute()

            return {
                "message": result['choices'][0]['message']['content'],
                "tokens": {
                    "prompt_tokens": result['usage']['prompt_tokens'],
                    "completion_tokens": result['usage']['completion_tokens'],
                },
                "model": result['model']
            }
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error occurred: {e.response.status_code}")
            raise HTTPException(status_code=e.response.status_code, detail="e")
        except httpx.TimeoutException:
            logging.error("Request timed out")
            raise HTTPException(status_code=408, detail="Request timed out")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {str(e)}")
            raise HTTPException(status_code=500, detail="An unexpected error")

