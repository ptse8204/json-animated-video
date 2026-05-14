import { readFileSync } from "node:fs";
import { readdir } from "node:fs/promises";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const root = new URL("..", import.meta.url).pathname;
const runtimeDir = join(root, "packages/motionjson-runtime/src");
const sdkDir = join(root, "packages/motionjson-sdk/src");
const examplesDir = join(root, "examples");
const forbiddenRuntime = /\b(openrouter|sam2|segmentation|provider|api[_-]?key|secret)\b/i;
const forbiddenExampleCdn = /https?:\/\/(?:unpkg|cdn|jsdelivr|cdnjs)\./i;

async function files(dir, suffixes) {
  const output = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) output.push(...await files(path, suffixes));
    if (entry.isFile() && suffixes.some((suffix) => entry.name.endsWith(suffix))) output.push(path);
  }
  return output;
}

const jsFiles = await files(runtimeDir, [".js"]);
const sdkFiles = await files(sdkDir, [".js"]);
const testFiles = await files(join(root, "packages/motionjson-runtime/test"), [".mjs"]);
const sdkTestFiles = await files(join(root, "packages/motionjson-sdk/test"), [".mjs"]);

for (const file of [...jsFiles, ...sdkFiles, ...testFiles, ...sdkTestFiles, join(root, "scripts/lint_runtime.mjs")]) {
  const result = spawnSync(process.execPath, ["--check", file], { encoding: "utf8" });
  if (result.status !== 0) {
    process.stderr.write(result.stderr || result.stdout);
    process.exit(result.status || 1);
  }
}

for (const file of jsFiles) {
  const text = readFileSync(file, "utf8");
  if (forbiddenRuntime.test(text)) {
    throw new Error(`Runtime must not couple to AI/provider code: ${file}`);
  }
}

for (const file of await files(examplesDir, [".html"])) {
  const text = readFileSync(file, "utf8");
  if (forbiddenExampleCdn.test(text)) {
    throw new Error(`Examples must not depend on external CDNs: ${file}`);
  }
}

console.log(`Checked ${jsFiles.length} runtime modules, ${sdkFiles.length} SDK modules, ${testFiles.length + sdkTestFiles.length} tests, and examples for offline runtime constraints.`);
