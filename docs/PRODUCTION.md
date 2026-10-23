# Production notes

## Scale and coordinates

The only real measurement I have is the bed: a standard Twin XL mattress, 36 × 80 in (0.9144 × 2.032 m). Everything else is scaled from the photos around it. The v1 scene's room is 3.00 × 4.15 × 2.82 m. The later calibrated source (see [CALIBRATION.md](CALIBRATION.md)) moves this to 3.33 × 4.54 × 3.035 m. Both are estimates, not survey data. Cabinet sizes, the window opening, cloth folds and anything hidden in the photos are my best guesses.

Blender uses metres and Z up. The entry wall is at `y=0` and the window wall at `y=4.15` (v1). glTF export is Y up, so Blender `(x, y, z)` becomes `(x, z, -y)`. Random variation uses a fixed seed, so every build gives the same scene.

## Materials

- **Wood:** Poly Haven's CC0 Red Oak Veneer diffuse and normal maps, with UVs that follow each part's long direction. A constant amber Multiply node `(0.80, 0.47, 0.16)` gives the stain, and it exports to glTF as `baseColorFactor`, so the browser model keeps the colour.
- **Fabrics and printed items:** rose cotton, carpet weave, the generic door notice and a spare blue pattern are drawn by [`make_textures.py`](../scripts/make_textures.py). The duvet and pillowcase prints are AI-generated from my photos ([AI_TEXTURES.md](AI_TEXTURES.md)). The later dresser, desk and package textures are sampled from my photos (folders under `assets/textures/`).
- No original photo and no real screen contents are in the scene. The laptop, tablet and door notice show generic graphics.

## Rendering

The four gallery images were rendered with Blender 4.5.13 LTS, Cycles on the CPU (12 threads, Intel Core i5-1240P), at 1600 × 1200, 64 samples, with denoising. `renders/render-stats.json` records each run. These were the render times:

| View | Lens | Time |
| --- | --- | --- |
| Bedroom | 21 mm | 25.0 min |
| Kitchen | 21 mm | 19.9 min |
| Desk | 30 mm | 15.9 min |
| Overview (cutaway) | 42 mm | 3.5 min |

```sh
blender --background scene/room.blend --python-exit-code 1 --python scripts/render.py -- \
  --view all --resolution 1600 --samples 64 --threads 12
```

`render.py` renders the saved cameras without changing the `.blend`. The overview hides the front wall, left wall, ceiling, ceiling light and smoke detector. Use `--view bedroom` (or another view) and `--stats-file renders/probe.json` for quick single-view tests that leave the main record alone. After a full run, copy `renders/*.jpg` to `demo/public/renders/`. `python scripts/check_assets.py` fails if the copies differ.

`scripts/audit_scene.py` is a read-only check of a `.blend`. It counts objects, materials and packed textures, confirms the cameras and mattress size, checks that small parts have plausible sizes, and casts rays into the sink to make sure the basin is open:

```sh
blender --background scene/room.blend --python-exit-code 1 --python scripts/audit_scene.py
```

## Browser model vs. Cycles

Cycles does the indirect light, reflections, glass and the full shader graphs. The browser uses Three.js with shadow maps, a generated room environment and its own lights. Blender's area lights are not exported. The browser tone-maps with ACES, while Blender uses AgX. Procedural bump and other Blender-only nodes do not survive glTF export. Use the web viewer to look at the layout. The renders are the reference for materials and light.

`build_scene.py` writes the full export to `scene/room.glb` (about 42 MB). The demo loads a 6 MB copy made by [`scripts/web-model`](../scripts/web-model/make_web_model.mjs):

```sh
cd scripts/web-model
npm install
npm run build        # scene/room.glb -> demo/public/models/room-web.glb
```

This step shrinks textures to 1024 px JPEG, then quantizes and meshopt-compresses the geometry. It keeps node names and cameras, because the viewer finds walls, doors and viewpoints by name. At load time the viewer merges static meshes that share a material: the 1,279 meshes in the file become 262.
