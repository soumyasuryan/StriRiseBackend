from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from urllib.parse import urljoin
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)
CORS(app)

# -------------------------
# Config
# -------------------------
SKILL_URLS = {
    "Beauty & Hair Care Services": "https://www.99businessideas.com/beauty-salon-business/",
    "Homemade Pickle & Snack Sales": "https://www.99businessideas.com/pickle-making-business/",
    "Rabbit Farm": "https://www.99businessideas.com/how-to-start-a-rabbit-farm/",
    "Cardamon Farming": "https://www.99businessideas.com/cardamom-farming/",
    "Carp Fish Business": "https://www.99businessideas.com/carp-fish-business/",
    "Soft Toy Business": "https://www.99businessideas.com/soft-toys-making-business/",
    "Goat Farming": "https://www.99businessideas.com/goat-farming-business/",
    "Event Photography": "https://www.99businessideas.com/photography-business/",
    "Flower Business": "https://www.99businessideas.com/flower-business-ideas/"
}

CACHE = {"all_skills": None, "last_updated": 0}
CACHE_EXPIRY = 60 * 60 * 24  # seconds (24 hours)


# -------------------------
# Helpers: static scrape
# -------------------------
def scrape_page(url, min_summary_len=30):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")

        # title
        title_tag = soup.find("h1") or soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else None

        # paragraphs - collect first useful paragraphs
        paras = [p.get_text(strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
        summary = " ".join(paras[:3]).strip() if paras else ""

        # fallback meta description
        if not summary:
            meta = soup.find("meta", attrs={"name": "description"})
            if meta and meta.get("content"):
                summary = meta.get("content", "").strip()

        # image (og or first img)
        image_url = None
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            image_url = og["content"]
        else:
            img = soup.select_one("article img, .entry-content img, img")
            if img and img.get("src"):
                image_url = img.get("src")

        if image_url:
            if image_url.startswith("//"):
                image_url = "https:" + image_url
            elif image_url.startswith("/"):
                image_url = urljoin(url, image_url)

        summary = re.sub(r"\s+", " ", summary).strip()
        if not title:
            # try meta title
            mt = soup.find("meta", attrs={"property": "og:title"}) or soup.find("meta", attrs={"name": "twitter:title"})
            if mt and mt.get("content"):
                title = mt.get("content")

        if not title or not summary or len(summary) < min_summary_len:
            return None

        return {
            "title": title,
            "summary": summary[:800],
            "image": image_url or None,
            "url": url
        }

    except Exception as e:
        print("scrape_page error:", e, url)
        return None


# -------------------------
# Helpers: Selenium fallback
# -------------------------
def scrape_with_selenium(url, min_summary_len=30):
    try:
        opts = Options()
        opts.add_argument("--headless")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--window-size=1280,1024")

        driver = webdriver.Chrome(ChromeDriverManager().install(), options=opts)
        driver.get(url)
        # small wait for JS
        time.sleep(2)
        html = driver.page_source
        driver.quit()

        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("h1") or soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else None

        paras = [p.get_text(strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
        summary = " ".join(paras[:4]).strip() if paras else ""
        if not summary:
            meta = soup.find("meta", attrs={"name": "description"})
            if meta and meta.get("content"):
                summary = meta.get("content", "").strip()

        image_url = None
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            image_url = og["content"]
        else:
            img = soup.select_one("article img, .entry-content img, img")
            if img and img.get("src"):
                image_url = img.get("src")

        if image_url and image_url.startswith("/"):
            image_url = urljoin(url, image_url)
        if image_url and image_url.startswith("//"):
            image_url = "https:" + image_url

        summary = re.sub(r"\s+", " ", summary).strip()

        if not title or not summary or len(summary) < min_summary_len:
            return None

        return {"title": title, "summary": summary[:800], "image": image_url or None, "url": url}

    except Exception as e:
        print("selenium error:", e, url)
        return None


# -------------------------
# Helpers: DuckDuckGo search fallback
# -------------------------
def search_skill_online(skill):
    try:
        with DDGS() as ddgs:
            query = f"{skill} business idea"
            results = list(ddgs.text(query, max_results=8))

        for r in results:
            link = r.get("href") or r.get("url")
            if not link:
                continue
            # try static scrape first
            data = scrape_page(link, min_summary_len=20)
            if data:
                return data
            # fallback to selenium
            data = scrape_with_selenium(link, min_summary_len=20)
            if data:
                return data
        return None
    except Exception as e:
        print("search_skill_online error:", e)
        return None


# -------------------------
# Preload / cache predefined skills
# -------------------------
def refresh_all_skills_cache(force=False):
    now = time.time()
    if not force and CACHE["all_skills"] and (now - CACHE["last_updated"] < CACHE_EXPIRY):
        return CACHE["all_skills"]

    results = {}
    failed = []
    for skill, url in SKILL_URLS.items():
        data = scrape_page(url, min_summary_len=20)
        if not data:
            data = scrape_with_selenium(url, min_summary_len=20)
        if data:
            results[skill] = data
        else:
            failed.append(url)

    CACHE["all_skills"] = {"skills": results, "failed_urls": failed, "last_updated": now}
    CACHE["last_updated"] = now
    return CACHE["all_skills"]


# -------------------------
# Routes
# -------------------------
@app.route("/")
def root():
    return jsonify({
        "message": "Skill Info API (requests + DDG + Selenium)",
        "endpoints": ["/api/all-skills", "/api/get-skill?skill=..."]
    })


@app.route("/api/all-skills", methods=["GET"])
def api_all_skills():
    data = refresh_all_skills_cache()
    # return only successful skills clean JSON
    return jsonify({"skills": data["skills"], "count": len(data["skills"])})


@app.route("/api/get-skill", methods=["GET"])
def api_get_skill():
    skill = request.args.get("skill", "").strip()
    if not skill:
        return jsonify({"error": "Please provide a skill name"}), 400

    # 1) check cached predefined matches
    cache = refresh_all_skills_cache()
    for k, v in cache["skills"].items():
        if skill.lower() in k.lower():
            return jsonify({"skill": k, "source": "predefined", "data": v})

    # 2) try online search (DDG)
    found = search_skill_online(skill)
    if found:
        return jsonify({"skill": skill, "source": "web_search", "data": found})

    # 3) nothing found
    return jsonify({"error": "No relevant data found for this skill"}), 404


# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    app.run(debug=True)
