# Drawer front textures

`rebuild.py` remakes the drawer-front PNGs in `assets/textures/dresser_photo_v5/` from my photo 14. That photo is not in the repository, so this is mostly for my own use; the scene build only needs the committed PNGs. The script checks the photo's hash before using it, needs NumPy, SciPy and Pillow, and writes to `.local/dresser-photo-rebuild` (or `--output-dir`) so the committed files stay untouched.

```sh
python scripts/dresser_photo_tools/rebuild.py --reference path/to/photo14.jpg
```
