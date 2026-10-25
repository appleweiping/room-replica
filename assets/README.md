# Textures

Where each image in `textures/` came from. The scene build only reads the committed files. The scripts named below are there so the images can be made again; none of them download anything.

## Downloaded from Poly Haven (CC0)

| Set | Files | Used for | Listed in |
| --- | --- | --- | --- |
| [Red Oak Veneer](https://polyhaven.com/a/red_oak_veneer) by Jenelle van Heerden | `red_oak_veneer_*_2k.jpg` | doors, wardrobe and cabinets in v1, with an amber stain in the shader | `ASSET_SOURCES.json` |
| [Oak Veneer 01](https://polyhaven.com/a/oak_veneer_01) by Jenelle van Heerden | `oak_veneer_01_*_2k.jpg` | the oak in the later revision | `MATERIALS_V2_SOURCES.json` |
| [Dirty Carpet](https://polyhaven.com/a/dirty_carpet) by Rohit Seervi | `dirty_carpet_*_2k.jpg` | the carpet in the later revision | `CARPET_V3_SOURCES.json` |
| [Kitchen Wood](https://polyhaven.com/a/kitchen_wood) by Rob Tuytel | `kitchen_wood_*_2k.jpg` | nothing yet; kept for editing | `ASSET_SOURCES.json` |

The pixels are as downloaded. Load `diff` as sRGB, and `rough` and `nor_gl` as Non-Color (the normals are OpenGL style).

## Drawn by script

- `rose_cotton.png`, `blue_floral.png`, `carpet_weave.png`, `door_notice.png`: [`scripts/make_textures.py`](../scripts/make_textures.py).
- `backpack_v4/`: plain-weave normal and roughness maps from [`provenance/generate_backpack_weave.py`](provenance/generate_backpack_weave.py).
- `puffer_v6_crumpled_nylon_*_r3.png`: crumpled nylon for the jacket, from `scripts/puffer_shape_v6.py`.
- `pillowcase_satin_*_v4.png`: fine satin normal and roughness for the pillowcase, from `scripts/chair_pillow_finish_v4.py`.
- `desktop_surface_v4/`: keycap legends, a made-up laptop screen, a tablet notes page and two roughness maps. `author_graphics.py` redraws them with NumPy and Pillow, using Consolas or DejaVu Sans Mono and Segoe Print if they are installed, so the lettering can differ between machines. Nothing comes from a real screen.
- `desktop_packages_v5/`: the paper towel roll and a generic snack wrapper, drawn by `author_graphics.py` with Windows' Arial. I release these under CC0.

## AI-generated

`blue_floral_art.png`, `blue_floral_panel_v6.png`, `blue_floral_reference_v3.png`, `rose_cotton_reference_v3.png`, `pillowcase_damask_art_v4.png` and `oak_honey_straight_reference_v3.png`. Each was made from one of my photos as a reference. See [`docs/AI_TEXTURES.md`](../docs/AI_TEXTURES.md).

## Sampled from my photos

These folders hold crops of my own photos, flattened to the object's surface and colour-corrected so they work as a base colour. The full photos are not in the repository.

| Folder | What it is | From photo |
| --- | --- | --- |
| `wood_photo_v4/` | grain for the side door, the wardrobe and the entry door | 1, 2, 14 |
| `dresser_photo_v5/` | the three drawer fronts | 14 |
| `desktop_package_capture_v6/` | the crisp packet on the desk | 12 |
| `dresser_package_capture_v7/` | the wet-wipe pack and snack packet on the dresser | 11 |

The colour correction only roughly removes the room's lighting, so some shading from the photo is still in them. Spots hidden by cables, labels or other objects are filled from nearby wood on the same board, or with the plain film colour on the packages. Hidden backs and undersides get a plain colour, and no hidden print is made up. Each folder has a `PROVENANCE.json` with the photo's hash and the output checksums. The crop corners are in it too, or in `sampling-recipe.json` for the two package folders.

Making them again needs the original photo, so in practice only I can do it. The package samplers need NumPy, SciPy, Pillow, PyOpenColorIO and Blender 4.5's colour config:

```sh
python assets/textures/desktop_package_capture_v6/sample_texture.py --reference photo12.jpg \
  --ocio-config <blender>/4.5/datafiles/colormanagement/config.ocio
```

`dresser_package_capture_v7/sample_packages.py` works the same way with photo 11, and [`scripts/dresser_photo_tools/`](../scripts/dresser_photo_tools/README.md) rebuilds the drawer fronts from photo 14.

These images are not covered by MIT or CC0. Any product artwork or trademarks on the packages belong to their owners.

## Other files

- `uv/blue_quilt_print_v6.*`: UV charts that lay the duvet print over the folded duvet. [`scripts/bedding_print_tools/`](../scripts/bedding_print_tools/README.md) regenerates them.
- `cache/open_luggage_support_v5.*`: the stored pose of the open suitcase and the clothes in it, used by `scripts/puffer_shape_v5.py`.
