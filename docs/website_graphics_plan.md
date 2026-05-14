# Website Graphics Plan: AI-Extracted Video Elements as Reusable Web Motion Assets

## Core thesis

The strongest commercial use of this pipeline is not just faster video editing. It is turning video elements into reusable website graphics that behave like web-native motion layers.

A video-derived object becomes:

```text
transparent raster or vector asset
+ JSON timing / transform / state data
+ web runtime
+ optional interaction rules
```

The object can then be used in a hero section, landing page, product story, interactive article, ad creative, onboarding screen, educational module, or ecommerce configurator.

## Why this is a better wedge than pure video-to-JSON

Website graphics already need:

- small assets
- fast previews
- responsive sizing
- interaction states
- scroll triggers
- hover/click behavior
- CMS/template reuse
- analytics hooks
- easy embedding

These needs fit a JSON scene graph better than traditional video timelines.

## The product should generate a Web Motion Asset Package

Recommended package:

```text
asset.json
spritesheet.webp or transparent.webm
mask.json or mask spritesheet
preview.html
embed.js
templates/
snippets/
fallback.mp4
```

Example manifest:

```json
{
  "version": "0.1",
  "type": "web_motion_asset",
  "objectId": "strawberry_01",
  "renderMode": "raster_alpha_layer",
  "asset": "strawberry_01_alpha.webm",
  "fallback": "strawberry_01_fallback.mp4",
  "states": {
    "idle": { "loop": true, "fps": 12 },
    "hover": { "scale": 1.08, "outline": true },
    "click": { "emit": "add_to_cart" }
  },
  "responsive": {
    "mobile": { "maxWidth": 240 },
    "desktop": { "maxWidth": 520 }
  }
}
```

## Rendering strategy

Use routing instead of one format:

```text
simple flat object      -> SVG / Lottie / dotLottie
interactive vector UI   -> Rive / Lottie
photoreal object        -> transparent WebM / WebP or AVIF sprite atlas + JSON
many small motion parts -> PixiJS/WebGL texture atlas
final video export      -> Remotion / FFmpeg
```

The resource win comes from caching the object once and changing only JSON transforms during website interaction.

## Website use cases

1. Product hero
   - Extract product, hand, ingredient, logo, or prop from video.
   - Reuse as interactive hero layer with hover and scroll motion.

2. Interactive ecommerce story
   - Break a product video into objects: product, ingredient, packaging, effect, label.
   - Let users explore each element without loading a full heavy video for every state.

3. Editorial/education graphics
   - Extract professor, diagram element, lab equipment, historical object, sports player.
   - Add clickable annotations and timed explanations.

4. Creator/brand asset library
   - Convert approved brand videos into reusable website motion stickers.
   - Designers drag these into landing pages and templates.

5. Programmatic ads and landing pages
   - One extraction creates reusable assets for many variants.
   - JSON changes copy, timing, position, CTA, color, and layout.

## Differentiation

Existing web animation tools are strong but usually start from designer-created assets. This product starts from video footage.

We should not compete by saying, "We are another Lottie/Rive/Webflow animation tool."

We should compete by saying:

```text
Turn footage into reusable web-native motion graphics.
```

## MVP feature set

- Upload short video
- Click/select object
- AI mask tracking
- Asset extraction
- Choose output target: hero, ecommerce, education, sticker, scroll animation, or product graphic
- Generate embed package
- Generate fallback MP4/WebM
- Generate responsive preview page
- Provide JSON manifest for developers

## Phase 14 productized website workflows

The runtime now includes template presets for `hero`, `ecommerce`, and `education`. Plain JavaScript embeds use `data-motionjson-template`, while React projects can create template-oriented components with `createMotionJSONTemplateEmbeds(React)`.

Generated output copies:

```text
preview/website_templates/
  hero.html
  ecommerce.html
  education.html
preview/website_snippets/
  webflow-style.html
  framer-style.html
  react-embed.jsx
```

Website ZIP packages include the same template and snippet surfaces at relative safe paths (`templates/` and `snippets/`) along with runtime modules, scene/object/resource JSON, rights metadata, and cached raster/alpha assets. The package manifest preserves rights summaries and records `aiUsage: "none"` because normal website preview and interaction are JSON transform updates over cached assets.

## Success metrics

- Time from video upload to embeddable graphic
- Preview FPS on mobile and desktop
- Package size versus equivalent video loop
- Lighthouse/Core Web Vitals impact
- Number of website templates generated per extracted asset
- Reuse count per object asset
- Manual cleanup minutes saved

## Commercial wedge

Start with:

```text
AI video-to-web-motion asset generator for brand/product teams.
```

Why this market is attractive:

- Brands already own their videos, reducing rights risk.
- Website teams need motion but often lack motion-design resources.
- Landing pages and product pages benefit from interactive motion.
- The same object can be reused across web, social, ads, and ecommerce.

## Implementation notes

Current prototype supports the core representation:

```text
scene_graph.json
cropped object layer frames
mask frames
Canvas preview
web_asset_manifest.json
spritesheet.webp
```

Next additions should be:

```text
sprite atlas exporter
transparent WebM exporter
embed.js runtime
hero-section template generator
Webflow/Framer-compatible embed docs
```

Those additions are now represented by runtime template presets and style-compatible snippets. They are not official Webflow or Framer integrations, and they do not add CDN, API, or network runtime dependencies.
