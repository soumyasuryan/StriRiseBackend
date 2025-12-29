from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
import re
from urllib.parse import urljoin
from flask_bcrypt import Bcrypt
import jwt
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import os
import joblib
import pandas as pd
import json

# Lightweight Hugging Face client (Inference API)
from huggingface_hub import InferenceClient

# -------------------------
# Config / HF client setup
# -------------------------
HF_TOKEN = os.environ.get("HF_TOKEN", None)
HF_MODEL = os.environ.get("HF_MODEL", "soumyasuryan/striRise_AiRoadMap-model")

# instantiate HF client (no heavy model loaded locally)
if HF_TOKEN:
    hf_client = InferenceClient(model=HF_MODEL, token=HF_TOKEN)
else:
    hf_client = None  # we'll check before calling

# -------------------------
# Flask app and DB config
# -------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_secret')  # change in prod
db_url = os.environ.get("DATABASE_URL")

if db_url:
    db_url = db_url.strip()  

if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)


app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

CORS(app, origins=["https://stri-rise.vercel.app", "http://localhost:3000"], supports_credentials=True)
bcrypt = Bcrypt(app)

db = SQLAlchemy(app)

# -------------------------
# User model / auth
# -------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
if os.environ.get("ENV") == "development":
    with app.app_context():
        db.create_all()



def token_required(f):
    """Decorator: checks Authorization Bearer <token> and returns current_user email to handler."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', None)
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid token header"}), 401

        token = auth_header.split(" ")[1]
        try:
            decoded = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = decoded.get("email")
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        return f(current_user, *args, **kwargs)
    return decorated

# -------------------------
# Auth routes
# -------------------------
@app.route('/signup', methods=['POST'])
def signup():
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already exists"}), 400

    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = jwt.encode(
        {
            "email": user.email,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2)
        },
        app.config['SECRET_KEY'],
        algorithm="HS256"
    )

    return jsonify({"message": "Signup successful!", "token": token}), 200

@app.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401

    token = jwt.encode(
        {"email": user.email, "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2)},
        app.config['SECRET_KEY'],
        algorithm="HS256"
    )
    return jsonify({"message": "Login successful!", "token": token}), 200

@app.route("/api/profile", methods=["GET"])
@token_required
def profile(current_user):
    user = User.query.filter_by(email=current_user).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"email": user.email, "message": f"Welcome back, {user.email}!"}), 200

# --------------------------------------------------------
# Scraper & skill routes (unchanged)
# --------------------------------------------------------
SKILL_URLS = {
    "Beauty & Hair Care Services": "https://www.99businessideas.com/beauty-salon-business/",
    "Homemade Pickle & Snack Sales": "https://www.99businessideas.com/pickle-making-business/",
    "Rabbit Farm": "https://www.99businessideas.com/how-to-start-a-rabbit-farm/",
    "Cardamon Farming": "https://www.99businessideas.com/cardamom-farming/",
    "Carp Fish Buissness": "https://www.99businessideas.com/carp-fish-business/",
    "Soft Toy Buissness": "https://www.99businessideas.com/soft-toys-making-business/",
    "Goat Farming": "https://www.99businessideas.com/goat-farming-business/",
    "Event Photography": "https://www.99businessideas.com/photography-business/",
    "Flower Buissness": "https://www.99businessideas.com/flower-business-ideas/"
}

def scrape_page(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return None
        soup = BeautifulSoup(res.text, "html.parser")

        title = None
        for t in ["h1", "title"]:
            tag = soup.find(t)
            if tag:
                title = tag.get_text(strip=True)
                break
        if not title:
            meta_t = soup.find("meta", attrs={"property": "og:title"}) or soup.find("meta", attrs={"name": "twitter:title"})
            if meta_t and meta_t.get("content"):
                title = meta_t["content"]
        title = title or "No title found"

        summary = ""
        paragraphs = soup.find_all("p")
        if paragraphs:
            summary = " ".join([p.get_text(strip=True) for p in paragraphs[:15]])
        if not summary:
            meta = soup.find("meta", attrs={"name": "description"})
            if meta and meta.get("content"):
                summary = meta["content"]
        if not summary:
            divs = soup.find_all("div")
            if divs:
                summary = " ".join([d.get_text(strip=True) for d in divs[:3]])
        summary = re.sub(r"\s+", " ", summary).strip()

        image_url = None
        for prop in ["og:image", "twitter:image"]:
            meta_img = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
            if meta_img and meta_img.get("content"):
                image_url = meta_img["content"]
                break
        if not image_url:
            img_tag = soup.find("img")
            if img_tag and img_tag.get("src"):
                image_url = img_tag["src"]
        if image_url:
            if image_url.startswith("//"):
                image_url = "https:" + image_url
            elif image_url.startswith("/"):
                image_url = urljoin(url, image_url)

        return {"title": title, "summary": summary if summary else "No summary found", "url": url, "image": image_url or "No image found"}
    except Exception as e:
        print("❌ Error scraping:", url, e)
        return None

def search_skill_online(skill):
    print(f"🔍 Searching online for: {skill}")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"{skill} business idea", max_results=8))
        for r in results:
            link = r.get("href") or r.get("url")
            if not link:
                continue
            data = scrape_page(link)
            if data and data["summary"] and len(data["summary"]) > 30:
                print(f"✅ Found usable match: {link}")
                return data
        print("⚠️ No good match found from DuckDuckGo.")
        return None
    except Exception as e:
        print("❌ Search error:", e)
        return None

@app.route("/api/get-skill", methods=["GET"])
@token_required
def get_skill_info(current_user):
    skill = request.args.get("skill", "").strip()
    if not skill:
        return jsonify({"error": "Please provide a skill name"}), 400
    for name, url in SKILL_URLS.items():
        if skill.lower() in name.lower():
            data = scrape_page(url)
            if data:
                return jsonify({"skill": name, "source": "predefined", "result": data})
    online_data = search_skill_online(skill)
    if online_data:
        return jsonify({"skill": skill, "source": "web_search", "result": online_data})
    return jsonify({"error": "No relevant data found for this skill"}), 404

@app.route("/api/all-skills", methods=["GET"])
@token_required
def all_skills(current_user):
    results = {}
    for skill, url in SKILL_URLS.items():
        data = scrape_page(url)
        if data:
            results[skill] = data
    return jsonify(results)

@app.route("/")
def home():
    return jsonify({
        "message": "Skill Info Scraper API is running ✅",
        "available_skills": list(SKILL_URLS.keys()),
        "usage_example": "/api/get-skill?skill=Home Cleaning Service"
    })

# --------------------------------------------------------
# Classic ML prediction model (joblib) - unchanged
# --------------------------------------------------------
BASE_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(BASE_DIR, "business_recommendation_model.joblib")
ENCODER_PATH = os.path.join(BASE_DIR, "business_label_encoder.joblib")

# ensure these files exist in your project
model = joblib.load(MODEL_PATH)
label_encoder = joblib.load(ENCODER_PATH)
print("✅ Model and Label Encoder loaded successfully!")

@app.route("/business_rec", methods=["POST"])
def business_rec():
    return jsonify({"message": "✅ Business Recommendation API is running!"})

@app.route("/predict", methods=["POST"])
@token_required
def predict(current_user):
    try:
        data = request.get_json()
        df = pd.DataFrame([data])

        preprocessor = model.named_steps["preprocessor"]
        categorical_features = preprocessor.transformers_[0][2]
        numeric_features = preprocessor.transformers_[1][2]
        expected_cols = categorical_features + numeric_features

        for col in expected_cols:
            if col not in df.columns:
                if col in categorical_features:
                    df[col] = "Unknown"
                else:
                    df[col] = 0

        prediction = model.predict(df)
        result = label_encoder.inverse_transform(prediction)[0]

        return jsonify({"success": True, "predicted_business": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/items', methods=['GET'])
def get_items():
    base_path = os.path.dirname(os.path.abspath(__file__))
    purchasable_path = os.path.join(base_path, 'purchasable.json')
    rentable_path = os.path.join(base_path, 'rentable.json')

    with open(purchasable_path, 'r') as f:
        purchasable_items = json.load(f)

    with open(rentable_path, 'r') as f:
        rentable_items = json.load(f)

    return jsonify({'purchasable_items': purchasable_items, 'rentable_items': rentable_items})

@app.route('/api/courses', methods=['GET'])
def get_courses():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(current_dir, 'courses.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        courses_data = json.load(f)
    return jsonify(courses_data)

# --------------------------------------------------------
# Lightweight HF-backed Hinglish roadmap endpoint
# --------------------------------------------------------
def sanitize_input(text):
    banned_words = ["sex", "nude", "kill", "bomb", "drugs"]
    for w in banned_words:
        if w.lower() in text.lower():
            return None
    return text


# -----------------------------
# HF Chat Completion with Retry
# -----------------------------
def generate_roadmap(prompt, retries=3):
    for attempt in range(retries):
        try:
            response = hf_client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a helpful AI who replies in Hinglish."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=350,
                temperature=0.7,
                top_p=0.9,
                stream=False
            )

            # HF chat returns `choices`
            if response and "choices" in response:
                return response["choices"][0]["message"]["content"]

            return "Unable to generate roadmap."

        except Exception as e:
            print(f"⚠️ HF attempt {attempt+1} failed → {e}")
            time.sleep(1.2)

    return None




# -----------------------------
# API Endpoint
# -----------------------------
@app.route("/api/business-roadmap", methods=["POST"])
@token_required
def business_roadmap(current_user):
    try:
        data = request.get_json()

        gender = data.get("gender")
        age = data.get("age")
        location = data.get("location")
        budget = data.get("budget")
        skills = data.get("skills")
        risk_tolerance = data.get("risk_tolerance")
        business_type = data.get("business_type")

        profile = f"{gender}, age {age}, location {location}, budget {budget}, skills: {skills}, risk tolerance: {risk_tolerance}"

        # Build instruction
        if business_type:
            instruction = f"{profile}. Suggest a practical roadmap for {business_type} in Hinglish."
        else:
            instruction = f"{profile}. Suggest a practical business idea and roadmap in Hinglish."

        # Safety Check
        if sanitize_input(instruction) is None:
            return jsonify({"success": False, "error": "Unsafe or invalid input"}), 400

        # Generate Roadmap
        roadmap_text = generate_roadmap(instruction)

        if not roadmap_text:
            return jsonify({"success": False, "error": "HF model failed after retries"}), 500

        # Clean output (remove markdown artifacts)
        roadmap_text = re.sub(r"[#*`_]+", "", roadmap_text)

        return jsonify({
            "success": True,
            "profile": profile,
            "instruction": instruction,
            "roadmap": roadmap_text
        })

    except Exception as e:
        print("❌ business_roadmap error:", e)
        return jsonify({"success": False, "error": str(e)}), 500




# -------------------------
# Run the app
# -------------------------
# -------------------------
# Run the app
# -------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
