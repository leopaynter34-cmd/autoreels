# 🎬 AI YouTube Video Generator

Turn any topic into a fully produced YouTube video in minutes.
**Topic → GPT-4o script → OpenAI TTS voiceover → Pexels stock footage → MP4**

---

## How it works

```
[Your Topic]
     │
     ▼
┌─────────────────┐
│ 1. Script       │  GPT-4o writes segments, each with narration + footage keywords
└────────┬────────┘
         ▼
┌─────────────────┐
│ 2. Voiceover    │  OpenAI TTS converts each segment to MP3
└────────┬────────┘
         ▼
┌─────────────────┐
│ 3. Footage      │  Pexels API searches & downloads matching stock clips (FREE)
└────────┬────────┘
         ▼
┌─────────────────┐
│ 4. Assembly     │  MoviePy: resize clips → sync audio → burn subtitles → export
└────────┬────────┘
         ▼
   [output/*.mp4]
```

---

## Prerequisites

| Tool | Install |
|------|---------|
| Python 3.10+ | https://python.org |
| FFmpeg | `brew install ffmpeg` / `sudo apt install ffmpeg` / [windows](https://ffmpeg.org/download.html) |
| ImageMagick | `brew install imagemagick` / `sudo apt install imagemagick` *(subtitles only)* |

---

## Setup

```bash
# 1. Clone / download the project
cd ai-video-generator

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your API keys
cp .env.example .env
# Edit .env and fill in OPENAI_API_KEY and PEXELS_API_KEY
```

**Get your free keys:**
- OpenAI: https://platform.openai.com/api-keys (~$0.30 per video)
- Pexels: https://www.pexels.com/api/ (completely free)

---

## Usage

```bash
# Basic usage
python main.py "5 incredible facts about black holes"

# Custom duration (90 seconds)
python main.py "How photosynthesis works" --duration 90

# Different styles
python main.py "Top 10 productivity hacks" --style listicle
python main.py "The history of the internet" --style storytelling

# Different voice (alloy, echo, fable, onyx, nova, shimmer)
python main.py "How to meditate" --voice nova

# No subtitles
python main.py "Ocean facts" --no-subtitles
```

Output is saved to `output/Your_Video_Title.mp4`.

---

## Cost estimate

| Component | Cost |
|-----------|------|
| GPT-4o script (~500 tokens) | ~$0.01 |
| OpenAI TTS (~600 words) | ~$0.03 |
| Pexels footage | **Free** |
| **Total per video** | **~$0.04** |

---

## Project structure

```
ai-video-generator/
├── main.py                 # Entry point & pipeline orchestration
├── pipeline/
│   ├── script.py           # GPT-4o script generation
│   ├── tts.py              # OpenAI Text-to-Speech
│   ├── footage.py          # Pexels stock footage search & download
│   └── assembler.py        # MoviePy video assembly
├── output/                 # Final MP4s go here
├── temp/                   # Temporary files (auto-cleaned each run)
├── requirements.txt
└── .env.example
```

---

## Customisation ideas

- **Background music**: load an MP3 in `assembler.py` and mix it at low volume with `CompositeAudioClip`
- **Intro/outro**: prepend/append a branded clip in `assembler.py`
- **Upload to YouTube**: use the YouTube Data API v3 after generation
- **Shorts mode**: change `TARGET_W = 1080` and `TARGET_H = 1920` in `assembler.py`
- **Better quality TTS**: swap `tts-1` → `tts-1-hd` in `tts.py`
- **ElevenLabs voices**: replace `pipeline/tts.py` with the ElevenLabs SDK

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ImageMagick not found` | Install ImageMagick (subtitles are skipped automatically if missing) |
| `ffmpeg not found` | Install FFmpeg and ensure it's on your PATH |
| Quota errors from Pexels | Their free tier allows 200 req/hour — wait and retry |
| Blurry video | Change `preset="fast"` → `preset="slow"` in `assembler.py` |
