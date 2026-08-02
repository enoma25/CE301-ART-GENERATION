# CE301 — Art Generation with Evolutionary Algorithms

An interactive system that generates digital artwork automatically using **genetic algorithms**, combining automated fitness evaluation with human aesthetic feedback — no machine-learning training required. A population of candidate images evolves over successive generations, and the user can guide that evolution through a **Streamlit** interface, watching the results develop in real time.

Final-year capstone project, BSc Computer Science, University of Essex (2025–2026). Supervised by Dr Riccardo Poli.


---

## What it does

The system composes each candidate image from patches of source imagery, treating every candidate as an individual in a population. Over many generations, the population evolves using classic evolutionary operators — selection, crossover, and mutation — guided by a combination of an **automated fitness function** and **human aesthetic feedback**, so the results reflect both measurable similarity and the user's own taste. Users can adjust parameters such as canvas size, the number of image parts, and artistic goals like colour emphasis or composition style.

The project demonstrates how **evolutionary computation** can be applied to a creative, open-ended problem — producing novel visual output through a human-in-the-loop process rather than traditional machine-learning training.

## How it works

The genetic algorithm follows a generational cycle:

1. **Initial population** — a set of candidate images is generated from source image patches.
2. **Fitness evaluation** — each candidate is scored automatically, with the option for human aesthetic feedback to influence selection.
3. **Selection** — tournament selection chooses the strongest candidates as parents.
4. **Crossover** — parents are combined to produce offspring inheriting features from both.
5. **Mutation** — random changes introduce colour and composition variation, maintaining diversity.
6. **Replacement** — the new generation replaces the old, and the cycle repeats.

## Key features

- Generational genetic algorithm evolving image compositions from patches
- Combined automated fitness evaluation and human aesthetic feedback (human-in-the-loop)
- Tournament selection for choosing parents
- Mutation operator introducing colour variation and maintaining population diversity
- Interactive **Streamlit** interface for running the evolution and visualising progress
- User-adjustable parameters: canvas size, number of image parts, colour and composition goals

## Key findings

- The system reliably evolves images that develop coherent compositions over many generations.
- Increasing population size improves output quality but raises computation time — a clear quality/performance trade-off.
- Mutation rate strongly influences both population diversity and convergence speed, and required careful tuning.

## Built with

**Python** · **Streamlit** (interactive interface) · **Matplotlib** (visualisation) · **Git** (version control)

## Repository contents

- `ui_streamlit_app.py` — the Streamlit interface for running and visualising the evolution
- `evolver_with_bboxes_coherent.py` — the core evolutionary engine (patch-based, bounding-box composition)
- `grid_picker.py` — utility for selecting image regions
- `datasets/` — source imagery used by the system
- `requirements.txt` — dependencies

## Running it locally

```bash
# Clone the repository
git clone https://github.com/enoma25/CE301-ART-GENERATION.git
cd CE301-ART-GENERATION

# Install dependencies
pip install -r requirements.txt

# Launch the Streamlit app
streamlit run ui_streamlit_app.py
```

Then use the browser interface to run the evolution and guide it with your own feedback.

## Possible extensions

Identified during the project as directions for future work:

- Parallelised evolution for faster results
- More sophisticated fitness functions
- Multi-objective optimisation (balancing several artistic goals at once)
- Higher-resolution art generation

## Full write-up

The complete dissertation — covering background, design decisions, experiments, and evaluation in full — is available here: [dissertation.pdf](dissertation.pdf)
