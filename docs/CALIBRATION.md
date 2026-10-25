# Camera calibration

v1 was laid out by eye from the photos. For the later revision I ran COLMAP on the same photos to get real camera poses, corrected the layout against them, and added Blender cameras at the photo positions so I could compare a render with the photo taken from the same spot. The result is still an estimate of the room, not a survey.

## What COLMAP gave me

I took 16 photos. I left the ceiling shot out, and COLMAP 4.2.0 registered 13 of the other 15. The two that failed were close-ups: the desk (photo 12) and the bed frame (photo 15). The sparse model has 1,376 points, and the reprojection error is 0.85 px RMS. That only says the feature tracks agree with each other; it says nothing about how accurate the room is.

All photos share one SIMPLE_RADIAL camera: focal length 677.8 px on 1707 × 1280 images, which is about 14.3 mm on Blender's 36 mm sensor.

The room frame is in metres with Z up, Y running from the entry wall to the window, and X across the bed. I got "down" from 16 vertical wall and door-frame edges that I picked by hand in 8 of the photos. Leaving out any one photo changes that direction by less than 0.1°.

## Scale

COLMAP can't tell how big anything is. The only size I know is the bed: a standard Twin XL mattress, 36 × 80 in (0.9144 × 2.032 m). From that I estimated the bed posts to be 2.14 m apart, which gives 0.3026 m per COLMAP unit. As a cross-check I assumed the entry door is a standard 36 × 84 in door. That gives 0.2996 m per unit, within 1%. Both numbers rest on assumptions, so the room size of 3.33 × 4.54 × 3.035 m is only as good as they are.

## What I fitted to the photos

- **Entry door:** a plane through 38 matched points, plus the door corners seen in several photos.
- **Window:** four corners of the recess, triangulated from photos 3 and 13. The blind hides the real frame edges.
- **Dresser and desk:** three top corners of the dresser and the two front corners of the desk. The hidden corners and the desk's depth are my guesses.
- **Wardrobe:** one top corner and one top edge. Its width and depth are weakly constrained.
- **Bed:** the four post caps and seven points on the cream cover. Fitting the posts rotated the bed by 1.7°. A post cap I had not used in the fit then landed 2.9 px from its spot in photo 13, down from 38 px. The cover points showed the mattress was 57 mm too high, so I lowered the mattress and its support. The mattress itself keeps its standard size.
- **Ceiling:** three corners seen with enough parallax. A fourth had too little parallax to use.
- **Smaller things:** the storage box lid (photos 9 and 16), the suitcase, which I had turned 90° the wrong way, the backpack, and the window blind (68 slats about 21.5 mm apart). The chair, bin and shoes are only placed to within a few centimetres.

I did not move the floor to match shadows or suitcase wheels. Those observations disagreed with each other.

## The two photos COLMAP missed

For photos 12 and 15 I fitted cameras by hand in `scripts/reference_cameras_v4.py`, using the same focal length. For photo 12, I matched ten corners of the laptop screen, laptop base and tablet across photos 2, 9 and 12. The fit has 2.9 px RMS error, but a desk corner I left out of the fit is 25 px off, so treat that camera as approximate. The photo 15 camera is rougher still (24 px RMS on eight points). After I made it I moved the two right bed rails by 86 and 107 mm, so it is only good for a quick visual check.

## Files and commands

- `config/calibration.json` holds the room dimensions, furniture placements and the 13 COLMAP camera poses. `scripts/layout_v3.py` applies them when the scene is built. You don't need the photos to rebuild.
- Each photo camera has an `exposure_ev` property. I estimated it from bare wall patches for the kitchen and bedroom photos. The other cameras share a rough guess.

Render the view from one photo, for example photo 4:

```sh
blender --background scene/room.blend --python-exit-code 1 --python scripts/render.py -- \
  --reference 4 --resolution 1600 --samples 96 --threads 8
```

This writes `renders/reference-04.jpg`. `--view all` still means the four gallery cameras, and you can't combine `--reference` and `--view` in one run. `tests/blender_reference_camera.py` checks that a reference render uses the right camera and leaves the `.blend` unchanged.
