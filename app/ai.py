import json
import requests

from app.config import GEMINI_API_KEY, GEMINI_MODEL


GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
)


def generate_text(prompt):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing.")

    url = (
        GEMINI_URL
        + GEMINI_MODEL
        + ":generateContent?key="
        + GEMINI_API_KEY
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 8192
        }
    }

    last_error = None

    for attempt in range(3):
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=180
            )

            if response.status_code in [429, 500, 502, 503, 504]:
                last_error = response.text
                continue

            response.raise_for_status()

            data = response.json()

            return data["candidates"][0]["content"]["parts"][0]["text"]

        except Exception as error:
            last_error = str(error)

    raise RuntimeError(
        f"Gemini generation failed: {last_error}"
    )


def analyze_segment(segment_number, total_segments, scene_notes):
    prompt = f"""
You are a professional movie story analyst.

Analyze video segment {segment_number} of {total_segments}.

The supplied visual notes are:

{scene_notes}

Instructions:
- Write in natural Burmese.
- Describe only events supported by the supplied notes.
- Preserve chronological order.
- Identify visible characters only when identifiable from context.
- Record important actions, locations, conflicts and emotions.
- Do not invent scenes or dialogue.
- Do not assume the segment is the ending.
- Return structured JSON.

JSON structure:
{{
  "events": [],
  "characters": [],
  "locations": [],
  "important_objects": [],
  "unresolved_questions": [],
  "segment_summary": ""
}}
"""

    return generate_text(prompt)


def create_story_outline(segment_analyses):
    prompt = f"""
You are a professional movie story editor.

Combine these chronological segment analyses:

{json.dumps(segment_analyses, ensure_ascii=False)}

Create a coherent full-story outline in Burmese.

Requirements:
- Maintain the real event order.
- Explain the beginning, conflict, escalation and ending.
- Track character relationships.
- Resolve contradictions using the available evidence.
- Mark uncertain details instead of inventing them.
- Include major twists and consequences.
- Do not fabricate a happy ending.
- Return Burmese prose and structured JSON.
"""

    return generate_text(prompt)


def create_recap_script(story_outline, target_minutes=15):
    prompt = f"""
သင်သည် မြန်မာ Movie Recap ဇာတ်ကြောင်းပြောသူတစ်ဦးဖြစ်သည်။

အောက်ပါ ဇာတ်လမ်းအချက်အလက်ကို အခြေခံပြီး
မူရင်းမြန်မာ Recap Narration Script ရေးပါ။

ဇာတ်လမ်း:
{story_outline}

လိုအပ်ချက်များ:

1. စတင်ချိန်မှာ စိတ်ဝင်စားစေမည့် Hook ပါရမည်။
2. သဘာဝကျသော မြန်မာစကားပြောပုံစံဖြစ်ရမည်။
3. ဇာတ်လမ်းကို အစဉ်လိုက်ရှင်းပြရမည်။
4. Suspense နှင့် Emotion ကို သင့်တင့်စွာသုံးရမည်။
5. ဇာတ်ကောင်အမည်များကို တစ်သမတ်တည်းသုံးရမည်။
6. ဇာတ်သိမ်းကို အချက်အလက်အတိုင်း ရှင်းပြရမည်။
7. ရုပ်ရှင်ထဲက Dialogue များကို ရှည်လျားစွာ ကူးမရေးရ။
8. မရှိသောအဖြစ်အပျက်များ မဖန်တီးရ။
9. မူရင်းသုံးသပ်ချက်နှင့် ကိုယ်ပိုင်ဇာတ်ကြောင်းပြောမှု ပါဝင်ရမည်။
10. Copyright-free သို့မဟုတ် Monetization အာမခံချက် မပေးရ။

ရည်မှန်း Narration ကြာချိန်:
{target_minutes} မိနစ်။

Script ကို အခန်းကဏ္ဍခွဲပြီး ရေးပါ။
"""

    return generate_text(prompt)
