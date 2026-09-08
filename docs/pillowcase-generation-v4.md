# Pillowcase finish v4: authored image provenance

The albedo is **AI-assisted reference reconstruction, not a captured or scanned surface**. The authoring inputs were the user's reference photographs 9 and 16. Only the pillowcase's grey-rose field and ornate dark border informed the output; no room render was generated, repaired or composited, and the output contains no names, screen content, addresses or other identifying text.

- Tool: built-in `image_gen.imagegen`, one generation call; no CLI/API fallback.
- Output: `assets/textures/pillowcase_damask_art_v4.png`, 1086 × 1448 pixels.
- SHA256: `e44a09c8812df13ed0e61830116f041fa688bd71d260c8dee9016973b9da4751`.
- Original generated file remains under `$CODEX_HOME/generated_images/01a07e70-bf5a-7bf1-8745-7f3331bde7a0/exec-87b19431-75e4-4400-b34b-c13bcc490d91.png`; the project copy is unchanged.
- Reference files: `082f3635b99a7310bc667f148f13f367.jpg` (9) and `6726d5e8f498b7ba911e93d2d1bc3e44.jpg` (16), supplied by the user. Their hashes and asset hashes are recorded in the accompanying JSON manifest.
- Attribution: AI-assisted artwork authored for this reference reconstruction. No third-party stock photograph or scanned textile was downloaded for this asset. It does not establish an exact identity with the photographed commercial fabric.

## Exact generation prompt

Use case: photorealistic-natural. Asset type: one flat rectangular UV albedo texture for the grey-pink pillowcase visible on the black chair in the supplied reference photographs. These photographs are REFERENCE IMAGES ONLY: derive the pillowcase PRINT, never generate or modify a room render. Create ONE portrait 3:4 high-resolution image of the ENTIRE FLATTENED PRINT PATTERN, filling every pixel edge-to-edge. The long central field is muted dusty grey rose / pale mauve beige, with extremely subtle woven longitudinal satin stripes. Around ALL FOUR SIDES, an ornate wide dark charcoal-grey and muted brown Baroque/damask border: rich interlocking acanthus leaves, filled paisley scrolls, small scalloped fans, curling foliage, complex dense curvilinear ink details. The broad ornamental border is about 10-13 percent of cloth width, inset about 3 percent from the outside, joined naturally at the four corners, with several narrow straight fine double-rule borders inside and outside it. Match the reference's softly aged grey-black ornament on warm grey-pink cloth; do not substitute simple flower outlines, cartoon line drawings, a central medallion, bright colors or pure white. The large inner center remains quiet and mostly unornamented, as in the real pillowcase. Surface is perfectly flat, orthographic and uniformly neutrally illuminated, like a material color swatch; show fine silk-like woven textile grain only at micro scale. This is diffuse BASE COLOR artwork for a 3D material: absolutely NO folds, NO wrinkles, NO shading, NO glossy highlights, NO cast shadows, NO perspective, NO pillow volume, NO visible sewing geometry, NO room, NO furniture, NO people, NO screen content, NO names, NO address, NO letters, NO logos, NO watermark. Edge-to-edge rectangular print rather than an object on a background. AI-assisted reference-informed reconstruction, not an actual scan.

## PBR implementation

`scripts/chair_pillow_finish_v4.py` provides the optional `refine_chair_pillow_finish(M=None)` candidate, called after `chair_pillow_v4.refine_chair_pillow`. The generated sRGB albedo connects **directly** from Image Texture to Principled Base Color, with no unsupported color-ramp chain. No post-generation color correction or resampling was applied to this albedo.

Two separate, deterministic numerical surface maps are authored by the module, not generated from or extracted from the reference photographs:

- `pillowcase_satin_normal_v4.png`: tangent-space fine textile surface, encoded as a Non-Color normal map. Irregular anisotropic random fields provide fine grain and shallow wrinkles.
- `pillowcase_satin_mr_v4.png`: Non-Color metallic/roughness data; green contains roughness, blue is zero metallic, red is one. The image channels connect to the Principled roughness/metallic inputs.

The three images are packed in native Blender and exported as embedded GLB images. The finish retains the stable v4 cloth perimeter and thickness modifier, changes interior detail by no more than 4.8 mm, and replaces the inherited bright back-support material with black powder-coated steel. It does not alter chair placement, chair legs or other objects.

Blender 4.5's bundled `io_scene_gltf2/blender/exp/material/extensions/sheen.py` exports Sheen Tint directly and only uses Sheen Weight as an enable/disable gate. The module therefore encodes the modest sheen strength in Tint with Weight 1.0. This avoids exporting an unintended full-white velvet layer. Anisotropy and sheen are verified in the exported material JSON; their exact appearance remains renderer-dependent.

This finish is an incremental reconstruction candidate. The print is reference-informed artwork, not evidence that the geometry or final image is indistinguishable from the actual room.

## Actual export regression

The isolated 18-object chair export was inspected as a GLB, not only as Blender nodes. All three embedded PNG payloads and decoded pixel arrays match the source assets exactly. The Khronos glTF-Validator 2.0.0-dev.3.10 check returned 0 errors and 0 warnings. Local evidence is recorded in `.local/chair-pillow-finish-v4/pbr-regression.json`, `gltf-validation.json` and `gltf-validation-run.json`; these are experiment artifacts, not a replacement for validating the final whole-room export.

The actual reference-16 Cycles preview preserves the v4 silhouette and improves the print and black back-support material. Its large-scale drape remains smoother than the photograph; the finish does not establish scene-level photorealism.
