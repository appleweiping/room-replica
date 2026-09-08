# Photographed wood material estimates

Editable wood materials derived deterministically from the user’s own photographs. These files contain bare wood or sampling masks; original room photographs are not included. They are **photo derivatives, not measured/scanned albedo and not CC0 stock**.

Call `refine_photo_wood(M=None, texture_dir=None)` from `scripts/wood_photo_v4.py` after layout and the original wood UV pass. The default asset path is relative to the repository; an explicit asset directory is supported. The operation is idempotent. All five meshes preserve their original vertices, transforms, modifiers, and UV0. Images connect directly to Principled Base Color on UV1 / glTF TEXCOORD_1. Original coat/specular/roughness remain; the incompatible synthetic macrograin normal is disconnected on replaced surfaces.

## Side door and wardrobe

`side-*` samples the side door from reference14; `wardrobe-*` samples a clean wardrobe region from reference2. `*-rectified-raw.png` keeps the captured appearance; `*-estimated-normalized.png` removes an estimated first-order log illumination gradient; `*-estimated-tile.png` separately makes the local boundary periodic. `*-estimated-basecolor.png` bakes one common RGB calibration under fixed native lighting and AgX. Texture size in the model is respectively0.72×0.835m and0.26×1.505m. Unobserved sides/edges remain editable repeated samples.

## Entrance full board

`entry-estimated-basecolor.png` uses the entrance’s own full leaf from reference1 exactly once across the front. It preserves the long cathedral grain; it does not repeat the side-door sample. Unobserved entry edges/back retain the pre-existing PBR.

`entry-raw-masked.png` preserves sampled appearance with excluded pixels black. `source-sample-mask.png` and `rectified-sample-mask.png` use255 for observed wood and0 for excluded hardware/notice regions. `entry-inferred-fill-mask.png` uses255 for inferred pixels (6.90% of the board). The filled regions use vertical donor patches from the SAME entry board; donor rectangles are recorded in PROVENANCE.json. No personal notice/text is included. `entry-filled-captured.png` is the separately archived captured-light appearance with those fills.

`entry-illumination-estimate.npz` stores the estimated first-order per-channel log gradient; its PNG is only a visualization. `entry-estimated-basecolor-uncalibrated.png` applies that estimate. The final image additionally bakes exactly one common linear RGB gain(0.47552,0.58193,0.68891), under unchanged native lights/EV/AgX. No per-triangle colour adjustment is made. Output460×1080 resamples approximately290×635 source pixels and creates no new photographic detail.

Actual640×480,16sample CPU Cycles checks were made at registered reference1/reference6 and a new oblique viewpoint. Reference1 upper-board median RGB MAE decreased0.1455→0.0257, but reference6 remains darker with MAE0.0886. This unresolved cross-view lighting/exposure difference is not a pass or evidence of measured reflectance. Source and native generic notice/hardware placements differ slightly; inferred wood may be visible near their edges.

Exact source hashes, quadrilaterals, masks, fill donors, illumination coefficients, colour gains and output hashes are in `PROVENANCE.json`. Private original-view renders and diagnostics stay under`.local/photo-texture-v1/wood/entry-full-board/`.
