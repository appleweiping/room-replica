"""Photograph-informed electronic surface details after desktop_pose_v4.

Existing device shells, display rectangles and their matrices stay unchanged.
Original neutral PNG graphics replace simplified geometric lettering. No source
screen pixels/text are used. See assets/textures/desktop_surface_v4/PROVENANCE.json.
"""
from pathlib import Path
import json, math

import bpy

VERSION = "4.0.0"
COLLECTION = "Props / Desktop surface v4"


def _image(directory, name, noncolor=False):
    image = bpy.data.images.load(str(directory / name), check_existing=True)
    image.colorspace_settings.name = "Non-Color" if noncolor else "sRGB"
    image.pack()
    return image


def _material(name, color, roughness, metallic=0):
    mat = bpy.data.materials.new("DesktopSurfaceV4 / " + name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1)
    bs = mat.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = (*color, 1)
    bs.inputs["Metallic"].default_value = metallic
    bs.inputs["Roughness"].default_value = roughness
    bs.inputs["Specular IOR Level"].default_value = 0.32
    return mat


def _texture(mat, image, socket="Base Color"):
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.name = "Authored " + socket
    node.image = image
    node.extension = "EXTEND"
    node.interpolation = "Linear"
    bs = mat.node_tree.nodes.get("Principled BSDF")
    for link in list(bs.inputs[socket].links):
        mat.node_tree.links.remove(link)
    mat.node_tree.links.new(node.outputs["Color"], bs.inputs[socket])
    return node


def _mesh(name, vertices, faces, material, matrix, collection, smooth=False):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    ob = bpy.data.objects.new(name, mesh)
    collection.objects.link(ob)
    mesh.materials.append(material)
    ob.matrix_world = matrix.copy()
    for poly in mesh.polygons:
        poly.use_smooth = smooth
    return ob


def _rounded_rectangle(hx, hy, radius, subdivisions=8):
    points = []
    corners = ((hx-radius, hy-radius), (-hx+radius, hy-radius),
               (-hx+radius, -hy+radius), (hx-radius, -hy+radius))
    for corner, (cx, cy) in enumerate(corners):
        for step in range(subdivisions):
            angle = (corner + step/subdivisions) * math.pi/2
            points.append((cx+radius*math.cos(angle), cy+radius*math.sin(angle)))
    return points


def _keycap(key, index, matrix, material, collection):
    # The keyboard frame uses local +X toward the hinge, -Y toward the numeric
    # pad. Low-profile shoulders and a 0.16 mm dished top are actual geometry.
    depth, width = key["depth"], key["width"]
    outline = _rounded_rectangle(depth/2, width/2, min(depth, width)*0.10)
    count = len(outline)
    levels = ((1.0, .01005), (1.0, .01140), (.91, .01240),
              (.63, .01232), (.30, .01226))
    vertices = [(key["x"]+x*scale, key["center_y"]+y*scale, z)
                for scale, z in levels for x, y in outline]
    faces = []
    for ring in range(len(levels)-1):
        for j in range(count):
            k = (j+1) % count
            faces.append((ring*count+j, ring*count+k, (ring+1)*count+k, (ring+1)*count+j))
    center = len(vertices)
    vertices.append((key["x"], key["center_y"], .01224))
    last = (len(levels)-1)*count
    for j in range(count):
        faces.append((last+j, last+(j+1)%count, center))
    # A planar underside fan avoids Blender's n-gon tangent warning during a
    # global tangent export. Visible key surfaces and UV coordinates are intact.
    bottom_center = len(vertices)
    vertices.append((key["x"], key["center_y"], levels[0][1]))
    for j in range(count):
        faces.append((bottom_center, (j+1)%count, j))
    ob = _mesh(f"DesktopSurfaceV4_Key_{index:03d}_{key['label']}", vertices,
               faces, material, matrix, collection, True)
    uv = ob.data.uv_layers.new(name="Keycap atlas")
    col, row = key["atlas_cell"]
    for poly in ob.data.polygons:
        for li in poly.loop_indices:
            x, y, _ = vertices[ob.data.loops[li].vertex_index]
            u = .5-(y-key["center_y"])/width
            v = .5+(x-key["x"])/depth
            # Slightly inset from atlas-cell boundaries to avoid filtered bleed.
            u, v = .025+.95*u, .025+.95*v
            uv.data[li].uv = ((col+u)/16, 1-(row+1-v)/8)
    ob["detail_type"] = "Real low-profile dished keycap; authored subdued laser legend"
    return ob


def _display(ob, directory, filename, normal_axis, collection):
    ob.data = ob.data.copy()
    mesh = ob.data
    mat = _material(filename, (.03, .035, .045), .25)
    node = _texture(mat, _image(directory, filename))
    bs = mat.node_tree.nodes.get("Principled BSDF")
    mat.node_tree.links.new(node.outputs["Color"], bs.inputs["Emission Color"])
    bs.inputs["Emission Strength"].default_value = .42 if normal_axis==0 else .28
    bs.inputs["Coat Weight"].default_value = .08
    bs.inputs["Coat Roughness"].default_value = .25
    _texture(mat, _image(directory, "display-subtle-roughness.png", True), "Roughness")
    mesh.materials.append(mat)
    layer = mesh.uv_layers.active or mesh.uv_layers.new(name="UVMap")
    points = [v.co for v in mesh.vertices]
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    for poly in mesh.polygons:
        front = poly.normal.x < -.9 if normal_axis==0 else poly.normal.z > .9
        if not front:
            continue
        poly.material_index = len(mesh.materials)-1
        for li in poly.loop_indices:
            p = points[mesh.loops[li].vertex_index]
            u = (hi[1]-p.y)/(hi[1]-lo[1])
            v = (p.z-lo[2])/(hi[2]-lo[2]) if normal_axis==0 else (p.x-lo[0])/(hi[0]-lo[0])
            layer.data[li].uv = (u, v)
    ob["screen_content"] = "Original neutral authored UI; not copied from personal screen"
    return mat


def refine_desktop_surfaces(M=None, texture_dir=None):
    """Replace local small details without moving the calibrated devices.

    Must follow desktop_pose_v4. Reapplying to the same scene is a no-op.
    """
    scene = bpy.context.scene
    if scene.get("desktop_surface_v4") == VERSION:
        return json.loads(scene["desktop_surface_v4_audit"])
    directory = Path(texture_dir) if texture_dir else Path(__file__).resolve().parents[1]/"assets/textures/desktop_surface_v4"
    layout = json.loads((directory/"keyboard-layout.json").read_text(encoding="utf-8"))
    required = ("Laptop aluminium lower shell", "Laptop touchpad inset",
                "Laptop active display", "Tablet note display", "Tablet folio rim")
    for name in required:
        if name not in bpy.data.objects:
            raise ValueError("Missing calibrated device anchor: " + name)
    if not scene.get("desktop_pose_refinement"):
        raise ValueError("desktop_pose_v4 must run before desktop surface refinement")
    anchors = {name: bpy.data.objects[name] for name in required}
    matrices = {name: [list(row) for row in ob.matrix_world] for name, ob in anchors.items()}
    bounds = {name: [list(v.co) for v in ob.data.vertices] for name, ob in anchors.items()}
    collection = bpy.data.collections.get(COLLECTION) or bpy.data.collections.new(COLLECTION)
    if collection.name not in scene.collection.children:
        scene.collection.children.link(collection)
    remove_prefix = ("Laptop key ", "Key legend", "Long spacebar", "Touchpad engraved border",
                     "Editor ", "Screen neutral heading", "Tablet ruled paper line", "Tablet authored title")
    removed = [ob.name for ob in bpy.data.objects if ob.name.startswith(remove_prefix)]
    for name in removed:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    key_material = _material("subdued charcoal keycaps", (.03, .035, .04), .47)
    _texture(key_material, _image(directory, "keycap-legends.png"))
    created = [_keycap(key, i, anchors["Laptop aluminium lower shell"].matrix_world,
                       key_material, collection).name for i, key in enumerate(layout["keys"])]
    # A thin planar groove with true small-radius corners replaces the old
    # auto-Bezier loop, which overshot into a large rounded coil.
    pad = anchors["Laptop touchpad inset"]
    px = max(v.co.x for v in pad.data.vertices)
    py = max(v.co.y for v in pad.data.vertices)
    pz = max(v.co.z for v in pad.data.vertices)+.000015
    outer = _rounded_rectangle(px-.00025, py-.00025, .0015, 12)
    inner = _rounded_rectangle(px-.00040, py-.00040, .00135, 12)
    count = len(outer)
    vertices = [(x,y,pz)for x,y in outer+inner]
    faces = [(i,(i+1)%count,(i+1)%count+count,i+count)for i in range(count)]
    groove = _material("touchpad narrow engraved channel", (.045,.049,.055), .53)
    created.append(_mesh("DesktopSurfaceV4_Touchpad groove", vertices, faces, groove,
                         pad.matrix_world, collection).name)
    wear = _image(directory, "anodized-handwear-roughness.png", True)
    for name in ("Laptop aluminium lower shell", "Laptop touchpad inset", "Laptop screen lid"):
        ob = bpy.data.objects[name]
        # A material copy avoids changing any silver prop outside this task.
        mat = ob.data.materials[0].copy()
        mat.name = "DesktopSurfaceV4 / anodized finish " + name
        bs = mat.node_tree.nodes.get("Principled BSDF")
        bs.inputs["Metallic"].default_value = .62
        for link in list(bs.inputs["Normal"].links):
            mat.node_tree.links.remove(link)
        _texture(mat, wear, "Roughness")
        ob.data = ob.data.copy()
        ob.data.materials[0] = mat
    _display(anchors["Laptop active display"], directory, "laptop-neutral-workspace.png", 0, collection)
    _display(anchors["Tablet note display"], directory, "tablet-neutral-notes.png", 2, collection)
    assert all(matrices[name]==[list(row)for row in ob.matrix_world] for name,ob in anchors.items())
    assert all(bounds[name]==[list(v.co)for v in ob.data.vertices] for name,ob in anchors.items())
    audit = {"version": VERSION, "removed_objects": removed, "created_objects": created,
             "keycaps": len(layout["keys"]), "device_anchor_matrices_and_vertices_unchanged": True,
             "content": "Original neutral graphics; no personal screenshot content",
             "order": "After desktop_pose_v4", "original_device_camera_fit_retained": True}
    scene["desktop_surface_v4"] = VERSION
    scene["desktop_surface_v4_audit"] = json.dumps(audit)
    return audit
