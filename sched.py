import anthropic
import base64
import re
import requests
import json
from datetime import datetime
from Scweet import Scweet
from dotenv import load_dotenv
import os
import glob

for old_file in glob.glob("schedule_*.jpg"):
    os.remove(old_file)
    print(f"Removed {old_file}")

load_dotenv()

auth_token = os.getenv("AUTH_TOKEN")
anthropic_key = os.getenv("ANTHROPIC_KEY")

name_corrections = {
    "Tie": "Tle",
    "Tia": "Tle",
    "TIe": "Tle",
    "James":"Jamessu",
}

def correct_names(artists):
    if isinstance(artists, list):
        return [name_corrections.get(a.strip(), a.strip()) for a in artists]
    return name_corrections.get(artists.strip(), artists.strip())

s = Scweet(auth_token=auth_token)
tweets = s.search("#DMDschedule", from_users=["DomundiTV"], limit=20)

schedule_tweets = []
for tweet in tweets:
    text = tweet.get("text", "")
    match = re.search(r'(\d{1,2}-\d{1,2}\s+\w+\s+\d{4})', text)
    if match:
        date_str = match.group(1)
        end_day = re.search(r'-(\d{1,2})', date_str).group(1)
        month_year = re.search(r'\w+\s+\d{4}', date_str).group(0)
        parsed = datetime.strptime(f"{end_day} {month_year}", "%d %B %Y")
        schedule_tweets.append((parsed, tweet))

if not schedule_tweets:
    print("No schedule tweets found.")
else:
    latest_tweet = max(schedule_tweets, key=lambda x: x[0])[1]
    print("Latest schedule tweet:", latest_tweet.get("text", ""))

    image_links = latest_tweet.get("media", {}).get("image_links", [])
    if not image_links:
        print("No images found.")
    else:
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
                max_tokens=1000,
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