import argparse
import csv
import json
import math
import random
from pathlib import Path
from collections import Counter, namedtuple

import imageio
import numpy as np
from PIL import Image, ImageFilter, ImageOps, ImageChops, ImageEnhance, ImageStat


# ============================================================
# ARGUMENTS
# ============================================================
def parse_args():
    ap = argparse.ArgumentParser(description="Evolutionary collage / visual art generator")

    ap.add_argument("--art_dir", type=str, default="art_population",
                    help="Folder containing source images.")
    ap.add_argument("--out_dir", type=str, default="runs/parts_evolver_coherent",
                    help="Output folder.")

    ap.add_argument("--w", type=int, default=1024, help="Canvas width.")
    ap.add_argument("--h", type=int, default=1024, help="Canvas height.")

    ap.add_argument("--fast", action="store_true", help="Quick demo mode.")
    ap.add_argument("--pop", type=int, default=None, help="Population size override.")
    ap.add_argument("--gens", type=int, default=None, help="Generations override.")
    ap.add_argument("--k", type=int, default=None, help="Number of parts/genes override.")

    ap.add_argument("--fps", type=int, default=7, help="GIF fps.")
    ap.add_argument("--blur", type=float, default=7.0, help="Background blur radius.")
    ap.add_argument("--feather", type=float, default=12.0, help="Patch edge feather.")
    ap.add_argument("--max_patch", type=int, default=280, help="Max patch side for speed.")
    ap.add_argument("--seed", type=int, default=42, help="Random seed.")

    ap.add_argument("--composition", type=int, default=None,
                    help="0 neutral, 1 centre, 2 balanced, 3 chaotic.")
    ap.add_argument("--colour", type=int, default=None,
                    help="0 none, 1 favour red, 2 favour blue.")
    ap.add_argument("--style", type=int, default=None,
                    help="0 neutral, 1 calm, 2 vivid, 3 dark/moody.")

    ap.add_argument("--interactive_review", action="store_true",
                    help="Every few generations, review top candidates manually.")
    ap.add_argument("--review_every", type=int, default=5,
                    help="Interactive review interval.")
    ap.add_argument("--save_feedback_pack", action="store_true",
                    help="Create PNGs + CSV template for human scoring.")

    return ap.parse_args()


ARGS = parse_args()

ART_DIR = Path(ARGS.art_dir)
OUT_DIR = Path(ARGS.out_dir)
OUT_DIR.mkdir(parents=True, exist_ok=True)

CANV_W, CANV_H = ARGS.w, ARGS.h
GIF_FPS = ARGS.fps
BG_BLUR = ARGS.blur
FEATHER = ARGS.feather
MAX_PATCH_SIDE = ARGS.max_patch

random.seed(ARGS.seed)
np.random.seed(ARGS.seed)


# ============================================================
# RUN SETTINGS
# ============================================================
FAST = bool(ARGS.fast)

if FAST:
    POP = 12
    GENS = 24
    K_PARTS = 9
else:
    POP = 20
    GENS = 80
    K_PARTS = 16

if ARGS.pop is not None:
    POP = int(ARGS.pop)
if ARGS.gens is not None:
    GENS = int(ARGS.gens)
if ARGS.k is not None:
    K_PARTS = int(ARGS.k)

ELITES = 2
MUT_P = 0.24

# refined to look less chaotic
SCALE_RANGE = (0.82, 1.22)
ROT_RANGE = (-10, 10)
ALPHA_RANGE = (0.72, 1.00)

# slightly larger source regions = stronger composition
MIN_BOX_FRAC = 0.18
MAX_BOX_FRAC = 0.62

COHERENCE_WEIGHT = 0.75
COMPOSITION_WEIGHT = 0.70
INSTR_PENALTY_WEIGHT = 0.95
COLOUR_BONUS_WEIGHT = 2.40
STYLE_WEIGHT = 0.55
PALETTE_WEIGHT = 0.85

# smaller drift from layout slots = more unified result
MAX_OFFSET_FRAC = 0.10

COMPOSITION_MODE = 0
COLOUR_MODE = 0
STYLE_MODE = 0


# ============================================================
# GOALS
# ============================================================
def prompt_if_none(current, text):
    if current is not None:
        return int(current)
    try:
        print(text)
        s = input("Choose mode (Enter for 0): ").strip()
        return int(s) if s else 0
    except Exception:
        return 0


COMPOSITION_MODE = prompt_if_none(
    ARGS.composition,
    "\nComposition goal:\n0 neutral | 1 centre-focused | 2 balanced | 3 chaotic"
)
COLOUR_MODE = prompt_if_none(
    ARGS.colour,
    "\nColour goal:\n0 none | 1 favour RED | 2 favour BLUE"
)
STYLE_MODE = prompt_if_none(
    ARGS.style,
    "\nStyle goal:\n0 neutral | 1 calm/soft | 2 vivid/high-energy | 3 dark/moody"
)

COMPOSITION_MODE = max(0, min(3, COMPOSITION_MODE))
COLOUR_MODE = max(0, min(2, COLOUR_MODE))
STYLE_MODE = max(0, min(3, STYLE_MODE))


# ============================================================
# LOAD SOURCE IMAGES
# ============================================================
def load_sources(folder: Path):
    imgs, names = [], []
    if not folder.exists():
        raise SystemExit(f"Folder not found: {folder}")

    for p in sorted(folder.iterdir()):
        if p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        try:
            im = Image.open(p).convert("RGBA")
            imgs.append(im)
            names.append(p.name)
        except Exception as e:
            print("Warning loading", p, e)

    return imgs, names


SOURCES, SOURCE_NAMES = load_sources(ART_DIR)
if not SOURCES:
    raise SystemExit(f"No images found in {ART_DIR}")

print(f"\nLoaded {len(SOURCES)} source images from {ART_DIR}")
print(f"Canvas: {CANV_W}x{CANV_H} | POP={POP} | GENS={GENS} | K_PARTS={K_PARTS}")
print(f"Modes: composition={COMPOSITION_MODE}, colour={COLOUR_MODE}, style={STYLE_MODE}")
print(f"Interactive review: {ARGS.interactive_review}\n")


# ============================================================
# SLOT LAYOUT
# ============================================================
def make_slots(k: int, w: int, h: int):
    cols = int(math.ceil(math.sqrt(k)))
    rows = int(math.ceil(k / cols))
    slots = []
    cell_w = w / cols
    cell_h = h / rows
    for i in range(k):
        r = i // cols
        c = i % cols
        cx = int((c + 0.5) * cell_w)
        cy = int((r + 0.5) * cell_h)
        slots.append((cx, cy, cell_w, cell_h))
    return slots


SLOTS = make_slots(K_PARTS, CANV_W, CANV_H)


# ============================================================
# GENE
# ============================================================
Gene = namedtuple(
    "Gene",
    ["img_id", "x1", "y1", "x2", "y2", "scale", "rot", "alpha", "z", "slot", "ox", "oy"]
)


def clamp_bbox(x1, y1, x2, y2, img_w, img_h):
    x1 = int(max(0, min(x1, img_w - 6)))
    y1 = int(max(0, min(y1, img_h - 6)))
    x2 = int(max(x1 + 6, min(x2, img_w)))
    y2 = int(max(y1 + 6, min(y2, img_h)))
    return x1, y1, x2, y2


def sample_random_bbox(img: Image.Image):
    w, h = img.size
    short = min(w, h)
    side = max(10, int(short * random.uniform(MIN_BOX_FRAC, MAX_BOX_FRAC)))
    x1 = random.randint(0, max(0, w - side))
    y1 = random.randint(0, max(0, h - side))
    return clamp_bbox(x1, y1, x1 + side, y1 + side, w, h)


def rand_offset_for_slot(slot_idx: int):
    _, _, cell_w, cell_h = SLOTS[slot_idx]
    max_dx = int(cell_w * MAX_OFFSET_FRAC)
    max_dy = int(cell_h * MAX_OFFSET_FRAC)
    return random.randint(-max_dx, max_dx), random.randint(-max_dy, max_dy)


def rand_gene(slot_idx: int):
    img_id = random.randrange(len(SOURCES))
    x1, y1, x2, y2 = sample_random_bbox(SOURCES[img_id])
    ox, oy = rand_offset_for_slot(slot_idx)
    return Gene(
        img_id=img_id,
        x1=x1, y1=y1, x2=x2, y2=y2,
        scale=random.uniform(*SCALE_RANGE),
        rot=random.uniform(*ROT_RANGE),
        alpha=random.uniform(*ALPHA_RANGE),
        z=random.random(),
        slot=slot_idx,
        ox=ox,
        oy=oy
    )


def rand_chrom():
    return [rand_gene(i) for i in range(K_PARTS)]


# ============================================================
# MUTATION / CROSSOVER
# ============================================================
def mutate_gene(g: Gene):
    if random.random() > MUT_P:
        return g

    img_id, x1, y1, x2, y2, sc, rt, a, z, slot, ox, oy = g
    choice = random.randrange(10)

    if choice == 0:
        img_id = random.randrange(len(SOURCES))
        x1, y1, x2, y2 = sample_random_bbox(SOURCES[img_id])
    else:
        W, H = SOURCES[img_id].size

        if choice in (1, 2):
            dx = int(random.uniform(-0.05, 0.05) * (x2 - x1))
            dy = int(random.uniform(-0.05, 0.05) * (y2 - y1))
            x1 += dx
            y1 += dy
            x2 += dx
            y2 += dy
            x1, y1, x2, y2 = clamp_bbox(x1, y1, x2, y2, W, H)

        elif choice == 3:
            side = max(10, x2 - x1)
            delta = int(random.uniform(-0.08, 0.08) * side)
            x2 += delta
            y2 += delta
            x1, y1, x2, y2 = clamp_bbox(x1, y1, x2, y2, W, H)

        elif choice == 4:
            sc = max(SCALE_RANGE[0], min(SCALE_RANGE[1], sc * (1 + random.uniform(-0.12, 0.12))))
        elif choice == 5:
            rt = max(ROT_RANGE[0], min(ROT_RANGE[1], rt + random.uniform(-3, 3)))
        elif choice == 6:
            a = max(ALPHA_RANGE[0], min(ALPHA_RANGE[1], a + random.uniform(-0.10, 0.10)))
        elif choice == 7:
            z = random.random()
        else:
            _, _, cell_w, cell_h = SLOTS[slot]
            max_dx = int(cell_w * MAX_OFFSET_FRAC)
            max_dy = int(cell_h * MAX_OFFSET_FRAC)
            ox = int(max(-max_dx, min(max_dx, ox + random.randint(-max(1, max_dx // 5), max(1, max_dx // 5)))))
            oy = int(max(-max_dy, min(max_dy, oy + random.randint(-max(1, max_dy // 5), max(1, max_dy // 5)))))

    return Gene(img_id, x1, y1, x2, y2, sc, rt, a, z, slot, ox, oy)


def mutate_chrom(chrom):
    return [mutate_gene(g) for g in chrom]


def crossover(a, b):
    cut = random.randint(1, len(a) - 1)
    child = a[:cut] + b[cut:]
    fixed = []
    for i, g in enumerate(child):
        fixed.append(g._replace(slot=i))
    return fixed


# ============================================================
# LOOK / POLISH
# ============================================================
def dominant_source_index(chrom):
    counts = Counter([g.img_id for g in chrom])
    return counts.most_common(1)[0][0]


def make_blurred_background(chrom):
    # better than random: background matches the dominant image in the composition
    idx = dominant_source_index(chrom)
    base = SOURCES[idx].convert("RGB")
    base = ImageOps.fit(base, (CANV_W, CANV_H), method=Image.LANCZOS)
    base = base.filter(ImageFilter.GaussianBlur(radius=float(BG_BLUR)))
    base = ImageEnhance.Color(base).enhance(0.80)
    base = ImageEnhance.Contrast(base).enhance(0.92)
    return base.convert("RGBA")


def feather_patch(patch_rgba: Image.Image, feather_radius: float):
    if feather_radius <= 0:
        return patch_rgba
    r, g, b, a = patch_rgba.split()
    mask = Image.new("L", patch_rgba.size, 255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=float(feather_radius)))
    a2 = ImageChops.multiply(a, mask)
    return Image.merge("RGBA", (r, g, b, a2))


# ============================================================
# RENDER
# ============================================================
def render_and_alpha_accum(chrom):
    canvas = make_blurred_background(chrom)
    alpha_sum = np.zeros((CANV_H, CANV_W), dtype=np.float32)

    for gene in sorted(chrom, key=lambda g: g.z):
        img = SOURCES[gene.img_id]
        W, H = img.size

        x1, y1, x2, y2 = clamp_bbox(gene.x1, gene.y1, gene.x2, gene.y2, W, H)
        patch = img.crop((x1, y1, x2, y2))

        if max(patch.size) > MAX_PATCH_SIDE:
            patch.thumbnail((MAX_PATCH_SIDE, MAX_PATCH_SIDE), Image.LANCZOS)

        pw = max(10, int(patch.width * gene.scale))
        ph = max(10, int(patch.height * gene.scale))
        patch = patch.resize((pw, ph), Image.BICUBIC)

        if abs(gene.rot) > 0.5:
            patch = patch.rotate(gene.rot, resample=Image.BICUBIC, expand=True)

        r, g, b, a = patch.split()
        a = a.point(lambda v: int(v * gene.alpha))
        patch = Image.merge("RGBA", (r, g, b, a))
        patch = feather_patch(patch, FEATHER)

        slot_cx, slot_cy, _, _ = SLOTS[gene.slot]
        cx = int(slot_cx + gene.ox)
        cy = int(slot_cy + gene.oy)

        px = int(cx - patch.width / 2)
        py = int(cy - patch.height / 2)

        canvas.alpha_composite(patch, (px, py))

        a_np = np.array(patch.split()[-1]).astype(np.float32) / 255.0
        x0 = max(0, px)
        y0 = max(0, py)
        x1c = min(CANV_W, px + a_np.shape[1])
        y1c = min(CANV_H, py + a_np.shape[0])

        if x0 < x1c and y0 < y1c:
            sx0 = x0 - px
            sy0 = y0 - py
            sx1 = sx0 + (x1c - x0)
            sy1 = sy0 + (y1c - y0)
            alpha_sum[y0:y1c, x0:x1c] += a_np[sy0:sy1, sx0:sx1]

    return canvas, alpha_sum


# ============================================================
# METRICS
# ============================================================
def colour_metrics_from_img(img_rgba: Image.Image):
    arr = np.array(img_rgba.convert("RGB"), dtype=np.uint8)
    if arr.size == 0:
        return {"red": 0.0, "blue": 0.0, "brightness": 0.0, "saturation": 0.0}

    red_mask = (arr[:, :, 0] > 150) & (arr[:, :, 0] > arr[:, :, 1] + 20) & (arr[:, :, 0] > arr[:, :, 2] + 20)
    blue_mask = (arr[:, :, 2] > 150) & (arr[:, :, 2] > arr[:, :, 1] + 20) & (arr[:, :, 2] > arr[:, :, 0] + 20)

    brightness = float(arr.mean() / 255.0)
    saturation = float(np.mean(np.max(arr, axis=2) - np.min(arr, axis=2)) / 255.0)

    return {
        "red": float(red_mask.mean()),
        "blue": float(blue_mask.mean()),
        "brightness": brightness,
        "saturation": saturation
    }


def palette_consistency_score(chrom):
    # reward similar average colour across selected patches for a more unified painting feel
    means = []
    for g in chrom:
        img = SOURCES[g.img_id]
        W, H = img.size
        x1, y1, x2, y2 = clamp_bbox(g.x1, g.y1, g.x2, g.y2, W, H)
        patch = img.crop((x1, y1, x2, y2)).convert("RGB")
        stat = ImageStat.Stat(patch)
        means.append(np.array(stat.mean[:3], dtype=np.float32))

    if len(means) < 2:
        return 1.0

    arr = np.stack(means, axis=0)
    std = arr.std(axis=0).mean()
    return max(0.0, min(1.0, 1.0 - (std / 128.0)))


def coherence_score(chrom):
    centers = []
    for g in chrom:
        slot_cx, slot_cy, _, _ = SLOTS[g.slot]
        centers.append((slot_cx + g.ox, slot_cy + g.oy))

    if len(centers) < 2:
        return 1.0

    dsum = 0.0
    cnt = 0
    for i in range(len(centers)):
        for j in range(i + 1, len(centers)):
            dsum += math.hypot(centers[i][0] - centers[j][0], centers[i][1] - centers[j][1])
            cnt += 1

    avg_d = dsum / cnt
    maxd = math.hypot(CANV_W, CANV_H)
    return max(0.0, min(1.0, 1.0 - (avg_d / maxd)))


def composition_score(chrom):
    if not chrom:
        return 0.0

    centre_x = CANV_W * 0.5
    centre_y = CANV_H * 0.5
    dists = []
    max_dist = math.hypot(centre_x, centre_y)

    for g in chrom:
        slot_cx, slot_cy, _, _ = SLOTS[g.slot]
        cx = slot_cx + g.ox
        cy = slot_cy + g.oy
        dists.append(math.hypot(cx - centre_x, cy - centre_y))

    avg_dist = sum(dists) / len(dists)
    norm = avg_dist / max_dist if max_dist > 0 else 0.0

    if COMPOSITION_MODE == 1:
        return 1.0 - norm
    if COMPOSITION_MODE == 2:
        return max(0.0, 1.0 - abs(norm - 0.5) * 2.0)
    if COMPOSITION_MODE == 3:
        return norm
    return 0.0


def style_score(cm):
    if STYLE_MODE == 1:
        return 0.6 * cm["brightness"] + 0.4 * (1.0 - cm["saturation"])
    if STYLE_MODE == 2:
        return 0.4 * cm["brightness"] + 0.6 * cm["saturation"]
    if STYLE_MODE == 3:
        return 1.0 - cm["brightness"]
    return 0.0


def instruction_penalty(chrom):
    rot_pen = 0.0
    scale_pen = 0.0
    alpha_pen = 0.0
    tiny_pen = 0.0
    off_pen = 0.0

    for g in chrom:
        if abs(g.rot) > 8:
            rot_pen += (abs(g.rot) - 8) / 15.0

        if g.scale < 0.85:
            scale_pen += (0.85 - g.scale) / 0.20
        if g.scale > 1.12:
            scale_pen += (g.scale - 1.12) / 0.20

        if g.alpha < 0.75:
            alpha_pen += (0.75 - g.alpha) / 0.15

        area = max(1, (g.x2 - g.x1) * (g.y2 - g.y1))
        if area < 3200:
            tiny_pen += (3200 - area) / 3200.0

        _, _, cell_w, cell_h = SLOTS[g.slot]
        max_dx = max(1.0, cell_w * MAX_OFFSET_FRAC)
        max_dy = max(1.0, cell_h * MAX_OFFSET_FRAC)
        off_pen += 0.5 * (abs(g.ox) / max_dx + abs(g.oy) / max_dy)

    n = max(1, len(chrom))
    return (
        0.9 * rot_pen / n +
        0.8 * scale_pen / n +
        1.0 * alpha_pen / n +
        0.7 * tiny_pen / n +
        0.4 * off_pen / n
    )


def fitness(chrom):
    img, alpha_sum = render_and_alpha_accum(chrom)

    coverage = float((alpha_sum > 0.02).mean())
    overlap = float((alpha_sum > 1.0).mean())

    base = 0.98 * coverage - 1.95 * overlap - 0.80 * (max(0.0, coverage - 0.93)) ** 2

    coh = coherence_score(chrom)
    comp = composition_score(chrom)
    instr_pen = instruction_penalty(chrom)
    pal = palette_consistency_score(chrom)

    cm = colour_metrics_from_img(img)

    colour_bonus = 0.0
    if COLOUR_MODE == 1:
        colour_bonus = COLOUR_BONUS_WEIGHT * cm["red"]
    elif COLOUR_MODE == 2:
        colour_bonus = COLOUR_BONUS_WEIGHT * cm["blue"]

    sty = style_score(cm)

    f = (
        base
        + COHERENCE_WEIGHT * coh
        + COMPOSITION_WEIGHT * comp
        + PALETTE_WEIGHT * pal
        + colour_bonus
        + STYLE_WEIGHT * sty
        - INSTR_PENALTY_WEIGHT * instr_pen
    )

    return float(f), coverage, overlap, coh, comp, pal, sty, instr_pen, cm, img


# ============================================================
# SAVE HELPERS
# ============================================================
def save_rgb(img_rgba, path: Path):
    img_rgba.convert("RGB").save(path)


def chrom_to_instruction_json(chrom):
    data = []
    for g in sorted(chrom, key=lambda x: x.z):
        data.append({
            "type": "PATCH_DRAW",
            "source": SOURCE_NAMES[g.img_id],
            "bbox": [int(g.x1), int(g.y1), int(g.x2), int(g.y2)],
            "transform": {
                "scale": float(g.scale),
                "rot": float(g.rot),
                "alpha": float(g.alpha)
            },
            "placement": {
                "slot": int(g.slot),
                "offset": [int(g.ox), int(g.oy)]
            },
            "layer_z": float(g.z)
        })
    return {"instructions": data}


def save_feedback_pack(images_for_feedback):
    fb_dir = OUT_DIR / "feedback_pack"
    fb_dir.mkdir(parents=True, exist_ok=True)

    csv_path = fb_dir / "feedback_scores.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["image_name", "rater_name", "score_1_to_10", "comments"])
        for name in images_for_feedback:
            writer.writerow([name, "", "", ""])

    # copy selected images into feedback folder
    for name in images_for_feedback:
        src = OUT_DIR / name
        if src.exists():
            img = Image.open(src).convert("RGB")
            img.save(fb_dir / name)

    print(f"Saved feedback pack to {fb_dir}")


# ============================================================
# OPTIONAL INTERACTIVE REVIEW
# ============================================================
def review_top_candidates(scored, gen_idx):
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return None

    top = scored[:4]
    if len(top) < 4:
        return None

    fig, axes = plt.subplots(2, 2, figsize=(8, 8))
    axes = axes.flatten()

    for i, ax in enumerate(axes):
        img = top[i][9].convert("RGB")
        ax.imshow(img)
        ax.set_title(f"{i+1} | fit={top[i][0]:.3f}")
        ax.axis("off")

    fig.suptitle(f"Generation {gen_idx}: choose favourite 1-4")
    plt.tight_layout()
    plt.show(block=False)

    try:
        choice = input(f"Generation {gen_idx}: pick favourite 1-4 (Enter to skip): ").strip()
        plt.close(fig)
        if not choice:
            return None
        idx = int(choice) - 1
        if 0 <= idx < 4:
            return idx
    except Exception:
        pass

    try:
        plt.close(fig)
    except Exception:
        pass
    return None


# ============================================================
# MAIN LOOP
# ============================================================
def run_evolution():
    pop = [rand_chrom() for _ in range(POP)]
    frames = []

    best_overall = None
    best_overall_f = -1e9
    best_overall_metrics = None
    feedback_images = []

    for gen in range(GENS):
        scored = []
        for ind in pop:
            f, cov, ovl, coh, comp, pal, sty, pen, cm, img = fitness(ind)
            scored.append((f, cov, ovl, coh, comp, pal, sty, pen, cm, img, ind))

        scored.sort(key=lambda t: t[0], reverse=True)

        if ARGS.interactive_review and gen % max(1, ARGS.review_every) == 0 and len(scored) >= 4:
            fav_idx = review_top_candidates(scored, gen)
            if fav_idx is not None:
                fav = scored[fav_idx]
                boosted = (fav[0] + 1.0, *fav[1:])
                scored[fav_idx] = boosted
                scored.sort(key=lambda t: t[0], reverse=True)

        best_f, best_cov, best_ovl, best_coh, best_comp, best_pal, best_sty, best_pen, best_cm, best_img, best_ind = scored[0]

        name = f"best_gen_{gen:03d}.png"
        save_rgb(best_img, OUT_DIR / name)
        frames.append(np.array(best_img.convert("RGB")))

        if gen in {0, GENS // 2, GENS - 1}:
            feedback_images.append(name)

        print(
            f"Gen {gen:03d}: fit={best_f:.4f} cov={best_cov:.3f} ovl={best_ovl:.3f} "
            f"coh={best_coh:.3f} comp={best_comp:.3f} pal={best_pal:.3f} "
            f"style={best_sty:.3f} pen={best_pen:.3f}"
        )

        if best_f > best_overall_f:
            best_overall_f = best_f
            best_overall = best_ind
            best_overall_metrics = {
                "best_fitness": best_f,
                "coverage": best_cov,
                "overlap": best_ovl,
                "coherence": best_coh,
                "composition_score": best_comp,
                "palette_consistency": best_pal,
                "style_score": best_sty,
                "instruction_penalty": best_pen,
                "colour": best_cm,
                "composition_mode": COMPOSITION_MODE,
                "colour_mode": COLOUR_MODE,
                "style_mode": STYLE_MODE,
                "canvas": [CANV_W, CANV_H],
                "k_parts": K_PARTS,
                "pop": POP,
                "gens": GENS,
                "art_dir": str(ART_DIR)
            }

        elites = [scored[i][10] for i in range(min(ELITES, len(scored)))]
        parents = [s[10] for s in scored[:max(POP // 2, 2)]]

        new_pop = elites[:]
        while len(new_pop) < POP:
            a, b = random.sample(parents, 2)
            child = crossover(a, b)
            child = mutate_chrom(child)
            new_pop.append(child)

        pop = new_pop

    if frames:
        save_rgb(Image.fromarray(frames[-1]).convert("RGBA"), OUT_DIR / "final_composition.png")
        imageio.mimsave(str(OUT_DIR / "evolution.gif"), frames, fps=GIF_FPS)

    if best_overall is not None:
        (OUT_DIR / "best_instructions.json").write_text(
            json.dumps(chrom_to_instruction_json(best_overall), indent=2)
        )
        (OUT_DIR / "best_metrics.json").write_text(
            json.dumps(best_overall_metrics, indent=2)
        )

    if ARGS.save_feedback_pack:
        save_feedback_pack(feedback_images)

    print("\nSaved:")
    print(OUT_DIR / "final_composition.png")
    print(OUT_DIR / "evolution.gif")
    print(OUT_DIR / "best_instructions.json")
    print(OUT_DIR / "best_metrics.json")
    if ARGS.save_feedback_pack:
        print(OUT_DIR / "feedback_pack")


if __name__ == "__main__":
    run_evolution()
    print("\nDone.")
