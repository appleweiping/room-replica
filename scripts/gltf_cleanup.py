"""Keep portable tangents only where the material uses a tangent frame.

Blender's global tangent export can emit zero tangents on degenerate UVs in
otherwise valid, untextured meshes. Those attributes have no material effect.
This postprocessor removes only unused TANGENT attributes, then drops their
unreferenced accessors/buffer views and losslessly repacks embedded data.
Positions, normals, indices, UVs, images and material definitions are unchanged.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import struct


# These extensions do not introduce accessor/buffer-view references. Unknown
# extensions disable binary compaction rather than risk rewriting opaque data.
MATERIAL_EXTENSIONS = {
    "KHR_materials_clearcoat",
    "KHR_materials_transmission",
    "KHR_materials_ior",
    "KHR_materials_volume",
    "KHR_materials_specular",
    "KHR_materials_sheen",
    "KHR_materials_emissive_strength",
    "KHR_materials_unlit",
    "KHR_materials_iridescence",
    "KHR_materials_dispersion",
    "KHR_materials_pbrSpecularGlossiness",
    "KHR_materials_anisotropy",
}
COMPACTABLE_EXTENSIONS = MATERIAL_EXTENSIONS | {
    "KHR_texture_transform",
    "KHR_texture_basisu",
    "EXT_texture_webp",
    "EXT_texture_avif",
    "MSFT_texture_dds",
    "KHR_mesh_quantization",
    "KHR_lights_punctual",
    "KHR_materials_variants",
    "EXT_mesh_gpu_instancing",
}


def needs_tangent(material: dict) -> bool:
    """Conservatively preserve tangents for normal maps or anisotropy."""
    if "normalTexture" in material:
        return True
    extensions = material.get("extensions", {})
    if "clearcoatNormalTexture" in extensions.get("KHR_materials_clearcoat", {}):
        return True
    if "KHR_materials_anisotropy" in extensions:
        return True
    return bool(set(extensions) - MATERIAL_EXTENSIONS)


def read_glb(filename: Path):
    source = filename.read_bytes()
    if len(source) < 20:
        raise ValueError("GLB is shorter than its header")
    magic, version, total = struct.unpack_from("<4sII", source)
    if magic != b"glTF" or version != 2 or total != len(source):
        raise ValueError("Invalid GLB 2 header or byte length")
    chunks, cursor = [], 12
    while cursor < len(source):
        if cursor + 8 > len(source):
            raise ValueError("Truncated GLB chunk header")
        length, kind = struct.unpack_from("<II", source, cursor)
        cursor += 8
        if cursor + length > len(source) or length % 4:
            raise ValueError("Invalid GLB chunk length")
        chunks.append((kind, source[cursor : cursor + length]))
        cursor += length
    if chunks[0][0] != 0x4E4F534A:
        raise ValueError("GLB must start with its JSON chunk")
    data = json.loads(chunks[0][1])
    return data, chunks, len(source)


def accessor_references(data):
    """Mutable (parent, key) references in core glTF and supported instancing."""
    references = []
    for mesh in data.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            attributes = primitive.get("attributes", {})
            references.extend((attributes, key) for key in attributes)
            if "indices" in primitive:
                references.append((primitive, "indices"))
            for target in primitive.get("targets", []):
                references.extend((target, key) for key in target)
    for skin in data.get("skins", []):
        if "inverseBindMatrices" in skin:
            references.append((skin, "inverseBindMatrices"))
    for animation in data.get("animations", []):
        for sampler in animation.get("samplers", []):
            references.extend([(sampler, "input"), (sampler, "output")])
    for node in data.get("nodes", []):
        attributes = (
            node.get("extensions", {}).get("EXT_mesh_gpu_instancing", {}).get("attributes", {})
        )
        references.extend((attributes, key) for key in attributes)
    return references


def buffer_view_references(data):
    references = []
    for accessor in data.get("accessors", []):
        if "bufferView" in accessor:
            references.append((accessor, "bufferView"))
        for sparse_part in accessor.get("sparse", {}).values():
            if isinstance(sparse_part, dict) and "bufferView" in sparse_part:
                references.append((sparse_part, "bufferView"))
    for image in data.get("images", []):
        if "bufferView" in image:
            references.append((image, "bufferView"))
    return references


def cleanup_unused_tangents(filename: Path | str) -> dict:
    filename = Path(filename)
    data, chunks, original_bytes = read_glb(filename)
    materials = data.get("materials", [])
    removed_accessors = set()
    removed_attributes = 0
    retained_attributes = 0
    for mesh in data.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            attributes = primitive.get("attributes", {})
            if "TANGENT" not in attributes:
                continue
            material = materials[primitive["material"]] if "material" in primitive else {}
            variants = (
                primitive.get("extensions", {})
                .get("KHR_materials_variants", {})
                .get("mappings", [])
            )
            if needs_tangent(material) or any(
                needs_tangent(materials[item["material"]]) for item in variants
            ):
                retained_attributes += 1
                continue
            removed_accessors.add(attributes.pop("TANGENT"))
            removed_attributes += 1

    binary_chunks = [i for i, (kind, _) in enumerate(chunks) if kind == 0x004E4942]
    buffers = data.get("buffers", [])
    unknown_extensions = set(data.get("extensionsUsed", [])) - COMPACTABLE_EXTENSIONS
    compact = (
        not unknown_extensions
        and len(buffers) == 1
        and "uri" not in buffers[0]
        and len(binary_chunks) == 1
        and all(view.get("buffer", 0) == 0 for view in data.get("bufferViews", []))
    )
    dropped_accessors = dropped_views = 0
    if compact and removed_accessors:
        references = accessor_references(data)
        used = {parent[key] for parent, key in references}
        remove = removed_accessors - used
        old_accessors = data.get("accessors", [])
        candidate_views = {
            old_accessors[i]["bufferView"] for i in remove if "bufferView" in old_accessors[i]
        }
        index_map, kept = {}, []
        for i, accessor in enumerate(old_accessors):
            if i not in remove:
                index_map[i] = len(kept)
                kept.append(accessor)
        data["accessors"] = kept
        for parent, key in references:
            parent[key] = index_map[parent[key]]
        dropped_accessors = len(remove)

        view_references = buffer_view_references(data)
        used_views = {parent[key] for parent, key in view_references}
        remove_views = candidate_views - used_views
        old_binary = chunks[binary_chunks[0]][1]
        view_map, kept_views, new_binary = {}, [], bytearray()
        for i, view in enumerate(data.get("bufferViews", [])):
            if i in remove_views:
                continue
            start = view.get("byteOffset", 0)
            length = view["byteLength"]
            if start < 0 or length < 0 or start + length > len(old_binary):
                raise ValueError("Buffer view exceeds embedded data")
            new_binary.extend(b"\0" * (-len(new_binary) % 4))
            view = dict(view)
            view["byteOffset"] = len(new_binary)
            new_binary.extend(old_binary[start : start + length])
            view_map[i] = len(kept_views)
            kept_views.append(view)
        for parent, key in view_references:
            parent[key] = view_map[parent[key]]
        data["bufferViews"] = kept_views
        buffers[0]["byteLength"] = len(new_binary)
        new_binary.extend(b"\0" * (-len(new_binary) % 4))
        chunks[binary_chunks[0]] = (0x004E4942, bytes(new_binary))
        dropped_views = len(remove_views)

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    payload += b" " * (-len(payload) % 4)
    chunks[0] = (0x4E4F534A, payload)
    output = bytearray(struct.pack("<4sII", b"glTF", 2, 12 + sum(8 + len(p) for _, p in chunks)))
    for kind, payload in chunks:
        output.extend(struct.pack("<II", len(payload), kind))
        output.extend(payload)
    if removed_attributes:
        temporary = filename.with_suffix(filename.suffix + ".tmp")
        temporary.write_bytes(output)
        os.replace(temporary, filename)
    return {
        "removed_unused_tangent_attributes": removed_attributes,
        "retained_required_tangent_attributes": retained_attributes,
        "removed_accessors": dropped_accessors,
        "removed_buffer_views": dropped_views,
        "binary_compaction": compact,
        "unknown_extensions_preserved": sorted(unknown_extensions),
        "bytes_before": original_bytes,
        "bytes_after": filename.stat().st_size,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("glb", type=Path)
    args = parser.parse_args()
    print(json.dumps(cleanup_unused_tangents(args.glb), indent=2))
