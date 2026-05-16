const API_ROUTES = [
  "/api/health",
  "/api/capabilities",
  "/api/projects",
  "/api/run-config/defaults",
  "/api/videos",
  "/api/jobs",
];

const state = {
  health: null,
  capabilities: null,
  runDefaults: null,
  projects: [],
  selectedProjectId: "",
  videos: [],
  selectedVideoId: "",
  jobs: [],
  errors: {},
};

const $ = (selector) => document.querySelector(selector);

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      headers: { "content-type": "application/json", ...(options.headers || {}) },
      ...options,
    });
  } catch (error) {
    throw new Error(`Local API unavailable: ${error.message}`);
  }

  const body = await response.text();
  let payload = {};
  if (body) {
    try {
      payload = JSON.parse(body);
    } catch {
      payload = { error: body.slice(0, 180) };
    }
  }

  if (!response.ok) {
    throw new Error(payload.error || payload.detail || `Request failed: ${response.status}`);
  }
  return payload;
}

function escapeHtml(value) {
  return String(value).replace(
    /[&<>"']/g,
    (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]),
  );
}

function escapeAttribute(value) {
  return escapeHtml(value);
}

function setFacts(element, facts) {
  element.innerHTML = Object.entries(facts)
    .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value ?? "not reported")}</dd>`)
    .join("");
}

function statusClass(status, available) {
  const normalized = String(status || "").toLowerCase();
  if (/missing|unavailable|not available|failed|error|invalid|not found|unconfigured/.test(normalized)) return "is-bad";
  if (available === true || /ready|healthy|\bavailable\b|ok|enabled|complete|succeeded/.test(normalized)) return "is-ready";
  if (/mock|no-model|optional|disabled|local/.test(normalized)) return "is-neutral";
  return "is-warn";
}

function statusChip(label, status, available) {
  return `<span class="status-chip ${statusClass(status || label, available)}">${escapeHtml(label)}</span>`;
}

function detailChip(label) {
  return `<span class="status-chip is-muted">${escapeHtml(label)}</span>`;
}

function asArray(value) {
  if (value == null) return [];
  return Array.isArray(value) ? value : [value];
}

function isActiveJob(job) {
  const status = String(job.status || "").toLowerCase();
  return /queued|pending|running|working|started/.test(status);
}

function normalizeProgress(job) {
  const direct = job.progress ?? job.percent ?? job.percentage;
  if (typeof direct === "number" && Number.isFinite(direct)) {
    return Math.max(0, Math.min(100, direct <= 1 ? Math.round(direct * 100) : Math.round(direct)));
  }

  const completedFrames = job.completedFrames ?? job.completed_frames;
  const totalFrames = job.totalFrames ?? job.total_frames;
  if (typeof completedFrames === "number" && typeof totalFrames === "number" && totalFrames > 0) {
    return Math.max(0, Math.min(100, Math.round((completedFrames / totalFrames) * 100)));
  }

  const status = String(job.status || "").toLowerCase();
  if (/complete|succeeded/.test(status)) return 100;
  if (/running|working|started/.test(status)) return 25;
  return 0;
}

function renderApiStatus(kind, label) {
  const chip = $("#apiStatus");
  chip.className = `status-chip ${kind}`;
  chip.textContent = label;
}

function renderHealth() {
  const routes = asArray(state.health?.routes);
  if (!state.health) {
    setFacts($("#healthStatus"), {
      status: state.errors.health || "not connected",
      version: "not reported",
      local: "expected",
      mock: "not reported",
    });
  } else {
    setFacts($("#healthStatus"), {
      status: state.health.status,
      version: state.health.version,
      local: state.health.localFirst ? "yes" : "not reported",
      mock: state.health.mockMode ? "on" : state.health.mockModeAvailable ? "available" : "unavailable",
    });
  }

  $("#routeList").innerHTML = (routes.length ? routes : API_ROUTES)
    .map((route) => {
      const routeState = routes.length ? "reported by local API" : "expected local API route";
      return `<div class="route-row"><strong>${escapeHtml(route)}</strong><span class="row-meta">${routeState}</span></div>`;
    })
    .join("");
}

function renderMockStatus() {
  const providers = asArray(state.capabilities?.providers);
  const mockProviders = providers.filter((provider) => {
    const haystack = [provider.name, provider.displayName, provider.kind, provider.status, ...asArray(provider.reasons)]
      .join(" ")
      .toLowerCase();
    return /mock|no-model|cpu/.test(haystack);
  });
  const unavailableModelProviders = providers.filter((provider) => {
    const haystack = [provider.name, provider.displayName, provider.kind, provider.status, ...asArray(provider.reasons)]
      .join(" ")
      .toLowerCase();
    return !provider.available && /sam|cuda|torch|detector|model|mask|segment/.test(haystack);
  });
  const defaults = state.runDefaults?.defaults || {};

  setFacts($("#mockStatus"), {
    mode: state.health?.mockMode ? "on" : state.health?.mockModeAvailable ? "available" : "not reported",
    "mask default": defaults.maskProvider || "not reported",
    "mock providers": mockProviders.length ? `${mockProviders.length} reported` : "not reported",
    "ML unavailable": unavailableModelProviders.length ? `${unavailableModelProviders.length} provider(s)` : "none reported",
  });
}

function providerChip(provider) {
  const status = provider.status || (provider.available ? "available" : "not available");
  return statusChip(status, status, provider.available);
}

function providerDetails(provider) {
  const details = [];
  if (provider.kind) details.push(provider.kind);
  if (provider.device) details.push(`device: ${provider.device}`);
  if (provider.model) details.push(`model: ${provider.model}`);
  if (provider.optional === true) details.push("optional");
  if (provider.mock === true) details.push("mock");
  return details;
}

function renderCapabilities() {
  const list = $("#capabilityList");
  const summary = $("#capabilitySummary");
  const notice = $("#capabilityNotice");

  if (!state.capabilities) {
    summary.textContent = "Unavailable";
    summary.className = "status-chip is-bad";
    notice.textContent = state.errors.capabilities || "Capability report has not loaded.";
    list.innerHTML = `<div class="error-state">${escapeHtml(state.errors.capabilities || "No capability data available.")}</div>`;
    return;
  }

  const providers = asArray(state.capabilities.providers);
  const readyCount = providers.filter((provider) => provider.available).length;
  const total = providers.length;
  const unavailableCount = total - readyCount;
  summary.textContent = `${readyCount}/${total} ready`;
  summary.className = `status-chip ${readyCount === total ? "is-ready" : readyCount ? "is-warn" : "is-bad"}`;
  notice.textContent = unavailableCount
    ? `${unavailableCount} provider(s) unavailable; optional ML failures stay visible for diagnostics.`
    : "All reported providers are available.";

  list.innerHTML = providers.length
    ? providers
        .slice(0, 12)
        .map((provider) => {
          const reasons = asArray(provider.reasons).join(" ");
          const details = providerDetails(provider);
          return `
            <div class="capability-row">
              <strong>${escapeHtml(provider.displayName || provider.name || "Unnamed provider")}</strong>
              ${providerChip(provider)}
              <span class="row-meta">${escapeHtml(reasons || "No diagnostics reported.")}</span>
              <div class="provider-detail">
                ${details.map((detail) => detailChip(detail)).join("")}
              </div>
            </div>
          `;
        })
        .join("")
    : `<div class="empty-state">The local API returned no provider records.</div>`;
}

function renderRunDefaults() {
  if (!state.runDefaults) {
    setFacts($("#runDefaults"), {
      status: state.errors.runDefaults || "not loaded",
      mask: "not reported",
      discovery: "not reported",
      output: "not reported",
    });
    return;
  }
  const defaults = state.runDefaults.defaults || {};
  setFacts($("#runDefaults"), {
    mask: defaults.maskProvider,
    discovery: defaults.discoveryProvider,
    fps: defaults.sampleFps,
    frames: defaults.maxFrames,
    output: defaults.outputMode,
  });
}

function renderProjects() {
  const select = $("#projectSelect");
  $("#projectCount").textContent = `${state.projects.length} project${state.projects.length === 1 ? "" : "s"}`;
  if (!state.projects.length) {
    select.innerHTML = `<option value="">${escapeHtml(state.errors.projects || "No local projects yet")}</option>`;
    state.selectedProjectId = "";
    return;
  }
  if (!state.selectedProjectId || !state.projects.some((project) => project.id === state.selectedProjectId)) {
    state.selectedProjectId = state.projects[0].id;
  }
  select.innerHTML = state.projects
    .map((project) => `<option value="${escapeAttribute(project.id)}">${escapeHtml(project.name)}</option>`)
    .join("");
  select.value = state.selectedProjectId;
}

function renderVideos() {
  const select = $("#videoSelect");
  $("#videoCount").textContent = `${state.videos.length} video${state.videos.length === 1 ? "" : "s"}`;
  if (state.errors.videos) {
    select.innerHTML = `<option value="">Video unavailable</option>`;
    $("#videoList").innerHTML = `<div class="error-state">${escapeHtml(state.errors.videos)}</div>`;
    return;
  }
  if (!state.videos.length) {
    state.selectedVideoId = "";
    select.innerHTML = `<option value="">No local videos yet</option>`;
  } else {
    if (!state.selectedVideoId || !state.videos.some((video) => video.id === state.selectedVideoId)) {
      state.selectedVideoId = state.videos[0].id;
    }
    select.innerHTML = state.videos
      .map((video) => {
        const filename = video.metadata?.filename || video.filename || video.path || video.id;
        return `<option value="${escapeAttribute(video.id)}">${escapeHtml(filename)}</option>`;
      })
      .join("");
    select.value = state.selectedVideoId;
  }
  $("#videoList").innerHTML = state.videos.length
    ? state.videos
        .map((video) => {
          const filename = video.metadata?.filename || video.filename || video.path || video.id;
          const detail = video.content_type || video.contentType || "source_video";
          const active = video.id === state.selectedVideoId;
          return `
            <button class="artifact-row video-choice ${active ? "is-selected" : ""}" type="button" data-video-id="${escapeAttribute(video.id)}" aria-pressed="${active}">
              <strong>${escapeHtml(filename)}</strong>
              <span class="row-meta">${escapeHtml(active ? `${detail} - selected` : detail)}</span>
            </button>
          `;
        })
        .join("")
    : `<div class="empty-state">Add a local video path after creating a project.</div>`;
}

function renderJobs() {
  const activeCount = state.jobs.filter(isActiveJob).length;
  $("#jobSummary").textContent = `${activeCount} active`;

  if (state.errors.jobs) {
    $("#jobList").innerHTML = `<div class="error-state">${escapeHtml(state.errors.jobs)}</div>`;
    return;
  }

  $("#jobList").innerHTML = state.jobs.length
    ? state.jobs
        .map((job) => {
          const progress = normalizeProgress(job);
          const status = job.status || "unknown";
          const diagnostics = [
            job.error,
            job.reason,
            job.message,
            job.vectorUnavailableReason,
            job.vector_unavailable_reason,
            job.rasterOnlyReason,
            job.raster_only_reason,
          ].filter(Boolean);
          return `
            <div class="artifact-row">
              <strong>${escapeHtml(job.type || "job")}</strong>
              ${statusChip(status, status, /complete|succeeded/.test(String(status).toLowerCase()))}
              <span class="row-meta">${escapeHtml(job.id || "no id reported")}</span>
              <div class="job-progress" role="group" aria-label="${escapeAttribute(`${job.type || "job"} progress`)}">
                <div class="job-progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress}">
                  <div class="job-progress-bar" style="--progress: ${progress}%"></div>
                </div>
                <span class="job-progress-text">${progress}% complete${diagnostics.length ? ` - ${escapeHtml(diagnostics.join(" "))}` : ""}</span>
              </div>
            </div>
          `;
        })
        .join("")
    : `<div class="empty-state">Jobs will appear here with status, progress, and export diagnostics.</div>`;
}

async function loadRootData() {
  const entries = await Promise.all(
    [
      ["health", "/api/health"],
      ["capabilities", "/api/capabilities"],
      ["runDefaults", "/api/run-config/defaults"],
      ["projects", "/api/projects"],
    ].map(async ([key, route]) => {
      try {
        return [key, await api(route), null];
      } catch (error) {
        return [key, null, error.message];
      }
    }),
  );

  state.errors = {};
  for (const [key, payload, error] of entries) {
    if (error) state.errors[key] = error;
    if (key === "health") state.health = payload;
    if (key === "capabilities") state.capabilities = payload;
    if (key === "runDefaults") state.runDefaults = payload;
    if (key === "projects") state.projects = payload?.projects || [];
  }
}

async function refreshAll() {
  renderApiStatus("is-neutral", "Checking API");
  await loadRootData();
  renderHealth();
  renderCapabilities();
  renderRunDefaults();
  renderMockStatus();
  renderProjects();
  renderApiStatus(state.errors.health ? "is-bad" : "is-ready", state.errors.health ? "API unavailable" : "API ready");
  await refreshProjectData();
}

async function refreshProjectData() {
  state.errors.videos = "";
  state.errors.jobs = "";
  if (!state.selectedProjectId) {
    state.videos = [];
    state.jobs = [];
  } else {
    const [videos, jobs] = await Promise.all(
      [
        ["videos", `/api/videos?projectId=${encodeURIComponent(state.selectedProjectId)}`],
        ["jobs", `/api/jobs?projectId=${encodeURIComponent(state.selectedProjectId)}`],
      ].map(async ([key, route]) => {
        try {
          return [key, await api(route), null];
        } catch (error) {
          return [key, null, error.message];
        }
      }),
    );

    state.videos = videos[1]?.videos || [];
    state.jobs = jobs[1]?.jobs || [];
    if (videos[2]) state.errors.videos = videos[2];
    if (jobs[2]) state.errors.jobs = jobs[2];
  }
  renderVideos();
  renderJobs();
}

$("#refreshButton").addEventListener("click", refreshAll);

document.querySelectorAll(".goal").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".goal").forEach((goal) => goal.classList.remove("is-active"));
    button.classList.add("is-active");
  });
});

$("#projectForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const created = await api("/api/projects", {
      method: "POST",
      body: JSON.stringify({ name: $("#projectName").value.trim() }),
    });
    state.selectedProjectId = created.project.id;
    await refreshAll();
  } catch (error) {
    state.errors.projects = error.message;
    renderProjects();
  }
});

$("#projectSelect").addEventListener("change", async (event) => {
  state.selectedProjectId = event.target.value;
  state.selectedVideoId = "";
  await refreshProjectData();
});

$("#videoSelect").addEventListener("change", (event) => {
  state.selectedVideoId = event.target.value;
  renderVideos();
});

$("#videoList").addEventListener("click", (event) => {
  const choice = event.target.closest("[data-video-id]");
  if (!choice) return;
  state.selectedVideoId = choice.dataset.videoId;
  renderVideos();
});

$("#videoForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.selectedProjectId) {
    $("#videoList").innerHTML = `<div class="error-state">Create a project before adding a video.</div>`;
    return;
  }
  try {
    await api("/api/videos", {
      method: "POST",
      body: JSON.stringify({ projectId: state.selectedProjectId, path: $("#videoPath").value.trim() }),
    });
    await refreshProjectData();
  } catch (error) {
    $("#videoList").innerHTML = `<div class="error-state">${escapeHtml(error.message)}</div>`;
  }
});

refreshAll();
