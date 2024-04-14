from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import httpx

app = FastAPI()

class Message(BaseModel):
    role: str
    content: str

class Payload(BaseModel):
    messages: list[Message]

@app.post("/generate-response/")
async def generate_response(payload: Payload):
    url = "https://canopy-gpt4-production.up.railway.app/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "X-Auth-Token": "suka"  # Secure this token, possibly with environment variables
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload.dict(), headers=headers)
            response.raise_for_status()
            result = response.json()
            return {
                "message": result['choices'][0]['message']['content'],
                "tokens": {
                    "prompt_tokens": result['usage']['prompt_tokens'],
                    "completion_tokens": result['usage']['completion_tokens']
                },
                "model": result['model']
            }
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))

