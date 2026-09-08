# Multi-view calibration — working refinement

The current refinement is an **estimated reconstruction**, not a dimensioned survey. Visual fidelity is still under review. The published v1 release remains separate from the private iteration renders.

## Evidence and coordinate system

Sixteen photographs were supplied. The isolated ceiling photograph was excluded from the first structure-from-motion run. COLMAP 4.2.0 registered **13 of the remaining 15 photographs**, recovering 1,376 sparse points and 4,134 observations. Desktop close-up 12 and bed-frame close-up 15 did not register. A bounded registration retry added neither image; unsupported poses were not fabricated.

The shared SIMPLE_RADIAL camera has focal length 677.77858 pixels on 1707 × 1280 images, principal point (853.5, 640), and radial coefficient −0.0001745593. This corresponds to approximately 14.294 mm on a 36 mm horizontal Blender sensor. The sparse reprojection RMS is 0.8515 pixels. This describes the fit to selected feature tracks; it does **not** establish photo-realism, dense surface accuracy or metric accuracy.

The room frame uses metres, Z up, Y from the entry wall toward the window, and X across the bed. Gravity was estimated from 16 manually checked architectural vertical edges in eight registered photographs. Its direction in the original SfM frame is `(0.04202959, 0.99269415, 0.11310101)` downward. Maximum line-plane residual is 0.418°; leaving out one photograph changes the inferred direction by at most 0.086°. Incorrect old picks that mixed mirror and door edges were removed.

## Scale is conditional

The [official Yudof page](https://housing.umn.edu/yudof) gives a 36 × 80-inch mattress, modelled as **0.9144 × 2.032 m**. No dimensioned plan specific to room 521 was found. The sparse reconstruction cannot recover an absolute scale by itself.

The present similarity scale is **0.3025935 m per SfM unit**, based on an estimated 2.14 m bed-post span around that mattress. The post span is not an official measurement. A separate entry-door check recovers a height-to-width ratio of approximately 2.325; assuming a 36 × 84-inch door gives 0.2996 m per SfM unit, within about 1% of the bed-based estimate. That door size is also an assumption. The cross-check supports consistency but is not an independent measurement.

## What constrains each part

| Part | Evidence | Remaining limitation |
| --- | --- | --- |
| Entry door | Robust plane from 38 deduplicated inlier tracks; multi-view leaf corners | Most tracks occupy a limited region; a false wood match was rejected |
| Window | Four visible recessed perimeter proxies triangulated from photos 3 and 13 | Blind rails partly occlude true aluminum-frame edges; wall opening and sill use separate points |
| Dresser | Three top corners, each visible in three to five views; unconstrained adjacent angle 89.88° | Fourth corner inferred as a parallelogram; feet and back are occluded |
| Desk | Two front tabletop corners | Rear corners obscured; depth remains an authored estimate |
| Wardrobe | Bed-side top corner and weaker top-edge intersection | Width/depth poorly conditioned; do not interpret the line result as a surveyed width |
| Bed | Four independently selected post-cap midpoints, seven exposed cover tracks and two piping observations | Cover height is constrained separately from post pose; dark floor-contact picks remain weak |
| Ceiling | Three useful multi-view corners with 10–18° parallax | One kitchen-side corner has only 2.47° parallax and is not used to determine height |
| Right rear wall projection | Calibrated rays, window-side corner, wardrobe relationship | Geometry is an orthogonal architectural approximation |

Manual point uncertainty is reported separately from shared camera and scale uncertainty. Millimetre-level point perturbation results must not be described as millimetre-level accuracy of the real room.

## Rebuilding and reviewing

`config/calibration.json` stores the accepted working dimensions, assembly placements and all 13 calibrated camera poses. `scripts/layout_v3.py` applies those estimates to the editable authored assets. The official mattress dimensions remain unchanged by the layout transforms. The construction is deterministic and does not require the original photographs to rebuild the released scene.

Private candidate builds use `--output-dir .local/iterations/<iteration>` and record source hashes alongside the native scene. Corresponding reference cameras support direct visual comparison. Final review must inspect the whole scene and close-ups for surface quality, contact, lighting, texture scale, object shape and occlusion—not just this calibration table or engineering checks.

Render a specific registered photograph's camera after rebuilding the calibrated scene:

```sh
blender --background scene/room.blend --python-exit-code 1 --python scripts/render.py -- --reference 4 --resolution 1600 --samples 96 --threads 8
```

This writes `renders/reference-04.jpg`. `--view all` still selects the four standard presentation cameras; it does not silently expand to every reference camera. Reference selection and standard view selection are mutually exclusive. A camera can carry an `exposure_ev` custom property for the corresponding capture exposure; each output's statistics record the actual exposure, view transform and look.

The renderer temporarily unbinds timeline-marker cameras during capture and restores them afterward. A Blender integration regression (`tests/blender_reference_camera.py`) verifies the selected unmarked camera against two differently colored, spatially separated panels, then checks that the original rig and native file remain intact.

Capture exposure is separate from room illumination. Initial kitchen and bedroom exposure estimates compare corresponding bare-wall regions; the remaining reference cameras start from an explicitly provisional shared exposure. These values do not establish a radiometric calibration or compensate for geometric differences. Final appearance is reviewed from the rendered scene, including wood, white appliances, textiles and the wall patches together.

## Subsequent placement corrections

Four post-cap midpoint observations support a bed center near `(0.00011, 3.98993)` m, a `+1.666°` rotation about Z and a `0.92302` m front/back post-center span. The independently picked window-side cap in photograph 13 improves from 38.32 px to 2.87 px reprojection error. This is a held-out feature check with an already registered camera, not an independent survey. The official mattress remains unchanged; only the connecting bed-frame members and rigid bed pose follow this fit.

Floor objects use separate entries under `layout.floor_props`. Photographs 9 and 16 constrain the storage lid to an estimated `0.3925 × 0.6134` m rectangle at Z `0.3194` m and `+14.8°` yaw. The standing suitcase faces approximately into the room at `−11°`, replacing an incorrect quarter-turn. Chair, bin and shoe positions use broader reference-derived estimates, with typical horizontal uncertainty of several centimetres.

The floor has **not** been lowered to match ambiguous shadow or wheel observations. A first twin-wheel correspondence was rejected after it produced incompatible contact heights. Corrected pairs give Z near 0 and a third-view far-wheel check near −0.01 m; these do not resolve the absolute floor level or a small carpet/vinyl height difference. The current floor surfaces remain a working construction assumption.

## Bed support and secondary details

Seven separately inspected exposed cream-cover features, each supported by three or four registered photographs, lie at Z 0.5963–0.6029 m. Their mean is 0.6010 m. The previous cover surface was about 57 mm too high at the same XY positions. The support refinement therefore lowers the mattress and steel support by 57 mm, giving a **resolved mattress top of 0.586 m**, a 0.482 m mattress centre and a nominal cover top of 0.601 m. The original `layout.bed.surface_z=0.643` remains an explicitly separate construction baseline. The new `bed_support` configuration records the deformation and resolved values; the build manifest includes the applied result.

The corrected front cover transition retracts by up to 50 mm and retains locally observed rise near the right side. The blue quilt's lower casing follows the lower support while its already matched upper silhouette stays fixed above Z 0.735 m. These are smooth authored deformations constrained by sparse observations. They are not a dense scan, and the fixed cameras and metric scale remain a source of shared uncertainty.

Four backpack views support a uniform scale of 0.894 and a base pivot near (−1.271, 2.8618, 0.741) m. Separate pocket and seam refinement follows this placement. The blind assembly now contains 68 strips, about 21.52 mm apart in world Z, with a true 25 mm strip depth and a 64° authored tilt after the window transform. Count uncertainty is approximately one strip where the headrail occludes the first opening.
# Additional manual review cameras

References 12 (desktop) and 15 (right bed frame) do not have reliable automatic SfM registration. The new `reference_cameras_v4` module fits manually identified static furniture and rigid-object landmarks using the existing 677.778580 px focal length. It does not replace the thirteen registered reference cameras.

Reference 12 has six fitted points (20.3 px RMS) and six independent held-out points (64.6 px RMS). Existing desktop prop positions are approximate, so this is only a rough appearance-review camera. Reference 15 has eight fitted points (24.0 px RMS) and three held-out screw centres (14.5 px RMS). These errors are measured at 1707 × 1280. Neither camera establishes surveyed geometry or successful SfM recovery. Coordinates, observation descriptions and residuals are embedded in the module. Exposure remains provisional.
