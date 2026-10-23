// Full Blender export (~42 MB) -> web model (~6 MB) for the demo.
//
//   cd scripts/web-model && npm install && npm run build
//
// Steps: drop duplicate data, drop the luggage-tag lettering, shrink textures
// to at most 1024 px (Pillow, JPEG unless the image has alpha), then quantize
// and meshopt-compress the geometry. Node names and cameras are kept because
// the viewer looks walls, cameras and doors up by name.
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { dedup, meshopt, prune } from "@gltf-transform/functions";
import { MeshoptEncoder } from "meshoptimizer";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const [, , input, output] = process.argv;
if (!input || !output) {
  console.error("usage: node make_web_model.mjs <full.glb> <web.glb>");
  process.exit(2);
}
const python = process.env.PYTHON ?? (process.platform === "win32" ? "python" : "python3");
const shrink = `import sys
from PIL import Image
src, dst = sys.argv[1], sys.argv[2]
im = Image.open(src)
alpha = im.mode in ("RGBA", "LA") and im.getchannel("A").getextrema()[0] < 255
im.thumbnail((1024, 1024), Image.LANCZOS)
if alpha:
    im.save(dst + ".png", optimize=True)
    print("png")
else:
    im.convert("RGB").save(dst + ".jpg", quality=86, optimize=True)
    print("jpg")
`;

await MeshoptEncoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({
  "meshopt.encoder": MeshoptEncoder,
});
const doc = await io.read(input);
const root = doc.getRoot();

for (const node of root.listNodes()) {
  if (/Luggage tag neutral lettering/i.test(node.getName())) node.dispose();
}

const work = mkdtempSync(path.join(tmpdir(), "room-web-"));
try {
  writeFileSync(path.join(work, "shrink.py"), shrink);
  for (const [i, texture] of root.listTextures().entries()) {
    const src = path.join(work, `in${i}`);
    writeFileSync(src, texture.getImage());
    const kind = execFileSync(python, [path.join(work, "shrink.py"), src, path.join(work, `out${i}`)])
      .toString()
      .trim();
    const bytes = readFileSync(path.join(work, `out${i}.${kind}`));
    console.log(`${texture.getName()}: ${texture.getImage().byteLength} -> ${bytes.byteLength} bytes (${kind})`);
    texture.setImage(bytes).setMimeType(kind === "png" ? "image/png" : "image/jpeg");
  }
} finally {
  rmSync(work, { recursive: true, force: true });
}

await doc.transform(
  dedup(),
  prune({ keepLeaves: true, keepAttributes: true }),
  meshopt({ encoder: MeshoptEncoder, level: "high" }),
);
await io.write(output, doc);
console.log(`wrote ${output} (${(readFileSync(output).byteLength / 1e6).toFixed(1)} MB)`);
