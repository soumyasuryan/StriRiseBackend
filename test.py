import requests
from bs4 import BeautifulSoup
import json
import time

# List of skills and their respective URLs
skills_urls = {
    "Beauty & Hair Care Services": "https://www.99businessideas.com/beauty-salon-business/",
    "Homemade Pickle & Snack Sales": "https://www.99businessideas.com/pickle-making-business/",
    "Rabbit Farm": "https://www.99businessideas.com/rabbit-farming-business/",
    "Cardamon Farming": "https://www.99businessideas.com/cardamom-farming/",
    "Carp Fish Buissness": "https://www.99businessideas.com/fish-farming-business/",
    "Soft Toy Buissness": "https://www.99businessideas.com/soft-toys-making-business/",
    "Goat Farming": "https://www.99businessideas.com/goat-farming-business/",
    "Event Photography": "https://www.99businessideas.com/photography-business/",
    "Flower Buissness": "https://www.99businessideas.com/flower-business/",
}

# User-agent header to avoid blocking
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

results = {}

print("🔍 Testing all skill URLs...\n")

for skill, url in skills_urls.items():
    print(f"Fetching: {skill} -> {url}")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract title
        title = soup.find("h1")
        title_text = title.get_text(strip=True) if title else soup.title.get_text(strip=True)

        # Extract summary or paragraph snippet
        p_tag = soup.find("p")
        summary_snippet = p_tag.get_text(strip=True)[:250] if p_tag else "No summary found."

        # Extract image (try og:image first)
        image_tag = soup.find("meta", property="og:image")
        if image_tag and image_tag.get("content"):
            image_url = image_tag["content"]
        else:
            # fallback: find first <img> in content
            img = soup.find("img")
            image_url = img["src"] if img and img.get("src") else None

        if not image_url:
            image_url = "https://via.placeholder.com/300x200?text=No+Image"

        print(f"✅ Success: {title_text[:60]}...")

        results[skill] = {
            "status": "success",
            "title": title_text,
            "summary_snippet": summary_snippet,
            "image_url": image_url
        }

    except Exception as e:
        print(f"❌ Failed to scrape ({e})")
        results[skill] = {"status": "failed"}

    time.sleep(1)  # polite delay

print("\n🧾 Final Results:\n")
print(json.dumps(results, indent=2, ensure_ascii=False))

# Save output
with open("skill_data.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
