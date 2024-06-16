from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
import httpx
from supabase import create_client, Client
import os
import logging
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
import uuid
import time
from typing import List

app = FastAPI()

origins = [
    "http://localhost:3000",
    "https://localhost:3000",
    "http://localhost:8080",
    "http://localhost:4200",
    "http://localhost:8000",
    "https://zanzam.kz",
    "https://legendary-doodle-beta.vercel.app/"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
AUTH_TOKEN = os.getenv("AUTH_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.DEBUG)


class Submission(BaseModel):
    question: str


@app.post("/submit/")
async def submit_gpt4(submission: Submission, background_tasks: BackgroundTasks):
    start_time = time.time()

    # # Moderation check
    # moderation_start = time.time()
    # moderation_response = openai_client.moderations.create(input=submission.question)
    # if moderation_response.results[0].flagged:
    #     logging.error("Content flagged by moderation")
    #     raise HTTPException(status_code=400, detail="Content not acceptable")
    # moderation_end = time.time()
    # logging.debug(f"Moderation took {moderation_end - moderation_start:.2f} sec")

    # Preparing the payload and making the API call
    api_call_start = time.time()
    url = "https://canopy-gpt4-production.up.railway.app/v1/chat/completions"
    logging.debug(f"Received submission with question: {submission.question}")

    payload = {
        "messages": [{"role": "user", "content": submission.question}],
    }

    if hasattr(submission, 'style_example') and submission.style_example:
        payload["style_example"] = submission.style_example

    headers = {
        "Content-Type": "application/json",
        "X-Auth-Token": AUTH_TOKEN
    }

    timeout = httpx.Timeout(50.0, connect=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
            logging.debug("API call successful")
    except httpx.HTTPStatusError as e:
        logging.error(f"HTTP error occurred: {e.response.status_code}")
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except httpx.TimeoutException:
        logging.error("Request timed out")
        raise HTTPException(status_code=408, detail="Request timed out")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error")
    api_call_end = time.time()
    logging.debug(f"API call took {api_call_end - api_call_start:.2f} seconds")

    # Saving response to Supabase in the background
    unique_id = str(uuid.uuid4())
    response_data = jsonable_encoder(result)

    background_tasks.add_task(save_to_supabase, unique_id, submission.question, response_data)

    total_time = time.time() - start_time
    logging.debug(f"Total function execution time: {total_time:.2f} seconds")

    return {
        "id": unique_id,
        "message": result['choices'][0]['message']['content'],
        "tokens": {
            "prompt_tokens": result['usage']['prompt_tokens'],
            "completion_tokens": result['usage']['completion_tokens'],
        },
        "model": result['model']
    }


async def save_to_supabase(unique_id: str, question: str, response_data: dict):
    supabase_start = time.time()
    supabase.table("api_logs").insert({
        "id": unique_id,
        "request_question": question,
        "response_data": response_data
    }).execute()
    supabase_end = time.time()
    logging.debug(f"Saving to db {supabase_end - supabase_start:.2f} sec")

    # Define the request and response models
class AnswerCheckRequest(BaseModel):
    user_answer: str
    correct_answer: str

class AnswerCheckResponse(BaseModel):
    is_correct: bool

# Define the endpoint to check the answer
@app.post("/check-answer", response_model=AnswerCheckResponse)
async def check_answer(request: AnswerCheckRequest):
    try:
        # Construct the prompt for the OpenAI model
        prompt = f"""
        The user's answer is: {request.user_answer}
        The correct answer is: {request.correct_answer}
        Is the user's answer roughly correct or similar? Respond with "true" if it is somewhat close, or the main idea is correct. otherwise respond with "false". Be VERY lenient, the child is answering.  Try to forgive some mistakes. But if it's completely wrong/nonsense say false.
        """

        # Call the OpenAI API
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a forgiving middle school teacher."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=10
        )

        # Extract the response content
        assistant_response = response.choices[0].message.content.strip().lower()

        # Interpret the response
        if "true" in assistant_response:
            return AnswerCheckResponse(is_correct=True)
        elif "false" in assistant_response:
            return AnswerCheckResponse(is_correct=False)
        else:
            raise HTTPException(status_code=500, detail="Unexpected response from OpenAI API")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class QaraIntro(BaseModel):
    id: int
    created_at: str
    label: str
    video_url: str


@app.get("/qara_intro", response_model=List[QaraIntro])
async def get_qara_intro():
    response = supabase.table("qara_intro").select("*").execute()
    if response.error:
        raise HTTPException(status_code=400, detail=response.error.message)
    return response.data
