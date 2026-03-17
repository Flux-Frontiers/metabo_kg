# MetaKG Viz

Launch the MetaKG interactive network visualization.

## Command Argument Handling

**Usage:**
- `/metakg-viz` — Ask the user which visualizer to launch (2D or 3D)
- `/metakg-viz 2d` — Launch 2D Streamlit explorer
- `/metakg-viz 3d` — Launch 3D PyVista visualization (allium layout)
- `/metakg-viz 3d allium` — 3D hub-spoke layout
- `/metakg-viz 3d cake` — 3D concentric-rings layout

---

## Prerequisites

Confirm the database exists:
```bash
ls -lh .metakg/meta.sqlite
```

If missing, build first: `metakg-build --data data/hsa_pathways`

---

## 2D Explorer (Streamlit)

```bash
metakg-viz                   # default port 8500
metakg-viz --port 8501       # custom port
```

Opens at `http://localhost:8500` automatically.

---

## 3D Visualization (PyVista)

```bash
metakg-viz3d                          # allium layout (default)
metakg-viz3d --layout allium         # hub-spoke
metakg-viz3d --layout cake           # concentric rings by topology
metakg-viz3d --width 1400 --height 900
```

### Layout Modes

| Layout | Best For | Description |
|--------|----------|-------------|
| `allium` (default) | Cross-pathway overview | Pathways at center, reactions radially distributed |
| `cake` | Metabolic flow | Concentric rings by topological distance |

### Recommended Workflow

1. `metakg-viz3d --layout cake` — start with flow view
2. Select a pathway (e.g., Glycolysis)
3. Adjust visibility toggles
4. Click "Render Graph"
5. Switch layouts from the sidebar to compare

---

## Troubleshooting

- **Streamlit not found**: `poetry install --all-extras`
- **PyVista not found**: `poetry install --all-extras`
- **Port in use**: `metakg-viz --port 8501`
- **Slow rendering**: Filter to a single pathway first
