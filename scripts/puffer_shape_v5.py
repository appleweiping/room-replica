"""Photograph-constrained puffer reconstruction used by the main build.

No shader changes and no global spatial warp. The sleeve sections retain their
explicit centimetre-scale radii along measured centreline targets. Call after
layout_v3. The packaged support cache restores the fitted open-case contents.
"""

from __future__ import annotations

import math
import hashlib
import json
from pathlib import Path
import bpy
import bmesh
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

COLLECTION = "Props / Open suitcase and puffer jacket"
BODY_NAME = "Puffer V3 compressed filled torso"
TAG = "puffer_shape_v5_candidate"
TAU = math.tau

# Surface observations and tube centres are different: the upper sleeve surface
# is up to 6 cm above its axis. The cuff lower exterior is about z=0.173 m.
LEFT_PATH = (
    (0.090, 2.975, 0.532),
    (0.030, 2.932, 0.489),
    (-0.045, 2.879, 0.411),
    (-0.112, 2.800, 0.329),
    (-0.163, 2.729, 0.248),
    (-0.195, 2.698, 0.211),
)
LEFT_RADII = (
    (0.081, 0.068),
    (0.078, 0.068),
    (0.070, 0.062),
    (0.061, 0.054),
    (0.047, 0.042),
    (0.036, 0.033),
)
RIGHT_PATH = (
    (0.364, 2.974, 0.508),
    (0.467, 3.000, 0.435),
    (0.510, 2.968, 0.356),
    (0.490, 2.897, 0.302),
    (0.412, 2.851, 0.283),
    (0.337, 2.816, 0.280),
)
RIGHT_RADII = (
    (0.082, 0.068),
    (0.079, 0.065),
    (0.071, 0.057),
    (0.061, 0.051),
    (0.047, 0.042),
    (0.039, 0.034),
)
TORSO_PATH = (
    (0.205, 3.205, 0.275),
    (0.185, 3.158, 0.376),
    (0.179, 3.080, 0.482),
    (0.190, 2.993, 0.532),
    (0.205, 2.885, 0.423),
    (0.216, 2.805, 0.310),
)
TORSO_RADII = (
    (0.204, 0.020),
    (0.243, 0.034),
    (0.236, 0.041),
    (0.210, 0.049),
    (0.180, 0.035),
    (0.127, 0.027),
)


def _spline(values, t):
    values = np.asarray(values, dtype=float)
    q = np.clip(t, 0, 1) * (len(values) - 1)
    i = min(int(q), len(values) - 2)
    f = q - i
    p0 = values[max(i - 1, 0)]
    p1 = values[i]
    p2 = values[i + 1]
    p3 = values[min(i + 2, len(values) - 1)]
    return 0.5 * (
        (2 * p1)
        + (-p0 + p2) * f
        + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f * f
        + (-p0 + 3 * p1 - 3 * p2 + p3) * f * f * f
    )


def _mesh(name, vertices, faces, material, collection):
    mesh = bpy.data.meshes.new(name + " surface")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    ob = bpy.data.objects.new(name, mesh)
    collection.objects.link(ob)
    mesh.materials.append(material)
    for p in mesh.polygons:
        p.use_smooth = True
    return ob


def _curve(name, points, radius, material, collection):
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions = "3D"
    data.resolution_u = 1
    data.bevel_resolution = 1
    data.bevel_depth = radius
    line = data.splines.new("POLY")
    line.points.add(len(points) - 1)
    for p, co in zip(line.points, points):
        p.co = (*co, 1)
    ob = bpy.data.objects.new(name, data)
    collection.objects.link(ob)
    data.materials.append(material)
    return ob


def _crease(t, a, seed):
    """Local narrow pressure folds; no broad smooth noise bulges."""
    amount = 0.0
    for k in range(23):
        u = 0.035 + 0.93 * ((k * 0.61803398875 + seed * 0.173) % 1)
        phi = TAU * ((k * 0.38196601125 + seed * 0.217) % 1)
        d = math.atan2(math.sin(a - phi), math.cos(a - phi))
        centre = u + 0.033 * math.sin(d * 1.2 + seed + k)
        width = 0.006 + 0.008 * ((k * 0.236 + seed * 0.31) % 1)
        depth = 0.0013 + 0.0029 * ((k * 0.71 + seed * 0.13) % 1)
        amount -= depth * math.exp(-(((t - centre) / width) ** 2) - (d / 0.70) ** 2)
        # One tight asymmetrical folded lip next to the compression crease.
        amount += (
            0.36
            * depth
            * math.exp(-(((t - centre - width * 1.3) / (width * 0.65)) ** 2) - (d / 0.62) ** 2)
        )
    return amount


def _sweep(
    name,
    path,
    radii,
    cuts,
    material,
    collection,
    seed,
    rings=208,
    sides=80,
    torso=False,
    opening=True,
):
    centres = np.array([_spline(path, i / rings) for i in range(rings + 1)])
    arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(centres, axis=0), axis=1))]
    vertices = []
    faces = []
    rows = []
    samples = []
    previous = None
    for i, p in enumerate(centres):
        t = i / rings
        tangent = centres[min(i + 1, rings)] - centres[max(i - 1, 0)]
        tangent /= np.linalg.norm(tangent)
        axis = np.array([1.0, 0, 0])
        side = axis - np.dot(axis, tangent) * tangent
        side /= np.linalg.norm(side)
        if previous is not None and np.dot(side, previous) < 0:
            side = -side
        previous = side
        normal = np.cross(tangent, side)
        normal /= np.linalg.norm(normal)
        if normal[2] < 0:
            side = -side
            normal = -normal
            previous = side
        if torso:
            twist = 0.25 * math.exp(-(((t - 0.86) / 0.17) ** 2)) + 0.025 * math.sin(t * 4)
            old_side = side.copy()
            side = side * math.cos(twist) + normal * math.sin(twist)
            normal = normal * math.cos(twist) - old_side * math.sin(twist)
        width, depth = _spline(radii, t)
        # Sweep validity: do not let an elbow's minor radius exceed curvature.
        if 0 < i < rings:
            a = centres[i] - centres[i - 1]
            b = centres[i + 1] - centres[i]
            cross = np.linalg.norm(np.cross(a, b))
            if cross > 1e-12:
                radius = np.linalg.norm(a) * np.linalg.norm(b) * np.linalg.norm(a + b) / (2 * cross)
                depth = min(depth, max(0.022, 0.72 * radius))
        row = []
        for j in range(sides):
            angle = TAU * j / sides
            skew = 0.027 * math.sin(2 * angle + seed) + 0.017 * math.sin(5 * angle + seed * 0.4)
            phase = t + skew * math.sin(math.pi * t)
            k = next((k for k in range(len(cuts) - 1) if phase <= cuts[k + 1]), len(cuts) - 2)
            fraction = np.clip((phase - cuts[k]) / (cuts[k + 1] - cuts[k]), 0, 1)
            seam_distance = min(abs(phase - c) for c in cuts[1:-1]) if len(cuts) > 2 else 1
            channel = math.exp(-((seam_distance / 0.0045) ** 2))
            # Baffle loft stays below 9 mm, avoiding the old 3-cm sausage ridges.
            loft = (0.0065 if torso else 0.0045) * math.sin(math.pi * fraction) ** 0.65
            loft *= 0.65 + 0.35 * math.sin(angle * 2.5 + seed + k * 0.8) ** 2
            wrinkle = _crease(t, angle, seed) * math.sin(math.pi * t) ** 0.5
            width_at = width * (1 - (0.014 if torso else 0.05) * channel)
            depth_at = depth + loft - (0.004 if torso else 0.003) * channel
            if torso and math.sin(angle) > 0:
                # Folded front opening: a narrow depressed zipper valley, with
                # unequal padded panels instead of one uniformly inflated slab.
                zip_angle = math.pi / 2 + 0.16 * math.sin(t * 4.7)
                delta = math.atan2(math.sin(angle - zip_angle), math.cos(angle - zip_angle))
                depth_at -= 0.013 * math.exp(-((delta / 0.17) ** 2)) * math.sin(math.pi * t) ** 0.7
            radial = side * math.cos(angle) + normal * math.sin(angle)
            q = p + side * (width_at * math.cos(angle)) + normal * (depth_at * math.sin(angle))
            # Broad torso width is anatomical; small folds only displace normal.
            q += radial * wrinkle
            row.append(q)
            vertices.append(tuple(q))
            samples.append((tuple(q), t, angle, seed))
        rows.append(row)
    for i in range(rings):
        for j in range(sides):
            a = i * sides + j
            b = i * sides + (j + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    sample_faces = []
    for a, b, c, d in faces:
        sample_faces.extend(((a, b, c), (a, c, d)))
    faces.append(tuple(range(sides - 1, -1, -1)))
    end = centres[-1]
    direction = end - centres[-2]
    direction /= np.linalg.norm(direction)
    last = rings * sides
    if opening:
        inner = len(vertices)
        for q in rows[-1]:
            vertices.append(tuple(end + (q - end) * 0.73 - direction * 0.020))
        for j in range(sides):
            faces.append((last + j, last + (j + 1) % sides, inner + (j + 1) % sides, inner + j))
        faces.append(tuple(inner + j for j in range(sides)))
    else:
        faces.append(tuple(last + j for j in range(sides)))
    ob = _mesh(name, vertices, faces, material, collection)
    ob["construction"] = (
        "Bounded elliptical cross-sections along an explicit photographic centreline"
    )
    seams = []
    for k, c in enumerate(cuts[1:-1]):
        row = round(c * rings)
        seams.append((name + " quilting %02d" % k, rows[row] + rows[row][:1], 0.00034))
    seams.append(
        (
            name + " cuff binding" if not torso else name + " collar binding",
            rows[-1] + rows[-1][:1],
            0.0012,
        )
    )
    if torso:
        zip_path = []
        for i in range(12, rings - 5):
            angle = math.pi / 2 + 0.16 * math.sin(i / rings * 4.7)
            j = angle / TAU * sides
            a = int(j) % sides
            f = j - int(j)
            zip_path.append(rows[i][a] * (1 - f) + rows[i][(a + 1) % sides] * f)
        seams.append((name + " folded centre zip tape", zip_path, 0.0020))
    return (
        ob,
        seams,
        {
            "axis_length_m": float(arc[-1]),
            "maximum_half_width_m": max(r[0] for r in radii),
            "maximum_half_depth_m": max(r[1] for r in radii),
            "rings": rings,
            "sides": sides,
        },
        samples,
        sample_faces,
    )


def _union(parts, material, collection):
    vertices = []
    faces = []
    for ob in parts:
        offset = len(vertices)
        vertices.extend(tuple(v.co) for v in ob.data.vertices)
        faces.extend(tuple(offset + i for i in p.vertices) for p in ob.data.polygons)
    body = _mesh("Puffer V5 sewn volume", vertices, faces, material, collection)
    mod = body.modifiers.new("Closed garment seams / 2.3 mm union", "REMESH")
    mod.mode = "VOXEL"
    mod.voxel_size = 0.0023
    mod.use_smooth_shade = True
    deps = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(body.evaluated_get(deps), depsgraph=deps)
    body.modifiers.clear()
    old = body.data
    body.data = mesh
    if old.users == 0:
        bpy.data.meshes.remove(old)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.000005)
    bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1e-8)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    remaining = set(bm.verts)
    components = []
    while remaining:
        seed = remaining.pop()
        island = [seed]
        stack = [seed]
        while stack:
            v = stack.pop()
            for e in v.link_edges:
                other = e.other_vert(v)
                if other in remaining:
                    remaining.remove(other)
                    island.append(other)
                    stack.append(other)
        components.append(island)
    crumbs = [v for island in components if len(island) < 32 for v in island]
    if crumbs:
        bmesh.ops.delete(bm, geom=crumbs, context="VERTS")
    stats = {
        "connected_components": sum(len(c) >= 32 for c in components),
        "nonmanifold_edges": sum(not e.is_manifold for e in bm.edges),
        "vertices": len(bm.verts),
        "faces": len(bm.faces),
        "union_voxel_size_m": 0.0023,
    }
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True
    if not len(mesh.materials):
        mesh.materials.append(material)
    for ob in parts:
        bpy.data.objects.remove(ob, do_unlink=True)
    body.name = BODY_NAME
    return body, stats


def _world_points(ob):
    refs = []
    if ob.type == "MESH":
        refs = [(v, "co") for v in ob.data.vertices]
    elif ob.type == "CURVE":
        for spline in ob.data.splines:
            if spline.type == "BEZIER":
                for p in spline.bezier_points:
                    refs.extend([(p, "co"), (p, "handle_left"), (p, "handle_right")])
            else:
                refs.extend((p, "co") for p in spline.points)
    pts = np.array([tuple(ob.matrix_world @ Vector(tuple(getattr(p, a))[:3])) for p, a in refs])
    return pts, refs


def _surface_relief(body, samples, sample_faces):
    """Actual millimetre relief after union, so small folds are not voxel-filtered.

    Barycentric interpolation on the closest authored triangle supplies a
    continuous local length/angle chart. Creases
    gather near seam constraints; there is no uniform broad noise displacement.
    """
    positions = [Vector(s[0]) for s in samples]
    attributes = np.array([(s[1], math.sin(s[2]), math.cos(s[2])) for s in samples])
    tree = BVHTree.FromPolygons(positions, sample_faces, all_triangles=True)
    count = len(body.data.vertices)
    parameters = np.empty((count, 4))
    points = np.empty((count, 3))
    normals = np.empty((count, 3))
    for i, v in enumerate(body.data.vertices):
        co, _, index, distance = tree.find_nearest(v.co)
        ia, ib, ic = sample_faces[index]
        pa, pb, pc = positions[ia], positions[ib], positions[ic]
        ab = pb - pa
        ac = pc - pa
        aq = co - pa
        aa = ab.dot(ab)
        bb = ab.dot(ac)
        cc = ac.dot(ac)
        dd = aq.dot(ab)
        ee = aq.dot(ac)
        denominator = aa * cc - bb * bb
        vv = (cc * dd - bb * ee) / denominator
        ww = (aa * ee - bb * dd) / denominator
        uu = 1 - vv - ww
        attribute = attributes[ia] * uu + attributes[ib] * vv + attributes[ic] * ww
        t = float(np.clip(attribute[0], 0, 1))
        angle = math.atan2(attribute[1], attribute[2])
        seed = samples[ia][3]
        parameters[i] = (t, angle, seed, distance)
        points[i] = v.co
        normals[i] = v.normal
    # A voxel surface has high-frequency normal stair steps even on a broad,
    # smooth panel. Average the displacement frame locally before measuring its
    # curvature; otherwise that sampling noise suppresses almost all wrinkles.
    normal_lengths = np.linalg.norm(normals, axis=1)
    edges = np.array([tuple(e.vertices) for e in body.data.edges], dtype=int)
    a, b = edges.T
    for _ in range(4):
        summed = normals * 3
        np.add.at(summed, a, normals[b])
        np.add.at(summed, b, normals[a])
        normals = summed / np.maximum(np.linalg.norm(summed, axis=1)[:, None], 1e-12)
    # Keep the strongest correction out of truly sharp folded lips; the exact
    # self-intersection protection below handles the remaining unsafe patches.
    minimum_dot = np.ones(count)
    dots = np.einsum("ij,ij->i", normals[a], normals[b])
    np.minimum.at(minimum_dot, a, dots)
    np.minimum.at(minimum_dot, b, dots)
    curvature_weight = np.clip((minimum_dot - 0.55) / 0.35, 0, 1)
    displacement = np.zeros(count)
    for seed in (1.7, 2.9, 5.6):
        mask = np.isclose(parameters[:, 2], seed)
        t = parameters[mask, 0]
        a = parameters[mask, 1]
        height = np.zeros(len(t))
        for k in range(160):
            centre = 0.035 + 0.93 * ((k * 0.61803398875 + seed * 0.137) % 1)
            phi = TAU * ((k * 0.38196601125 + seed * 0.297) % 1)
            angle = np.arctan2(np.sin(a - phi), np.cos(a - phi))
            slope = 0.042 * math.sin(k * 2.34 + seed)
            line = centre + slope * angle + 0.009 * np.sin(angle * 3 + seed + k)
            width = 0.0080 + 0.0065 * ((k * 0.236 + seed * 0.31) % 1)
            amplitude = 0.0015 + 0.0024 * ((k * 0.71 + seed * 0.13) % 1)
            extent = 0.36 + 0.58 * ((k * 0.429 + seed * 0.25) % 1)
            envelope = np.exp(-((angle / extent) ** 2))
            height -= amplitude * np.exp(-(((t - line) / width) ** 2)) * envelope
            height += (
                amplitude
                * 0.38
                * np.exp(-(((t - line - width * 1.7) / (width * 0.75)) ** 2))
                * envelope
            )
        weight = np.sqrt(np.maximum(0, np.sin(np.pi * t)))
        # Suppress relief where a union attachment has no close local section.
        weight *= np.clip(1 - (parameters[mask, 3] - 0.002) / 0.006, 0, 1)
        displacement[mask] = np.clip(height, -0.0040, 0.0025) * weight * curvature_weight[mask]
    if not np.all(np.isfinite(displacement)):
        raise ValueError("Nonfinite coordinate relief; source section interpolation failed")
    cleanup = _protect_relief_intersections(body, points, normals, displacement)
    return {
        "minimum_displacement_m": float(displacement.min()),
        "maximum_displacement_m": float(displacement.max()),
        "localized_creases_per_section": 160,
        "geometry_relief_not_shader_change": True,
        "normal_length_before_smoothing_percentiles": np.percentile(
            normal_lengths, [0, 50, 100]
        ).tolist(),
        "displacement_frame_smoothing_steps": 4,
        "continuous_barycentric_section_chart": True,
        "vertices_with_relief_over_1mm": int(np.sum(abs(displacement) > 0.001)),
        "curvature_weight_percentiles": np.percentile(
            curvature_weight, [0, 10, 50, 90, 100]
        ).tolist(),
        "intersection_protection": cleanup,
    }


def _noncoplanar_crossing_pairs(points, triangles):
    tree = BVHTree.FromPolygons(points.tolist(), triangles.tolist(), all_triangles=True, epsilon=0)
    raw = tree.overlap(tree)
    pairs = [(i, j) for i, j in raw if i < j and not set(triangles[i]).intersection(triangles[j])]
    del raw
    if not pairs:
        return np.empty((0, 2), dtype=int)
    pairs = np.asarray(pairs, dtype=int)
    a = points[triangles[pairs[:, 0]]]
    b = points[triangles[pairs[:, 1]]]
    result = np.zeros(len(a), dtype=bool)
    for edge in range(3):
        for first, second in ((a, b), (b, a)):
            origin = first[:, edge]
            delta = first[:, (edge + 1) % 3] - origin
            e1 = second[:, 1] - second[:, 0]
            e2 = second[:, 2] - second[:, 0]
            h = np.cross(delta, e2)
            det = np.einsum("ij,ij->i", e1, h)
            ok = abs(det) > 1e-11
            inv = np.zeros_like(det)
            inv[ok] = 1 / det[ok]
            s = origin - second[:, 0]
            u = inv * np.einsum("ij,ij->i", s, h)
            q = np.cross(s, e1)
            v = inv * np.einsum("ij,ij->i", delta, q)
            t = inv * np.einsum("ij,ij->i", e2, q)
            result |= (
                ok & (u > 1e-7) & (v > 1e-7) & (u + v < 1 - 1e-7) & (t > 1e-7) & (t < 1 - 1e-7)
            )
    return pairs[result]


def _protect_relief_intersections(body, points, normals, displacement):
    """Attenuate only unsafe relief patches, returning to the valid union there.

    This is a deterministic geometric constraint, not a cloth solver. The check
    uses the same noncoplanar triangle test as the independent scene audit.
    """
    gate = np.ones(len(points))
    edges = np.array([tuple(e.vertices) for e in body.data.edges], dtype=int)
    first_count = None
    for iteration in range(7):
        q = points + normals * (displacement * gate)[:, None]
        if not np.all(np.isfinite(q)):
            raise ValueError("Nonfinite puffer vertex during relief constraint")
        for vertex, xyz in zip(body.data.vertices, q):
            vertex.co = xyz
        body.data.update()
        body.data.calc_loop_triangles()
        triangles = np.array([tuple(f.vertices) for f in body.data.loop_triangles], dtype=int)
        pairs = _noncoplanar_crossing_pairs(q, triangles)
        if first_count is None:
            first_count = len(pairs)
        if not len(pairs):
            return {
                "iterations": iteration,
                "initial_crossing_pairs": first_count,
                "final_crossing_pairs": 0,
                "locally_attenuated_vertices": int(np.sum(gate < 1)),
                "coplanar_overlap_tested": False,
            }
        bad = np.unique(triangles[pairs.ravel()].ravel())
        protection = np.ones(len(points))
        protection[bad] = 0
        frontier = bad
        for value in (0.10, 0.28, 0.50, 0.72, 0.90):
            touching = np.isin(edges[:, 0], frontier) | np.isin(edges[:, 1], frontier)
            frontier = np.unique(edges[touching].ravel())
            protection[frontier] = np.minimum(protection[frontier], value)
        gate = np.minimum(gate, protection)
    raise RuntimeError("Puffer relief could not satisfy its triangle self-intersection constraint")


def _raise_black_support(collection, shell):
    """Fill the observed black garment mound while keeping its underside seated."""
    ob = next(
        (
            o
            for o in collection.all_objects
            if o.type == "MESH" and o.name == "Folded clothing V3 central black outerwear"
        ),
        None,
    )
    if ob is None:
        raise ValueError("Expected central black support garment missing")
    p, refs = _world_points(ob)
    nx, ny = 64, 76
    count = (nx + 1) * (ny + 1)
    if len(p) != 2 * count:
        raise ValueError("Unexpected closed black garment topology")
    roof = BVHTree.FromPolygons(
        [v.co for v in shell.data.vertices], [tuple(f.vertices) for f in shell.data.polygons]
    )
    maximum = 0.0
    for j in range(ny + 1):
        for i in range(nx + 1):
            k = j * (nx + 1) + i
            u = i / nx
            v = j / ny
            xyz = p[k]
            interior = max(0, math.sin(math.pi * u) * math.sin(math.pi * v)) ** 0.65
            mound = (
                0.135
                * math.exp(-(((xyz[0] - 0.125) / 0.25) ** 2) - ((xyz[1] - 3.015) / 0.29) ** 2)
                * interior
            )
            ridge = 0.017 * math.exp(-(((v - 0.56 - 0.28 * (u - 0.5)) / 0.06) ** 2)) * interior
            lift = mound + ridge
            hit = roof.ray_cast(Vector((xyz[0], xyz[1], 0.145)), Vector((0, 0, 1)), 1)
            if hit[0] is not None:
                lift = min(lift, max(0, hit[0].z - 0.007 - xyz[2]))
            p[k, 2] += lift
            maximum = max(maximum, lift)
    _write(ob, refs, p)
    return {
        "maximum_upper_surface_lift_m": maximum,
        "underside_unchanged": True,
        "method": "Closed packed garment upper layer mound, bounded by puffer underside",
    }


def _write(ob, refs, points):
    inv = ob.matrix_world.inverted()
    for (p, a), xyz in zip(refs, points):
        q = inv @ Vector(xyz)
        old = getattr(p, a)
        setattr(p, a, (*q, old[3]) if len(old) == 4 else q)
    if ob.type == "MESH":
        ob.data.update()


def _load_authored_support_cache(collection):
    """Restore the reviewed case/textile pose without executing the rejected warp."""
    directory = Path(__file__).resolve().parents[1] / "assets/cache"
    metadata_path = directory / "open_luggage_support_v5.json"
    data_path = directory / "open_luggage_support_v5.npz"
    if not metadata_path.is_file() or not data_path.is_file():
        raise FileNotFoundError(
            "Puffer v5 requires assets/cache/open_luggage_support_v5.{json,npz}"
        )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(data_path.read_bytes()).hexdigest()
    if metadata.get("format_version") != 1 or digest != metadata.get("npz_sha256"):
        raise ValueError("Authored luggage support cache version or SHA-256 does not match")
    available = {o.name: o for o in collection.all_objects}
    staged = []
    with np.load(data_path, allow_pickle=False) as arrays:
        for entry in metadata["objects"]:
            ob = available.get(entry["name"])
            if ob is None or ob.type != entry["type"]:
                raise ValueError("Authored support object mismatch: " + entry["name"])
            _, refs = _world_points(ob)
            points = arrays[entry["array"]].copy()
            if len(refs) != entry["point_count"] or len(points) != len(refs):
                raise ValueError("Authored support topology changed: " + entry["name"])
            if ob.type == "MESH" and len(ob.data.polygons) != entry["mesh_faces"]:
                raise ValueError("Authored support face count changed: " + entry["name"])
            if not np.all(np.isfinite(points)):
                raise ValueError("Nonfinite authored support cache")
            staged.append((ob, refs, points, Matrix(entry["matrix_world"])))
    for ob, refs, points, matrix in staged:
        ob.matrix_world = matrix
        if len(refs):
            _write(ob, refs, points)
    return {
        "source": "assets/cache/open_luggage_support_v5.npz",
        "sha256": digest,
        "objects": len(staged),
        "authored_geometry_not_simulation": True,
    }


def _compress_support(objects, shell):
    """Shared positive height map: deterministic modeling, not cloth simulation."""
    records = []
    vertices = []
    faces = []
    for ob in objects:
        if not ob.name.startswith(("Folded clothing", "Grey shirt", "Light blue loose garment")):
            continue
        p, refs = _world_points(ob)
        if not len(p):
            continue
        records.append((ob, p, refs))
        if ob.type == "MESH":
            off = len(vertices)
            vertices.extend(p.tolist())
            faces.extend(tuple(off + i for i in f.vertices) for f in ob.data.polygons)
    tree = BVHTree.FromPolygons(vertices, faces)
    coat = BVHTree.FromPolygons(
        [v.co for v in shell.data.vertices], [tuple(p.vertices) for p in shell.data.polygons]
    )
    p = np.concatenate([r[1] for r in records])
    lo = p[:, :2].min(0) - 0.035
    hi = p[:, :2].max(0) + 0.035
    pitch = 0.006
    nx, ny = np.ceil((hi - lo) / pitch).astype(int) + 1
    ceiling = np.full((nx, ny), 1.2)
    top = np.full((nx, ny), 0.149)
    for i in range(nx):
        for j in range(ny):
            x, y = lo + np.array([i, j]) * pitch
            hit = coat.ray_cast(Vector((x, y, 0.145)), Vector((0, 0, 1)), 1)
            if hit[0] is not None:
                ceiling[i, j] = hit[0].z
            hit = tree.ray_cast(Vector((x, y, 1.2)), Vector((0, 0, -1)), 1.2)
            if hit[0] is not None:
                top[i, j] = hit[0].z

    def minimum(a, r):
        pad = np.pad(a, r, mode="edge")
        return np.minimum.reduce(
            [pad[i : i + nx, j : j + ny] for i in range(2 * r + 1) for j in range(2 * r + 1)]
        )

    ceiling = minimum(ceiling, 2)
    top = -minimum(-top, 1)
    floor = 0.1485
    factor = np.clip((ceiling - 0.006 - floor) / np.maximum(top - floor, 0.001), 0.08, 1)
    for _ in range(3):
        q = np.pad(factor, 1, mode="edge")
        smooth = (4 * q[1:-1, 1:-1] + q[2:, 1:-1] + q[:-2, 1:-1] + q[1:-1, 2:] + q[1:-1, :-2]) / 8
        factor = np.minimum(factor, smooth)

    def sample(points):
        ij = (points[:, :2] - lo) / pitch
        a = np.floor(ij).astype(int)
        w = ij - a
        a[:, 0] = np.clip(a[:, 0], 0, nx - 2)
        a[:, 1] = np.clip(a[:, 1], 0, ny - 2)
        i, j = a.T
        u, v = w.T
        return (
            (1 - u) * (1 - v) * factor[i, j]
            + u * (1 - v) * factor[i + 1, j]
            + (1 - u) * v * factor[i, j + 1]
            + u * v * factor[i + 1, j + 1]
        )

    maximum_drop = 0
    for ob, p, refs in records:
        f = sample(p)
        q = p.copy()
        q[:, 2] = floor + f * (p[:, 2] - floor)
        if ob.name.startswith("Folded clothing V3 central black outerwear"):
            q[:, 2] += 0.0015
        maximum_drop = max(maximum_drop, float((p[:, 2] - q[:, 2]).max()))
        _write(ob, refs, q)
    return {
        "maximum_additional_drop_m": maximum_drop,
        "minimum_height_factor": float(factor.min()),
        "textile_objects": len(records),
        "black_layer_clearance_m": 0.0015,
        "authored_geometry_not_simulation": True,
    }


def rebuild_puffer_shape():
    """Apply the reviewed v5 baseline after layout_v3, without rebuilding the room.

    Dependencies: Blender bpy/bmesh, bundled NumPy, and the two authored support
    cache files under assets/cache. No v4 code, network or photo files are used.
    """
    collection = bpy.data.collections.get(COLLECTION)
    if collection is None:
        raise ValueError("Open luggage collection not found")
    if collection.get(TAG):
        return {"status": "already_applied", "candidate": True}
    old = bpy.data.objects.get(BODY_NAME)
    if old is None:
        raise ValueError("Original puffer shell missing")
    material = old.data.materials[0]
    seam = next(
        (m for m in bpy.data.materials if "puffer stitched seams" in m.name.lower()), material
    )
    objects = list(collection.all_objects)
    # The private v4 candidate already contains the corrected case/support. A
    # clean layout input receives only the case rigid move; no failed warp runs.
    prior_support = bool(collection.get("luggage_pose_v4_candidate"))
    support_cache = None
    if not prior_support:
        initial = np.array([tuple(old.matrix_world @ v.co) for v in old.data.vertices])
        if not (2.60 < initial[:, 1].min() < 2.64 and 3.25 < initial[:, 1].max() < 3.29):
            raise ValueError("Puffer v5 must run after the original layout_v3 +0.40m Y placement")
        support_cache = _load_authored_support_cache(collection)
    for ob in objects:
        if ob.name.startswith("Puffer"):
            bpy.data.objects.remove(ob, do_unlink=True)
    parts = []
    seams = []
    section_stats = {}
    all_samples = []
    all_sample_faces = []
    specs = (
        (
            "torso",
            TORSO_PATH,
            TORSO_RADII,
            [0, 0.10, 0.215, 0.34, 0.47, 0.60, 0.73, 0.86, 1],
            1.7,
            True,
        ),
        (
            "left descending sleeve",
            LEFT_PATH,
            LEFT_RADII,
            [0, 0.12, 0.265, 0.42, 0.57, 0.71, 0.86, 1],
            2.9,
            False,
        ),
        (
            "right folded sleeve",
            RIGHT_PATH,
            RIGHT_RADII,
            [0, 0.11, 0.245, 0.395, 0.55, 0.69, 0.835, 1],
            5.6,
            False,
        ),
    )
    for label, path, radii, cuts, seed, torso in specs:
        ob, stitches, stats, samples, sample_faces = _sweep(
            "Puffer V5 " + label, path, radii, cuts, material, collection, seed, torso=torso
        )
        parts.append(ob)
        seams.extend(stitches)
        section_stats[label] = stats
        offset = len(all_samples)
        all_samples.extend(samples)
        all_sample_faces.extend(tuple(offset + i for i in f) for f in sample_faces)
    body, topology = _union(parts, material, collection)
    relief = _surface_relief(body, all_samples, all_sample_faces)
    tree = BVHTree.FromPolygons(
        [v.co for v in body.data.vertices], [tuple(f.vertices) for f in body.data.polygons]
    )
    for name, points, radius in seams:
        projected = []
        for p in points:
            hit = tree.find_nearest(Vector(p))
            if hit[0] is not None and hit[3] < 0.006:
                projected.append(tuple(hit[0] + hit[1] * radius * 0.5))
            else:
                if len(projected) > 3:
                    _curve(name, projected, radius, seam, collection)
                projected = []
        if len(projected) > 3:
            _curve(name, projected, radius, seam, collection)
    black_support = _raise_black_support(collection, body)
    support = _compress_support(list(collection.all_objects), body)
    collection[TAG] = True
    return {
        "status": "applied",
        "candidate": True,
        "strategy": "Explicit closed elliptical sections and 2.3 mm volume union",
        "retained_v4_support": prior_support,
        "materials_unchanged": True,
        "sections": section_stats,
        "authored_support_cache": support_cache,
        "topology": topology,
        "support": support,
        "relief": relief,
        "black_support": black_support,
        "left_sleeve_centres_m": LEFT_PATH,
        "limitations": [
            "Section radii are photograph-constrained estimates, not physical measurements",
            "Exact triangle intersections and real-camera visual review required",
            "Private v4 support input and clean layout input require separate visual checks",
        ],
    }
