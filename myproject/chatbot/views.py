import json
import logging
import os

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
from django.http import JsonResponse
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

# ---- Configuration (set via environment variables, never hard-code keys) ----
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")          # Mumbai
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
MAX_HISTORY_MESSAGES = 20      # last 10 user/assistant turns kept per visitor
MAX_INPUT_CHARS = 1000

SYSTEM_PROMPT = """
You are the official AI assistant for Roam India, a travel and booking website.

Only help with:
- Hotel searches and reservations
- Flights and travel bookings
- Holiday homes and accommodation
- Activities and travel experiences
- Airport transfers
- Booking procedures, cancellations and support
- Travel destinations and trip planning related to bookings

Rules:
1. Only answer questions related to the website's travel and booking services.
2. Politely decline unrelated questions.
3. For unrelated questions, reply:
"I'm here to help with our website's travel and booking services. Please ask me about hotels, flights, accommodations, activities or bookings."
4. Never invent prices, availability or booking confirmations.
5. Never claim a booking is completed unless the website confirms it.
6. Be friendly, professional and concise.
"""

_client = None


def get_client():
    """Create the Bedrock client once. Credentials come from the standard AWS chain
    (env vars, ~/.aws/credentials, or an IAM role when running on AWS)."""
    global _client
    if _client is None:
        _client = boto3.client(
            "bedrock-runtime",
            config=Config(
                region_name=AWS_REGION,
                read_timeout=60,
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )
    return _client


@require_POST
def chatbot_response(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"reply": "Invalid request."}, status=400)

    message = str(data.get("message", "")).strip()
    if not message:
        return JsonResponse({"reply": "Please enter a message."}, status=400)
    if len(message) > MAX_INPUT_CHARS:
        return JsonResponse(
            {"reply": f"Please keep your message under {MAX_INPUT_CHARS} characters."},
            status=400,
        )

    # Conversation memory is stored per visitor in the Django session.
    history = request.session.get("chat_history", [])
    messages = history + [{"role": "user", "content": [{"text": message}]}]

    try:
        response = get_client().converse(
            modelId=MODEL_ID,
            system=[{"text": SYSTEM_PROMPT}],
            messages=messages,
            inferenceConfig={"maxTokens": 500, "temperature": 0.4},
        )
        reply = response["output"]["message"]["content"][0]["text"].strip()

    except NoCredentialsError:
        logger.error("AWS credentials not found")
        return JsonResponse({"reply": "The assistant is not configured yet."}, status=503)

    except ClientError as error:
        code = error.response["Error"]["Code"]
        logger.error("Bedrock error %s: %s", code, error)
        if code == "ThrottlingException":
            return JsonResponse({"reply": "I'm busy right now. Please try again in a moment."}, status=429)
        if code in ("AccessDeniedException", "ResourceNotFoundException", "ValidationException"):
            return JsonResponse({"reply": "The assistant is not configured correctly."}, status=503)
        return JsonResponse({"reply": "Something went wrong. Please try again."}, status=502)

    except (BotoCoreError, KeyError, IndexError) as error:
        logger.error("Chatbot error: %s", error)
        return JsonResponse({"reply": "Something went wrong. Please try again."}, status=500)

    # Save history (trim, and make sure it always starts with a user message).
    messages.append({"role": "assistant", "content": [{"text": reply}]})
    messages = messages[-MAX_HISTORY_MESSAGES:]
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    request.session["chat_history"] = messages

    return JsonResponse({"reply": reply})