# Interactive demo

Vite + Three.js page for the room model: orbit the whole room, jump to the bedroom, kitchen and desk cameras, change lighting and exposure, and look at the Cycles renders. The text is in English and Chinese.

```sh
cd demo
npm ci
npm run dev        # http://127.0.0.1:5173
npm run build      # static site in dist/, deployable to any subpath
```

Needs Node 20.19+ or 22.12+. It loads `public/models/room-web.glb` (the meshopt-compressed model, see `../scripts/web-model`) and `public/renders/*.jpg`. Everything is served locally, with no CDN. Open it through the dev server, not `file://`.
