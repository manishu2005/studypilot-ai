import { useEffect, useState } from "react";
import {
  BookOpen, LayoutDashboard, Upload, Search, MessageSquare,
  Brain, ClipboardList, Network, CalendarDays, Menu, X,
  FileText, Video, Send, RefreshCw, CheckCircle, AlertCircle,
  Eye, Layers, Clock, Hash, BookMarked
} from "lucide-react";
import "./App.css";

const API = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...(options.body && !(options.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...options.headers,
    },
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail?.message || data.detail || data.message || `Request failed (${response.status})`);
  }
  return data;
}

const navItems = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "library", label: "My Library", icon: BookOpen },
  { id: "search", label: "Knowledge Search", icon: Search },
  { id: "tutor", label: "AI Tutor", icon: MessageSquare },
  { id: "quiz", label: "Practice & Quiz", icon: ClipboardList },
  { id: "mastery", label: "Learning Progress", icon: Brain },
  { id: "graph", label: "Course Graph", icon: Network },
  { id: "revision", label: "Revision Planner", icon: CalendarDays },
];

function App() {
  const [page, setPage] = useState("dashboard");
  const [documents, setDocuments] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [mastery, setMastery] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [mobileMenu, setMobileMenu] = useState(false);

  // Inspector state to view extracted file details
  const [inspectDocId, setInspectDocId] = useState(null);

  async function run(action, successMessage = "") {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await action();
      if (successMessage) setNotice(successMessage);
      return result;
    } catch (e) {
      setError(typeof e.message === "string" ? e.message : JSON.stringify(e.message));
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function loadDocuments() {
    const result = await api("/api/documents");
    const docList = Array.isArray(result) ? result : result.documents || [];
    setDocuments(docList);
    return docList;
  }

  async function loadMastery() {
    const result = await api("/api/learner/dashboard");
    setDashboard(result);
    const profiles = result.topics || result.mastery || result.topic_mastery || [];
    setMastery(Array.isArray(profiles) ? profiles : []);
    return result;
  }

  async function refreshAll() {
    await Promise.allSettled([loadDocuments(), loadMastery()]);
  }

  useEffect(() => {
    refreshAll();
  }, []);

  function navigate(id) {
    setPage(id);
    setMobileMenu(false);
    setError("");
    setNotice("");
    if (id === "library") run(loadDocuments);
    if (id === "mastery" || id === "dashboard") run(loadMastery);
  }

  const currentPage = navItems.find((item) => item.id === page);

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileMenu ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-icon"><Brain size={23} /></div>
          <div><strong>StudyPilot</strong><span>AI Learning Companion</span></div>
          <button className="mobile-close" onClick={() => setMobileMenu(false)}><X /></button>
        </div>

        <div className="nav-label">WORKSPACE</div>
        <nav>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={`nav-item ${page === item.id ? "active" : ""}`}
                onClick={() => navigate(item.id)}>
                <Icon size={18} /><span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="sidebar-bottom">
          <div className="status-dot" />
          <div><strong>StudyPilot API</strong><span>Backend active</span></div>
          <button title="Refresh data" onClick={() => run(refreshAll)}><RefreshCw size={15} /></button>
        </div>
      </aside>

      {mobileMenu && <button className="mobile-overlay" onClick={() => setMobileMenu(false)} />}

      <main className="main-area">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileMenu(true)}><Menu /></button>
          <div className="breadcrumb">Workspace <span>/</span> {currentPage?.label || "Dashboard"}</div>
          <div className="topbar-right"><span className="online-dot" /> Online</div>
        </header>

        <section className="page-content">
          {(error || notice) && (
            <div className={`alert ${error ? "alert-error" : "alert-success"}`}>
              {error ? <AlertCircle size={18} /> : <CheckCircle size={18} />}
              <span>{error || notice}</span>
              <button onClick={() => { setError(""); setNotice(""); }}><X size={16} /></button>
            </div>
          )}
          {busy && <div className="loading-line" />}

          {page === "dashboard" && (
            <Dashboard
              documents={documents}
              dashboard={dashboard}
              mastery={mastery}
              navigate={navigate}
              refresh={() => run(refreshAll)}
              onInspect={(id) => setInspectDocId(id)}
            />
          )}

          {page === "library" && (
            <Library
              documents={documents}
              busy={busy}
              refresh={() => run(loadDocuments)}
              run={run}
              onInspect={(id) => setInspectDocId(id)}
            />
          )}

          {page === "search" && <KnowledgeSearch run={run} />}
          {page === "tutor" && <Tutor run={run} />}
          {page === "quiz" && <Quiz run={run} documents={documents} />}
          {page === "mastery" && <Mastery mastery={mastery} dashboard={dashboard} run={run} refresh={() => run(loadMastery)} />}
          {page === "graph" && <CourseGraphPage run={run} />}
          {page === "revision" && <RevisionPlanner run={run} mastery={mastery} />}
        </section>
      </main>

      {/* Persistent modal to inspect extracted details of any file */}
      {inspectDocId && (
        <DocumentDetailsModal
          documentId={inspectDocId}
          onClose={() => setInspectDocId(null)}
          run={run}
        />
      )}
    </div>
  );
}

function PageHeading({ eyebrow = "STUDYPILOT", title, description, action }) {
  return (
    <div className="page-heading">
      <div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>
      {action}
    </div>
  );
}

function StatCard({ label, value, detail, icon: Icon }) {
  return (
    <div className="stat-card">
      <div className="stat-top"><span>{label}</span><div className="stat-icon"><Icon size={19} /></div></div>
      <div className="stat-value">{value}</div>
      <div className="stat-detail">{detail}</div>
    </div>
  );
}

function ResourceRow({ doc, onInspect }) {
  const isVideo = /\.(mp4|mov|mkv|webm|avi|m4v)$/i.test(doc.filename || "");
  const docId = doc.id || doc.document_id;

  return (
    <div className="resource-row">
      <div className="resource-icon">{isVideo ? <Video size={18} /> : <FileText size={18} />}</div>
      <div className="resource-main">
        <strong>{doc.filename || "Untitled resource"}</strong>
        <small>
          {doc.status || "ready"} · {doc.chunk_count ?? 0} chunks
          {doc.page_count ? ` · ${doc.page_count} pages` : ""}
        </small>
      </div>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <button
          className="btn btn-secondary btn-small"
          onClick={() => onInspect(docId)}
          title="Inspect extracted text, chunks and diagrams"
        >
          <Eye size={14} /> Extracted Details
        </button>
        <span className={`status-pill ${doc.status === "ready" ? "status-ready" : ""}`}>
          {doc.status || "indexed"}
        </span>
      </div>
    </div>
  );
}

function Dashboard({ documents, dashboard, mastery, navigate, refresh, onInspect }) {
  const topics = mastery.length || dashboard?.topic_count || 0;
  const attempts = dashboard?.total_attempts ?? dashboard?.attempts ?? 0;
  const average = dashboard?.average_mastery ?? dashboard?.mastery_average;

  return (
    <>
      <PageHeading
        title="Your learning dashboard"
        description="Your learning materials, knowledge and progress in one workspace."
        action={<button className="btn btn-secondary" onClick={refresh}><RefreshCw size={16} /> Refresh</button>}
      />
      <div className="stats-grid">
        <StatCard label="Learning resources" value={documents.length} detail="Indexed documents and lectures" icon={BookOpen} />
        <StatCard label="Tracked topics" value={topics} detail="Topics with learning progress" icon={Network} />
        <StatCard label="Quiz attempts" value={attempts} detail="Recorded practice activity" icon={ClipboardList} />
        <StatCard label="Average mastery" value={average == null ? "—" : `${Math.round(Number(average) * (Number(average) <= 1 ? 100 : 1))}%`} detail="Calculated by learner engine" icon={Brain} />
      </div>

      <div className="dashboard-grid">
        <div className="panel">
          <div className="panel-heading"><div><h2>Quick actions</h2><p>Continue your learning workflow</p></div></div>
          <div className="quick-actions">
            <button onClick={() => navigate("library")}><Upload /><span><strong>Upload materials</strong><small>PDF, slides or lecture video</small></span></button>
            <button onClick={() => navigate("search")}><Search /><span><strong>Search knowledge</strong><small>Find concepts in your sources</small></span></button>
            <button onClick={() => navigate("tutor")}><MessageSquare /><span><strong>Ask AI Tutor</strong><small>Get source-grounded answers</small></span></button>
            <button onClick={() => navigate("quiz")}><ClipboardList /><span><strong>Practice a quiz</strong><small>Generate questions from content</small></span></button>
            <button onClick={() => navigate("graph")}><Network /><span><strong>Plan a learning path</strong><small>Prerequisites and study tasks</small></span></button>
            <button onClick={() => navigate("revision")}><CalendarDays /><span><strong>Review topics</strong><small>Create a revision schedule</small></span></button>
          </div>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <div><h2>Recent resources</h2><p>Latest items indexed into your knowledge base</p></div>
            <button className="text-button" onClick={() => navigate("library")}>View all</button>
          </div>
          {documents.length === 0 ? (
            <EmptyState title="No materials yet" text="Upload a PDF, PPTX or lecture video to start building your knowledge base." />
          ) : (
            <div className="resource-list">
              {documents.slice(0, 5).map((doc) => (
                <ResourceRow key={doc.id || doc.document_id} doc={doc} onInspect={onInspect} />
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function Library({ documents, busy, refresh, run, onInspect }) {
  const [file, setFile] = useState(null);
  const [lastUploadedDoc, setLastUploadedDoc] = useState(null);

  async function upload(e) {
    e.preventDefault();
    if (!file) return;
    const form = new FormData();
    form.append("file", file);

    const response = await run(async () => {
      const data = await api("/api/documents/upload", { method: "POST", body: form });
      setLastUploadedDoc(data);
      await refresh();
      return data;
    }, "Document indexed! Opening extracted details...");

    if (response) {
      setFile(null);
      // Automatically open the details drawer for immediate inspection
      if (response.document_id) {
        onInspect(response.document_id);
      }
    }
  }

  return (
    <>
      <PageHeading title="My library" description="Upload, extract and inspect knowledge from learning materials." />
      <div className="panel upload-panel">
        <div className="panel-heading">
          <div>
            <h2><Upload size={19} /> Add learning material</h2>
            <p>Supported formats: PDF, PPTX, MP4, MOV, MKV, WEBM, AVI, M4V</p>
          </div>
        </div>
        <form onSubmit={upload}>
          <label className="upload-zone">
            <input
              type="file"
              accept=".pdf,.pptx,.mp4,.mov,.mkv,.webm,.avi,.m4v"
              onChange={(e) => { setFile(e.target.files?.[0] || null); setLastUploadedDoc(null); }}
            />
            <div className="upload-icon"><Upload size={24} /></div>
            <strong>{file ? file.name : "Choose a file to upload"}</strong>
            <span>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : "Select a document or video"}</span>
          </label>
          <button className="btn btn-primary" disabled={!file || busy}>
            <Upload size={16} /> {busy ? "Extracting & Indexing..." : "Upload and extract details"}
          </button>
        </form>

        {lastUploadedDoc && (
          <div className="result-box" style={{ marginTop: "1rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3>Extraction Finished: {lastUploadedDoc.filename}</h3>
              {lastUploadedDoc.document_id && (
                <button className="btn btn-secondary btn-small" onClick={() => onInspect(lastUploadedDoc.document_id)}>
                  <Eye size={14} /> View All Extracted Content
                </button>
              )}
            </div>
            <div className="result-field"><span>Status</span><strong>{lastUploadedDoc.status}</strong></div>
            <div className="result-field"><span>Chunks Extracted</span><strong>{lastUploadedDoc.chunk_count}</strong></div>
            {lastUploadedDoc.page_count != null && <div className="result-field"><span>Pages</span><strong>{lastUploadedDoc.page_count}</strong></div>}
            {lastUploadedDoc.duration_seconds != null && <div className="result-field"><span>Duration</span><strong>{formatTime(lastUploadedDoc.duration_seconds)}</strong></div>}
          </div>
        )}
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div><h2>Indexed resources</h2><p>{documents.length} files currently stored</p></div>
          <button className="btn btn-secondary btn-small" onClick={refresh}><RefreshCw size={15} /> Refresh</button>
        </div>
        {documents.length ? (
          <div className="resource-list">
            {documents.map((doc) => (
              <ResourceRow
                key={doc.id || doc.document_id || doc.filename}
                doc={doc}
                onInspect={onInspect}
              />
            ))}
          </div>
        ) : (
          <EmptyState title="Library is empty" text="Upload your first document above to view extracted details." />
        )}
      </div>
    </>
  );
}

/**
 * Full details inspection modal to view chunks, transcripts, diagrams, and metadata
 */
function DocumentDetailsModal({ documentId, onClose, run }) {
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("chunks"); // 'chunks' | 'diagrams' | 'topics' | 'metadata'

  useEffect(() => {
    async function fetchDetails() {
      setLoading(true);
      const res = await run(async () => {
        return await api(`/api/documents/${documentId}`);
      });
      if (res) setDetails(res);
      setLoading(false);
    }
    fetchDetails();
  }, [documentId]);

  return (
    <div
      className="modal-backdrop"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0,0,0,0.65)",
        zIndex: 1000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "1.5rem",
      }}
    >
      <div
        className="panel"
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: "900px",
          width: "100%",
          maxHeight: "88vh",
          display: "flex",
          flexDirection: "column",
          padding: 0,
          overflow: "hidden",
        }}
      >
        {/* Modal Header */}
        <div style={{ padding: "1.25rem 1.5rem", borderBottom: "1px solid var(--border, #333)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <div className="eyebrow" style={{ fontSize: "0.75rem", marginBottom: "0.2rem" }}>DOCUMENT DETAILS</div>
            <h2 style={{ fontSize: "1.25rem", margin: 0 }}>{details?.filename || "Loading details..."}</h2>
            <small style={{ color: "var(--muted, #888)" }}>ID: {documentId}</small>
          </div>
          <button className="btn btn-secondary btn-small" onClick={onClose}><X size={16} /></button>
        </div>

        {/* Modal Tabs */}
        <div style={{ display: "flex", borderBottom: "1px solid var(--border, #333)", background: "rgba(0,0,0,0.15)", padding: "0 1.5rem" }}>
          <button
            className={`tab-btn ${activeTab === "chunks" ? "active" : ""}`}
            onClick={() => setActiveTab("chunks")}
            style={{ padding: "0.75rem 1rem", border: "none", background: "none", cursor: "pointer", borderBottom: activeTab === "chunks" ? "2px solid #3b82f6" : "none", color: activeTab === "chunks" ? "#fff" : "#aaa", fontWeight: 600 }}
          >
            <Layers size={14} style={{ display: "inline", marginRight: "6px" }} />
            Text Chunks ({details?.chunks?.length ?? 0})
          </button>
          <button
            className={`tab-btn ${activeTab === "diagrams" ? "active" : ""}`}
            onClick={() => setActiveTab("diagrams")}
            style={{ padding: "0.75rem 1rem", border: "none", background: "none", cursor: "pointer", borderBottom: activeTab === "diagrams" ? "2px solid #3b82f6" : "none", color: activeTab === "diagrams" ? "#fff" : "#aaa", fontWeight: 600 }}
          >
            <BookMarked size={14} style={{ display: "inline", marginRight: "6px" }} />
            Extracted Slides ({details?.diagrams?.length ?? 0})
          </button>
          <button
            className={`tab-btn ${activeTab === "metadata" ? "active" : ""}`}
            onClick={() => setActiveTab("metadata")}
            style={{ padding: "0.75rem 1rem", border: "none", background: "none", cursor: "pointer", borderBottom: activeTab === "metadata" ? "2px solid #3b82f6" : "none", color: activeTab === "metadata" ? "#fff" : "#aaa", fontWeight: 600 }}
          >
            <Hash size={14} style={{ display: "inline", marginRight: "6px" }} />
            File Metadata
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: "1.5rem", overflowY: "auto", flexGrow: 1 }}>
          {loading ? (
            <p>Loading document details from database...</p>
          ) : !details ? (
            <p>No details found for this file.</p>
          ) : (
            <>
              {activeTab === "chunks" && (
                <div>
                  {details.chunks?.length ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                      {details.chunks.map((ch, idx) => (
                        <div key={ch.id || idx} style={{ border: "1px solid var(--border, #333)", borderRadius: "6px", padding: "0.75rem", background: "rgba(255,255,255,0.02)" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "#888", marginBottom: "0.4rem" }}>
                            <span><strong>Chunk #{ch.chunk_index ?? idx}</strong></span>
                            <span>{ch.source_type === "video" ? `Timestamp: ${formatTime(ch.location_number)}` : `Page / Loc: ${ch.location_number}`}</span>
                          </div>
                          <p style={{ margin: 0, fontSize: "0.88rem", whiteSpace: "pre-wrap", lineHeight: 1.45 }}>{ch.text}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <EmptyState title="No text chunks recorded" text="No extracted text chunks were stored in SQLite for this document." />
                  )}
                </div>
              )}

              {activeTab === "diagrams" && (
                <div>
                  {details.diagrams?.length ? (
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "1rem" }}>
                      {details.diagrams.map((d, idx) => (
                        <div key={d.id || idx} style={{ border: "1px solid var(--border, #333)", borderRadius: "6px", padding: "0.75rem", background: "rgba(255,255,255,0.02)" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "#888", marginBottom: "0.3rem" }}>
                            <span>{d.diagram_type || "Slide"}</span>
                            <span>{d.location_number != null ? formatTime(d.location_number) : `#${d.image_index}`}</span>
                          </div>
                          <strong>{d.title || `Slide ${idx + 1}`}</strong>
                          {d.educational_value && <p style={{ fontSize: "0.82rem", margin: "0.3rem 0" }}>{d.educational_value}</p>}
                          {d.description && (
                            <pre style={{ fontSize: "0.75rem", background: "rgba(0,0,0,0.3)", padding: "0.4rem", borderRadius: "4px", maxHeight: "120px", overflowY: "auto", margin: "0.4rem 0 0" }}>
                              {d.description}
                            </pre>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <EmptyState title="No diagrams extracted" text="No slide diagrams or keyframes were saved for this file." />
                  )}
                </div>
              )}

              {activeTab === "metadata" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  <div className="result-field"><span>Filename</span><strong>{details.filename}</strong></div>
                  <div className="result-field"><span>Status</span><strong>{details.status}</strong></div>
                  <div className="result-field"><span>Total Chunks</span><strong>{details.chunk_count}</strong></div>
                  <div className="result-field"><span>Page Count</span><strong>{details.page_count || "N/A"}</strong></div>
                  <div className="result-field"><span>SHA256 Hash</span><code style={{ fontSize: "0.75rem" }}>{details.sha256}</code></div>
                  {details.video_info && (
                    <>
                      <div className="result-field"><span>Video Duration</span><strong>{formatTime(details.video_info.duration_seconds)}</strong></div>
                      <div className="result-field"><span>Detected Language</span><strong>{details.video_info.language}</strong></div>
                    </>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function EmptyState({ title, text }) {
  return (
    <div className="empty-state">
      <div className="empty-icon"><BookOpen size={22} /></div>
      <strong>{title}</strong>
      <p>{text}</p>
    </div>
  );
}

function KnowledgeSearch({ run }) {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [matches, setMatches] = useState([]);

  async function search(e) {
    e.preventDefault();
    if (!query.trim()) return;
    const data = await run(() => api("/api/search", { method: "POST", body: JSON.stringify({ query, top_k: Number(topK) }) }));
    if (data) setMatches(data.matches || []);
  }

  return (
    <>
      <PageHeading title="Knowledge search" description="Search indexed learning material and inspect the source location for each match." />
      <div className="panel">
        <form className="search-form" onSubmit={search}>
          <div className="field grow">
            <label>Search query</label>
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. Explain gradient descent..." />
          </div>
          <div className="field topk-field">
            <label>Results</label>
            <select value={topK} onChange={(e) => setTopK(e.target.value)}>
              {[3, 5, 8, 10, 15, 20].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <button className="btn btn-primary" disabled={!query.trim()}><Search size={16} /> Search</button>
        </form>
      </div>
      <div className="results-header"><h2>Search results</h2><span>{matches.length} matches</span></div>
      {matches.length ? matches.map((item, i) => (
        <div className="source-card" key={i}>
          <div className="source-meta">
            <span>Result #{i + 1}</span>
            <span>{item.start_seconds != null ? `Timestamp ${formatTime(item.start_seconds)}` : `Location ${item.location_number ?? item.page_number ?? 1}`}</span>
          </div>
          <strong>{item.source || item.filename || "Source"}</strong>
          <p>{item.text}</p>
        </div>
      )) : (
        <EmptyState title="No results to show" text="Enter a query above to search through indexed content." />
      )}
    </>
  );
}

function Tutor({ run }) {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState([]);
  const [topK, setTopK] = useState(8);

  async function ask(e) {
    e.preventDefault();
    const q = question.trim();
    if (!q) return;
    const data = await run(() => api("/api/tutor", { method: "POST", body: JSON.stringify({ question: q, top_k: Number(topK) }) }));
    if (data) {
      setHistory((prev) => [...prev, { question: q, answer: data }]);
      setQuestion("");
    }
  }

  return (
    <>
      <PageHeading title="AI Tutor" description="Ask source-grounded questions about your uploaded materials." />
      <div className="tutor-layout">
        <div className="panel tutor-panel">
          {!history.length && <EmptyState title="What are you studying?" text="Ask a question grounded in your uploaded resources." />}
          <div className="chat-history">
            {history.map((entry, i) => (
              <div className="chat-pair" key={i}>
                <div className="chat-question"><span className="chat-avatar user-avatar">You</span><p>{entry.question}</p></div>
                <div className="chat-answer">
                  <span className="chat-avatar ai-avatar"><Brain size={17} /></span>
                  <div className="answer-content">
                    <p>{entry.answer.answer || entry.answer.response || "No answer returned."}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <form className="tutor-form" onSubmit={ask}>
            <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={3} placeholder="Ask a question..." />
            <div className="form-footer">
              <button className="btn btn-primary" disabled={!question.trim()}><Send size={16} /> Ask tutor</button>
            </div>
          </form>
        </div>
      </div>
    </>
  );
}

function Quiz({ run, documents }) {
  const [query, setQuery] = useState("");
  const [number, setNumber] = useState(5);
  const [type, setType] = useState("mcq");
  const [difficulty, setDifficulty] = useState("medium");
  const [quiz, setQuiz] = useState(null);

  async function generate(e) {
    e.preventDefault();
    const data = await run(() => api("/api/quiz/generate", {
      method: "POST",
      body: JSON.stringify({
        query: query.trim() || "Course questions",
        number_of_questions: Number(number),
        question_type: type,
        difficulty
      })
    }));
    if (data) setQuiz(data);
  }

  const questions = Array.isArray(quiz) ? quiz : quiz?.questions || [];

  return (
    <>
      <PageHeading title="Practice & quiz" description="Generate quizzes from indexed content." />
      <div className="panel">
        <form className="quiz-config" onSubmit={generate}>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Topic or concept..." />
          <button className="btn btn-primary"><ClipboardList size={16} /> Generate quiz</button>
        </form>
      </div>
      {questions.length > 0 && (
        <div className="panel">
          {questions.map((q, i) => (
            <div key={i} className="question-card">
              <h3>{q.question}</h3>
              {q.options?.map((opt, j) => <div key={j} className="option">{opt}</div>)}
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function Mastery({ mastery }) {
  return (
    <>
      <PageHeading title="Learning progress" description="Track topic mastery." />
      <div className="panel">
        {mastery.length ? mastery.map((m, i) => (
          <div key={i} className="mastery-row">
            <strong>{m.topic}</strong>
            <span>{Math.round((m.mastery || 0) * 100)}%</span>
          </div>
        )) : <EmptyState title="No mastery tracked yet" text="Complete activities to populate topic progress." />}
      </div>
    </>
  );
}

function CourseGraphPage() {
  return <PageHeading title="Course Graph" description="Visualize prerequisites and learning paths." />;
}

function RevisionPlanner() {
  return <PageHeading title="Revision Planner" description="Plan upcoming reviews." />;
}

function formatTime(seconds) {
  const val = Math.max(0, Math.floor(Number(seconds) || 0));
  const m = Math.floor(val / 60);
  const s = val % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default App;