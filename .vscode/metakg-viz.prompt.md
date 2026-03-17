---
mode: 'agent'
description: 'Launch the MetaKG 2D Streamlit network explorer or 3D PyVista visualization.'
---

# MetaKG Viz

Launch the MetaKG interactive network visualization. Choose between 2D (Streamlit browser-based) or 3D (PyVista desktop).

## Command Argument Handling

**Usage:**
- No argument — Ask the user which visualizer to launch (2D or 3D)
- `2d` — Launch 2D Streamlit explorer
- `3d` — Launch 3D PyVista visualization
- `3d allium` — 3D with allium (hub-spoke) layout
- `3d cake` — 3D with layer-cake (concentric rings) layout

---

## Prerequisites

1. Confirm the database exists:
   ```bash
   ls -lh .metakg/meta.sqlite
   ```
2. If missing, build first: `metakg-build --data data/hsa_pathways`

---

## 2D Explorer (Streamlit)

Browser-based interactive network explorer:

```bash
metakg-viz
```

Options:
```bash
metakg-viz --port 8500          # Custom port (default: 8500)
metakg-viz --db .metakg/meta.sqlite
```

**Features in the UI:**
- Search pathways by name
- Click nodes to see details
- Filter by pathway
- Zoom/pan the network

Opens automatically in your browser at `http://localhost:8500`.

---

## 3D Visualization (PyVista)

Desktop 3D graph visualization with two layout modes:

```bash
metakg-viz3d                          # Default: allium layout
metakg-viz3d --layout allium         # Hub-spoke (pathways at center)
metakg-viz3d --layout cake           # Concentric rings by topology
```

Options:
```bash
metakg-viz3d --layout allium|cake
metakg-viz3d --db .metakg/meta.sqlite
metakg-viz3d --width 1400 --height 900
```

### Layout Modes

| Layout | Best For | Description |
|--------|----------|-------------|
| `allium` (default) | Overview of all pathways | Pathways at center, reactions radially distributed |
| `cake` | Metabolic flow | Concentric rings by topological distance |

### In the UI

- **Pathway Filter**: Select a single pathway or "(All Pathways)"
- **Layout Selector**: Switch between Allium and LayerCake dynamically
- **Visibility Toggles**: Show/hide edges, labels, enzyme detail
- **Render Graph**: Apply all staged changes

### Recommended Workflow

1. Start with `--layout cake` for metabolic flow visualization
2. Select a specific pathway (e.g., Glycolysis / hsa00010)
3. Toggle edge/label visibility as needed
4. Click "Render Graph" to apply
5. Switch to `allium` layout to compare cross-pathway connectivity

---

## Category-Based Exploration

Filter pathways by biological domain using the Python API:

```python
from metakg import MetaKG
from metakg.primitives import PATHWAY_CATEGORY_METABOLIC, PATHWAY_CATEGORY_SIGNALING

kg = MetaKG()

# List all metabolic pathways
metabolic = kg.store.all_nodes(kind="pathway", category=PATHWAY_CATEGORY_METABOLIC)
for p in metabolic:
    print(p.node_id, p.name)
```

---

## Troubleshooting

- **Streamlit not found**: `poetry install --all-extras` or `pip install streamlit`
- **PyVista not found**: `poetry install --all-extras` or `pip install pyvista`
- **Port in use**: `metakg-viz --port 8501`
- **Slow rendering**: Filter to a single pathway first
