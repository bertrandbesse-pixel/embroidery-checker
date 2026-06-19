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

        prompt = """You are an expert quality control inspector for luxury hand embroidery at Olympia Le-Tan.
The embroidery photo shows the piece from multiple angles in one image: FRONT (recto), SPINE (tranche), and BACK (verso).

INSPECTION RULES — read carefully before scoring:

A. LETTERFORM INTEGRITY (most critical)
   Examine every single letter individually against the mock-up:
   - Are all strokes complete? Check beginnings and ends of each stroke (no missing terminals, no short ends)
   - Are vertical strokes truly vertical? Are curved strokes correctly shaped?
   - Is each letter the same height as its neighbours in the same word?
   - Are the proportions of each letter correct (not too wide, not too narrow)?
   - Is letter spacing even throughout each word?
   Example defects to flag: "W end is short", "R shorter than E from top", "X lower lines broader than upper", "D standing line does not touch curve"

B. SPELLING & ACCENTS
   Check every character: accents (é, è, ê, à, ç, ù…), spelling, punctuation. Flag any difference.

C. SPINE / TRANCHE
   - Text must be perfectly straight (no tilt), same height for all letters, even spacing between letters
   - OLT logo must be present on the spine and correctly positioned
   Example defect: "S letters have extra space between them"

D. FACES (if present)
   - Eyes must look in the exact same direction
   - Both eyebrows must be the same size and shape

E. COLORS
   - Thread colors must match the mock-up exactly (no shade differences)

Be VERY brief in comments. Workers need specific, actionable feedback — name the exact letter or detail.

Respond ONLY with this JSON (no extra text, no markdown):
{
  "overall_score": <integer 0-100>,
  "verdict": "<APPROVED | NEEDS REVIEW | REJECTED>",
  "verdict_reason": "<max 8 words>",
  "dimensions": {
    "letterform_accuracy": { "score": <0-100>, "comment": "<max 8 words — name specific letters with issues>" },
    "text_spelling": { "score": <0-100>, "comment": "<max 6 words — accents/spelling or OK>" },
    "spine_quality": { "score": <0-100>, "comment": "<max 6 words — straightness, spacing, logo>" },
    "color_matching": { "score": <0-100>, "comment": "<max 6 words>" },
    "face_detail": { "score": <0-100>, "comment": "<max 6 words — eyes/eyebrows, or N/A>" }
  },
  "issues": [
    {"text": "<defect description, max 8 words>", "x": <0-100>, "y": <0-100>},
    ...one entry per distinct defect
  ],
  "strengths": ["<max 6 words>", "<max 6 words>"]
}

For "x" and "y": approximate center of the defective letter or area in the EMBROIDERY PHOTO.
x=0 is left edge, x=100 is right edge, y=0 is top, y=100 is bottom.

Verdicts: APPROVED ≥85, NEEDS REVIEW 65-84, REJECTED <65.
First = mock-up design. Second image = embroidery photo (front + spine + back)."""

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
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
