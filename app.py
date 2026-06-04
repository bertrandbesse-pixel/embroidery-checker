import os
import base64
import json
import traceback
from flask import Flask, render_template, request, jsonify
import anthropic

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20 MB max upload

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB per image


def encode_image(image_data: bytes) -> str:
    return base64.standard_b64encode(image_data).decode("utf-8")


def get_media_type(file):
    ct = (file.content_type or "").lower()
    if "png" in ct:
        return "image/png"
    if "webp" in ct:
        return "image/webp"
    if "gif" in ct:
        return "image/gif"
    return "image/jpeg"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    return jsonify({
        "status": "ok",
        "api_key_set": bool(key),
        "api_key_prefix": key[:10] + "..." if key else "NOT SET"
    })


@app.route("/api/compare", methods=["POST"])
def compare():
    try:
        if "mockup" not in request.files or "photo" not in request.files:
            return jsonify({"error": "Both images are required"}), 400

        mockup_file = request.files["mockup"]
        photo_file = request.files["photo"]

        mockup_data = mockup_file.read()
        photo_data = photo_file.read()

        if len(mockup_data) > MAX_IMAGE_SIZE or len(photo_data) > MAX_IMAGE_SIZE:
            return jsonify({"error": "Image too large (max 10MB each)"}), 400

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return jsonify({"error": "ANTHROPIC_API_KEY not configured on server"}), 500

        client = anthropic.Anthropic(api_key=api_key)

        mockup_b64 = encode_image(mockup_data)
        photo_b64 = encode_image(photo_data)
        mockup_media = get_media_type(mockup_file)
        photo_media = get_media_type(photo_file)

        prompt = """You are a quality control checker for luxury embroidery. Compare the mock-up to the embroidery photo.

Be VERY brief. Workers need short, practical feedback — no long sentences.

Respond ONLY with this JSON:
{
  "overall_score": <integer 0-100>,
  "verdict": "<APPROVED | NEEDS REVIEW | REJECTED>",
  "verdict_reason": "<max 8 words>",
  "dimensions": {
    "composition": { "score": <0-100>, "comment": "<max 6 words>" },
    "text_accuracy": { "score": <0-100>, "comment": "<max 6 words>" },
    "color_matching": { "score": <0-100>, "comment": "<max 6 words>" },
    "detail_quality": { "score": <0-100>, "comment": "<max 6 words>" },
    "edge_definition": { "score": <0-100>, "comment": "<max 6 words>" }
  },
  "issues": ["<5 words max>", "<5 words max>"],
  "strengths": ["<5 words max>", "<5 words max>"]
}

Verdicts: APPROVED ≥85, NEEDS REVIEW 65-84, REJECTED <65.
First image = mock-up. Second = embroidery photo."""

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Here is the original mock-up design:"},
                        {"type": "image", "source": {"type": "base64", "media_type": mockup_media, "data": mockup_b64}},
                        {"type": "text", "text": "Here is the photo of the finished embroidery:"},
                        {"type": "image", "source": {"type": "base64", "media_type": photo_media, "data": photo_b64}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )

        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)
        return jsonify(result)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
