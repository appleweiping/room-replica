# Rebuild the photographed drawer assets

Scene construction uses the committed PNGs and needs no private photographs.
This optional authoring recipe requires the exact reference-14 photograph
identified by SHA-256 in the asset provenance, plus Python, NumPy, SciPy and
Pillow. It verifies the photograph hash before processing it.

```powershell
python scripts/dresser_photo_tools/rebuild.py --reference "path/to/reference14.jpg"
```

The default output is `.local/dresser-photo-rebuild`; the committed assets are
not overwritten. `--output-dir` selects another destination. Source wood is
rectified, exclusions filled from the same drawer, and the recorded first-order
illumination/height response applied. This reproduces all fifteen delivered
wood/mask PNGs. It performs no download, upload, generative processing or render.

The frozen color-response coefficients were fitted against actual Cycles crops
under the documented room lighting and per-camera exposure. Rebuilding these
maps does not re-estimate the scene illumination or prove photographic accuracy.
