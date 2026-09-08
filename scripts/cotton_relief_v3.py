"""Sparse elongated cotton creases; retained portable printed albedo.

Shader-only look development. Dimensions describe authored relief, not a scan.
Long creases follow the existing cloth UVs and are broken into uneven patches.
The module preserves the photographed-print reconstruction and geometry.
"""

from materials_v2 import _bump, _noise

VERSION = "3.0.0"


def refine_cotton_relief(materials):
    report = []
    for material in materials:
        nodes, links = material.node_tree.nodes, material.node_tree.links
        old_bump = nodes.get("Cotton / millimetre-scale compression creases")
        if old_bump is None:
            continue
        # Reuse the nominal metre-scaled cloth UV node from the base shader.
        old_noise = nodes["Cotton / fine relaxed compression wrinkles"]
        uv = old_noise.inputs["Vector"].links[0].from_socket
        threads = nodes["Cotton / 130 micron thread relief"]
        rose = "cream" in material.name.lower() or "rose" in material.name.lower()
        warp = _noise(nodes, links, uv, 3.1, "COTTONV3 / slow direction variation", 2.0)
        offset = nodes.new("ShaderNodeVectorMath")
        offset.operation = "SCALE"
        offset.inputs["Scale"].default_value = 0.075
        links.new(warp.outputs["Color"], offset.inputs[0])
        warped = nodes.new("ShaderNodeVectorMath")
        warped.operation = "ADD"
        links.new(uv, warped.inputs[0])
        links.new(offset.outputs["Vector"], warped.inputs[1])
        elongate = nodes.new("ShaderNodeVectorMath")
        elongate.operation = "MULTIPLY"
        elongate.inputs[1].default_value = (68.0, 12.5, 1.0)
        links.new(warped.outputs["Vector"], elongate.inputs[0])
        folded = _noise(
            nodes,
            links,
            elongate.outputs["Vector"],
            1.0,
            "COTTONV3 / elongated local compression",
            2.5,
        )
        ridge = nodes.new("ShaderNodeMath")
        ridge.operation = "SUBTRACT"
        ridge.inputs[1].default_value = 0.51
        links.new(folded.outputs["Fac"], ridge.inputs[0])
        absolute = nodes.new("ShaderNodeMath")
        absolute.operation = "ABSOLUTE"
        links.new(ridge.outputs[0], absolute.inputs[0])
        profile = nodes.new("ShaderNodeMapRange")
        profile.interpolation_type = "SMOOTHERSTEP"
        profile.inputs["From Min"].default_value = 0.018
        profile.inputs["From Max"].default_value = 0.105
        profile.inputs["To Min"].default_value = 1.0
        profile.inputs["To Max"].default_value = 0.0
        links.new(absolute.outputs[0], profile.inputs["Value"])
        density = nodes.new("ShaderNodeMapRange")
        density.interpolation_type = "SMOOTHERSTEP"
        density.inputs["From Min"].default_value = 0.38
        density.inputs["From Max"].default_value = 0.63
        density.inputs["To Min"].default_value = 0.07
        density.inputs["To Max"].default_value = 1.0
        links.new(warp.outputs["Fac"], density.inputs["Value"])
        height = nodes.new("ShaderNodeMath")
        height.operation = "MULTIPLY"
        links.new(profile.outputs["Result"], height.inputs[0])
        links.new(density.outputs["Result"], height.inputs[1])
        normal = _bump(
            nodes,
            links,
            height.outputs[0],
            0.42,
            0.00065 if rose else 0.0016,
            "COTTONV3 / sparse sharp cotton creases",
        )
        links.new(normal, threads.inputs["Normal"])
        for node in (old_bump, old_noise, nodes.get("Cotton / soft crease cross section")):
            if node is not None:
                nodes.remove(node)
        material["cotton_relief_version"] = VERSION
        report.append({"material": material.name, "relief_m": 0.00065 if rose else 0.0016})
    return {"version": VERSION, "materials": report}
