import os, json
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from pathlib import Path

# ---------------- CONFIG ----------------
IMAGE_DIR = Path("art_population")
OUT_DIR = Path("parts_selected")
OUT_DIR.mkdir(exist_ok=True)

GRID_SIZE = 3   # 3x3 grid (good balance)
# ---------------------------------------

class GridSelector:
    def __init__(self, image_paths):
        self.image_paths = image_paths
        self.idx = 0
        self.selected = []

        self.fig, self.ax = plt.subplots()
        self.cid = self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.kid = self.fig.canvas.mpl_connect('key_press_event', self.on_key)

        self.load_image()
        plt.show(block=True)

    def load_image(self):
        self.selected = []
        img_path = self.image_paths[self.idx]
        self.img = mpimg.imread(img_path)

        self.ax.clear()
        self.ax.imshow(self.img)
        self.ax.set_title(f"{img_path.name} ({self.idx+1}/{len(self.image_paths)})")
        self.ax.set_xticks([])
        self.ax.set_yticks([])

        self.h, self.w = self.img.shape[:2]
        self.tw = self.w // GRID_SIZE
        self.th = self.h // GRID_SIZE

        self.draw_grid()
        self.fig.canvas.draw()

    def draw_grid(self):
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                x = c * self.tw
                y = r * self.th
                self.ax.add_patch(
                    plt.Rectangle((x, y), self.tw, self.th,
                                  fill=False, edgecolor="white", linewidth=1)
                )

    def on_click(self, event):
        if event.xdata is None or event.ydata is None:
            return

        c = int(event.xdata // self.tw)
        r = int(event.ydata // self.th)

        x1 = c * self.tw
        y1 = r * self.th
        x2 = x1 + self.tw
        y2 = y1 + self.th

        self.selected.append((x1, y1, x2, y2))
        self.ax.add_patch(
            plt.Rectangle((x1, y1), self.tw, self.th,
                          fill=True, color="yellow", alpha=0.3)
        )
        self.fig.canvas.draw()

    def on_key(self, event):
        if event.key == "s":
            self.save_instructions()
        elif event.key == "n":
            self.next_image()
        elif event.key == "q":
            plt.close("all")

    def save_instructions(self):
        img_name = self.image_paths[self.idx].name
        instructions = []

        for bbox in self.selected:
            instructions.append({
                "source_image": img_name,
                "bbox": list(map(int, bbox))
            })

        out_path = OUT_DIR / f"{img_name}_instructions.json"
        with open(out_path, "w") as f:
            json.dump(instructions, f, indent=2)

        print(f"Saved {len(instructions)} instructions to {out_path}")

    def next_image(self):
        self.idx += 1
        if self.idx >= len(self.image_paths):
            print("All images processed.")
            plt.close("all")
            return
        self.load_image()


# -------- RUN --------
images = [p for p in IMAGE_DIR.iterdir()
          if p.suffix.lower() in (".png", ".jpg", ".jpeg")]

GridSelector(images)
