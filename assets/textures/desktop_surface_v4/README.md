# Desktop surface artwork

Original neutral electronic-display and keyboard assets for
`scripts/desktop_surface_v4.py`. They contain no copied personal screenshot
pixels, conversation text, product serial numbers or reference-photo textures.

| File | Purpose |
| --- | --- |
| `keycap-legends.png` | 4096×2048 atlas for100 low-profile keycaps; legends have a consistent physical size across wide/tall keys |
| `keyboard-layout.json` | Different key widths, function row, numeric cluster, arrows and per-key atlas cells |
| `laptop-neutral-workspace.png` | Original1920×1200 dark document interface |
| `tablet-neutral-notes.png` | Original1470×1000 blue note page, fine ruling and neutral handwritten words |
| `anodized-handwear-roughness.png` | Authored512×512 subtle palm-contact and finish variation |
| `display-subtle-roughness.png` | Authored512×512 mild screen finish variation |
| `author_graphics.py` | Rebuild graphics with Python, NumPy and Pillow |
| `PROVENANCE.json` | Authorship, font-rasterizer information, hashes and limitations |

The committed PNGs are the canonical input assets. Regeneration uses a local
Consolas or DejaVu Sans Mono font; a local Segoe Print font, when available,
supplies the authored handwritten words. No font file is redistributed. Output
glyph appearance may differ on a machine with a different font/rasterizer.

After `desktop_pose_v4`, call
`refine_desktop_surfaces(M=None, texture_dir=None)`. The default asset directory
is relative to the module's repository; `texture_dir` can provide another copy
of this directory. The operation is idempotent and does not move device shells,
display rectangles or cameras. It replaces only simplified key/legend/ruled-line
objects and the old touchpad loop, and creates100 actual shallow-dished keycaps
plus a0.15mm narrow touchpad groove. Existing device outlines stay unchanged.

Colour images connect directly to Principled Base Color. Screens also use their
same original image as emission; roughness maps load as Non-Color and remain
portable through glTF ORM packing. Native small-scale wear is authored, not a
measurement of this exact laptop. The key layout is plausible and informed by
the photos, not an identified manufacturer's CAD model.

Actual native reviews used the calibrated reference12 and reference9 cameras,
their own exposure properties,640×480 CPU Cycles,24 samples and four threads.
Two review rounds were made. Fine key lettering remains weak at640 pixels due
to projected size and denoising; the artwork contains real small glyphs rather
than oversized white placeholders. This is an accepted surface increment and
does not establish complete room photorealism.
