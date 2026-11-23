"""
PaciFrame art generator — RTX 3090 Ti edition.

- FLUX.1-dev at bfloat16, full model on GPU (24 GB VRAM — fits easily)
- Generates at 2x native Inky res (1600x960) → downscale on Pi for crisp dithering
- Refuses to run on battery (no-op on a desktop)
- Uploads each image + prompt sidecar to Google Drive via rclone

Target display: Pimoroni Inky Impression 7.3" (800x480, 5:3).

Setup:
  pip install -U diffusers transformers accelerate sentencepiece protobuf pillow
  hf auth login                       # accept FLUX.1-dev license on HF first
  sudo apt install rclone
  rclone config                        # remote named "gdrive" → Google Drive
  rclone mkdir gdrive:PaciFramePhotos

Usage:
  python generate_art_diffusers.py                 # default: 5 images
  python generate_art_diffusers.py --count 10
  python generate_art_diffusers.py --count 1 --no-upload
"""

import argparse
import csv
import os
import random
import subprocess
import time
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch
from diffusers import FluxPipeline

# ---------- config ----------
OUTPUT_DIR = Path("./frames")
WIDTH, HEIGHT = 1600, 960                          # 2x native Inky 7.3" (800x480)
STEPS = 25                                         # FLUX dev sweet spot
GUIDANCE = 3.5
MODEL_ID = "black-forest-labs/FLUX.1-dev"

RCLONE_REMOTE = os.environ.get("RCLONE_REMOTE", "gdrive:PaciFramePhotos")
FILENAME_PREFIX = "artoftheday"                    # paciframe.py filters by this
UPLOAD_TO_DRIVE = os.environ.get("UPLOAD_TO_DRIVE", "1") == "1"
DEFAULT_COUNT = 5

CANDIDATES_PER_PROMPT = 3


# ---------- AC power guard ----------
def is_on_ac_power() -> bool:
    """True if a power adapter is plugged in, OR if no battery exists (desktop)."""
    base = Path("/sys/class/power_supply")
    if not base.exists():
        return True
    has_battery = False
    for ps in base.iterdir():
        type_file = ps / "type"
        online_file = ps / "online"
        if not (type_file.exists() and online_file.exists()):
            continue
        t = type_file.read_text().strip()
        if t == "Battery":
            has_battery = True
        if t == "Mains" and online_file.read_text().strip() == "1":
            return True
    return not has_battery


# ---------- prompt building ----------
STYLE_PRESETS = [
    {
        "name": "impressionist",
        "modifiers": "impressionist oil painting, visible brushstrokes, soft natural light, "
                     "loose gestural style, plein air, in the style of Monet and Pissarro",
        "palette": "muted blues, sage green, warm ochre, soft lavender",
    },
    {
        "name": "ukiyo-e",
        "modifiers": "ukiyo-e woodblock print, flat color planes, bold outlines, "
                     "Edo period Japanese aesthetic, in the style of Hokusai and Hiroshige",
        "palette": "indigo, vermillion, cream, deep prussian blue",
    },
    {
        "name": "art_nouveau",
        "modifiers": "art nouveau illustration, flowing organic lines, decorative botanical motifs, "
                     "in the style of Alphonse Mucha, ornate frame composition",
        "palette": "gold leaf, sage, dusty rose, cream",
    },
    {
        "name": "moody_baroque",
        "modifiers": "baroque oil painting, dramatic chiaroscuro, single light source, "
                     "deep shadows, Caravaggio-inspired, museum quality",
        "palette": "rich umber, deep crimson, candlelight gold, bone white",
    },
    {
        "name": "studio_ghibli",
        "modifiers": "studio ghibli style illustration, hand-painted, soft watercolor, "
                     "warm afternoon light, whimsical and serene atmosphere",
        "palette": "sky blue, meadow green, warm cream, gentle peach",
    },
    {
        "name": "cinematic_photoreal",
        "modifiers": "cinematic photograph, shot on Hasselblad, golden hour, "
                     "shallow depth of field, atmospheric haze, sharp focus, 8k",
        "palette": "warm amber, cool teal shadows, soft pastels",
    },
    {
        "name": "minimalist_ink",
        "modifiers": "minimalist sumi-e ink painting, negative space, single brush gesture, "
                     "rice paper texture, zen aesthetic",
        "palette": "ink black, paper white, single accent of vermillion",
    },
    {
        "name": "pixel_art",
        "modifiers": "detailed pixel art, 16-bit JRPG aesthetic, dithered gradients, "
                     "crisp sprite composition, warm nostalgic lighting",
        "palette": "limited retro palette, vivid primaries, deep purples",
    },
    {
        "name": "nordic_watercolor",
        "modifiers": "loose nordic watercolor, cold crisp air, soft wet-on-wet technique, "
                     "scandinavian landscape painting",
        "palette": "pale blue, silver birch, misty gray, muted ochre",
    },
    {
        "name": "retro_travel_poster",
        "modifiers": "vintage travel poster, mid-century modern illustration, bold flat shapes, "
                     "stylized clouds and mountains, serigraph print aesthetic",
        "palette": "burnt orange, teal, cream, deep navy",
    },
]

SUBJECTS = [
    "a lone fisherman's boat on a still mountain lake at dawn",
    "a windswept coastal cliff with crashing waves and circling gulls",
    "a quiet teahouse courtyard with cherry blossoms drifting down",
    "a vast wheatfield under a turbulent sky with a single tree",
    "an old stone library with shafts of dusty light",
    "a snow-covered forest path with a small wooden bridge",
    "a desert canyon at sunset with long shadows",
    "a misty bamboo grove with a stone lantern",
    "a fishing village harbor at twilight, lanterns reflecting on water",
    "an alpine meadow in summer with wildflowers and distant peaks",
    "a quiet city street in the rain, neon reflections on wet cobblestones",
    "a hot air balloon over rolling hills at sunrise",
    "an abandoned greenhouse reclaimed by ivy and ferns",
    "a moonlit Japanese garden with a koi pond",
    "a rocky shore with a single lighthouse against a stormy sky",
    "a stone bridge over a mossy stream in deep forest",
    "an observatory on a mountaintop under the milky way",
    "a vineyard terrace in Tuscany in late afternoon light",
    "an ice-covered pine forest at the edge of a frozen lake",
    "a canal in Venice at blue hour with gondolas moored",
    "a Himalayan monastery clinging to a cliffside in mist",
    "a redwood grove with sunbeams through morning fog",
    "a salt flat mirroring a dramatic sky at sunset",
    "a wooden cabin in a birch forest in autumn",
    "an open window over a Mediterranean village at dawn",
]

QUALITY_TAIL = "highly detailed, masterpiece composition, gallery quality, rich atmosphere"


def build_prompt(metadata_csv: Path | None = None) -> tuple[str, str]:
    preset = random.choice(STYLE_PRESETS)
    subject = random.choice(SUBJECTS)
    if metadata_csv and metadata_csv.exists():
        with metadata_csv.open() as f:
            objects = [row["objects"] for row in csv.DictReader(f) if row.get("objects")]
        if objects and random.random() < 0.3:
            subject = random.choice(objects)
    prompt = (f"{subject}, {preset['modifiers']}, "
              f"color palette of {preset['palette']}, {QUALITY_TAIL}")
    return prompt, preset["name"]


# ---------- pipeline ----------
def load_pipe() -> FluxPipeline:
    print(f"Loading {MODEL_ID}...")
    pipe = FluxPipeline.from_pretrained(
        MODEL_ID, torch_dtype=torch.bfloat16, low_cpu_mem_usage=True,
    )
    pipe.enable_model_cpu_offload()
    pipe.vae.enable_tiling()
    pipe.set_progress_bar_config(disable=True)
    return pipe

def _generate_image(pipe: FluxPipeline, prompt: str, seed: int):
    return pipe(
        prompt=prompt,
        width=WIDTH, height=HEIGHT,
        num_inference_steps=STEPS, guidance_scale=GUIDANCE,
        generator=torch.Generator("cuda").manual_seed(seed),
    ).images[0]


def generate_one(pipe: FluxPipeline, metadata_csv: Path | None) -> Path:
    prompt, preset_name = build_prompt(metadata_csv)
    print(f"  [{preset_name}] {prompt[:110]}...")

    seed = random.randint(0, 2**32 - 1)
    img = _generate_image(pipe, prompt, seed)
    ts = int(time.time())
    out = OUTPUT_DIR / f"{FILENAME_PREFIX}_{ts}_{preset_name}_{seed}.jpg"
    img.save(out, format="JPEG", quality=92)

    out.with_suffix(".txt").write_text(prompt)
    return out


# ---------- rclone ----------
def rclone(*args) -> bool:
    cmd = ["rclone", *args]
    print("  $", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
        return True
    except FileNotFoundError:
        print("  !! rclone not installed. `sudo apt install rclone` + `rclone config`")
        return False
    except subprocess.CalledProcessError as e:
        print(f"  !! rclone exited {e.returncode}")
        return False


def upload_to_drive(image_path: Path, prompt_path: Path) -> bool:
    if not UPLOAD_TO_DRIVE:
        return True
    ok = rclone("copy", str(image_path), RCLONE_REMOTE)
    ok = rclone("copy", str(prompt_path), RCLONE_REMOTE) and ok
    return ok


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=DEFAULT_COUNT)
    ap.add_argument("--metadata", default="metadata.csv")
    ap.add_argument("--no-upload", action="store_true", help="Skip rclone upload")
    args = ap.parse_args()

    if args.no_upload:
        global UPLOAD_TO_DRIVE
        UPLOAD_TO_DRIVE = False

    if not is_on_ac_power():
        print("!! On battery. Refusing to run (GPU throttling → CUDA crashes).")
        return 2

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    meta = Path(args.metadata) if Path(args.metadata).exists() else None

    pipe = load_pipe()

    for i in range(args.count):
        try:
            t0 = time.time()
            img = generate_one(pipe, meta)
            print(f"  -> {img.name}  ({time.time() - t0:.1f}s)")
            upload_to_drive(img, img.with_suffix(".txt"))
        except Exception as e:
            print(f"  !! {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
