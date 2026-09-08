# Rebuild the editable blue-quilt print charts

The ordinary scene build reads the bundled `assets/uv/blue_quilt_print_v6.npz`;
it requires no SciPy and never runs a new cloth simulation. The scene module
uses an exact topology/coordinate fast path and a strictly checked geometric
correspondence path for the voxel cleanup's small indexing/topology variation.

The full rebuild can produce 675610 vertices where the original saved scene
contained 675614. The cache therefore also stores calibrated world vertices,
face centres and chart identity. The fallback permits at most 1.2 mm nearest
vertex residual, 0.05 mm at the 99th percentile, 2.5 mm face-centre residual,
and 0.5 mm bounds change. Reverse correspondence is independently sampled.
Every target face chooses one existing chart; its loops must have an existing
source `(vertex, chart)` coordinate, including seam overrides. Any failed gate
requires regeneration instead of silently misbinding UVs. The original saved
scene's UV result remains byte-identical. These narrow tolerances accommodate
cleanup variation, not an arbitrary cloth or layout change.

These two optional tools make the cache reproducible if the quilt topology or
its accepted pose changes. Work from the repository root. Use Blender 4.5.13
and a native scene containing the accepted `bed_support_v4` result. The exporter
applies `bedding_surface_v5` in memory if it is not already present.

```powershell
python -m pip install -r scripts/bedding_print_tools/requirements.txt
& $blender -b scene/room.blend -t 4 --python-exit-code 1 --python scripts/bedding_print_tools/export_donors.py -- --work-dir .local/bedding-print-build
python scripts/bedding_print_tools/transfer_uv.py --work-dir .local/bedding-print-build
```

Set `$blender` to the Blender executable before running these commands. The
first command that executes Blender reads the supplied scene without saving
it, reconstructs only the five original cloth surfaces as temporary UV donors,
and exports their measured charts. It does not voxel-remesh the whole quilt.
The second command uses a single-worker nearest-triangle transfer and writes
the new UV cache. The generated `donor-report.json` and `uv-transfer-report.json`
record the scene hash, topology, physical lengths and projection distances.
For an isolated comparison, add `--output-dir <temporary-directory>` to the
transfer command; this leaves the shipped cache untouched. The expanded cache
was regenerated this way and matched the checked asset byte for byte.

The new charts use the actual folded-surface arc lengths to normalize the
printed motif scale. This removes the former independent image zoom levels;
it is not a claim that every non-developable padded surface is distortion-free.
Chart boundaries follow the joins between the original cloth pieces. A small
set of loop overrides prevents the material from interpolating across those
joins. Surface topology and coordinates are never changed by the print pass.

After regenerating the cache, rebuild the scene and inspect the same reference
cameras before committing the asset. Albedo edits use a separate named UV map,
so the existing weave/crease mapping remains intact. The optional colour
multiplier exports as standard glTF `baseColorFactor`, with `baseColorTexture`
using the named print UV channel.
