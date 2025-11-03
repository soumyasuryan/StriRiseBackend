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

app = Flask(__name__)
CORS(app)
bcrypt = Bcrypt(app)

app.config['SECRET_KEY'] = 'supersecretkey123'  # change this in production

# In-memory user store (for demo)
USERS = {}

# ✅ SIGNUP
@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    print(f"New signup: {name}, {email}")
    return jsonify({"message": "Signup successful!"}), 200

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    print(f"Login attempt: {email}")
    
    # Simple check — replace with real DB logic
    if email == "test@example.com" and password == "1234":
        return jsonify({"message": "Login successful!"}), 200
    else:
        return jsonify({"error": "Invalid email or password"}), 401

# ✅ Example protected route
@app.route("/api/profile", methods=["GET"])
def profile():
    token = request.headers.get("Authorization")

    if not token:
        return jsonify({"error": "Missing token"}), 401

    try:
        decoded = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        return jsonify({"username": decoded["username"], "message": "Welcome back!"})
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401


# --------------------------------------------------------
# 1️⃣ Predefined skill URLs
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

# --------------------------------------------------------
# 2️⃣ Scraper function
# --------------------------------------------------------
def scrape_page(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return None

        soup = BeautifulSoup(res.text, "html.parser")

        # Title
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

        # Summary - more aggressive extraction
        summary = ""
        paragraphs = soup.find_all("p")
        if paragraphs:
            summary = " ".join([p.get_text(strip=True) for p in paragraphs[:4]])
        if not summary:
            meta = soup.find("meta", attrs={"name": "description"})
            if meta and meta.get("content"):
                summary = meta["content"]
        if not summary:
            divs = soup.find_all("div")
            if divs:
                summary = " ".join([d.get_text(strip=True) for d in divs[:3]])

        summary = re.sub(r"\s+", " ", summary).strip()

        # Image extraction
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

        return {
            "title": title,
            "summary": summary[:600] if summary else "No summary found",
            "url": url,
            "image": image_url or "No image found"
        }

    except Exception as e:
        print("❌ Error scraping:", url, e)
        return None


def search_skill_online(skill):
    print(f"🔍 Searching online for: {skill}")
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(f"{skill} business idea", max_results=8))

        for r in results:
            link = r.get("href") or r.get("url")
            if not link:
                continue

            data = scrape_page(link)
            # now accept even smaller summaries
            if data and data["summary"] and len(data["summary"]) > 30:
                print(f"✅ Found usable match: {link}")
                return data

        print("⚠️ No good match found from DuckDuckGo.")
        return None

    except Exception as e:
        print("❌ Search error:", e)
        return None


# --------------------------------------------------------
# 4️⃣ Combined API
# --------------------------------------------------------
@app.route("/api/get-skill", methods=["GET"])
def get_skill_info():
    skill = request.args.get("skill", "").strip()
    if not skill:
        return jsonify({"error": "Please provide a skill name"}), 400

    # Step 1: Check predefined
    for name, url in SKILL_URLS.items():
        if skill.lower() in name.lower():
            data = scrape_page(url)
            if data:
                return jsonify({"skill": name, "source": "predefined", "result": data})

    # Step 2: Search online fallback 
    online_data = search_skill_online(skill)
    if online_data:
        return jsonify({"skill": skill, "source": "web_search", "result": online_data})

    return jsonify({"error": "No relevant data found for this skill"}), 404


# --------------------------------------------------------
# 5️⃣ Get all skills for home page
# --------------------------------------------------------
@app.route("/api/all-skills", methods=["GET"])
def all_skills():
    results = {}
    for skill, url in SKILL_URLS.items():
        data = scrape_page(url)
        if data:  # only include successful ones
            results[skill] = data
    return jsonify(results)


# --------------------------------------------------------
# 6️⃣ Root route
# --------------------------------------------------------
@app.route("/")
def home():
    return jsonify({
        "message": "Skill Info Scraper API is running ✅",
        "available_skills": list(SKILL_URLS.keys()),
        "usage_example": "/api/get-skill?skill=Home Cleaning Service"
    })

import joblib
import os



# --------------------------------------------------------
# 1️⃣ Load Model and Label Encoder
# --------------------------------------------------------
BASE_DIR = os.path.dirname(__file__)

MODEL_PATH = os.path.join(BASE_DIR, "business_recommendation_model.joblib")
ENCODER_PATH = os.path.join(BASE_DIR, "business_label_encoder.joblib")

model = joblib.load(MODEL_PATH)
label_encoder = joblib.load(ENCODER_PATH)

print("✅ Model and Label Encoder loaded successfully!")

# --------------------------------------------------------
# 2️⃣ Health Check Route
# --------------------------------------------------------
@app.route("/business_rec", methods=["POST"])
def business_rec():
    return jsonify({"message": "✅ Business Recommendation API is running!"})

import pandas as pd
# --------------------------------------------------------
# 3️⃣ Prediction Route
# --------------------------------------------------------
@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json()

        # Convert JSON input to DataFrame
        df = pd.DataFrame([data])

        # Extract expected columns from model preprocessor
        preprocessor = model.named_steps["preprocessor"]
        categorical_features = preprocessor.transformers_[0][2]
        numeric_features = preprocessor.transformers_[1][2]
        expected_cols = categorical_features + numeric_features

        # Handle missing columns gracefully
        for col in expected_cols:
            if col not in df.columns:
                # Assign default values
                if col in categorical_features:
                    df[col] = "Unknown"
                else:
                    df[col] = 0

        # Make prediction
        prediction = model.predict(df)
        result = label_encoder.inverse_transform(prediction)[0]

        return jsonify({
            "success": True,
            "predicted_business": result
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })
import json
@app.route('/items', methods=['GET'])
def get_items():
    base_path = os.path.dirname(os.path.abspath(__file__))
    purchasable_path = os.path.join(base_path, 'purchasable.json')
    rentable_path = os.path.join(base_path, 'rentable.json')

    with open(purchasable_path, 'r') as f:
        purchasable_items = json.load(f)

    with open(rentable_path, 'r') as f:
        rentable_items = json.load(f)

    return jsonify({
        'purchasable_items': purchasable_items,
        'rentable_items': rentable_items
    })
@app.route('/api/courses', methods=['GET'])
def get_courses():
    # Get the path to the JSON file in the same directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(current_dir, 'courses.json')
    
    # Read JSON data from the file
    with open(json_path, 'r', encoding='utf-8') as f:
        courses_data = json.load(f)
    
    # Return JSON response
    return jsonify(courses_data)
# --------------------------------------------------------
# 4️⃣ Run the App
# --------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
