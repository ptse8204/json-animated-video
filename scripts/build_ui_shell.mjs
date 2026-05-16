import { readFile } from "node:fs/promises";
import { join } from "node:path";

const root = process.cwd();
const staticDir = join(root, "src", "motionjson", "ui", "static");
const files = ["index.html", "app.css", "app.js"];
const contents = new Map();

for (const file of files) {
  const content = await readFile(join(staticDir, file), "utf8");
  if (!content.trim()) {
    throw new Error(`${file} is empty`);
  }
  contents.set(file, content);
}

const index = contents.get("index.html");
const script = contents.get("app.js");
const style = contents.get("app.css");

for (const reference of ["/ui/app.css", "/ui/app.js"]) {
  if (!index.includes(reference)) {
    throw new Error(`index.html does not reference ${reference}`);
  }
}

for (const id of [
  "healthStatus",
  "mockStatus",
  "apiStatus",
  "capabilitySummary",
  "capabilityNotice",
  "capabilityList",
  "projectForm",
  "projectSelect",
  "videoForm",
  "videoSelect",
  "videoList",
  "jobSummary",
  "jobList",
  "routeList",
]) {
  if (!index.includes(`id="${id}"`)) {
    throw new Error(`index.html is missing #${id}`);
  }
}

for (const route of ["/api/health", "/api/capabilities", "/api/projects", "/api/run-config/defaults", "/api/videos", "/api/jobs"]) {
  if (!script.includes(route)) {
    throw new Error(`app.js does not call ${route}`);
  }
}

for (const affordance of ["job-progress", "mockStatus", "provider(s) unavailable", "rasterOnlyReason", "selectedVideoId", "video-choice"]) {
  if (!script.includes(affordance) && !style.includes(affordance) && !index.includes(affordance)) {
    throw new Error(`UI shell is missing ${affordance}`);
  }
}

const remotePattern = /https?:\/\//;
for (const [file, content] of contents) {
  if (remotePattern.test(content)) {
    throw new Error(`local UI shell must not load remote resources: ${file}`);
  }
}

console.log(
  JSON.stringify(
    {
      status: "ok",
      checkedFiles: files,
      mode: "dependency-free-static-ui",
    },
    null,
    2,
  ),
);
