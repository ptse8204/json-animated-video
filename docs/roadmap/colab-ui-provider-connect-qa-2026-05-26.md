# Colab UI provider-connect QA - 2026-05-26

## Summary

The Colab notebook can launch the MotionJSON Local UI on a Colab L4 GPU
runtime and the normal UI-first path is mostly reachable:

- selected a Colab **L4 GPU** runtime;
- accepted the GitHub notebook execution warning;
- ran the normal launch path:
  - cell 1 cloned/updated `ptse8204/json-animated-video` and completed
    `python3 -m pip install -e .[ui]` with return code 0;
  - cell 2 launched `motionjson ui --no-open --host 127.0.0.1 --port 8766`;
  - cell 4 created `examples/demo_red_ball.mp4`;
- opened the proxied UI at the Colab `8766-gpu-l4...prod.colab.dev/ui/`
  address;
- confirmed the Local UI reported **Local API ready**;
- selected **Find everything in scene**;
- registered `examples/demo_red_ball.mp4`;
- confirmed browser preview preparation for `demo_red_ball.mp4`
  (`h264`, `640x360`, `4s`);
- opened **Model setup** and saw the recommended **SAM3 Scene Sweep** path,
  plus fallback options for **SAM2 HF automatic masks** and a custom SAM3
  endpoint.

The live test did not reach a real model extraction. The SAM3 local path still
requires Hugging Face/Meta access before `facebook/sam3` can be checked or
cached, and no approved token was available in this session. I also did not
download/cache SAM2 or SAM3 weights.

## Colab MCP result

Requested Colab MCP control did not work in this session.

- `open_colab_browser_connection` failed with `Transport closed`.
- `get_colab_connection_info` also failed with `Transport closed`.
- A local `colab-mcp` bridge process was running on port `18585`, and the
  notebook was reloaded with the generated `mcpProxyToken` and `mcpProxyPort`
  URL fragment.
- `lsof` still showed no established browser connection to the local bridge.

Chrome extension automation was used as the fallback because it could claim the
authenticated Colab tab and open the proxied Local UI.

## Findings

### 1. Model setup state is internally inconsistent

For the **Find everything in scene** workflow, the SAM3 Scene Sweep card shows:

- `local model`;
- `ready`;
- `facebook/sam3`;
- `Needs Hugging Face access`;
- `Ready for this workflow`.

That is contradictory for a nontechnical user. The runtime/package may be
available, but the model is not actually runnable until access is checked and
the model is cached or resolved.

### 2. Switching to SAM2 fallback leaves the sticky primary action stale

After opening **Change model** and selecting **SAM2 HF automatic masks**, the
selected provider area changes to SAM2 and shows:

- `facebook/sam2.1-hiera-large`;
- `Confirm model cache`;
- `Ready for this workflow`.

However, the sticky footer primary button still says **Check Hugging Face
access**, which belongs to the SAM3 path. That makes the fallback path feel
blocked by the wrong provider and prevents a clear "cache model" or "continue"
next step.

### 3. Native browser confirmations make setup actions fragile

The setup flow uses browser `window.confirm(...)` for network, install, cache,
and smoke-test acknowledgements. In Colab/iframe/proxy usage this is fragile:
browser automation timed out around the Hugging Face access action, and the UI
did not provide a durable in-app job state that could be inspected afterward.

The confirmation requirements are correct, but they should be rendered as
in-app confirmation panels/buttons with explicit network, disk, cost, privacy,
and cancel states.

### 4. Colab runtime cleanup is incomplete in the notebook

The notebook has a cell to terminate the MotionJSON UI subprocess, but it does
not provide an explicit final cleanup cell for deleting the Colab runtime. For
paid GPU sessions, the notebook should include a clear final cell using Colab's
runtime shutdown API, for example:

```python
from google.colab import runtime
runtime.unassign()
```

The UI server stop cell is useful, but it is not the same as disconnecting and
deleting the Colab runtime.

### 5. Real local model run prerequisites need a clearer preflight ladder

The notebook and UI correctly explain that SAM3 requires gated access, but the
live flow should separate these facts more explicitly:

- Colab GPU is connected.
- Python/CUDA is available.
- MotionJSON UI is installed.
- Optional SAM3/SAM2 runtime package is installed.
- Hugging Face access is configured and approved.
- Model weights are cached or resolved locally.
- Smoke test passed.
- Extraction can run.

Right now some of those states collapse into `ready` or `Needs Hugging Face
access`, which is too coarse for the first-run model setup screen.

## Improvement Plan

1. Fix the model setup state machine.
   - Split provider state into `runtime_available`, `access_configured`,
     `model_cached`, `smoke_tested`, and `runnable`.
   - Reserve `Ready for this workflow` for `runnable=true`.
   - Add UI tests for SAM3 Scene Sweep without token and SAM2 fallback without
     cached weights.

2. Fix sticky footer action derivation.
   - Recompute the footer primary action from the currently selected
     model-setup provider, not from the previous provider or workflow contract.
   - Add a regression test: select SAM3, open alternatives, choose SAM2 HF
     fallback, assert the primary action is `Cache model` or `Continue to
     prepare`, never `Check Hugging Face access`.

3. Replace native setup confirmations with in-app confirmations.
   - Use an in-page confirmation card for network/disk/cost/privacy actions.
   - Show the exact provider, model id, action, expected download/network
     behavior, and cancel option.
   - Keep hosted calls opt-in and no-network diagnostics unchanged.

4. Add a Colab shutdown cell.
   - Keep the existing MotionJSON UI stop cell.
   - Add a separate final cell named "Disconnect and delete Colab runtime" that
     calls `google.colab.runtime.unassign()`.
   - Make the notebook instructions tell users to run that cell when finished
     with GPU work.

5. Add a repo-side Colab notebook smoke helper.
   - Validate notebook cell ordering and normal-path commands without needing a
     live browser session.
   - Exercise `/api/health`, `/api/capabilities`, demo video registration, and
     model setup action payloads in a local/mock mode.

6. Improve Colab MCP diagnostics.
   - When an MCP fragment is present but no bridge connection is established,
     surface a visible diagnostic with port, token-fragment presence, and a
     fallback instruction.
   - Record the failure as "MCP bridge unavailable" instead of silently falling
     back to manual/browser control.

## Validation Run

- Colab MCP attempted: failed with `Transport closed`.
- Chrome extension fallback: succeeded.
- Colab runtime type: L4 GPU selected and connected.
- Notebook cell 1 install: succeeded.
- Notebook cell 2 UI launch: succeeded.
- Notebook cell 4 demo video: succeeded.
- Local UI `/ui/`: loaded.
- Local API status in UI: ready.
- Demo video registration: succeeded.
- Browser-safe preview: succeeded.
- Model setup inspection: completed.

## Known Limitations

- No SAM3 or SAM2 model weights were downloaded.
- No real SAM extraction run was completed.
- No Hugging Face token or Meta-approved SAM3 access was available.
- Browser automation became unstable around model setup confirmation actions.
- Runtime deletion could not be verified through automation before this report
  was written; manual Colab shutdown may still be required if the runtime is
  still connected.
