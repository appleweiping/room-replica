import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";

const CUTAWAY_DETAIL = /^(Entry_Door|Interior_Door|Ceiling_Light|Smoke_detector)/i;

function isCutawayDetail(object) {
  for (let current = object; current; current = current.parent) {
    if (CUTAWAY_DETAIL.test(current.name)) return true;
  }
  return false;
}

// glTF axes after Blender export: (x, y, z) = (Blender x, Blender z, -Blender y).
export const VIEWPOINTS = Object.freeze({
  dollhouse: { position: [-4.8, 5.7, 5.6], target: [0, 0.9, -2.1], fov: 37 },
  bedroom: { position: [-0.1, 1.65, -0.62], target: [0, 1.04, -3.65], fov: 74 },
  kitchen: {
    position: [0.04, 1.66, -3.35],
    target: [-0.14, 1.23, -0.05],
    fov: 76,
  },
  desk: { position: [-0.35, 1.5, -2.4], target: [1.13, 0.93, -1.8], fov: 63 },
});

export class RoomViewer {
  constructor(host) {
    this.host = host;
    this.dirty = true;
    this.cutaway = true;
    this.walls = [];
    this.ceiling = [];
    this.cutawayDetails = [];
    this.meshCount = 0;
    this.lastTime = 0;
    this.currentView = "dollhouse";
    this.viewpoints = structuredClone(VIEWPOINTS);
    this.reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
    try {
      this.renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: false,
        preserveDrawingBuffer: true,
        powerPreference: "high-performance",
      });
    } catch {
      throw new Error("WEBGL_UNAVAILABLE");
    }
    this.renderer.setClearColor(0xe7e4db);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 0.8;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.shadowMap.autoUpdate = false;
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 1.25));
    host.append(this.renderer.domElement);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(37, 1, 0.025, 80);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = !this.reducedMotion;
    this.controls.dampingFactor = 0.08;
    this.controls.maxDistance = 16;
    this.controls.minDistance = 0.18;
    this.controls.maxPolarAngle = Math.PI * 0.49;
    this.controls.autoRotateSpeed = 0.5;
    this.controls.addEventListener("change", () => {
      this.dirty = true;
    });
    this.controls.addEventListener("start", () => {
      this.transition = null;
    });
    this.controls.listenToKeyEvents(host);
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    const environment = new RoomEnvironment();
    this.environmentTarget = pmrem.fromScene(environment, 0.04);
    this.scene.environment = this.environmentTarget.texture;
    this.scene.environmentIntensity = 0.42;
    environment.dispose();
    pmrem.dispose();

    this.ambient = new THREE.HemisphereLight(0xf5f7ff, 0x78624e, 0.65);
    this.scene.add(this.ambient);
    this.keyLight = new THREE.DirectionalLight(0xfff4dc, 1.1);
    this.keyLight.position.set(-2.5, 6, -2.0);
    this.keyLight.target.position.set(0, 0, -2);
    this.keyLight.castShadow = true;
    this.keyLight.shadow.mapSize.set(2048, 2048);
    this.keyLight.shadow.camera.left = -5;
    this.keyLight.shadow.camera.right = 5;
    this.keyLight.shadow.camera.top = 5;
    this.keyLight.shadow.camera.bottom = -5;
    this.keyLight.shadow.camera.near = 0.1;
    this.keyLight.shadow.camera.far = 20;
    this.keyLight.shadow.bias = -0.00012;
    this.keyLight.shadow.normalBias = 0.018;
    this.scene.add(this.keyLight, this.keyLight.target);
    this.interiorLight = new THREE.PointLight(0xfff6e5, 8, 9, 2);
    this.interiorLight.position.set(0, 2.55, -2.0);
    this.scene.add(this.interiorLight);
    this.windowLight = new THREE.PointLight(0xdceaff, 3, 7, 2);
    this.windowLight.position.set(0, 1.8, -3.75);
    this.scene.add(this.windowLight);

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(host);
    this.visibilityHandler = () => {
      this.dirty = true;
    };
    document.addEventListener("visibilitychange", this.visibilityHandler);
    this.renderer.domElement.addEventListener("webglcontextlost", (event) => {
      event.preventDefault();
      host.dispatchEvent(
        new CustomEvent("viewer-context-lost", { bubbles: true }),
      );
    });
    this.setView("dollhouse", false);
    this.resize();
    this.loop = this.loop.bind(this);
    this.frame = requestAnimationFrame(this.loop);
  }

  async load(url, onProgress) {
    const loader = new GLTFLoader();
    const gltf = await loader.loadAsync(url, (event) => {
      onProgress(
        event.total
          ? Math.min(99, Math.round((event.loaded / event.total) * 100))
          : Math.min(95, Math.round((event.loaded / 1024 / 1024) * 2)),
      );
    });
    if (this.model) this.scene.remove(this.model);
    this.model = gltf.scene;
    this.model.updateMatrixWorld(true);
    this.walls = [];
    this.ceiling = [];
    this.cutawayDetails = [];
    this.meshCount = 0;
    const maxAnisotropy = Math.min(
      8,
      this.renderer.capabilities.getMaxAnisotropy(),
    );
    this.model.traverse((object) => {
      // Browser lighting is calibrated separately from Cycles lights.
      if (object.isLight) object.visible = false;
      if (!object.isMesh) return;
      this.meshCount++;
      const isThinBlindSlat = /^Blind_Slat_/i.test(object.name);
      object.castShadow = !isThinBlindSlat;
      object.receiveShadow = !isThinBlindSlat;
      const materials = Array.isArray(object.material)
        ? object.material
        : [object.material];
      for (const material of materials) {
        if ("envMapIntensity" in material) material.envMapIntensity = 0.25;
        for (const texture of [
          material.map,
          material.normalMap,
          material.roughnessMap,
        ]) {
          if (texture) texture.anisotropy = maxAnisotropy;
        }
      }
      if (/Shell_Ceiling/i.test(object.name)) this.ceiling.push(object);
      if (isCutawayDetail(object)) {
        this.cutawayDetails.push({ object, originalVisibility: object.visible });
      }
      if (/Shell_Wall_/i.test(object.name)) {
        const box = new THREE.Box3().setFromObject(object);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        const normal =
          size.x < size.z
            ? new THREE.Vector3(Math.sign(center.x) || 1, 0, 0)
            : new THREE.Vector3(0, 0, Math.sign(center.z + 2.075) || 1);
        this.walls.push({ object, center, normal });
      }
    });
    this.scene.add(this.model);
    this.model.updateMatrixWorld(true);
    // Use the authored Blender cameras and their actual exported field of view.
    const targetDistances = { bedroom: 2.735, kitchen: 2.67, desk: 1.985 };
    for (const authoredCamera of gltf.cameras) {
      const key = authoredCamera.name.replace(/^Camera_/i, "").toLowerCase();
      if (!targetDistances[key] || !authoredCamera.isPerspectiveCamera)
        continue;
      authoredCamera.updateWorldMatrix(true, false);
      const position = authoredCamera.getWorldPosition(new THREE.Vector3());
      const direction = authoredCamera.getWorldDirection(new THREE.Vector3());
      this.viewpoints[key] = {
        position: position.toArray(),
        target: position
          .clone()
          .addScaledVector(direction, targetDistances[key])
          .toArray(),
        fov: authoredCamera.fov,
      };
    }
    this.batchStaticMeshes();
    this.renderer.shadowMap.needsUpdate = true;
    this.dirty = true;
    onProgress(100);
  }

  batchStaticMeshes() {
    // The source GLB stays editable. These batches exist only in browser memory.
    const groups = new Map();
    const inverseRoot = this.model.matrixWorld.clone().invert();
    this.model.traverse((object) => {
      if (!object.isMesh || object.isSkinnedMesh || object.isInstancedMesh)
        return;
      if (/Shell_(Wall_|Ceiling)/i.test(object.name)) return;
      if (isCutawayDetail(object)) return;
      if (Array.isArray(object.material) || !object.material) return;
      if (object.material.transparent || object.material.transmission > 0)
        return;
      if (object.matrixWorld.determinant() <= 0) return;
      if (Object.keys(object.geometry.morphAttributes).length) return;
      const attributes = Object.entries(object.geometry.attributes)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(
          ([name, value]) =>
            `${name}:${value.itemSize}:${value.normalized}:${value.array.constructor.name}`,
        )
        .join("|");
      const key = `${object.material.uuid}:${Boolean(object.geometry.index)}:${object.castShadow}:${object.receiveShadow}:${attributes}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(object);
    });
    let batches = 0;
    for (const objects of groups.values()) {
      if (objects.length < 2) continue;
      const geometries = objects.map((object) => {
        const geometry = object.geometry.clone();
        geometry.applyMatrix4(inverseRoot.clone().multiply(object.matrixWorld));
        return geometry;
      });
      const geometry = mergeGeometries(geometries, false);
      geometries.forEach((item) => item.dispose());
      if (!geometry) continue;
      geometry.computeBoundingBox();
      geometry.computeBoundingSphere();
      const batch = new THREE.Mesh(geometry, objects[0].material);
      batch.name = `BrowserBatch_${objects[0].material.name}_${batches++}`;
      batch.userData.sourceNames = objects.map((object) => object.name);
      batch.castShadow = objects[0].castShadow;
      batch.receiveShadow = objects[0].receiveShadow;
      objects.forEach((object) => object.removeFromParent());
      this.model.add(batch);
    }
    this.drawMeshCount = 0;
    this.model.traverse((object) => {
      if (object.isMesh) this.drawMeshCount++;
    });
    this.host.dataset.sourceMeshes = String(this.meshCount);
    this.host.dataset.batchedMeshes = String(this.drawMeshCount);
  }

  setView(key, animate = true) {
    const view = this.viewpoints[key] || this.viewpoints.dollhouse;
    this.currentView = key;
    this.cutaway = key === "dollhouse";
    this.controls.maxPolarAngle =
      key === "dollhouse" ? Math.PI * 0.49 : Math.PI * 0.94;
    this.controls.minDistance = key === "dollhouse" ? 2 : 0.18;
    this.controls.maxDistance = key === "dollhouse" ? 16 : 8;
    if (animate && !this.reducedMotion) {
      this.transition = {
        start: performance.now(),
        duration: 850,
        position: this.camera.position.clone(),
        target: this.controls.target.clone(),
        fov: this.camera.fov,
        endPosition: new THREE.Vector3(...view.position),
        endTarget: new THREE.Vector3(...view.target),
        endFov: this.framedFov(view.fov),
      };
    } else {
      this.camera.position.fromArray(view.position);
      this.controls.target.fromArray(view.target);
      this.camera.fov = this.framedFov(view.fov);
      this.camera.updateProjectionMatrix();
      this.controls.update();
    }
    this.dirty = true;
  }

  setCutaway(enabled) {
    this.cutaway = enabled;
    this.dirty = true;
  }
  setAutoRotate(enabled) {
    this.controls.autoRotate = enabled;
    this.dirty = true;
  }
  setExposure(value) {
    this.renderer.toneMappingExposure = value;
    this.dirty = true;
  }

  setLighting(mode) {
    const warm = mode === "warm";
    this.keyLight.color.set(warm ? 0xffd2a1 : 0xfff4dc);
    this.keyLight.intensity = warm ? 0.55 : 1.1;
    this.interiorLight.color.set(warm ? 0xffca89 : 0xfff6e5);
    this.interiorLight.intensity = warm ? 12 : 8;
    this.windowLight.intensity = warm ? 1.1 : 3;
    this.ambient.intensity = warm ? 0.48 : 0.65;
    this.renderer.shadowMap.needsUpdate = true;
    this.dirty = true;
  }

  setQuality(quality) {
    const high = quality === "high";
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, high ? 1.25 : 1));
    this.renderer.shadowMap.enabled = high;
    if (this.model)
      this.model.traverse((object) => {
        if (object.material)
          for (const material of Array.isArray(object.material)
            ? object.material
            : [object.material])
            material.needsUpdate = true;
      });
    this.renderer.shadowMap.needsUpdate = true;
    this.resize();
  }

  updateCutaway() {
    let changed = false;
    for (const { object, originalVisibility } of this.cutawayDetails) {
      const visible = originalVisibility && !this.cutaway;
      if (object.visible !== visible) {
        object.visible = visible;
        changed = true;
      }
    }
    for (const ceiling of this.ceiling) {
      if (ceiling.visible === this.cutaway) {
        ceiling.visible = !this.cutaway;
        changed = true;
      }
    }
    const direction = this.camera.position
      .clone()
      .sub(new THREE.Vector3(0, 1, -2.075))
      .normalize();
    for (const { object, normal } of this.walls) {
      const visible = !this.cutaway || normal.dot(direction) < 0.1;
      if (object.visible !== visible) {
        object.visible = visible;
        changed = true;
      }
    }
    if (changed) this.renderer.shadowMap.needsUpdate = true;
  }

  framedFov(baseFov) {
    if (this.currentView !== "dollhouse") return baseFov;
    const aspectCompensation = Math.max(1, 1.25 / this.camera.aspect);
    return THREE.MathUtils.radToDeg(
      2 * Math.atan(Math.tan(THREE.MathUtils.degToRad(baseFov / 2)) * aspectCompensation),
    );
  }

  resize() {
    const { width, height } = this.host.getBoundingClientRect();
    if (!width || !height) return;
    this.camera.aspect = width / height;
    const view = this.viewpoints[this.currentView] || this.viewpoints.dollhouse;
    this.camera.fov = this.framedFov(view.fov);
    if (this.transition) this.transition.endFov = this.camera.fov;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
    this.dirty = true;
  }

  loop(time) {
    this.frame = requestAnimationFrame(this.loop);
    if (document.hidden) return;
    const delta = Math.min(0.05, (time - this.lastTime) / 1000 || 0.016);
    this.lastTime = time;
    if (this.transition) {
      const a = this.transition;
      const progress = Math.min(1, (time - a.start) / a.duration);
      const eased = progress * progress * (3 - 2 * progress);
      this.camera.position.lerpVectors(a.position, a.endPosition, eased);
      this.controls.target.lerpVectors(a.target, a.endTarget, eased);
      this.camera.fov = THREE.MathUtils.lerp(a.fov, a.endFov, eased);
      this.camera.updateProjectionMatrix();
      if (progress === 1) this.transition = null;
      this.dirty = true;
    }
    this.controls.update(delta);
    if (this.dirty || this.controls.autoRotate) {
      this.updateCutaway();
      this.renderer.render(this.scene, this.camera);
      this.dirty = false;
    }
  }

  async capture() {
    this.updateCutaway();
    this.renderer.render(this.scene, this.camera);
    const blob = await new Promise((resolve, reject) => {
      this.renderer.domElement.toBlob((result) => {
        if (result) resolve(result);
        else reject(new Error("The browser could not encode the current view."));
      }, "image/png");
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.download = `room-${this.currentView}.png`;
    link.href = url;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }

  dispose() {
    cancelAnimationFrame(this.frame);
    this.resizeObserver.disconnect();
    document.removeEventListener("visibilitychange", this.visibilityHandler);
    this.controls.dispose();
    this.model?.traverse((object) => {
      object.geometry?.dispose();
      const materials = object.material
        ? Array.isArray(object.material)
          ? object.material
          : [object.material]
        : [];
      materials.forEach((material) => {
        Object.values(material)
          .filter((value) => value?.isTexture)
          .forEach((texture) => texture.dispose());
        material.dispose();
      });
    });
    this.environmentTarget.dispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}
