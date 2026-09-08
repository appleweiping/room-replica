# Room, remembered. — Interactive demo

中文 / English · Vite + Three.js · Local assets · No runtime CDN

这是房间 Blender 重建项目的交互展示页：旋转全景、室内视角、光线和画质调整，以及离线渲染画廊。页面明确区分实时预览与 Blender 离线渲染，并注明房间尺寸是照片推算。

## Run locally

Requirements: Node.js 20.19+ or 22.12+ and npm.

```sh
cd demo
npm ci
npm run dev
```

Open the localhost URL printed by Vite. The server binds to `127.0.0.1` by default. Do not open `index.html` directly with `file://`; model loading requires an HTTP server.

```sh
npm run check
npm run build
npm run preview
```

`dist/` is the deployable static site. `base: './'` makes URLs relative, including on a GitHub Pages repository subpath. A lockfile pins dependencies. JavaScript, fonts (system fonts), model and renders do not depend on third-party runtime hosts.

## Asset contract

```text
public/
  favicon.svg
  scene-manifest.json
  models/room.glb
  renders/bedroom.jpg
  renders/kitchen.jpg
  renders/desk.jpg
  renders/overview.jpg
```

The reconstruction pipeline supplies the binary model and JPEG renders. Copy them **before** the final production build: Vite copies `public/` into `dist/` at build time. The website does not create substitute geometry if the model is missing. A missing or invalid model produces a retry state; missing gallery images have an explicit unavailable state.

The GLB must be self-contained, with embedded textures. Source uses Blender meters and Z-up; the standard glTF exporter maps coordinates to Y-up: `(x, y, z) = (Blender x, Blender z, -Blender y)`. Interior presets use the cameras embedded in the GLB (`Camera_Bedroom`, `Camera_Kitchen`, `Camera_Desk`), including their exported position, direction and field of view. Fallback presets and the whole-room camera are in `src/viewer.js`. The reconstructed room occupies approximately Blender x ∈ [-1.5, 1.5], y ∈ [0, 4.15], z ∈ [0, 2.82]; these are reconstruction assumptions, not measurements.

Copy `scene/scene-manifest.json` to `public/scene-manifest.json` after rebuilding the Blender scene. The viewer displays its estimated width, length and height after checking that all three values are positive finite numbers and explicitly labeled `photo-estimated`. Missing metadata does not prevent model loading.

## Controls

| Interaction | Result |
| --- | --- |
| Left drag / one-finger drag | Orbit around the current target |
| Wheel / pinch | Zoom |
| Right drag / two-finger pan | Pan |
| Arrow keys while the canvas has focus | Pan |
| Viewpoint buttons | Smooth transition to whole-room, bed/window, kitchen or desk |
| Cutaway | Hide the ceiling and camera-facing shell walls |
| Lighting | Change daylight / warm artificial lighting |
| Exposure | Adjust display exposure, 0.50–1.80 |
| Quality | Detailed: higher pixel ratio and shadows; Smooth: lower pixel ratio without shadows |
| Auto orbit | Slowly orbit around the current target |
| Reset | Restore the currently selected camera preset |
| Save this view | Download the current WebGL canvas as a PNG |
| Full screen | Expand the viewer, when the browser supports the Fullscreen API |
| Download 3D model | Download the bundled GLB |
| Gallery image | Open a full-size image dialog; Escape closes it |
| EN / 中文 | Switch language; preference persists when local storage is available |

All controls have text labels or accessible names. Keyboard focus is visible. Reduced-motion preferences disable camera interpolation, control damping and CSS animation. The renderer pauses when the document is hidden and only draws when a view change requires it (or auto orbit is active). This is an orbit viewer, not a collision-aware first-person navigation system.

## Rendering details

`RoomEnvironment` generates a local environment map. A hemisphere, directional light, and interior/window point lights illuminate the scene. Blender-exported punctual lights are disabled so their unit conventions cannot unexpectedly overexpose the browser preview. Materials use Three.js PBR, sRGB output and ACES tone mapping.

The bundled GLB is approximately **42 MB** (41,832,444 bytes) before HTTP compression (size varies when textures are rebuilt). Initial loading time depends on the connection and GPU; downloading textures is distinct from shader compilation. The browser combines compatible static meshes by identical material into fewer draw batches. World transforms are applied to cloned geometry in model-root coordinates before merging. Shell walls/ceiling, transparent or transmissive meshes, multi-material meshes, negative transforms, and skinned/morph/instanced geometry stay separate. Required tangent frames for normal-mapped materials are included in the exported model; unused tangent attributes are removed losslessly by `scripts/gltf_cleanup.py`. Batch grouping includes the full vertex-attribute signature, and Three.js transforms tangent directions while preserving handedness. The downloadable GLB is not modified. Original and batched mesh counts are available as `data-source-meshes` and `data-batched-meshes` on `#canvas-host` for diagnostics.

The delivered asset contains **1,280 source mesh instances**. The actual batch count is exposed on the viewer DOM after loading; cutaway components remain separate so they can be restored in interior views. Mesh count is a draw-submission proxy, not a measured frame-rate guarantee.

Detailed mode caps device pixel ratio at **1.25**, while Smooth caps it at **1** and disables shadows. Shadow maps update only when the scene/cutaway/light state changes. Rendering is otherwise driven by changes to the camera or controls, rather than drawing an unchanged frame continuously. Detailed performance depends on integrated/discrete GPU capability; offline renders are available independently of the 3D viewer.

Near-wall cutaway uses mesh names starting with `Shell_Wall_` and the object's bounding-box orientation. Ceiling meshes use `Shell_Ceiling`. Meshes with their own name or an ancestor name beginning `Entry_Door`, `Interior_Door`, `Ceiling_Light`, or `Smoke_detector` are also hidden in cutaway mode to avoid floating or obstructing architectural details. These components are excluded from batching and restored when cutaway is disabled. All cabinetry and furnishings remain visible. Switch to a room preset to restore the full interior. Whole-room mode is designed for spatial inspection.

Browser rendering is an approximation of the Blender scene. Cycles shader networks, ray-traced mirrors, fabric microstructure and indirect lighting may render differently in glTF. The gallery shows the offline results. Photo-guided reconstruction does not establish survey accuracy; see the root project research and assumptions documents.

## Validation checklist

Before release, run `npm ci`, `npm run check`, `npm run build`, and `npm audit --registry=https://registry.npmjs.org`. Inspect the final built site with its actual model and image assets:

- Load the GLB; confirm object count and render gallery images appear.
- Change every viewpoint and ensure objects remain framed.
- Toggle cutaway, lighting, quality and exposure; verify the displayed view changes.
- Save a PNG; download and reopen the GLB.
- Open and close the image dialog using a mouse and Escape.
- Switch languages and check all control descriptions.
- Inspect desktop and narrow viewport layouts, and keyboard focus.
- Temporarily test an unavailable model URL to exercise the retry state.

Actual performed checks and remaining limitations belong in the root validation report; this checklist is not a claim that all checks have passed.

Primary implementation references: [Three.js documentation](https://threejs.org/docs/) and [Vite static deployment documentation](https://vite.dev/guide/static-deploy.html).
