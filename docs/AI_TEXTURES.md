# AI-generated textures

Two printed fabrics in the scene come from an image generator rather than a photo or a script. In both cases I gave it my photo of the real fabric as a reference and asked for a flat, evenly lit print. Folds, thickness and lighting all come from the Blender geometry and shaders, not from these images.

| Texture | Used for | Size |
| --- | --- | --- |
| `assets/textures/blue_floral_art.png` | the blue floral duvet cover | 1254 × 1254 |
| `assets/textures/pillowcase_damask_art_v4.png` | the grey-pink pillowcase on the chair | 1086 × 1448 |

Neither image is a scan, and neither matches the real fabric pixel for pixel. The flower and ornament placement is newly generated. The duvet print was asked to tile seamlessly, but its opposite edges differ by 8–13 out of 255 per channel on average, so it is mapped once across the duvet instead of repeated.

The later revision on `main` also uses four more generated images, made the same way from my photos:

| Texture | Used for | Notes in |
| --- | --- | --- |
| `assets/textures/blue_floral_panel_v6.png` | the duvet, as one full panel | `blue_floral_panel_v6.provenance.json` |
| `assets/textures/blue_floral_reference_v3.png` | blue floral cloth that the v6 panel does not cover | `assets/TEXTILE_V3_SOURCES.json` |
| `assets/textures/rose_cotton_reference_v3.png` | the rose bedsheet | `assets/TEXTILE_V3_SOURCES.json` |
| `assets/textures/oak_honey_straight_reference_v3.png` | the plainer straight-grain oak on some furniture | `assets/WOOD_V3_SOURCES.json` |

Everything else is a CC0 download from Poly Haven, drawn by a script, or sampled from my own photos. [assets/README.md](../assets/README.md) lists which is which.

## Duvet prompt

```text
Use case: style-transfer.
Asset type: one square, seamless, high-resolution (2048 × 2048 if available) diffuse/albedo texture for a Blender cotton comforter.
Input image role: reference only, specifically the blue floral printed comforter visible along the bottom. Do not reproduce the room or any of its furnishings.
Primary request: reconstruct a flat repeatable textile print informed by that comforter. Powder/periwinkle blue ground, realistic softly printed large pink roses and peonies with pale blush highlights, muted sage-green leaves, slender decorative curving ocher/gold garlands, a few tiny brown-and-cream butterflies, delicate outlined meandering stems across the open blue areas. Botanical motifs should feel like actual mass-printed cotton bedding, detailed and natural rather than icons or circles. Preserve the reference's airy blue areas and dusty, gently aged palette.
Composition: strictly orthographic, edge-to-edge square material swatch with seamless matching opposite edges. A few irregular rose bouquets separated by substantial blue negative space, connected by thin looping garlands. Show only the flat printed fabric surface, with extremely fine cotton weave visible uniformly.
Lighting: completely even neutral diffuse color, no directional lighting, no ambient shadow, no highlights or vignetting. This is an albedo map, not a lit beauty photograph.
Constraints: entirely flat and unwrinkled; absolutely no folds, quilting relief, fabric drape, seams, pillows, beds, room, objects, perspective, borders, text, logos or watermark. Do not bake three-dimensional shading into the print. Natural printed botanical coloration inside flower petals is allowed.
```

## Pillowcase prompt

```text
Use case: photorealistic-natural. Asset type: one flat rectangular UV albedo texture for the grey-pink pillowcase visible on the black chair in the supplied reference photographs. These photographs are REFERENCE IMAGES ONLY: derive the pillowcase PRINT, never generate or modify a room render. Create ONE portrait 3:4 high-resolution image of the ENTIRE FLATTENED PRINT PATTERN, filling every pixel edge-to-edge. The long central field is muted dusty grey rose / pale mauve beige, with extremely subtle woven longitudinal satin stripes. Around ALL FOUR SIDES, an ornate wide dark charcoal-grey and muted brown Baroque/damask border: rich interlocking acanthus leaves, filled paisley scrolls, small scalloped fans, curling foliage, complex dense curvilinear ink details. The broad ornamental border is about 10-13 percent of cloth width, inset about 3 percent from the outside, joined naturally at the four corners, with several narrow straight fine double-rule borders inside and outside it. Match the reference's softly aged grey-black ornament on warm grey-pink cloth; do not substitute simple flower outlines, cartoon line drawings, a central medallion, bright colors or pure white. The large inner center remains quiet and mostly unornamented, as in the real pillowcase. Surface is perfectly flat, orthographic and uniformly neutrally illuminated, like a material color swatch; show fine silk-like woven textile grain only at micro scale. This is diffuse BASE COLOR artwork for a 3D material: absolutely NO folds, NO wrinkles, NO shading, NO glossy highlights, NO cast shadows, NO perspective, NO pillow volume, NO visible sewing geometry, NO room, NO furniture, NO people, NO screen content, NO names, NO address, NO letters, NO logos, NO watermark. Edge-to-edge rectangular print rather than an object on a background. AI-assisted reference-informed reconstruction, not an actual scan.
```
