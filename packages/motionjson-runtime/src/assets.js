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
  const spritesheet = scene.assets.spritesheet?.url
    ? await loadImage(scene.assets.spritesheet.url, options)
    : null;
  if (spritesheet) {
    return { spritesheet, frames: [] };
  }
  const frames = await Promise.all(
    scene.assets.sequence.map((frame) => (frame.assetUrl ? loadImage(frame.assetUrl, options).catch(() => null) : null))
  );
  return { spritesheet: null, frames };
}
