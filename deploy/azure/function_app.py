"""
AgentHub Azure: HTTP endpoint that answers a question using a document
stored in Azure Blob Storage as context, generated via Azure OpenAI.

Request flow:
  1. List blobs in the "documents" container.
  2. Score each document by keyword overlap with the question and pick
     the highest scoring one.
  3. Send the question and document text to Azure OpenAI chat completion.
  4. Return the answer as JSON, including which document was used.
"""

import json
import logging
import os

import azure.functions as func
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

CONTAINER_NAME = "documents"


def get_blob_service_client() -> BlobServiceClient:
    conn_str = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    return BlobServiceClient.from_connection_string(conn_str)


def get_openai_client() -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_KEY"],
        api_version="2024-08-01-preview",
    )


def score_overlap(question: str, text: str) -> int:
    """Count words longer than 3 characters shared by the question and
    the document."""
    q_words = set(w.lower() for w in question.split() if len(w) > 3)
    t_words = set(w.lower() for w in text.split() if len(w) > 3)
    return len(q_words & t_words)


def find_best_document(blob_service: BlobServiceClient, question: str):
    container = blob_service.get_container_client(CONTAINER_NAME)
    best_name, best_text, best_score = None, "", -1

    for blob in container.list_blobs():
        blob_client = container.get_blob_client(blob.name)
        text = blob_client.download_blob().readall().decode("utf-8", errors="ignore")
        score = score_overlap(question, text)
        if score > best_score:
            best_name, best_text, best_score = blob.name, text, score

    return best_name, best_text


@app.route(route="ask", methods=["POST"])
def ask(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("agenthub-azure: /api/ask called")

    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Request body must be JSON with a 'question' field."}),
            status_code=400,
            mimetype="application/json",
        )

    question = (body or {}).get("question", "").strip()
    if not question:
        return func.HttpResponse(
            json.dumps({"error": "Field 'question' is required and cannot be empty."}),
            status_code=400,
            mimetype="application/json",
        )

    try:
        blob_service = get_blob_service_client()
        doc_name, doc_text = find_best_document(blob_service, question)
    except Exception as exc:  # noqa: BLE001 - surface storage errors to the caller
        logging.exception("Blob Storage lookup failed")
        return func.HttpResponse(
            json.dumps({"error": f"Storage lookup failed: {exc}"}),
            status_code=500,
            mimetype="application/json",
        )

    if not doc_name:
        return func.HttpResponse(
            json.dumps({"error": "No documents found in the 'documents' container."}),
            status_code=404,
            mimetype="application/json",
        )

    system_prompt = (
        "You answer questions using only the provided document context. "
        "If the answer is not in the context, say so plainly instead of guessing."
    )
    user_prompt = f"Document ({doc_name}):\n{doc_text}\n\nQuestion: {question}"

    try:
        client = get_openai_client()
        completion = client.chat.completions.create(
            model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_completion_tokens=500,
        )
        answer = completion.choices[0].message.content
    except Exception as exc:  # noqa: BLE001 - surface LLM errors to the caller
        logging.exception("Azure OpenAI call failed")
        return func.HttpResponse(
            json.dumps({"error": f"Azure OpenAI call failed: {exc}"}),
            status_code=500,
            mimetype="application/json",
        )

    return func.HttpResponse(
        json.dumps({"question": question, "source_document": doc_name, "answer": answer}),
        status_code=200,
        mimetype="application/json",
    )
