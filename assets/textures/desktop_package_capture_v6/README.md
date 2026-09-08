# Masked desktop package capture v6

This candidate samples the visible Lay’s logo, red band and black/gold film from
the user's photograph 12. It does not infer the exact product model. Photographs
2 and 9 provide appearance checks, with no multi-view pixel stitching.

`desktop_package_capture_v6.refine_desktop_package_capture()` replaces only the
outer material of the actual v5 packet mesh. Its vertices, mouth, support objects,
devices and cameras remain unchanged. This is a texture on a curved 3D surface,
not a whole-room or camera-plane image.

## Files and separation of evidence

- `masked-source-package.png`: cropped source packaging with transparent pixels
  outside the explicit mask; transparent pixels contain zero RGB.
- `source-package-mask.png`: full-resolution binary source mask. It excludes
  overlaid sachets and the desk/devices/background.
- `captured-front-panel.png`: UV-space source photograph layer retaining captured
  illumination, used for inspection only.
- `estimated-basecolor.png`: material color after selective local highlight
  reduction and one common RGB compensation gain under fixed Cycles/AgX.
- `captured-highlight-reduction.png`: explicit magnitude of highlight reduction.
- `inferred-texels.png`: white marks occluded/unobserved texels filled with plain
  sampled unprinted film colors. Hidden wording or branding is not reconstructed.
- `shallow-compression-normal.png`: separately authored nonuniform compression
  lines. It is not a height map of photographed ink or text.
- `sampling-recipe.json`: source hashes, mask polygons, UV control points,
  calibration values and the bounded pre-render mask/mapping correction.
- `PROVENANCE.json`: output image hashes, ownership and method/coverage limits.

The mask initially included a small portion of an overlaid sachet. The one
pre-render correction excludes source y<710 in that area and maps the existing
shell's cosine transverse position, instead of treating angle as flat width.
The first sampling state is retained privately for audit; no second source photo
or additional material candidate was introduced.

## Color limitations

The diagnostic captured layer is not an albedo measurement. The material uses
an **estimated** base color from that layer, compensated by a single RGB gain
under the existing room illumination, AgX Medium High Contrast and camera
exposure. The baseline is the already-rendered v5 reference12 image, so this
calibration does not require a new trial lighting setup. The recipe records its
hash and gain spread.

Local highlights are reduced only within explicit plain-gold film regions.
Roughness 0.64, metallic 0.025 and specular IOR level 0.10 avoid adding a second
strong highlight field. Some photographed shading remains, so this is not a
fully relightable product scan. The unobserved back is intentionally plain.

## Reproduction

The sampler needs the exact local reference photograph (hash checked), NumPy,
SciPy, Pillow, PyOpenColorIO, and the Blender 4.5 color-management configuration:

```powershell
python assets/textures/desktop_package_capture_v6/sample_texture.py --reference path/to/reference12.jpg --ocio-config path/to/Blender/4.5/datafiles/colormanagement/config.ocio
```

`--ocio-module-dir` can point to a separately installed OpenColorIO Python module.
The committed recipe preserves the one calibration gain. Re-estimating that gain
requires the private v5 surface/camera snapshot and already-rendered baseline,
documented in `.local/desktop-package-capture-v6/calibrate_recipe.py`.

Photo-derived product artwork retains its underlying rights and trademarks;
the user authorized its use in this reconstruction. It must not be described
as CC0. No private computer-screen content is included.
