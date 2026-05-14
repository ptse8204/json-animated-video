import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { readdir } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";

import {
  autoMountMotionJSON,
  createMotionJSONReactComponent,
  createMotionJSONTemplateComponent,
  createMotionJSONTemplateEmbeds,
  createPixiRuntime,
  duplicateLayer,
  frameAt,
  frameIndexAt,
  getMotionJSONTemplate,
  initializeEditorState,
  listMotionJSONTemplates,
  mountMotionJSON,
  motionJSONTemplateOptions,
  normalizeMotionJSON,
  resolveAssetUrl,
  serializeEditState,
  setBackground,
  setCurrentFrame,
  setLayerClip,
  setLayerOpacity,
  setLayerZIndex,
  sortVisibleLayers,
  stateTransforms
} from "../src/index.js";

const repoRoot = new URL("../../..", import.meta.url).pathname;

function sampleManifest() {
  return {
    schema: "motionjson.web_asset_manifest.v0.1",
    type: "web_motion_asset",
    assetId: "object_0",
    label: "selected_object",
    renderMode: "raster_alpha_sequence",
    canvas: { width: 100, height: 80, fps: 10, frameCount: 2 },
    assets: {
      poster: "objects/object_0/cutouts/cutout_000001.png",
      spritesheet: {
        path: "objects/object_0/spritesheet.webp",
        width: 40,
        height: 20,
        columns: 2,
        rows: 1,
        cellWidth: 20,
        cellHeight: 20,
        frames: [
          { x: 0, y: 0, w: 20, h: 20 },
          { x: 20, y: 0, w: 20, h: 20 }
        ]
      },
      sequence: [
        { frame: 1, t: 0, asset: "objects/object_0/cutouts/cutout_000001.png", x: 4, y: 5, width: 20, height: 20, anchor: [10, 10], opacity: 1, scale: 1, rotation: 0, visible: true, sprite: { x: 0, y: 0, w: 20, h: 20 } },
        { frame: 2, t: 0.1, asset: "objects/object_0/cutouts/cutout_000002.png", x: 6, y: 7, width: 20, height: 20, anchor: [10, 10], opacity: 0.8, scale: 1, rotation: 0.1, visible: true, sprite: { x: 20, y: 0, w: 20, h: 20 } }
      ]
    },
    states: {
      idle: { loop: true, scale: 1, opacity: 1 },
      hover: { scale: 1.06, outline: true },
      click: { scale: 0.96, action: "reuse_or_open_detail" },
      scroll: { translate: [40, -24], rotation: 0.35 }
    }
  };
}

function sampleSceneGraph() {
  const manifest = sampleManifest();
  return {
    schema: "motionjson.scene_graph.v0.1",
    version: "0.1.0",
    source: { width: 100, height: 80, sampleFps: 10, sampledFrameCount: 2 },
    canvas: { width: 100, height: 80, fps: 10, frame_count: 2 },
    objects: [
      {
        id: "object_0",
        label: "selected_object",
        renderMode: "raster_alpha_sequence",
        interactions: manifest.states,
        assets: { spritesheet: manifest.assets.spritesheet },
        motion: manifest.assets.sequence.map((frame) => ({ ...frame, w: frame.width, h: frame.height }))
      }
    ],
    layers: [
      {
        object_id: "object_0",
        frames: manifest.assets.sequence.map(({ sprite, ...frame }) => ({
          ...frame,
          width: frame.width,
          height: frame.height
        }))
      }
    ]
  };
}

function sampleMultiSceneGraph() {
  const scene = sampleSceneGraph();
  const secondSequence = sampleManifest().assets.sequence.map((frame) => ({
    ...frame,
    asset: frame.asset.replaceAll("object_0", "shadow"),
    x: frame.x + 40,
    y: frame.y + 10,
    width: 12,
    height: 12,
    w: 12,
    h: 12
  }));
  scene.objects.push({
    id: "shadow",
    label: "Shadow",
    renderMode: "raster_alpha_sequence",
    interactions: scene.objects[0].interactions,
    assets: {
      spritesheet: {
        ...sampleManifest().assets.spritesheet,
        path: "objects/shadow/spritesheet.webp"
      }
    },
    motion: secondSequence
  });
  scene.layers[0].id = "object_0_layer";
  scene.layers[0].z_index = 10;
  scene.layers.push({
    id: "shadow_layer",
    object_id: "shadow",
    z_index: 20,
    frames: secondSequence
  });
  return scene;
}

test("normalizes web_asset_manifest and resolves relative URLs", () => {
  const scene = normalizeMotionJSON(sampleManifest(), { baseUrl: "https://example.test/out/demo/web_asset_manifest.json" });

  assert.equal(scene.sourceType, "web_asset_manifest");
  assert.equal(scene.assets.spritesheet.url, "https://example.test/out/demo/objects/object_0/spritesheet.webp");
  assert.equal(scene.assets.sequence[0].assetUrl, "https://example.test/out/demo/objects/object_0/cutouts/cutout_000001.png");
  assert.equal(scene.canvas.fps, 10);
});

test("normalizes scene_graph with the same runtime frame shape", () => {
  const scene = normalizeMotionJSON(sampleSceneGraph(), { baseUrl: "/out/demo/scene_graph.json" });

  assert.equal(scene.sourceType, "scene_graph");
  assert.equal(scene.assets.sequence.length, 2);
  assert.equal(scene.assets.sequence[1].width, 20);
  assert.deepEqual(scene.assets.sequence[1].sprite, { x: 20, y: 0, w: 20, h: 20 });
  assert.equal(resolveAssetUrl("objects/object_0/cutouts/cutout_000002.png", "/out/demo/scene_graph.json"), "/out/demo/objects/object_0/cutouts/cutout_000002.png");
});

test("normalizes multi-object scene_graph without collapsing layers", () => {
  const scene = normalizeMotionJSON(sampleMultiSceneGraph(), { baseUrl: "/out/demo/scene_graph.json" });
  const editor = initializeEditorState(scene);

  assert.equal(scene.objects.length, 2);
  assert.deepEqual(scene.layers.map((layer) => layer.objectId), ["object_0", "shadow"]);
  assert.equal(scene.objects[1].assets.sequence[0].assetUrl, "/out/demo/objects/shadow/cutouts/cutout_000001.png");
  assert.deepEqual(editor.layers.map((layer) => layer.sourceAssetId), ["object_0", "shadow"]);
  assert.deepEqual(sortVisibleLayers(editor).map((layer) => layer.id), ["object_0_layer", "shadow_layer"]);
});

test("frame math loops and clamps", () => {
  const scene = normalizeMotionJSON(sampleManifest());

  assert.equal(frameIndexAt(0.19, 10, 2), 1);
  assert.equal(frameIndexAt(0.29, 10, 2), 0);
  assert.equal(frameIndexAt(99, 10, 2, { loop: false }), 1);
  assert.equal(frameAt(scene, 0.11).frame, 2);
});

test("state transforms are JSON-only and compose hover/scroll state", () => {
  const scene = normalizeMotionJSON(sampleManifest());
  const transforms = stateTransforms(scene, "hover", { scrollProgress: 0.5 });

  assert.equal(transforms[1].scale, 1.06);
  assert.equal(transforms[1].outline, true);
  assert.deepEqual(transforms[2].translate, [20, -12]);
  assert.deepEqual(stateTransforms(scene, "idle", { scrollProgress: 0 })[1].translate, [0, 0]);
});

test("runtime exports include plain embed and React factory", () => {
  assert.equal(typeof mountMotionJSON, "function");
  assert.equal(typeof autoMountMotionJSON, "function");
  assert.equal(typeof createMotionJSONReactComponent, "function");
  assert.equal(typeof createMotionJSONTemplateComponent, "function");
  assert.equal(typeof createMotionJSONTemplateEmbeds, "function");
});

test("template presets expose website targets without changing cached assets", () => {
  const templates = listMotionJSONTemplates();
  const ids = templates.map((template) => template.id);
  const options = motionJSONTemplateOptions("ecommerce", { background: "#fefefe", renderer: "canvas" });

  assert.deepEqual(ids, ["hero", "ecommerce", "education"]);
  assert.equal(getMotionJSONTemplate("hero").background, "#fbfaf6");
  assert.equal(options.template, "ecommerce");
  assert.equal(options.background, "#fefefe");
  assert.equal(options.renderer, "canvas");
  assert.equal(options.scrollState, false);
});

test("editor state initializes from normalized MotionJSON and serializes JSON-only edits", () => {
  const scene = normalizeMotionJSON(sampleSceneGraph(), { baseUrl: "/out/demo/scene_graph.json" });
  let editor = initializeEditorState(scene);

  assert.equal(editor.layers.length, 1);
  assert.equal(editor.layers[0].sourceAssetId, "object_0");
  assert.equal(editor.layers[0].zIndex, 10);

  editor = setLayerOpacity(editor, editor.layers[0].id, 0.42);
  editor = setLayerOpacity(editor, editor.layers[0].id, Number.NaN);
  editor = setLayerZIndex(editor, editor.layers[0].id, 22);
  editor = setBackground(editor, { type: "solid", color: "#101319" });
  editor = setCurrentFrame(editor, 2);
  editor = setLayerClip(editor, editor.layers[0].id, { startFrame: 99, endFrame: 120 });
  const serialized = serializeEditState(editor);

  assert.equal(serialized.background.type, "solid");
  assert.equal(serialized.layers[0].opacity, 0);
  assert.equal(serialized.layers[0].zIndex, 22);
  assert.deepEqual(serialized.layers[0].clip, { startFrame: 2, endFrame: 2 });
  assert.deepEqual(serialized.layers[0].transform.translate, [0, 0]);
  assert.equal(Object.hasOwn(serialized.layers[0], "asset"), false);
  assert.equal(serialized.currentFrame, 2);
});

test("duplicate layer reuses the cached source asset and sorts by z-index", () => {
  const scene = normalizeMotionJSON(sampleManifest());
  let editor = initializeEditorState(scene);
  const original = editor.layers[0];
  editor = duplicateLayer(editor, original.id, { id: "object_0_reuse_a", offsetX: 12, offsetY: -8 });

  const duplicate = editor.layers.find((layer) => layer.id === "object_0_reuse_a");
  assert.equal(editor.layers.length, 2);
  assert.equal(duplicate.sourceAssetId, original.sourceAssetId);
  assert.equal(duplicate.reusedFromLayerId, original.id);
  assert.notEqual(duplicate.id, original.id);
  assert.deepEqual(duplicate.transform.translate, [12, -8]);
  assert.deepEqual(sortVisibleLayers(editor).map((layer) => layer.id), [original.id, duplicate.id]);
});

test("Pixi runtime accepts injected fake Pixi without installing pixi.js", async () => {
  class Rectangle {
    constructor(x, y, width, height) {
      Object.assign(this, { x, y, width, height });
    }
  }
  class Texture {
    constructor(base, rectangle) {
      Object.assign(this, { base, rectangle });
    }
    static from(value) {
      return { value };
    }
  }
  class Sprite {
    constructor(texture) {
      this.texture = texture;
      this.pivot = { set: (x, y) => { this.pivotValue = [x, y]; } };
      this.scale = { set: (value) => { this.scaleValue = value; } };
    }
  }
  class Application {
    constructor(options) {
      this.options = options;
      this.view = {};
      this.stage = { children: [], addChild: (child) => this.stage.children.push(child) };
      this.ticker = { add() {}, remove() {} };
    }
    destroy() {
      this.destroyed = true;
    }
  }
  const fakePixi = { Application, Sprite, Texture, BaseTexture: { from: (url) => ({ url }) }, Rectangle };
  const target = { appended: [], appendChild(node) { this.appended.push(node); } };

  const runtime = await createPixiRuntime(target, sampleManifest(), { PIXI: fakePixi });
  runtime.render(0);
  runtime.setState("hover");
  runtime.render(0);

  assert.equal(runtime.renderer, "pixi");
  assert.equal(runtime.app.stage.children.length, 1);
  assert.equal(runtime.sprite.x, 14);
  assert.equal(runtime.sprite.y, 15);
  assert.deepEqual(runtime.sprite.pivotValue, [10, 10]);
  assert.equal(runtime.sprite.scaleValue, 1.06);
  runtime.setScrollProgress(0.5);
  runtime.render(0);
  assert.equal(runtime.sprite.x, 34);
});

test("mountMotionJSON uses the Pixi view as its embed surface without a canvas shim", async () => {
  const globals = ["document", "HTMLCanvasElement", "fetch", "addEventListener", "removeEventListener", "innerHeight", "scrollY"];
  const previous = new Map(globals.map((name) => [name, Object.getOwnPropertyDescriptor(globalThis, name)]));
  const defineGlobal = (name, value) => {
    Object.defineProperty(globalThis, name, { value, configurable: true, writable: true });
  };
  const restoreGlobals = () => {
    for (const name of globals) {
      const descriptor = previous.get(name);
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else delete globalThis[name];
    }
  };

  class FakeElement {
    constructor(name) {
      this.name = name;
      this.children = [];
      this.listeners = new Map();
    }
    appendChild(node) {
      this.children.push(node);
      node.parent = this;
    }
    remove() {
      this.removed = true;
      if (!this.parent) return;
      this.parent.children = this.parent.children.filter((child) => child !== this);
    }
    addEventListener(type, handler) {
      const handlers = this.listeners.get(type) || [];
      handlers.push(handler);
      this.listeners.set(type, handlers);
    }
    removeEventListener(type, handler) {
      const handlers = this.listeners.get(type) || [];
      this.listeners.set(type, handlers.filter((candidate) => candidate !== handler));
    }
    listenerCount(type) {
      return (this.listeners.get(type) || []).length;
    }
    dispatch(type) {
      for (const handler of this.listeners.get(type) || []) handler({ type, currentTarget: this });
    }
  }
  class FakeCanvas extends FakeElement {}
  class Rectangle {
    constructor(x, y, width, height) {
      Object.assign(this, { x, y, width, height });
    }
  }
  class Texture {
    constructor(base, rectangle) {
      Object.assign(this, { base, rectangle });
    }
    static from(value) {
      return { value };
    }
  }
  class Sprite {
    constructor(texture) {
      this.texture = texture;
      this.pivot = { set: () => {} };
      this.scale = { set: () => {} };
    }
  }
  class Application {
    constructor(options) {
      this.options = options;
      this.view = new FakeElement("pixi-view");
      this.stage = { children: [], addChild: (child) => this.stage.children.push(child) };
      this.ticker = { add: (handler) => { this.tick = handler; }, remove: () => { this.tick = null; } };
      Application.last = this;
    }
    destroy() {
      this.destroyed = true;
    }
  }

  const target = new FakeElement("target");
  const fakeDocument = {
    canvasCount: 0,
    documentElement: { scrollHeight: 1000 },
    querySelector: () => target,
    createElement: (tag) => {
      if (tag === "canvas") {
        fakeDocument.canvasCount += 1;
        return new FakeCanvas("canvas");
      }
      return new FakeElement(tag);
    }
  };
  const fakePixi = { Application, Sprite, Texture, BaseTexture: { from: (url) => ({ url }) }, Rectangle };
  const windowListeners = new Map();

  try {
    defineGlobal("document", fakeDocument);
    defineGlobal("HTMLCanvasElement", FakeCanvas);
    defineGlobal("fetch", async () => ({ ok: true, json: async () => sampleManifest() }));
    defineGlobal("addEventListener", (type, handler) => windowListeners.set(type, handler));
    defineGlobal("removeEventListener", (type) => windowListeners.delete(type));
    defineGlobal("innerHeight", 100);
    defineGlobal("scrollY", 0);

    const handle = await mountMotionJSON(target, "/manifest.json", { renderer: "pixi", PIXI: fakePixi, scrollState: false });

    assert.equal(fakeDocument.canvasCount, 0);
    assert.equal(target.children.length, 1);
    assert.equal(target.children[0].name, "pixi-view");
    assert.equal(handle.canvas, target.children[0]);
    assert.equal(handle.surface, target.children[0]);
    assert.equal(target.children[0].listenerCount("mouseenter"), 1);

    target.children[0].dispatch("mouseenter");
    assert.equal(handle.runtime.state, "hover");

    handle.destroy();
    assert.equal(Application.last.destroyed, true);
    assert.equal(target.children[0].listenerCount("mouseenter"), 0);
  } finally {
    restoreGlobals();
  }
});

test("runtime package source does not mention AI backend names or secrets", async () => {
  const runtimeDir = join(repoRoot, "packages/motionjson-runtime/src");
  const names = await readdir(runtimeDir);
  const forbidden = /\b(openrouter|sam2|segmentation|provider|api[_-]?key|secret)\b/i;
  for (const name of names.filter((entry) => entry.endsWith(".js"))) {
    const text = readFileSync(join(runtimeDir, name), "utf8");
    assert.equal(forbidden.test(text), false, `${name} should stay decoupled from ingest-time systems`);
  }
});

test("examples use local runtime imports and expose required embed surfaces", () => {
  const canvas = readFileSync(join(repoRoot, "examples/canvas_player.html"), "utf8");
  const website = readFileSync(join(repoRoot, "examples/website_graphics_hero.html"), "utf8");
  const plain = readFileSync(join(repoRoot, "examples/plain_js_embed.html"), "utf8");
  const heroTemplate = readFileSync(join(repoRoot, "examples/website_templates/hero.html"), "utf8");
  const ecommerceTemplate = readFileSync(join(repoRoot, "examples/website_templates/ecommerce.html"), "utf8");
  const educationTemplate = readFileSync(join(repoRoot, "examples/website_templates/education.html"), "utf8");
  const webflowSnippet = readFileSync(join(repoRoot, "examples/website_snippets/webflow-style.html"), "utf8");
  const framerSnippet = readFileSync(join(repoRoot, "examples/website_snippets/framer-style.html"), "utf8");
  const reactSnippet = readFileSync(join(repoRoot, "examples/website_snippets/react-embed.jsx"), "utf8");
  const timeline = readFileSync(join(repoRoot, "examples/timeline_editor.html"), "utf8");
  const timelineJs = readFileSync(join(repoRoot, "examples/timeline_editor.js"), "utf8");

  assert.match(canvas, /motionjson-runtime\/src\/index\.js/);
  assert.match(website, /motionjson-runtime\/src\/index\.js/);
  assert.match(plain, /data-motionjson-src/);
  assert.match(plain, /autoMountMotionJSON/);
  assert.match(heroTemplate, /data-motionjson-template="hero"/);
  assert.match(ecommerceTemplate, /data-motionjson-template="ecommerce"/);
  assert.match(educationTemplate, /data-motionjson-template="education"/);
  assert.match(webflowSnippet, /data-motionjson-template="hero"/);
  assert.match(framerSnippet, /template: "ecommerce"/);
  assert.match(reactSnippet, /createMotionJSONTemplateEmbeds/);
  assert.match(timeline, /timeline_editor\.js/);
  assert.match(timelineJs, /motionjson-runtime\/src\/index\.js/);
  assert.match(timelineJs, /duplicateLayer/);
  assert.doesNotMatch(
    canvas + website + plain + heroTemplate + ecommerceTemplate + educationTemplate + webflowSnippet + framerSnippet + reactSnippet + timeline + timelineJs,
    /https?:\/\/(?:unpkg|cdn|jsdelivr|cdnjs)\./
  );
});
