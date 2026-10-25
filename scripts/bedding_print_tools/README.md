# Duvet print UV tools

The scene build reads the duvet print's UV charts from `assets/uv/blue_quilt_print_v6.npz`, so you only need these two scripts if you change the duvet's shape or pose. `export_donors.py` runs in Blender on a `scene/room.blend` built from the current `main` (the committed one is v1). It rebuilds the original cloth pieces in memory and exports their UVs without saving the file. `transfer_uv.py` then maps them onto the folded duvet and writes a new cache. Rebuild the scene and check the reference views before committing the result.

```sh
python -m pip install -r scripts/bedding_print_tools/requirements.txt
blender -b scene/room.blend --python-exit-code 1 --python scripts/bedding_print_tools/export_donors.py -- --work-dir .local/bedding-print-build
python scripts/bedding_print_tools/transfer_uv.py --work-dir .local/bedding-print-build
```

Add `--output-dir <folder>` to the last command to write the cache somewhere else instead of overwriting the committed one.
