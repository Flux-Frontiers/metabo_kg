# MetaboKG Viz

Launch the MetaboKG interactive network visualization.

## Command Argument Handling

**Usage:**
- `/metabokg-viz` — Ask the user which visualizer to launch (2D or 3D)
- `/metabokg-viz 2d` — Launch 2D Streamlit explorer
- `/metabokg-viz 3d` — Launch 3D PyVista visualization (allium layout)
- `/metabokg-viz 3d allium` — 3D hub-spoke layout
- `/metabokg-viz 3d cake` — 3D concentric-rings layout

---

## Prerequisites

Confirm the database exists:
```bash
ls -lh .metabokg/meta.sqlite
```

If missing, build first: `metabokg-build --data data/hsa_pathways`

---

## 2D Explorer (Streamlit)

```bash
metabokg-viz                   # default port 8500
metabokg-viz --port 8501       # custom port
```

Opens at `http://localhost:8500` automatically.

---

## 3D Visualization (PyVista)

```bash
metabokg-viz3d                          # allium layout (default)
metabokg-viz3d --layout allium         # hub-spoke
metabokg-viz3d --layout cake           # concentric rings by topology
metabokg-viz3d --width 1400 --height 900
```

### Layout Modes

| Layout | Best For | Description |
|--------|----------|-------------|
| `allium` (default) | Cross-pathway overview | Pathways at center, reactions radially distributed |
| `cake` | Metabolic flow | Concentric rings by topological distance |

### Recommended Workflow

1. `metabokg-viz3d --layout cake` — start with flow view
2. Select a pathway (e.g., Glycolysis)
3. Adjust visibility toggles
4. Click "Render Graph"
5. Switch layouts from the sidebar to compare

---

## Troubleshooting

- **Streamlit not found**: `poetry install --all-extras`
- **PyVista not found**: `poetry install --all-extras`
- **Port in use**: `metabokg-viz --port 8501`
- **Slow rendering**: Filter to a single pathway first
