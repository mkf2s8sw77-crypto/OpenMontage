import {FormEvent, startTransition, useEffect, useMemo, useState} from "react";

type Project = {
  project_id: string;
  path: string;
  job_count: number;
};

type Asset = {
  path: string;
  category: string;
  filename: string;
  size_bytes: number;
};

type Job = {
  job_id: string;
  project_id: string;
  status: string;
  type: string;
  request: Record<string, unknown>;
  result: Record<string, unknown> | null;
  artifacts: string[];
  error: string | null;
  created_at: string;
  updated_at: string;
};

const tabs = ["tts", "image", "music", "video", "jobs"] as const;
type Tab = (typeof tabs)[number];

function apiPath(path: string): string {
  if (import.meta.env.DEV) {
    return path;
  }
  return path.replace(/^\//, "");
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiPath(path), {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const message = payload?.detail?.error?.message ?? payload?.detail ?? response.statusText;
    throw new Error(String(message));
  }
  return response.json() as Promise<T>;
}

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function buildFileUrl(projectId: string, path: string): string {
  const normalized = encodeURIComponent(path);
  return apiPath(`/api/studio/projects/${projectId}/files?path=${normalized}`);
}

function normalizeProjectRelativePath(projectId: string, value: unknown): string | null {
  if (typeof value !== "string" || !value) {
    return null;
  }
  const marker = `projects/${projectId}/`;
  const markerIndex = value.indexOf(marker);
  if (markerIndex >= 0) {
    return value.slice(markerIndex + marker.length);
  }
  if (value.startsWith("assets/") || value.startsWith("artifacts/")) {
    return value;
  }
  return null;
}

export default function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<string>("");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [tab, setTab] = useState<Tab>("tts");
  const [loading, setLoading] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [notice, setNotice] = useState<string>("");
  const [config, setConfig] = useState<{configured: boolean; host: string}>({
    configured: false,
    host: "https://api.minimaxi.com",
  });
  const [projectTitle, setProjectTitle] = useState("minimax-studio-smoke");
  const [ttsText, setTtsText] = useState("欢迎使用 OpenMontage MiniMax Studio。");
  const [imagePrompt, setImagePrompt] = useState("A cinematic creator control room, warm tungsten glow, brass and paper textures, 16:9.");
  const [musicPrompt, setMusicPrompt] = useState("Instrumental ambient piano with soft tape texture and reflective mood.");
  const [musicLyrics, setMusicLyrics] = useState("[Verse]\nWarm light on the desk tonight\nIdeas flicker into sight\n[Chorus]\nHold the frame and let it glow\nTurn the quiet into flow");
  const [videoPrompt, setVideoPrompt] = useState("A camera glides through a moody editing desk lit by warm practical lights, cinematic realism.");

  const selectedAssets = useMemo(() => assets.slice().reverse().slice(0, 8), [assets]);

  const recentAssetsByCategory = (category: Asset["category"]) =>
    assets.filter((asset) => asset.category === category).slice().reverse().slice(0, 8);

  const refreshProjects = async () => {
    const payload = await api<{projects: Project[]}>("/api/studio/projects");
    setProjects(payload.projects);
    if (!selectedProject && payload.projects.length > 0) {
      setSelectedProject(payload.projects[0].project_id);
    }
  };

  const refreshProjectData = async (projectId: string) => {
    if (!projectId) return;
    const [assetPayload, jobPayload] = await Promise.all([
      api<{project_id: string; assets: Asset[]}>(`/api/studio/projects/${projectId}/assets`),
      api<{jobs: Job[]}>(`/api/studio/jobs?project_id=${encodeURIComponent(projectId)}`),
    ]);
    setAssets(assetPayload.assets);
    setJobs(jobPayload.jobs);
  };

  useEffect(() => {
    void (async () => {
      const configPayload = await api<{minimax: {configured: boolean; host: string}}>("/api/studio/config/status");
      setConfig(configPayload.minimax);
      await refreshProjects();
    })().catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    void refreshProjectData(selectedProject).catch((err: Error) => setError(err.message));
  }, [selectedProject]);

  const createProject = async (event: FormEvent) => {
    event.preventDefault();
    setLoading("project");
    setError("");
    try {
      const payload = await api<{project: {project_id: string}}>("/api/studio/projects", {
        method: "POST",
        body: JSON.stringify({title: projectTitle}),
      });
      await refreshProjects();
      startTransition(() => setSelectedProject(payload.project.project_id));
      setNotice(`Project ready: ${payload.project.project_id}`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading("");
    }
  };

  const submit = async (category: "tts" | "image" | "music" | "video", payload: Record<string, unknown>) => {
    if (!selectedProject) {
      setError("Create or select a project first.");
      return;
    }
    setLoading(category);
    setError("");
    setNotice("");
    try {
      if (category === "video") {
        await api<{job: Job}>("/api/studio/video/jobs", {
          method: "POST",
          body: JSON.stringify({...payload, project_id: selectedProject}),
        });
        setNotice("Video job submitted.");
      } else {
        await api(`/api/studio/${category}`, {
          method: "POST",
          body: JSON.stringify({...payload, project_id: selectedProject}),
        });
        setNotice(`${category.toUpperCase()} generation finished.`);
      }
      await refreshProjectData(selectedProject);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading("");
    }
  };

  return (
    <div className="shell">
      <aside className="sidebar">
        <div>
          <p className="eyebrow">OpenMontage</p>
          <h1>MiniMax Studio</h1>
          <p className="lede">A local control room for one operator, one project tree, and direct MiniMax generation.</p>
        </div>

        <section className="panel">
          <div className="panel-head">
            <h2>Config</h2>
            <span className={config.configured ? "pill ok" : "pill warn"}>
              {config.configured ? "Key Loaded" : "Key Missing"}
            </span>
          </div>
          <p className="meta">Host: {config.host}</p>
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>Project</h2>
            <span className="pill neutral">{projects.length} total</span>
          </div>
          <form onSubmit={createProject} className="stack">
            <input value={projectTitle} onChange={(e) => setProjectTitle(e.target.value)} placeholder="new project name" />
            <button type="submit" disabled={loading === "project"}>{loading === "project" ? "Creating..." : "Create Project"}</button>
          </form>
          <div className="project-list">
            {projects.map((project) => (
              <button
                key={project.project_id}
                className={project.project_id === selectedProject ? "project-item active" : "project-item"}
                onClick={() => setSelectedProject(project.project_id)}
              >
                <strong>{project.project_id}</strong>
                <span>{project.job_count} jobs</span>
              </button>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>Recent Assets</h2>
            <span className="pill neutral">{selectedAssets.length}</span>
          </div>
          <div className="asset-list">
            {selectedAssets.map((asset) => (
              <a key={asset.path} className="asset-item" href={buildFileUrl(selectedProject, asset.path)} target="_blank" rel="noreferrer">
                <strong>{asset.filename}</strong>
                <span>{asset.category} · {formatBytes(asset.size_bytes)}</span>
              </a>
            ))}
          </div>
        </section>
      </aside>

      <main className="workspace">
        <header className="workspace-head">
          <div>
            <p className="eyebrow">Control Room</p>
            <h2>{selectedProject || "Select a project"}</h2>
          </div>
          <div className="tab-row">
            {tabs.map((item) => (
              <button
                key={item}
                className={item === tab ? "tab active" : "tab"}
                onClick={() => setTab(item)}
              >
                {item}
              </button>
            ))}
            <button className="tab ghost" onClick={() => void refreshProjectData(selectedProject)}>
              refresh
            </button>
          </div>
        </header>

        {error ? <div className="alert error">{error}</div> : null}
        {notice ? <div className="alert notice">{notice}</div> : null}

        {tab === "tts" && (
          <section className="canvas two-up">
            <div className="panel form-panel">
              <h3>TTS</h3>
              <textarea value={ttsText} onChange={(e) => setTtsText(e.target.value)} rows={7} />
              <button onClick={() => void submit("tts", {text: ttsText})} disabled={loading === "tts"}>
                {loading === "tts" ? "Generating..." : "Generate Speech"}
              </button>
            </div>
            <PreviewGrid projectId={selectedProject} assets={recentAssetsByCategory("audio")} />
          </section>
        )}

        {tab === "image" && (
          <section className="canvas two-up">
            <div className="panel form-panel">
              <h3>Image</h3>
              <textarea value={imagePrompt} onChange={(e) => setImagePrompt(e.target.value)} rows={7} />
              <button onClick={() => void submit("image", {prompt: imagePrompt, aspect_ratio: "16:9"})} disabled={loading === "image"}>
                {loading === "image" ? "Generating..." : "Generate Image"}
              </button>
            </div>
            <PreviewGrid projectId={selectedProject} assets={recentAssetsByCategory("images")} />
          </section>
        )}

        {tab === "music" && (
          <section className="canvas two-up">
            <div className="panel form-panel">
              <h3>Music</h3>
              <textarea value={musicPrompt} onChange={(e) => setMusicPrompt(e.target.value)} rows={7} />
              <textarea value={musicLyrics} onChange={(e) => setMusicLyrics(e.target.value)} rows={8} placeholder="lyrics" />
              <button onClick={() => void submit("music", {prompt: musicPrompt, lyrics: musicLyrics, duration_seconds: 15})} disabled={loading === "music"}>
                {loading === "music" ? "Generating..." : "Generate Music"}
              </button>
            </div>
            <PreviewGrid projectId={selectedProject} assets={recentAssetsByCategory("music")} />
          </section>
        )}

        {tab === "video" && (
          <section className="canvas two-up">
            <div className="panel form-panel">
              <h3>Video</h3>
              <textarea value={videoPrompt} onChange={(e) => setVideoPrompt(e.target.value)} rows={7} />
              <button onClick={() => void submit("video", {prompt: videoPrompt, duration: 6, resolution: "1080P"})} disabled={loading === "video"}>
                {loading === "video" ? "Submitting..." : "Create Video Job"}
              </button>
              <p className="meta">Video jobs are async. Submit here, then monitor them in the Jobs tab.</p>
            </div>
            <PreviewGrid projectId={selectedProject} assets={recentAssetsByCategory("video")} />
          </section>
        )}

        {tab === "jobs" && (
          <section className="canvas">
            <div className="jobs-grid">
              {jobs.length === 0 ? (
                <div className="panel empty">No jobs yet for this project.</div>
              ) : (
                jobs.map((job) => (
                  <article key={job.job_id} className="panel job-card">
                    <div className="panel-head">
                      <h3>{job.job_id}</h3>
                      <span className={`pill ${job.status === "success" ? "ok" : job.status === "failed" ? "warn" : "neutral"}`}>
                        {job.status}
                      </span>
                    </div>
                    <p className="meta">{job.type}</p>
                    <p className="meta">{job.created_at}</p>
                    {job.error ? <p className="error-text">{job.error}</p> : null}
                    {(() => {
                      const relativePath = normalizeProjectRelativePath(selectedProject, job.result?.output);
                      if (!relativePath) return null;
                      return (
                        <a href={buildFileUrl(selectedProject, relativePath)} target="_blank" rel="noreferrer">
                          Open output
                        </a>
                      );
                    })()}
                  </article>
                ))
              )}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

function PreviewGrid({projectId, assets}: {projectId: string; assets: Asset[]}) {
  if (!projectId) {
    return <div className="panel empty">Select a project to preview assets.</div>;
  }
  if (assets.length === 0) {
    return <div className="panel empty">No assets yet for this category.</div>;
  }
  return (
    <div className="preview-grid">
      {assets.map((asset) => {
        const fileUrl = buildFileUrl(projectId, asset.path);
        if (asset.category === "images") {
          return (
            <figure className="preview-card" key={asset.path}>
              <img src={fileUrl} alt={asset.filename} />
              <figcaption>{asset.filename}</figcaption>
            </figure>
          );
        }
        if (asset.category === "audio" || asset.category === "music") {
          return (
            <div className="preview-card" key={asset.path}>
              <audio controls src={fileUrl} />
              <figcaption>{asset.filename}</figcaption>
            </div>
          );
        }
        return (
          <div className="preview-card" key={asset.path}>
            <video controls src={fileUrl} />
            <figcaption>{asset.filename}</figcaption>
          </div>
        );
      })}
    </div>
  );
}
