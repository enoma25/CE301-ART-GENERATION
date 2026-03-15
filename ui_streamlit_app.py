import streamlit as st
import subprocess
import os
from pathlib import Path
from PIL import Image
import time

st.set_page_config(page_title="Evolutionary Art Generator", layout="wide")

st.title("🎨 Evolutionary Pixel Art Generator")

st.markdown(
"""
Create evolving artworks using **Genetic Algorithms**.

You can:
- change source images
- control evolution parameters
- generate wallpapers / collages
- watch images evolve
"""
)

# -------------------------
# USER CONTROLS
# -------------------------

st.sidebar.header("Evolution Settings")

image_folder = st.sidebar.text_input("Image Folder", "art_population")

canvas_size = st.sidebar.selectbox(
    "Canvas Size",
    ["512x512", "1024x1024", "1920x1080"]
)

population = st.sidebar.slider("Population", 10, 40, 20)

generations = st.sidebar.slider("Generations", 10, 200, 40)

parts = st.sidebar.slider("Number of Parts", 4, 30, 12)

composition = st.sidebar.selectbox(
    "Composition Goal",
    ["Neutral", "Centre", "Balanced", "Chaotic"]
)

colour = st.sidebar.selectbox(
    "Colour Bias",
    ["None", "Red", "Blue"]
)

style = st.sidebar.selectbox(
    "Style",
    ["Neutral", "Calm", "Vivid", "Dark"]
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
    "Neutral":0,
    "Centre":1,
    "Balanced":2,
    "Chaotic":3
}

colour_map = {
    "None":0,
    "Red":1,
    "Blue":2
}

style_map = {
    "Neutral":0,
    "Calm":1,
    "Vivid":2,
    "Dark":3
}

# -------------------------
# RUN EVOLUTION
# -------------------------

if run_button:

    st.write("Running evolution...")

    cmd = [
        "python",
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

    subprocess.run(cmd)

    st.success("Evolution finished!")

# -------------------------
# DISPLAY RESULTS
# -------------------------

run_folder = Path("runs/parts_evolver_coherent")

col1, col2 = st.columns(2)

with col1:

    st.subheader("Final Image")

    final_img = run_folder / "final_composition.png"

    if final_img.exists():
        st.image(Image.open(final_img), use_column_width=True)

with col2:

    st.subheader("Evolution GIF")

    gif = run_folder / "evolution.gif"

    if gif.exists():
        st.image(str(gif))


st.subheader("Generation Images")

if run_folder.exists():

    images = sorted(run_folder.glob("best_gen_*.png"))

    if images:

        cols = st.columns(4)

        for i, img_path in enumerate(images[-8:]):
            with cols[i % 4]:
                st.image(Image.open(img_path))

st.markdown("---")

st.subheader("Downloads")

if final_img.exists():

    with open(final_img, "rb") as file:
        st.download_button("Download Final Image", file, "final_art.png")

if gif.exists():

    with open(gif, "rb") as file:
        st.download_button("Download Evolution GIF", file, "evolution.gif")
