import anthropic
import base64
import re
import requests
import json
import tweepy
from dotenv import load_dotenv
import os
import glob

for old_file in glob.glob("schedule_*.jpg"):
    os.remove(old_file)
    print(f"Removed {old_file}")

load_dotenv()
bearer_token = os.getenv("X_BEARER_TOKEN")
anthropic_key = os.getenv("ANTHROPIC_KEY")

# --- Change this URL biweekly to point at the tweet with the current schedule ---
TARGET_TWEET_URL = "https://x.com/DomundiTV/status/2100245889575182340"

name_corrections = {
    "Tie": "Tle",
    "Tia": "Tle",
    "TIe": "Tle",
    "TeeToe": "TeeTee",
    "James": "Jamessu",
}

def correct_names(artists):
    if isinstance(artists, list):
        return [name_corrections.get(a.strip(), a.strip()) for a in artists]
    return name_corrections.get(artists.strip(), artists.strip())

def extract_tweet_id(url):
    match = re.search(r"status/(\d+)", url)
    if not match:
        raise ValueError(f"Could not find a tweet ID in URL: {url}")
    return match.group(1)

def get_tweet_media(client, target_url):
    """Fetch a single tweet by ID via the v2 API and return its image URLs."""
    tweet_id = extract_tweet_id(target_url)
    response = client.get_tweet(
        id=tweet_id,
        tweet_fields=["text"],
        expansions=["attachments.media_keys"],
        media_fields=["url", "type"]
    )
    if not response.data:
        return None, []

    text = response.data.text
    media = response.includes.get("media", []) if response.includes else []
    image_links = [m.url for m in media if m.type == "photo" and m.url]
    return text, image_links

client_x = tweepy.Client(bearer_token=bearer_token)

tweet_text, image_links = get_tweet_media(client_x, TARGET_TWEET_URL)

if tweet_text is None:
    print(f"Could not find tweet {TARGET_TWEET_URL}. Check the ID and your bearer token.")
elif not image_links:
    print("Tweet found but no images attached:", tweet_text)
else:
    print("Target schedule tweet:", tweet_text)
    for i, url in enumerate(image_links):
        img_data = requests.get(url).content
        with open(f"schedule_{i}.jpg", "wb") as f:
            f.write(img_data)
        print(f"Saved schedule_{i}.jpg")

    client = anthropic.Anthropic(api_key=anthropic_key)
    all_events = []
    for i in range(len(image_links)):
        with open(f"schedule_{i}.jpg", "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}},
                    {"type": "text", "text": "Extract the schedule from this image. The numbers at the first column are the day of the month. Return ONLY a JSON array, no explanation. Each object must have: date (as MM/DD/YYYY using the month/year from the image header), event, time, artists. Artist names are from the very right column; if there is an X between put comma. English only, ignore Thai text."}
                ]
            }]
        )
        raw = response.content[0].text.strip().replace("```json", "").replace("```", "")
        events = json.loads(raw)
        for event in events:
            event['artists'] = correct_names(event['artists'])
        all_events.extend(events)

    print(f"\n{'DATE':<12} {'EVENT':<55} {'TIME':<10} {'ARTISTS'}")
    print("-" * 100)
    for e in all_events:
        print(f"{e['date']:<12} {e['event']:<55} {e['time']:<10} {e['artists']}")

    with open("schedule.json", "w") as f:
        json.dump(all_events, f, indent=2)
    print("Saved schedule.json")
