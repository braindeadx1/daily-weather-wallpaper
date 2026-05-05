#!/usr/bin/env python3
"""
Daily Weather Wallpaper
AI-generated weather image via ComfyUI + FLUX.1-schnell
Overlay with Open-Meteo weather data, sent via WhatsApp

https://github.com/braindeadx1/daily-weather-wallpaper
"""

import json
import os
import sys
import time
import uuid
import subprocess
import urllib.request
import urllib.parse
import datetime
import tempfile
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install Pillow")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)


# ─── Config ──────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "config.json"

def load_config():
    if not CONFIG_FILE.exists():
        print(f"ERROR: config.json not found. Copy config.example.json to config.json and edit it.")
        sys.exit(1)
    return json.loads(CONFIG_FILE.read_text())


# ─── WMO Weather Code Mapping ─────────────────────────────────────────────────

WMO_DESCRIPTIONS = {
    0:  ("Klarer Himmel",       "clear sky"),
    1:  ("Überwiegend klar",    "mostly clear sky, few clouds"),
    2:  ("Teilweise bewölkt",   "partly cloudy sky, scattered clouds"),
    3:  ("Bedeckt",             "overcast cloudy sky"),
    45: ("Nebel",               "foggy misty atmosphere"),
    48: ("Raureif-Nebel",       "freezing fog"),
    51: ("Leichter Nieselregen", "light drizzle, wet streets"),
    53: ("Nieselregen",         "drizzle, grey wet weather"),
    55: ("Starker Nieselregen", "heavy drizzle, dark grey sky"),
    61: ("Leichter Regen",      "light rain, wet streets, puddles"),
    63: ("Regen",               "rain, dark clouds, wet atmosphere"),
    65: ("Starker Regen",       "heavy rain, stormy dark sky, rain drops"),
    71: ("Leichter Schnee",     "light snowfall, white landscape"),
    73: ("Schneefall",          "snowfall, white snowy landscape"),
    75: ("Starker Schnee",      "heavy snowfall, blizzard"),
    77: ("Schneekristalle",     "snow grains, icy cold"),
    80: ("Regenschauer",        "rain showers, dramatic clouds"),
    81: ("Starke Schauer",      "heavy rain showers, dark dramatic sky"),
    82: ("Heftige Schauer",     "violent rain showers, stormy"),
    85: ("Schneeschauer",       "snow showers, cold winter"),
    86: ("Starke Schneeschauer","heavy snow showers"),
    95: ("Gewitter",            "thunderstorm, dramatic lightning, dark sky"),
    96: ("Gewitter mit Hagel",  "thunderstorm with hail, dramatic"),
    99: ("Starkes Gewitter",    "severe thunderstorm, lightning, hail"),
}

WMO_MOOD = {
    # (base_mood, lighting, colors)
    0:  ("sunny",       "golden hour sunlight",     "bright warm golden colors, vivid"),
    1:  ("sunny",       "bright sunlight",           "warm colors, blue sky"),
    2:  ("partly_cloudy","mixed sunlight and clouds","blue and white sky, pleasant"),
    3:  ("cloudy",      "diffuse grey light",        "muted grey tones, overcast"),
    45: ("fog",         "foggy dim light",           "desaturated, grey, misty"),
    48: ("fog",         "freezing fog",              "cold grey white tones"),
    51: ("rain",        "dark grey light",           "grey blue tones, wet reflections"),
    53: ("rain",        "dark overcast",             "dark grey, wet streets"),
    55: ("rain",        "very dark overcast",        "dark grey, heavy rain"),
    61: ("rain",        "dark rainy",                "grey dark sky, rain streaks"),
    63: ("rain",        "stormy dark",               "dark stormy sky, heavy rain"),
    65: ("storm",       "dramatic dark",             "very dark dramatic sky"),
    71: ("snow",        "bright white",              "pure white, cold blue tones"),
    73: ("snow",        "snowy grey white",          "white grey, soft light"),
    75: ("blizzard",    "blinding white",            "white grey, blizzard"),
    80: ("rain",        "dark dramatic",             "dark clouds, rain"),
    81: ("storm",       "very dark",                 "stormy dark dramatic"),
    82: ("storm",       "extremely dark",            "violent storm"),
    95: ("thunderstorm","lightning flashes",         "very dark purple grey, dramatic lightning"),
    96: ("thunderstorm","lightning and hail",        "dark dramatic, lightning"),
    99: ("thunderstorm","severe lightning",          "extremely dark dramatic storm"),
}

def get_weather_emoji(code):
    emojis = {
        0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️",
        45: "🌫️", 48: "🌫️",
        51: "🌦️", 53: "🌧️", 55: "🌧️",
        61: "🌧️", 63: "🌧️", 65: "🌧️",
        71: "🌨️", 73: "❄️", 75: "❄️", 77: "🌨️",
        80: "🌦️", 81: "🌧️", 82: "⛈️",
        85: "🌨️", 86: "❄️",
        95: "⛈️", 96: "⛈️", 99: "⛈️",
    }
    return emojis.get(code, "🌡️")

def build_prompt(weather_code, temp_max, temp_min, location):
    desc_de, desc_en = WMO_DESCRIPTIONS.get(weather_code, ("Unbekannt", "unknown weather"))
    mood, lighting, colors = WMO_MOOD.get(weather_code, ("cloudy", "grey light", "grey tones"))
    prompt = (
        f"a beautiful cityscape of {location} in Germany at morning, "
        f"{desc_en}, {lighting}, {colors}, "
        f"temperature {temp_min:.0f} to {temp_max:.0f} degrees celsius, "
        f"photorealistic, high quality, cinematic, 8k"
    )
    negative = "text, watermark, ugly, blurry, distorted, cartoon, anime"
    return prompt, negative


# ─── Open-Meteo Weather Fetch ─────────────────────────────────────────────────

def fetch_weather(lat, lon, timezone):
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&hourly=temperature_2m,weathercode,precipitation_probability,windspeed_10m,apparent_temperature"
        f"&daily=weathercode,temperature_2m_max,temperature_2m_min,windspeed_10m_max,precipitation_probability_max"
        f"&timezone={urllib.parse.quote(timezone)}"
        f"&forecast_days=1"
    )
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()

def parse_weather(data):
    hourly = data["hourly"]
    daily = data["daily"]
    today = datetime.date.today()

    # Stunden 6-22 Uhr
    hours = []
    for i, t in enumerate(hourly["time"]):
        dt = datetime.datetime.fromisoformat(t)
        if dt.date() == today and 6 <= dt.hour <= 22:
            hours.append({
                "hour": dt.hour,
                "temp": hourly["temperature_2m"][i],
                "feels_like": hourly["apparent_temperature"][i],
                "rain_prob": hourly["precipitation_probability"][i],
                "wind": hourly["windspeed_10m"][i],
                "code": hourly["weathercode"][i],
            })

    # Tageswerte
    noon_code = daily["weathercode"][0]
    temp_max = daily["temperature_2m_max"][0]
    temp_min = daily["temperature_2m_min"][0]
    wind_max = daily["windspeed_10m_max"][0]
    rain_max = daily["precipitation_probability_max"][0]

    return {
        "hours": hours,
        "code": noon_code,
        "temp_max": temp_max,
        "temp_min": temp_min,
        "wind_max": wind_max,
        "rain_max": rain_max,
        "date": today,
    }


# ─── ComfyUI Image Generation ────────────────────────────────────────────────

def build_workflow(prompt, negative, steps=4, width=1920, height=1080):
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "flux1-schnell-Q5_K_S.gguf"}},
        "2": {"class_type": "DualCLIPLoader", "inputs": {
            "clip_name1": "t5xxl_fp8.safetensors",
            "clip_name2": "clip_l.safetensors",
            "type": "flux", "device": "default"
        }},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": negative}},
        "6": {"class_type": "EmptySD3LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0],
            "latent_image": ["6", 0], "seed": int(time.time()),
            "steps": steps, "cfg": 1.0, "sampler_name": "euler",
            "scheduler": "simple", "denoise": 1.0
        }},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "weather_daily", "images": ["8", 0]}},
    }

def generate_image(comfyui_host, prompt, negative):
    import json as jsonlib
    client_id = str(uuid.uuid4())
    workflow = build_workflow(prompt, negative)
    data = jsonlib.dumps({"prompt": workflow, "client_id": client_id}).encode()
    req = urllib.request.Request(
        f"http://{comfyui_host}/prompt", data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = jsonlib.loads(resp.read())
    prompt_id = result["prompt_id"]
    print(f"  ComfyUI Job: {prompt_id}")

    # Warten auf Ergebnis
    deadline = time.time() + 300
    while time.time() < deadline:
        with urllib.request.urlopen(f"http://{comfyui_host}/history/{prompt_id}", timeout=10) as resp:
            history = jsonlib.loads(resp.read())
        if prompt_id in history:
            outputs = history[prompt_id].get("outputs", {})
            for node_out in outputs.values():
                if "images" in node_out:
                    img = node_out["images"][0]
                    url = f"http://{comfyui_host}/view?filename={img['filename']}&subfolder={img.get('subfolder','')}&type=output"
                    return url, img["filename"]
        time.sleep(2)
    raise TimeoutError("ComfyUI timeout after 300s")

def download_image(url, dest_path):
    with urllib.request.urlopen(url, timeout=30) as resp:
        with open(dest_path, "wb") as f:
            f.write(resp.read())


# ─── Overlay Drawing ──────────────────────────────────────────────────────────

def draw_overlay(image_path, weather, location_name, output_path):
    img = Image.open(image_path).convert("RGBA")
    W, H = img.size
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Fonts (Fallback auf default wenn nicht vorhanden)
    def get_font(size):
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        ]
        for fp in font_paths:
            if os.path.exists(fp):
                return ImageFont.truetype(fp, size)
        return ImageFont.load_default()

    def get_font_regular(size):
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
        ]
        for fp in font_paths:
            if os.path.exists(fp):
                return ImageFont.truetype(fp, size)
        return ImageFont.load_default()

    font_large  = get_font(72)
    font_medium = get_font(48)
    font_small  = get_font(36)
    font_tiny   = get_font_regular(28)

    # Untere Leiste: dunkler Hintergrund
    bar_h = int(H * 0.38)
    bar_y = H - bar_h
    draw.rectangle([(0, bar_y), (W, H)], fill=(0, 0, 0, 180))

    # Obere Info-Zeile
    pad = 40
    today = weather["date"]
    WOCHENTAGE = ["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"]
    MONATE = ["Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember"]
    date_str = f"{WOCHENTAGE[today.weekday()]}, {today.day}. {MONATE[today.month - 1]} {today.year}"
    emoji = get_weather_emoji(weather["code"])
    desc_de = WMO_DESCRIPTIONS.get(weather["code"], ("", ""))[0]

    # Ort + Temperatur
    temp_str = f"{weather['temp_min']:.0f}°  /  {weather['temp_max']:.0f}°C"
    draw.text((pad, bar_y + 20), f"{location_name}", font=font_large, fill=(255, 255, 255, 255))
    draw.text((pad, bar_y + 100), f"{desc_de}", font=font_medium, fill=(200, 230, 255, 220))

    # Datum rechts
    bbox = draw.textbbox((0, 0), date_str, font=font_small)
    tw = bbox[2] - bbox[0]
    draw.text((W - tw - pad, bar_y + 30), date_str, font=font_small, fill=(200, 200, 200, 220))

    # Temperatur rechts
    bbox2 = draw.textbbox((0, 0), temp_str, font=font_medium)
    tw2 = bbox2[2] - bbox2[0]
    draw.text((W - tw2 - pad, bar_y + 80), temp_str, font=font_medium, fill=(255, 220, 100, 255))

    # Wind + Regen
    info_str = f"  {weather['wind_max']:.0f} km/h    {weather['rain_max']:.0f}% Regen"
    draw.text((pad, bar_y + 155), info_str, font=font_small, fill=(180, 220, 255, 220))

    # Temperaturkurve (6-22 Uhr)
    hours = weather["hours"]
    if hours:
        chart_x = pad
        chart_y = bar_y + 210
        chart_w = W - 2 * pad
        chart_h = bar_h - 240

        temps = [h["temp"] for h in hours]
        t_min = min(temps) - 1
        t_max = max(temps) + 1
        n = len(hours)

        def px(i, t):
            x = chart_x + int(i * chart_w / (n - 1))
            y = chart_y + chart_h - int((t - t_min) / (t_max - t_min) * chart_h)
            return x, y

        # Fuellbereich
        poly = [px(i, temps[i]) for i in range(n)]
        poly_fill = [(chart_x, chart_y + chart_h)] + poly + [(chart_x + chart_w, chart_y + chart_h)]
        draw.polygon(poly_fill, fill=(100, 180, 255, 60))

        # Linie
        for i in range(n - 1):
            draw.line([px(i, temps[i]), px(i + 1, temps[i + 1])], fill=(100, 200, 255, 230), width=3)

        # Punkte + Temperatur-Labels (alle 2h)
        for i, h in enumerate(hours):
            x, y = px(i, h["temp"])
            draw.ellipse([(x-5, y-5), (x+5, y+5)], fill=(255, 255, 255, 200))
            if i % 2 == 0:
                t_label = f"{h['temp']:.0f}°"
                draw.text((x - 15, y - 35), t_label, font=font_tiny, fill=(255, 255, 255, 200))
                h_label = f"{h['hour']:02d}h"
                draw.text((x - 15, chart_y + chart_h + 5), h_label, font=font_tiny, fill=(180, 180, 180, 180))

    # Zusammenfuehren
    final = Image.alpha_composite(img, overlay).convert("RGB")
    final.save(output_path, "JPEG", quality=92)
    print(f"  Overlay gespeichert: {output_path}")


# ─── WhatsApp Versand ─────────────────────────────────────────────────────────

def send_whatsapp(image_path, config, caption=""):
    wa = config["whatsapp"]
    method = wa.get("send_method", "openclaw_cli")

    if method == "openclaw_cli":
        ct = wa.get("openclaw_ct", "7200")
        cmd = [
            "pct", "exec", ct, "--",
            "sh", "-c",
            f"openclaw message send --channel whatsapp --target '{wa['target']}' --media /tmp/weather_daily.png --message '{caption}'"
        ]
        # Bild in CT kopieren
        subprocess.run(["pct", "push", ct, image_path, "/tmp/weather_daily.png"], check=True)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  FEHLER beim Senden: {result.stderr}")
            return False
        print(f"  Gesendet an {wa['target']}")
        return True
    else:
        print(f"  Unbekannte send_method: {method}")
        return False


def send_whatsapp_status(image_path, config, caption=""):
    """Post image to WhatsApp Status via the openclaw whatsapp-status plugin."""
    wa = config["whatsapp"]
    ct = wa.get("openclaw_ct", "7200")
    gw_token = wa.get("gateway_token", "23ec0f192e4806418cbea2de74b18d6817ed92485523c9cf")
    status_jid_list = wa.get("status_jid_list", ["4915152721601@s.whatsapp.net"])
    remote_path = "/tmp/weather_status.jpg"

    # Push image into CT
    subprocess.run(["pct", "push", ct, image_path, remote_path], check=True)

    params = json.dumps({
        "imagePath": remote_path,
        "caption": caption,
        "statusJidList": status_jid_list,
    }, ensure_ascii=False)

    cmd = [
        "pct", "exec", ct, "--",
        "openclaw", "gateway", "call", "whatsapp-status.send",
        "--params", params,
        "--token", gw_token,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  Status FEHLER: {result.stderr or result.stdout}")
        return False
    print(f"  WhatsApp Status gepostet")
    return True


# ─── Git Push ────────────────────────────────────────────────────────────────

def git_push(output_path, weather, location):
    today = weather["date"].strftime("%Y-%m-%d")
    desc = WMO_DESCRIPTIONS.get(weather["code"], ("Unbekannt", ""))[0]
    msg = f"Daily weather: {location} {today} - {desc} {weather['temp_min']:.0f}/{weather['temp_max']:.0f}°C"
    repo_dir = Path(__file__).parent
    subprocess.run(["git", "add", str(output_path)], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=repo_dir, check=True)
    subprocess.run(["git", "push"], cwd=repo_dir, check=True)
    print(f"  Git push: {msg}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    config = load_config()
    loc = config["location"]
    comfyui_host = config["comfyui"]["host"]

    print(f"[1/6] Wetterdaten abrufen fuer {loc['name']}...")
    raw = fetch_weather(loc["latitude"], loc["longitude"], loc["timezone"])
    weather = parse_weather(raw)
    desc_de = WMO_DESCRIPTIONS.get(weather["code"], ("Unbekannt", ""))[0]
    print(f"      {desc_de}, {weather['temp_min']:.0f}/{weather['temp_max']:.0f}°C, Wind {weather['wind_max']:.0f} km/h")

    print(f"[2/6] KI-Prompt erstellen...")
    prompt, negative = build_prompt(weather["code"], weather["temp_max"], weather["temp_min"], loc["name"])
    print(f"      Prompt: {prompt[:80]}...")

    print(f"[3/6] Bild generieren via ComfyUI ({comfyui_host})...")
    img_url, img_filename = generate_image(comfyui_host, prompt, negative)
    print(f"      Generiert: {img_filename}")

    print(f"[4/6] Overlay hinzufuegen...")
    output_dir = Path(config.get("output_dir", "./output"))
    output_dir.mkdir(exist_ok=True)
    today_str = weather["date"].strftime("%Y-%m-%d")
    raw_path = output_dir / f"{today_str}_raw.jpg"
    final_path = output_dir / f"{today_str}.jpg"

    download_image(img_url, raw_path)
    draw_overlay(str(raw_path), weather, loc["name"], str(final_path))
    raw_path.unlink()  # Raw-Bild loeschen

    print(f"[5/6] Per WhatsApp senden...")
    emoji = get_weather_emoji(weather["code"])
    caption = f"{emoji} {loc['name']} | {desc_de} | {weather['temp_min']:.0f}-{weather['temp_max']:.0f}°C"
    send_whatsapp(str(final_path), config, caption)
    send_whatsapp_status(str(final_path), config, caption)

    if config.get("github_push", False):
        print(f"[6/6] Git push...")
        try:
            git_push(final_path, weather, loc["name"])
        except Exception as e:
            print(f"  Git push fehlgeschlagen (nicht kritisch): {e}")
    else:
        print(f"[6/6] Git push uebersprungen (github_push=false)")

    print(f"\nFertig! {final_path}")


if __name__ == "__main__":
    main()
