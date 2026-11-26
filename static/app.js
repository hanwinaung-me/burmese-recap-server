let currentProjectId = null;
let pollTimer = null;

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, options);

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      data.detail || `HTTP ${response.status}`
    );
  }

  return data;
}

function show(id, message) {
  $(id).textContent = message;
}

async function checkServer() {
  try {
    await api("/health");
    $("serverStatus").textContent = "Server Online";
    $("serverStatus").style.color = "#22c55e";
  } catch (error) {
    $("serverStatus").textContent = "Server Offline";
  }
}

$("createProject").onclick = async () => {
  try {
    const form = new FormData();

    form.append(
      "name",
      $("projectName").value || "My Recap"
    );

    const data = await api("/api/projects", {
      method: "POST",
      body: form
    });

    currentProjectId = data.project.id;

    show(
      "createMessage",
      "Project created: " + currentProjectId
    );

    await refreshProjects();

  } catch (error) {
    show("createMessage", error.message);
  }
};

$("uploadVideo").onclick = async () => {
  try {
    if (!currentProjectId) {
      throw new Error("Create a project first.");
    }

    const file = $("videoFile").files[0];

    if (!file) {
      throw new Error("Select a video first.");
    }

    if (!$("rightsConfirmed").checked) {
      throw new Error("Please confirm your rights to process this video.");
    }

    const form = new FormData();

    form.append("file", file);
    form.append("rights_confirmed", "true");

    show("uploadMessage", "Uploading video...");

    const data = await api(
      `/api/projects/${currentProjectId}/upload`,
      {
        method: "POST",
        body: form
      }
    );

    show(
      "uploadMessage",
      "Upload complete. Duration: " +
      Math.round(data.video_info.duration / 60) +
      " minutes."
    );

  } catch (error) {
    show("uploadMessage", error.message);
  }
};

$("analyzeVideo").onclick = async () => {
  try {
    if (!currentProjectId) {
      throw new Error("Create a project first.");
    }

    await api(
      `/api/projects/${currentProjectId}/analyze`,
      { method: "POST" }
    );

    show("jobMessage", "Analysis started.");

    startPolling();

  } catch (error) {
    show("jobMessage", error.message);
  }
};

function startPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
  }

  pollTimer = setInterval(async () => {
    try {
      const data = await api(
        `/api/projects/${currentProjectId}`
      );

      const project = data.project;

      const progress = Number(project.progress || 0);

      $("progressBar").style.width =
        Math.max(0, Math.min(100, progress)) + "%";

      $("progressText").textContent =
        progress + "%";

      show(
        "jobMessage",
        project.status + " — " + project.message
      );

      if (
        project.status === "SCRIPT_READY" ||
        project.status === "FAILED"
      ) {
        clearInterval(pollTimer);
        pollTimer = null;

        if (project.status === "SCRIPT_READY") {
          await loadScript();
        }
      }

    } catch (error) {
      show("jobMessage", error.message);
    }
  }, 5000);
}

async function loadScript() {
  const data = await api(
    `/api/projects/${currentProjectId}/script`
  );

  $("scriptEditor").value = data.script || "";
}

$("loadScript").onclick = async () => {
  try {
    if (!currentProjectId) {
      throw new Error("Select a project first.");
    }

    await loadScript();

  } catch (error) {
    show("jobMessage", error.message);
  }
};

$("saveScript").onclick = async () => {
  try {
    const form = new FormData();

    form.append(
      "script",
      $("scriptEditor").value
    );

    await api(
      `/api/projects/${currentProjectId}/script`,
      {
        method: "PUT",
        body: form
      }
    );

    show("jobMessage", "Script saved.");

  } catch (error) {
    show("jobMessage", error.message);
  }
};

$("generateVoice").onclick = async () => {
  try {
    show("voiceMessage", "Generating voice...");

    const data = await api(
      `/api/projects/${currentProjectId}/voice`,
      { method: "POST" }
    );

    show(
      "voiceMessage",
      "Voice ready. Duration: " +
      data.duration.toFixed(1) +
      " seconds."
    );

  } catch (error) {
    show("voiceMessage", error.message);
  }
};

$("generateSubtitles").onclick = async () => {
  try {
    show("subtitleMessage", "Generating subtitles...");

    await api(
      `/api/projects/${currentProjectId}/subtitles`,
      { method: "POST" }
    );

    show("subtitleMessage", "Subtitles generated.");

  } catch (error) {
    show("subtitleMessage", error.message);
  }
};

$("renderVideo").onclick = async () => {
  try {
    show("renderMessage", "Rendering video...");

    const form = new FormData();

    form.append(
      "aspect_ratio",
      $("aspectRatio").value
    );

    form.append(
      "resolution",
      $("resolution").value
    );

    await api(
      `/api/projects/${currentProjectId}/render`,
      {
        method: "POST",
        body: form
      }
    );

    const link = $("downloadLink");

    link.href =
      `/api/projects/${currentProjectId}/download`;

    link.hidden = false;

    show("renderMessage", "Export completed.");

  } catch (error) {
    show("renderMessage", error.message);
  }
};

async function refreshProjects() {
  try {
    const data = await api("/api/projects");

    $("projectList").innerHTML = "";

    for (const project of data.projects) {
      const item = document.createElement("div");

      item.className = "project-item";

      const title = document.createElement("strong");
      title.textContent = project.name;

      const status = document.createElement("p");
      status.textContent =
        project.status + " · " +
        project.progress + "%";

      const select = document.createElement("button");
      select.textContent = "Open Project";

      select.onclick = () => {
        currentProjectId = project.id;
        show("createMessage", "Selected: " + project.id);

        if (project.status === "ANALYZING") {
          startPolling();
        }
      };

      item.append(title, status, select);
      $("projectList").appendChild(item);
    }

  } catch (error) {
    console.error(error);
  }
}

$("refreshProjects").onclick = refreshProjects;

checkServer();
refreshProjects();
