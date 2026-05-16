# Local UI

Phase 7 adds a dependency-light local UI shell for inspecting MotionJSON
provider readiness, creating local projects, registering source videos, and
viewing local job/progress state. It runs against the existing SQLite backend
and filesystem storage. It does not require GPU, SAM2, hosted services, or
network access for the mock/no-model smoke path.

## Launch

Use the packaged console command for normal local UI sessions:

```bash
motionjson ui
```

Use the module entry point for deterministic CPU-only smoke checks:

```bash
python3 -m motionjson.cli ui --no-open --mock
```

By default the UI uses:

- database: `.motionjson/backend.sqlite`
- storage root: `.motionjson/storage`
- host: `127.0.0.1`
- port: `8766`

Override those paths for tests or demos:

```bash
python3 -m motionjson.cli ui \
  --db /tmp/motionjson-local-ui/backend.sqlite \
  --storage-root /tmp/motionjson-local-ui/storage \
  --host 127.0.0.1 \
  --port 8766 \
  --no-open \
  --mock
```

The `--mock` flag keeps default run suggestions in no-model mode. It does not
pretend SAM2, CUDA, detectors, FFmpeg, or model weights are available; those
statuses still come from provider diagnostics.

## Routes

The UI serves static files under `/ui/` and local JSON routes under `/api/`:

- `GET /api/health`
- `GET /api/capabilities`
- `GET /api/run-config/defaults`
- `GET /api/exports/formats`
- `GET /api/projects`
- `POST /api/projects`
- `GET /api/videos?projectId=PROJECT_ID`
- `POST /api/videos`
- `GET /api/jobs?projectId=PROJECT_ID`
- `POST /api/jobs`
- `GET /api/progress?projectId=PROJECT_ID`
- `GET /api/jobs/JOB_ID`
- `GET /api/jobs/JOB_ID/events`
- `GET /api/jobs/JOB_ID/artifacts`
- `GET /api/artifacts?jobId=JOB_ID`

The local UI creates a reserved local user in the selected SQLite database and
uses that user for project, video, and job queries. API responses omit internal
storage keys, local `file://` storage URIs, and token material.

## Project And Video Flow

1. Open the UI command above.
2. Confirm health and capability diagnostics are visible.
3. Create a project from the project panel.
4. Add a source video by entering an existing local file path.
5. Select the video from the video picker or video list.
6. Review jobs and progress panels. Phase 7 exposes a mock-safe job enqueue
   route for API smoke checks; the full goal-first extraction wizard is
   deferred to Phase 8.

Video registration copies the selected local file into the configured local
storage root and records rights source metadata for the upload. Missing paths
return a visible API error.

## Build And Smoke

The frontend shell is static HTML/CSS/JavaScript packaged with the Python
distribution. It intentionally avoids remote resources and frontend runtime
dependencies in this phase.

```bash
npm run build
```

The root build script runs `node scripts/build_ui_shell.mjs`. The generated
shell is served by `motionjson ui` and packaged as Python package data:

```toml
[tool.setuptools.package-data]
motionjson = ["schemas/*.json", "ui/static/*", "ui/static/**/*"]
```

The build command checks that the static files are present, local routes are
referenced, and no remote resources are loaded by the shell. The recursive
package-data pattern keeps nested static assets available in installed Python
packages without requiring Node at runtime.

Useful command-surface checks:

```bash
motionjson ui --help
python3 -m motionjson.cli ui --help
```
