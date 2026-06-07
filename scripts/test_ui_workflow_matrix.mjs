import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { buildRunConfig, providerWarnings, validateRunConfigShape } from "../src/motionjson/ui/static/config_builder.js";

const matrixPath = resolve("tests", "fixtures", "local_ui_workflow_matrix.v0.1.json");
const matrix = JSON.parse(readFileSync(matrixPath, "utf8"));

assert.equal(matrix.schema, "motionjson.local_ui_workflow_matrix.v0.1");
assert.ok(Array.isArray(matrix.cases));
assert.ok(matrix.cases.length >= 20);

function getPath(value, dottedPath) {
  let current = value;
  for (const part of dottedPath.split(".")) {
    if (part === "length") return current.length;
    if (Array.isArray(current)) current = current[Number(part)];
    else current = current?.[part];
  }
  return current;
}

function warningTextForCase(config, workflowCase) {
  const capabilities = workflowCase.capabilityReport
    ? {
        schema: "motionjson.provider_diagnostics.v0.1",
        summary: { providersReady: 0, providersTotal: workflowCase.capabilityReport.providers?.length || 0 },
        environment: {},
        ...workflowCase.capabilityReport,
      }
    : { providers: [] };
  return providerWarnings(config, capabilities).join("\n");
}

const builderCases = matrix.cases.filter((workflowCase) => workflowCase.builderInput);
assert.ok(builderCases.length >= 14);

for (const workflowCase of builderCases) {
  const config = buildRunConfig({
    video: { id: "asset_1" },
    outputDir: "out/ui-workflow-matrix",
    ...workflowCase.builderInput,
  });
  for (const [path, expected] of Object.entries(workflowCase.expectedRunConfig || {})) {
    assert.deepEqual(getPath(config, path), expected, `${workflowCase.id}: ${path}`);
  }

  const shapeErrors = validateRunConfigShape(config);
  if (workflowCase.expectedValidation?.valid === false && workflowCase.providerName === "external") {
    assert.ok(
      shapeErrors.some((message) => /external masks require a mask directory/i.test(message)),
      `${workflowCase.id}: external mask directory blocker should be visible`,
    );
  } else {
    assert.deepEqual(shapeErrors, [], `${workflowCase.id}: generated config should pass static shape checks`);
  }

  const warningText = warningTextForCase(config, workflowCase);
  const blockerText = [warningText, ...shapeErrors].filter(Boolean).join("\n");
  const expectedValidation = workflowCase.expectedValidation || {};
  if (expectedValidation.blockingWarningCodesAnyOf || workflowCase.expectedJob?.uiCanStart === false) {
    assert.notEqual(blockerText, "", `${workflowCase.id}: blocked UI path should have config-builder warning or shape text`);
  }
  if (expectedValidation.messageContainsAnyOf) {
    assert.ok(
      expectedValidation.messageContainsAnyOf.some((fragment) => blockerText.includes(fragment)),
      `${workflowCase.id}: blocker text did not include any expected fragment`,
    );
  }
  for (const fragment of expectedValidation.mustNotMentionAnyOf || []) {
    assert.equal(blockerText.includes(fragment), false, `${workflowCase.id}: warning text leaked ${fragment}`);
  }
}

const sam3ProofBlocked = builderCases.find((workflowCase) => workflowCase.id === "sam3_scene_sweep_available_mocked");
const sam3ProofBlockedConfig = buildRunConfig({ video: { id: "asset_1" }, outputDir: "out/ui-workflow-matrix", ...sam3ProofBlocked.builderInput });
assert.match(warningTextForCase(sam3ProofBlockedConfig, sam3ProofBlocked), /runtime proof/i);

const hostedBlocked = builderCases.find((workflowCase) => workflowCase.id === "hosted_configured_no_network");
const hostedConfig = buildRunConfig({ video: { id: "asset_1" }, outputDir: "out/ui-workflow-matrix", ...hostedBlocked.builderInput });
assert.match(warningTextForCase(hostedConfig, hostedBlocked), /hosted|network|confirmation/i);
