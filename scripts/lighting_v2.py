"""Practical interior lighting and separate glazing for the photographed room.

The sink bar is unlit in the references. Daylight enters from outside the
window, rather than a small emitter directly against an opaque metallic pane.
"""

import bpy
from mathutils import Vector
from common import material
from calibration import CALIBRATION


def refine_lighting():
    glass = bpy.data.materials.get("Window / clear soda-lime glazing")
    if glass is None:
        glass = material("Window / clear soda-lime glazing", (0.97, 0.985, 0.98), 0.025)
    bs = glass.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Transmission Weight"].default_value = 1
    bs.inputs["IOR"].default_value = 1.52
    pane = bpy.data.objects.get("Window_Glass")
    if pane:
        pane.data.materials.clear()
        pane.data.materials.append(glass)
    blinds = bpy.data.materials.get("blinds")
    if blinds:
        shader = blinds.node_tree.nodes.get("Principled BSDF")
        # Opaque enamel coats the aluminium substrate.
        shader.inputs["Metallic"].default_value = 0
        shader.inputs["Roughness"].default_value = 0.49
    light = bpy.data.objects.get("Light_Window")
    if light:
        light.location = (
            CALIBRATION["window"]["center_x"],
            CALIBRATION["room"]["length"] + 0.77,
            1.74,
        )
        light.rotation_euler = (
            (Vector((CALIBRATION["window"]["center_x"], 1.9, 1.1)) - light.location)
            .to_track_quat("-Z", "Y")
            .to_euler()
        )
        light.data.energy = CALIBRATION.get("lighting", {}).get("window_power_w", 38)
        light.data.color = CALIBRATION.get("lighting", {}).get(
            "window_color_linear", (0.38, 0.66, 1.0)
        )
        light.data.size = 2.5
        light.data.size_y = 2.7
        # This large card approximates exterior illumination. Camera hiding
        # alone does not hide it after a glass transmission bounce: it became
        # a glowing rectangle in the lower blind gaps. Preserve its lighting
        # contribution while exposing the environment through the glazing.
        light.visible_transmission = False
    sink = bpy.data.objects.get("Light_Sink")
    if sink:
        sink.data.energy = 0
    main = bpy.data.objects.get("Light_Fluorescent")
    if main and "layout" in CALIBRATION:
        main.location.y = 2.25
        main.data.color = CALIBRATION.get("lighting", {}).get(
            "fluorescent_color_linear", (1, 0.956, 0.88)
        )
    cover = bpy.data.objects.get("Sink_wall_diffuser")
    if cover:
        unlit = bpy.data.materials.get("Sink / aged unlit diffuser")
        if unlit is None:
            unlit = material("Sink / aged unlit diffuser", (0.66, 0.65, 0.59), 0.51)
        cover.data.materials.clear()
        cover.data.materials.append(unlit)
