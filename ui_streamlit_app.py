import streamlit as st
import subprocess
import sys
from pathlib import Path
from PIL import Image

st.set_page_config(page_title="Evolutionary Art Generator", layout="wide")

st.title("🧬 Evolutionary Art Generator")
st.markdown("### 🔬 Watch AI evolve images in real time")
st.markdown(
    """
Choose a dataset, adjust the settings, and generate unique artwork using evolutionary algorithms.

You can:
- switch between datasets
- control evolution parameters
- generate artistic compositions
- watch images evolve over generations
"""
)

# -------------------------
# PATHS
# -------------------------
BASE_DIR = Path(".")
RUN_FOLDER = BASE_DIR / "runs" / "parts_evolver_coherent"

# -------------------------
# SIDEBAR CONTROLS
# -------------------------
st.sidebar.header("Evolution Settings")

dataset = st.sidebar.selectbox(
    "Choose Dataset",
    [
        "art_population",
        "datasets/Abstract",
        "datasets/Space",
        "datasets/Textures"
    ]
)

image_folder = dataset

image_folder = f"datasets/{dataset}"

canvas_size = st.sidebar.selectbox(
    "Canvas Size",
    ["512x512", "1024x1024", "1920x1080"],
    index=0
)

population = st.sidebar.slider("Population", 10, 40, 20)
generations = st.sidebar.slider("Generations", 10, 200, 80)
parts = st.sidebar.slider("Number of Parts", 4, 12, 5)

composition = st.sidebar.selectbox(
    "Composition Goal",
    ["Neutral", "Centre", "Balanced", "Chaotic"],
    index=2
)

colour = st.sidebar.selectbox(
    "Colour Bias",
    ["None", "Red", "Blue"],
    index=0
)

style = st.sidebar.selectbox(
    "Style",
    ["Neutral", "Calm", "Vivid", "Dark"],
    index=1
)

feedback_pack = st.sidebar.checkbox("Create feedback pack")
run_button = st.sidebar.button("🚀 Run Evolution")

# -------------------------
# CANVAS SIZE PARSE
# -------------------------
if canvas_size == "512x512":
    w, h = 512, 512
elif canvas_size == "1024x1024":
    w, h = 1024, 1024
else:
    w, h = 1920, 1080

composition_map = {
    "Neutral": 0,
    "Centre": 1,
    "Balanced": 2,
    "Chaotic": 3
}

colour_map = {
    "None": 0,
    "Red": 1,
    "Blue": 2
}

style_map = {
    "Neutral": 0,
    "Calm": 1,
    "Vivid": 2,
    "Dark": 3
}

# -------------------------
# RUN EVOLUTION
# -------------------------
if run_button:
    st.write("Running evolution...")

    cmd = [
        sys.executable,
        "evolver_with_bboxes_coherent.py",
        "--art_dir", image_folder,
        "--w", str(w),
        "--h", str(h),
        "--pop", str(population),
        "--gens", str(generations),
        "--k", str(parts),
        "--composition", str(composition_map[composition]),
        "--colour", str(colour_map[colour]),
        "--style", str(style_map[style]),
        "--fast"
    ]

    if feedback_pack:
        cmd.append("--save_feedback_pack")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        st.success("Evolution finished!")
    else:
        st.error("Evolution failed.")
        st.code(result.stderr if result.stderr else "No error output available.")

# -------------------------
# DATASET PREVIEW
# -------------------------
st.markdown("---")
st.subheader("Dataset Preview")

preview_folder = Path(image_folder)
preview_images = sorted(
    list(preview_folder.glob("*.png")) +
    list(preview_folder.glob("*.jpg")) +
    list(preview_folder.glob("*.jpeg")) +
    list(preview_folder.glob("*.webp"))
)

if preview_images:
    preview_cols = st.columns(5)
    for i, img_path in enumerate(preview_images[:10]):
        with preview_cols[i % 5]:
            st.image(Image.open(img_path), use_container_width=True)
            st.caption(img_path.name)
else:
    st.info("No images found in this dataset.")

# -------------------------
# DISPLAY RESULTS
# -------------------------
st.markdown("---")

col1, col2 = st.columns(2)

final_img = RUN_FOLDER / "final_composition.png"
gif = RUN_FOLDER / "evolution.gif"

with col1:
    st.subheader("Final Image")
    if final_img.exists():
        st.image(Image.open(final_img), use_container_width=True)
    else:
        st.info("No final image yet. Run evolution first.")

with col2:
    st.subheader("Evolution GIF")
    if gif.exists():
        st.image(str(gif))
    else:
        st.info("No GIF yet. Run evolution first.")

# -------------------------
# GENERATION IMAGES
# -------------------------
st.subheader("Recent Generations")

if RUN_FOLDER.exists():
    images = sorted(RUN_FOLDER.glob("best_gen_*.png"))
    if images:
        cols = st.columns(4)
        for i, img_path in enumerate(images[-8:]):
            with cols[i % 4]:
                st.image(Image.open(img_path), use_container_width=True)
                st.caption(img_path.name)
    else:
        st.info("No generation images found yet.")

# -------------------------
# DOWNLOADS
# -------------------------
st.markdown("---")
st.subheader("Downloads")

if final_img.exists():
    with open(final_img, "rb") as file:
        st.download_button("Download Final Image", file, "final_art.png")

if gif.exists():
    with open(gif, "rb") as file:
        st.download_button("Download Evolution GIF", file, "evolution.gif")
