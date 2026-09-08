# Dresser package surfaces v7

This independent candidate rebuilds the light-blue wet-wipe pack and yellow-green
snack packet as closed, editable soft-package meshes. Only their necessary
printed surface pixels are sampled from the user's photograph 11. References
10 and 14 check physical placement; they are not stitched into the texture.
The full photographs are not included in this folder.

Use `dresser_package_capture_v7.refine_dresser_packages()` after `layout_v3`, in
the final calibrated world coordinate system. It replaces seven original
package objects with two closed bodies, four thin heat-seal ends and a thin
reseal sticker. The dresser, backpack, cables, electronics, camera poses and
lighting remain unchanged. The support plane is the existing dresser at
Z = 0.7412 m.

## Placement evidence and limits

The old wet-wipe long edge ran along room X. Photograph11 corner rays and
registered10/14 cross-view checks instead support a long edge approximately
along Y, with center (-1.1120, 2.7911), yaw 84.95 degrees and top-plane rectangle
0.1675 × 0.1098 m. The snack rectangle is approximately 0.1905 × 0.1077 m at
(-1.0001, 2.9953), yaw 86.44 degrees. Thin seal margins extend beyond these
top-plane rectangles. Existing original bodies penetrated the support by about
8–9 mm; replacement bottoms sit approximately 0.06 mm above it.

These are photograph-informed soft-body estimates. Hand-selected corners,
assumed local top planes and a rectangle fit leave about 1.5–11 pixels of error
in photograph11. They are not measured dimensions. The matching projected
outlines in photographs10/14 are useful checks, not a claim of exact shape or
blind validation. Unobserved underside folds remain authored approximations.

## Source, masks and appearance

Each pack has six PNG files:

- `*-source-mask.png`: full-size binary selection mask, without photograph RGB.
- `*-masked-source.png`: cropped packaging pixels with alpha outside the mask;
  transparent pixels contain zero RGB.
- `*-captured.png`: UV atlas retaining the photographed illumination.
- `*-inferred-texels.png`: white marks unobserved atlas pixels filled with plain
  sampled film color. No hidden writing is invented.
- `*-estimated-basecolor.png`: actual shader color from a fixed-lighting estimate.
- `*-pressure-normal.png`: independently authored shallow compression detail;
  the printed writing is not converted to height.

The wipes atlas contains separate top and visible front-side surfaces. The
sticker samples its matching top atlas area and follows the actual mesh dents.
The snack uses its photographed top surface; hidden edges and underside use
plain color. No whole-room image or camera-plane billboard is introduced.

Estimated color uses a common RGB gain from the known original cyan flap
material and an existing r10 photograph14-view render, under the same AgX Medium
High Contrast and exposure. The recipe records the baseline/source/configuration
hashes and gain spread. Its calibration patch is small and illumination is only
approximated. Saturated source colors can exceed the feasible reflectance range;
the estimate is bounded to [0, 0.88], with the actual clipped-channel fractions
recorded in `PROVENANCE.json`. Residual captured shading remains. This is not a
measured albedo or fully relightable product scan.

The native material directly connects the estimated image to Principled Base
Color and a separate image to tangent Normal Map. Roughness is 0.60 for wipes
and 0.57 for the snack, with restrained specular response. Lights and exposure
are not adjusted to make these objects look better.

## Reproduction and ownership

The sampler requires the exact private source photograph, NumPy, SciPy, Pillow,
PyOpenColorIO and Blender 4.5's bundled OCIO configuration:

```powershell
python assets/textures/dresser_package_capture_v7/sample_packages.py --reference path/to/reference11.jpg --ocio-config path/to/Blender/4.5/datafiles/colormanagement/config.ocio
```

The optional `--ocio-module-dir` points to a separately installed OpenColorIO
Python package. All sampling polygons, UV quadrilaterals and the one gain are
preserved in `sampling-recipe.json`; output image hashes are in
`PROVENANCE.json`. The retained source resolution is limited; enlarged textures
do not recover unseen fine writing. Exact snack product names/models are not
guessed.

The user authorized reconstruction using these photographs. Photograph-derived
packaging graphics retain underlying rights and trademarks and are not labeled
CC0. The independently authored pressure maps are original project artwork.
