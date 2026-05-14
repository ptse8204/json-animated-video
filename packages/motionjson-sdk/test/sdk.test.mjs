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

test("SDK exposes beta, support, error, and admin helpers", async () => {
  const calls = [];
  const client = new MotionJSONClient({
    apiKey: "mj_local_test",
    fetch: async (url, init) => {
      calls.push({ path: new URL(url).pathname, search: new URL(url).search, method: init.method, body: init.body ? JSON.parse(init.body) : null });
      return jsonResponse({ ok: true });
    }
  });

  await client.betaStatus();
  await client.acceptBetaInvite("mjb_test");
  await client.createFeedback({ projectId: "p1", subject: "UX", message: "Needs help" });
  await client.createErrorReport({ projectId: "p1", jobId: "j1", message: "Boom", stackTrace: "Trace" });
  await client.adminDashboard();
  await client.createBetaInvite({ email: "beta@example.com", role: "member", ttlSeconds: 60 });
  await client.listBetaInvites({ includeRevoked: true });
  await client.revokeBetaInvite("invite1");
  await client.listBetaMembers();
  await client.listBillingPlans();
  await client.billingStatus();
  await client.listFeedback();
  await client.listErrorReports({ includeResolved: true });

  assert.deepEqual(calls.map((call) => call.path), [
    "/v1/beta/status",
    "/v1/beta/accept",
    "/v1/feedback",
    "/v1/error-reports",
    "/v1/admin/dashboard",
    "/v1/admin/beta/invites",
    "/v1/admin/beta/invites",
    "/v1/admin/beta/invites/invite1",
    "/v1/admin/beta/members",
    "/v1/billing/plans",
    "/v1/billing/status",
    "/v1/admin/feedback",
    "/v1/admin/error-reports"
  ]);
  assert.equal(calls[1].body.inviteToken, "mjb_test");
  assert.equal(calls[6].search, "?includeRevoked=true");
  assert.equal(calls[12].search, "?includeResolved=true");
});

test("SDK exposes asset library, collection, and creator pack helpers", async () => {
  const calls = [];
  const client = new MotionJSONClient({
    apiKey: "mj_local_test",
    fetch: async (url, init) => {
      calls.push({ path: new URL(url).pathname, search: new URL(url).search, method: init.method, body: init.body ? JSON.parse(init.body) : null });
      return jsonResponse({ ok: true });
    }
  });

  await client.saveLibraryAsset("p1", {
    assetId: "a1",
    type: "motion_sticker",
    title: "Sticker",
    tags: ["hero"]
  });
  await client.listLibraryAssets({ q: "stick", tag: "hero", licenseScope: "commercial", creatorApproved: true });
  await client.getLibraryAsset("la1");
  await client.createBrandCollection({ projectId: "p1", title: "Brand" });
  await client.listBrandCollections();
  await client.addCollectionAsset("c1", { libraryAssetId: "la1" });
  await client.listCollectionAssets("c1");
  await client.createCreatorPack({ collectionId: "c1", title: "Pack", libraryAssetIds: ["la1"] });
  await client.listCreatorPacks();

  assert.deepEqual(calls.map((call) => call.path), [
    "/v1/projects/p1/library-assets",
    "/v1/library/assets",
    "/v1/library/assets/la1",
    "/v1/library/collections",
    "/v1/library/collections",
    "/v1/library/collections/c1/assets",
    "/v1/library/collections/c1/assets",
    "/v1/library/packs",
    "/v1/library/packs"
  ]);
  assert.equal(calls[0].body.type, "motion_sticker");
  assert.equal(calls[1].search, "?q=stick&tag=hero&licenseScope=commercial&creatorApproved=true");
  assert.equal(calls[5].body.libraryAssetId, "la1");
  assert.deepEqual(calls[7].body.libraryAssetIds, ["la1"]);
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
