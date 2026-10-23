# Dresser front wood — reference-derived estimates

Each of the three PNG base-color maps belongs to the corresponding drawer,
used once across its observed front. Grain comes from my reference photo 14.
It is not a repeated generic wood sample or an AI-generated room image.

The sampler excludes the power cable, its nearby shadow and the hanging label.
About 5.6–6.9% of each selected face is inferred from an observed horizontal
neighbor on the same drawer. The binary observed masks distinguish those
regions. `*-masked-captured.png` contains only bare wood samples and zeros in
excluded areas; `*-filled-captured.png` retains photographed illumination.

`PROVENANCE.json` records manual source quadrilaterals, homographies, source
hash, donor offsets and the first-order illumination estimate. Its 512 × 138
resampling does not add captured detail to the approximately 350 × 80 source
pixels. The original reference photograph is not included in the public repo.

`COLOR_CALIBRATION.json` records the fixed-transport color estimate. A single
common RGB gain left the lower drawers too dark, so a first-order log response
versus board height was jointly fitted to the three unoccluded front medians.
Each board uses that smooth response at its center. No scene light, camera,
vertex position or original UV was changed. These are **estimated base colors**,
not measured, perfectly de-lit reflectance. Residual photograph lighting and
phone processing remain possible.

Actual Cycles reference-14, reference-11 and reference-3 crops were inspected.
Their own horizontal grain improves the prior generic material. Door/body
edges retain the old editable material, and drawer dimensions and broad room
lighting still need refinement. This is an incremental asset, not evidence of
photographic equivalence.

These derivatives come from my own photographs. They are not
third-party CC0 textures; the repository's software license does not assign
rights to the source photographs.
