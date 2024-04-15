import logging
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import httpx


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
    logging.info("Sending request to external API.")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload.dict(), headers=headers)
            response.raise_for_status()
            result = response.json()
            logging.info("Received valid response from external API.")
            return {
                "message": result['choices'][0]['message']['content'],
                "tokens": {
                    "prompt_tokens": result['usage']['prompt_tokens'],
                    "completion_tokens": result['usage']['completion_tokens']
                },
                "model": result['model']
            }
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error occurred: {str(e)}")
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            raise HTTPException(status_code=500, detail="An internal error occurred")

@app.get("/")
def read_root():
    return {"Hello": "World"}
