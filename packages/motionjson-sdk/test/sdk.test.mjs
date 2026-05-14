import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import test from "node:test";

import { MotionJSONClient, verifyWebhookSignature } from "../src/index.js";

function jsonResponse(body, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "OK",
    headers: { get: () => "application/json" },
    async json() {
      return body;
    }
  };
}

test("MotionJSONClient sends bearer requests through injected fetch", async () => {
  const calls = [];
  const client = new MotionJSONClient({
    baseUrl: "https://api.example.test/",
    apiKey: "mj_local_test",
    fetch: async (url, init) => {
      calls.push({ url, init });
      return jsonResponse({ id: "project_1" }, 201);
    }
  });

  const project = await client.createProject({ name: "Demo" });

  assert.equal(project.id, "project_1");
  assert.equal(calls[0].url, "https://api.example.test/v1/projects");
  assert.equal(calls[0].init.headers.authorization, "Bearer mj_local_test");
  assert.equal(JSON.parse(calls[0].init.body).name, "Demo");
});

test("SDK upload helper accepts bytes and render/package helpers use API routes", async () => {
  const paths = [];
  const client = new MotionJSONClient({
    apiKey: "mj_local_test",
    fetch: async (url, init) => {
      paths.push({ path: new URL(url).pathname, body: init.body ? JSON.parse(init.body) : null });
      return jsonResponse({ ok: true });
    }
  });

  await client.uploadAsset("p1", { filename: "clip.mp4", data: new Uint8Array([1, 2, 3]) });
  await client.createExtraction("p1", { assetId: "a1", maxFrames: 12 });
  await client.createAssetPackage("p1", { sourceJobId: "j1" });
  await client.createRender("p1", { sourceJobId: "j1", format: "remotion-plan" });

  assert.deepEqual(paths.map((call) => call.path), [
    "/v1/projects/p1/assets",
    "/v1/projects/p1/extractions",
    "/v1/projects/p1/asset-packages",
    "/v1/projects/p1/renders"
  ]);
  assert.equal(paths[0].body.dataBase64, "AQID");
  assert.equal(paths[1].body.assetId, "a1");
  assert.equal(paths[3].body.format, "remotion-plan");
});

test("verifyWebhookSignature validates MotionJSON HMAC signatures", async () => {
  const secret = "whsec_test";
  const payload = JSON.stringify({ type: "job.succeeded", data: { jobId: "j1" } });
  const timestamp = "2026-05-14T00:00:00+00:00";
  const digest = createHmac("sha256", secret).update(`${timestamp}.${payload}`).digest("hex");
  const signature = `t=${timestamp},v1=${digest}`;

  assert.equal(await verifyWebhookSignature({ secret, payload, signature }), true);
  assert.equal(await verifyWebhookSignature({ secret, payload: `${payload}x`, signature }), false);
});
