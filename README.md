# Daily Weather Wallpaper

Daily AI-generated weather image sent via WhatsApp — powered by ComfyUI (FLUX.1-schnell) + Open-Meteo + Pillow.

Every morning at 7:45, an image is generated that matches the mood of the day:
- **Sunny** → bright, warm, golden colors
- **Cloudy** → grey, muted tones
- **Rain** → dark, wet streets, dramatic
- **Storm** → lightning, very dramatic
- **Snow** → white, cold, peaceful

The image includes a weather overlay: location, date, temperature curve (6–22h), wind speed and rain probability.

## Example

![Example Weather Image](output/.gitkeep)

## Requirements

- Python 3.10+
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) with FLUX.1-schnell model
  - Models needed: `flux1-schnell-Q5_K_S.gguf`, `t5xxl_fp8.safetensors`, `clip_l.safetensors`, `ae.safetensors`
- [OpenClaw](https://openclaw.ai) with WhatsApp channel connected
- Proxmox LXC (or any Linux system with `pct` CLI) — or adapt `send_whatsapp()` for your setup

## Setup

```bash
git clone https://github.com/braindeadx1/daily-weather-wallpaper
cd daily-weather-wallpaper
pip install -r requirements.txt
cp config.example.json config.json
# Edit config.json with your settings
python3 weather_image.py
```

## config.json

```json
{
  "location": {
    "name": "Dortmund",
    "latitude": 51.5136,
    "longitude": 7.4653,
    "timezone": "Europe/Berlin"
  },
  "comfyui": {
    "host": "192.168.1.100:8188"
  },
  "whatsapp": {
    "target": "+491234567890",
    "send_method": "openclaw_cli",
    "openclaw_ct": "7200"
  },
  "output_dir": "./output",
  "github_push": true
}
```

## Cron / systemd

Run daily at 7:45 (systemd timer on Proxmox PVE):

```bash
# /etc/systemd/system/weather-wallpaper.service
[Unit]
Description=Daily Weather Wallpaper

[Service]
Type=oneshot
WorkingDirectory=/root/projects/daily-weather-wallpaper
ExecStart=/usr/bin/python3 /root/projects/daily-weather-wallpaper/weather_image.py
```

```bash
# /etc/systemd/system/weather-wallpaper.timer
[Unit]
Description=Daily Weather Wallpaper Timer

[Timer]
OnCalendar=*-*-* 07:45:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl enable --now weather-wallpaper.timer
```

## Weather Codes

Uses [WMO weather codes](https://open-meteo.com/en/docs) from Open-Meteo (free, no API key needed).

## License

MIT
