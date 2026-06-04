import os
import base64
import json
from flask import Flask, render_template, request, jsonify
import anthropic

app = Flask(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB


def encode_image(image_data: bytes, media_type: str) -> str:
    return base64.standard_b64encode(image_data).decode("utf-8")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/compare", methods=["POST"])
def compare():
    if "mockup" not in request.files or "photo" not in request.files:
        return jsonify({"error": "Both images are required"}), 400

    mockup_file = request.files["mockup"]
    photo_file = request.files["photo"]

    mockup_data = mockup_file.read()
    photo_data = photo_file.read()

    if len(mockup_data) > MAX_IMAGE_SIZE or len(photo_data) > MAX_IMAGE_SIZE:
        return jsonify({"error": "Image too large (max 10MB)"}), 400

    def get_media_type(file):
        ct = file.content_type or ""
        if "png" in ct:
            return "image/png"
        if "jpg" in ct or "jpeg" in ct:
            return "image/jpeg"
        if "webp" in ct:
            return "image/webp"
        return "image/jpeg"

    mockup_b64 = encode_image(mockup_data, get_media_type(mockup_file))
    photo_b64 = encode_image(photo_data, get_media_type(photo_file))
    mockup_media = get_media_type(mockup_file)
    photo_media = get_media_type(photo_file)

    prompt = """You are a quality control expert for luxury embroidery at a high-end fashion house (Olympia Le Tan).
Your job is to compare a digital mock-up design against a photo of the finished embroidery.

Analyze both images carefully across these dimensions:

1. OVERALL COMPOSITION — Does the layout, proportions, and placement match?
2. TEXT ACCURACY — Is any text correctly reproduced? Check spelling, typography style, size, position.
3. COLOR MATCHING — Are the colors (especially black, white, red threads) accurate to the mock-up?
4. DETAIL & LINE QUALITY — Are fine lines, illustrations, and intricate elements faithfully rendered?
5. EDGE DEFINITION — Are the borders and outlines clean and precise?

Respond ONLY with a valid JSON object in this exact format:
{
  "overall_score": <integer 0-100>,
  "verdict": "<APPROVED | NEEDS REVIEW | REJECTED>",
  "verdict_reason": "<one sentence summary>",
  "dimensions": {
    "composition": { "score": <0-100>, "comment": "<brief note>" },
    "text_accuracy": { "score": <0-100>, "comment": "<brief note>" },
    "color_matching": { "score": <0-100>, "comment": "<brief note>" },
    "detail_quality": { "score": <0-100>, "comment": "<brief note>" },
    "edge_definition": { "score": <0-100>, "comment": "<brief note>" }
  },
  "issues": ["<specific issue 1>", "<specific issue 2>"],
  "strengths": ["<strength 1>", "<strength 2>"]
}

Verdicts:
- APPROVED: overall_score >= 85 and no critical issues
- NEEDS REVIEW: overall_score 65-84 or minor issues found
- REJECTED: overall_score < 65 or critical flaws

Be precise and professional. The first image is the mock-up, the second is the embroidery photo."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Here is the original mock-up design:",
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mockup_media,
                            "data": mockup_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Here is the photo of the finished embroidery:",
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": photo_media,
                            "data": photo_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ],
    )

    raw = message.content[0].text.strip()
    # Strip markdown code block if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    result = json.loads(raw)
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
