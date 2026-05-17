export function defaultImageFactory() {
  if (typeof Image === "undefined") {
    throw new Error("Image constructor is not available; pass imageFactory in non-browser tests");
  }
  return new Image();
}

export function loadImage(url, options = {}) {
  if (!url) return Promise.resolve(null);
  const imageFactory = options.imageFactory || defaultImageFactory;
  return new Promise((resolve, reject) => {
    const image = imageFactory();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error(`Could not load image: ${url}`));
    if (options.crossOrigin) image.crossOrigin = options.crossOrigin;
    image.src = url;
  });
}

export async function loadRuntimeAssets(scene, options = {}) {
  const byObject = {};
  const objects = Array.isArray(scene.objects) && scene.objects.length
    ? scene.objects
    : [{ id: scene.assetId, assets: scene.assets }];
  for (const object of objects) {
    const spritesheet = object.assets?.spritesheet?.url
      ? await loadImage(object.assets.spritesheet.url, options)
      : null;
    if (spritesheet) {
      byObject[object.id] = { spritesheet, frames: [] };
      continue;
    }
    const sequence = object.assets?.sequence || [];
    const frames = await Promise.all(
      sequence.map((frame) => (frame.assetUrl ? loadImage(frame.assetUrl, options).catch(() => null) : null))
    );
    byObject[object.id] = { spritesheet: null, frames };
  }
  const defaultAssets = byObject[scene.assetId] || Object.values(byObject)[0] || { spritesheet: null, frames: [] };
  return { ...defaultAssets, byObject };
}
