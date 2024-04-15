from fastapi import FastAPI, HTTPException
import httpx
from pydantic import BaseModel
import logging

app = FastAPI()

# Setting up logging
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
        "X-Auth-Token": "suka"  # This should be managed securely
    }

    timeout = httpx.Timeout(30.0, connect=5.0)

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
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            raise HTTPException(status_code=500, detail="An unexpected error ")
