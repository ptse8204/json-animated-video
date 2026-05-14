# MotionJSON Web Runtime

MotionJSON includes a small browser runtime for web packages and a Phase 7 timeline editor MVP. It plays cached raster/alpha object layers from `web_asset_manifest.json` or `scene_graph.json` using JSON timing and transform data.

The runtime does not call ingest-time systems during preview or interaction. Normal hover, click, scroll, drag, scale, rotate, and opacity changes are JSON transform updates over cached spritesheets or PNG alpha sequences.

## Package

```text
packages/motionjson-runtime/
  src/
    manifest.js   Normalize web manifests and scene graphs.
    assets.js     Load spritesheet-first assets, with PNG sequence fallback.
    timeline.js   Frame index and state transform math.
    canvas.js     Canvas2D renderer.
    editor.js     Pure timeline editor state helpers.
    pixi.js       Optional Pixi/WebGL renderer through injected PIXI.
    embed.js      Plain JavaScript mount helper and data-attribute auto-mount.
    react.js      React component factory with injected React.
    templates.js  Website template presets for hero, ecommerce, and education embeds.
```

Run JavaScript validation:

```bash
npm test
npm run lint
```

## Canvas2D

```js
import { createCanvasRuntime, normalizeMotionJSON } from "../packages/motionjson-runtime/src/index.js";

const response = await fetch("/out/demo/web_asset_manifest.json");
const scene = normalizeMotionJSON(await response.json(), {
  baseUrl: "/out/demo/web_asset_manifest.json"
});
const runtime = createCanvasRuntime(document.querySelector("canvas"), scene, {
  background: "#fbfaf6",
  showBounds: true
});
await runtime.load();
runtime.start();
```

## Pixi/WebGL

Pixi is optional. The runtime never imports it directly; pass an injected `PIXI` object. If `PIXI` is unavailable, the helper falls back to Canvas2D.

```js
import { createPixiRuntime } from "../packages/motionjson-runtime/src/index.js";

const runtime = await createPixiRuntime(document.querySelector("#stage"), scene, {
  PIXI: window.PIXI
});
await runtime.load?.();
runtime.start?.();
```

## Plain JS Embed

```js
import { mountMotionJSON } from "../packages/motionjson-runtime/src/index.js";

const handle = await mountMotionJSON("#motion", "/out/demo/web_asset_manifest.json", {
  background: "#fbfaf6",
  showBounds: true,
  onClick: ({ action }) => console.log(action)
});

handle.destroy();
```

Or use data attributes:

```html
<div data-motionjson-src="/out/demo/web_asset_manifest.json" data-motionjson-bounds="true"></div>
<script type="module">
  import { autoMountMotionJSON } from "../packages/motionjson-runtime/src/index.js";
  await autoMountMotionJSON();
</script>
```

Template presets can be selected with `data-motionjson-template`. They set runtime defaults such as canvas class, background, click timing, and scroll behavior; they do not change cached assets or call ingest-time systems.

```html
<div
  data-motionjson-src="/out/demo/web_asset_manifest.json"
  data-motionjson-template="hero"
></div>
<script type="module">
  import { autoMountMotionJSON } from "../packages/motionjson-runtime/src/index.js";
  await autoMountMotionJSON();
</script>
```

## React

React is peer-style and injected by the application.

```js
import { createMotionJSONReactComponent } from "@motionjson/runtime/react";

export const MotionJSONPlayer = createMotionJSONReactComponent(React);
```

Template-oriented React helpers are also available:

```js
import { createMotionJSONTemplateEmbeds } from "@motionjson/runtime/react";

const { HeroMotionJSON, EcommerceMotionJSON, EducationMotionJSON } = createMotionJSONTemplateEmbeds(React);
```

## Examples

Serve the repo and open:

- `http://localhost:8080/examples/canvas_player.html?scene=/out/demo/web_asset_manifest.json`
- `http://localhost:8080/examples/canvas_player.html?scene=/out/demo/scene_graph.json`
- `http://localhost:8080/examples/pixi_player.html?scene=/out/demo/web_asset_manifest.json`
- `http://localhost:8080/examples/plain_js_embed.html?manifest=/out/demo/web_asset_manifest.json`
- `http://localhost:8080/examples/timeline_editor.html?scene=/out/demo/scene_graph.json`
- `http://localhost:8080/examples/website_graphics_hero.html?manifest=/out/demo/web_asset_manifest.json`
- `http://localhost:8080/examples/website_templates/hero.html?manifest=/out/demo/web_asset_manifest.json`
- `http://localhost:8080/examples/website_templates/ecommerce.html?manifest=/out/demo/web_asset_manifest.json`
- `http://localhost:8080/examples/website_templates/education.html?manifest=/out/demo/web_asset_manifest.json`

Generated preview folders copy the runtime source into `preview/runtime/`, website template pages into `preview/website_templates/`, and snippet examples into `preview/website_snippets/`, so `out/.../preview/*.html` works without a build step or CDN dependency.

## Website ZIP Export

Phase 8 can package a self-contained website ZIP from generated output:

```bash
python3 -m motionjson.cli export out/demo --format website-zip --out out/demo/exports/website_package.zip
```

The ZIP includes relative runtime paths, previews, template pages, style-compatible embed snippets, `web_asset_manifest.json`, scene/object/resource JSON, rights metadata, cached cutouts and spritesheets needed by the runtime, and ready production assets. It excludes `.env*`, caches, `node_modules`, masks, and debug frames by default. The package manifest records `aiUsage: "none"` because packaging uses cached raster/alpha assets and JSON transforms only.

## Timeline Editor MVP

`examples/timeline_editor.html` uses `editor.js` helpers to keep authoring state separate from cached assets. The helper API initializes editable state from normalized MotionJSON, selects layers, updates translate/scale/rotation, opacity, z-index, visibility, clip frame range, duplicate/reuse layer instances, background settings, visible layer sorting, and serialized edit JSON.

```js
import {
  duplicateLayer,
  initializeEditorState,
  serializeEditState,
  updateLayerTransform
} from "../packages/motionjson-runtime/src/index.js";

let editor = initializeEditorState(scene);
editor = updateLayerTransform(editor, editor.selectedLayerId, {
  translate: [32, 12],
  scale: 1.15,
  rotation: 0.08
});
editor = duplicateLayer(editor, editor.selectedLayerId);
const editJson = serializeEditState(editor);
```

Duplicate/reuse records a second layer instance with the same `sourceAssetId`. It does not copy image data. Background replacement is preview compositing behind alpha layers only; it is not clean-plate generation or hidden-pixel reconstruction.

Use serialized editor state with final MP4 export when Phase 7 layer transforms should be reflected in a rendered video:

```bash
python3 -m motionjson.cli export out/demo --format mp4 --out out/demo/exports/final.mp4 --editor-state out/demo/editor_state.json
```
