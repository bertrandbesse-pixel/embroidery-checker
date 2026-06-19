import os
import base64
import json
import traceback
from flask import Flask, render_template, request, jsonify
import anthropic

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB max upload

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB per file


def encode_image(image_data: bytes) -> str:
    return base64.standard_b64encode(image_data).decode("utf-8")


def get_media_type(file):
    ct = (file.content_type or "").lower()
    name = (file.filename or "").lower()
    if "pdf" in ct or name.endswith(".pdf"):
        return "application/pdf"
    if "png" in ct:
        return "image/png"
    if "webp" in ct:
        return "image/webp"
    if "gif" in ct:
        return "image/gif"
    return "image/jpeg"


def is_pdf(file) -> bool:
    return get_media_type(file) == "application/pdf"


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

        if len(mockup_data) > MAX_FILE_SIZE or len(photo_data) > MAX_FILE_SIZE:
            return jsonify({"error": "File too large (max 20MB each)"}), 400

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return jsonify({"error": "ANTHROPIC_API_KEY not configured on server"}), 500

        client = anthropic.Anthropic(api_key=api_key)

        mockup_b64 = encode_image(mockup_data)
        photo_b64 = encode_image(photo_data)
        photo_media = get_media_type(photo_file)

        if is_pdf(mockup_file):
            mockup_block = {
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": mockup_b64}
            }
        else:
            mockup_block = {
                "type": "image",
                "source": {"type": "base64", "media_type": get_media_type(mockup_file), "data": mockup_b64}
            }

        prompt = """You are a quality control inspector for luxury embroidery at Olympia Le-Tan.
The embroidery photo shows the piece from multiple angles: FRONT (recto), SPINE (tranche), and BACK (verso) in a single photo.

Be VERY brief. Workers need short, practical feedback — no long sentences.

CRITICAL CHECK POINTS:
1. TEXT ACCURACY: Check every character letter by letter — especially accents (é, è, ê, à, ç, ù, etc.) and exact spelling
2. SPINE ALIGNMENT: Text on the spine/tranche must be straight, evenly spaced and perfectly aligned
3. OLT LOGO: The OLT logo must be present on the spine and correctly positioned
4. FACES: If faces are present — eyes must look in the same direction, eyebrows must be the same size and shape
5. COLORS: Thread colors must match the mock-up exactly

Respond ONLY with this JSON:
{
  "overall_score": <integer 0-100>,
  "verdict": "<APPROVED | NEEDS REVIEW | REJECTED>",
  "verdict_reason": "<max 8 words>",
  "dimensions": {
    "text_accuracy": { "score": <0-100>, "comment": "<max 6 words — note any accent/spelling errors>" },
    "spine_alignment": { "score": <0-100>, "comment": "<max 6 words — text and logo straightness>" },
    "olt_logo": { "score": <0-100>, "comment": "<max 6 words — logo present and correctly placed>" },
    "color_matching": { "score": <0-100>, "comment": "<max 6 words>" },
    "face_detail": { "score": <0-100>, "comment": "<max 6 words — eyes/eyebrows, or write N/A if no faces>" }
  },
  "issues": ["<5 words max>", "<5 words max>"],
  "strengths": ["<5 words max>", "<5 words max>"]
}

Verdicts: APPROVED ≥85, NEEDS REVIEW 65-84, REJECTED <65.
First = mock-up design. Second image = embroidery photo (front + spine + back)."""

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Here is the original mock-up design:"},
                        mockup_block,
                        {"type": "text", "text": "Here is the photo of the finished embroidery (front, spine and back visible in one photo):"},
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
