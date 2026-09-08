# Desktop package surface assets

These seven small raster maps were authored procedurally for an editable paper
towel roll and a neutral snack wrapper. `author_graphics.py` reads no source
photographs. The photographs inform object types, color families and approximate
placement; no private screen content or branded package graphics is copied.

The paper side and end maps use direct Base Color and tangent-space Normal Map
inputs. The printed wrapper uses a direct sRGB color map, a scalar non-color
roughness map and a tangent-space normal map. This allows the principal surfaces
to retain their textures in glTF. The net tote's holes are actual mesh openings;
they are not a flat photograph or an opacity image.

`PROVENANCE.json` records the deterministic seed, authorship, license and SHA-256
of each image. These authored assets and generator are released under CC0-1.0.
Arial is rasterized from the local Windows installation; no font file is included.

To regenerate on a Windows environment with Python, Pillow, NumPy and SciPy:

```powershell
python assets/textures/desktop_packages_v5/author_graphics.py
```

Use `scripts/desktop_packages_v5.py` after `desktop_surface_v4` in the calibrated
r08 room. The module replaces only the original roll, tote and large snack bag,
and rigidly repositions the decorative handset carton and the separate small
silver sachet as support-related placement corrections. It preserves the actual
electronic devices and cameras. The flexible wrapper/net is pressed beneath the
fitted paper-roll underside; the sachet's height is seated against actual meshes.

The camera-12 fit is an approximate review camera. Paper-core center observations
in registered photographs 2 and 9 provide stronger position evidence than the
occluded rear silhouette. Carton and package folds remain authored estimates.
These material maps do not establish overall photorealism.
