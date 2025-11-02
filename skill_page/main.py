from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
import re
from urllib.parse import urljoin

app = Flask(__name__)
CORS(app)

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


# --------------------------------------------------------
# 7️⃣ Run
# --------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
