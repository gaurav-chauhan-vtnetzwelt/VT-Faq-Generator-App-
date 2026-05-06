(function () {
  const API = "";
  const TOKEN_KEY = "faq_saas_token";
  const CACHE_PREFIX = "faq_saas_cache_v1";

  const COUNTRIES = [
    { value: "", label: "Any / generic" },
    { value: "United States", label: "United States" },
    { value: "United Kingdom", label: "United Kingdom" },
    { value: "Canada", label: "Canada" },
    { value: "Australia", label: "Australia" },
    { value: "Germany", label: "Germany" },
    { value: "France", label: "France" },
    { value: "Spain", label: "Spain" },
    { value: "Italy", label: "Italy" },
    { value: "Netherlands", label: "Netherlands" },
    { value: "India", label: "India" },
    { value: "Brazil", label: "Brazil" },
    { value: "Mexico", label: "Mexico" },
    { value: "Japan", label: "Japan" },
    { value: "Singapore", label: "Singapore" },
    { value: "United Arab Emirates", label: "United Arab Emirates" },
    { value: "South Africa", label: "South Africa" },
  ];

  const LANGUAGES = [
    { value: "", label: "Default / infer from site" },
    { value: "English", label: "English" },
    { value: "Spanish", label: "Spanish" },
    { value: "German", label: "German" },
    { value: "French", label: "French" },
    { value: "Italian", label: "Italian" },
    { value: "Portuguese", label: "Portuguese" },
    { value: "Dutch", label: "Dutch" },
    { value: "Hindi", label: "Hindi" },
    { value: "Japanese", label: "Japanese" },
    { value: "Arabic", label: "Arabic" },
    { value: "Chinese (Simplified)", label: "Chinese (Simplified)" },
  ];

  const state = {
    selectedProjectId: null,
    selectedProjectName: "",
    projects: [],
    lastFaqs: [],
    me: null,
    cache: {
      projects: [],
      historyByProject: {},
      lastFaqsByProject: {},
      selectedProjectId: null,
    },
  };

  function getToken() {
    return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
  }

  function setAuth(token) {
    localStorage.setItem(TOKEN_KEY, token);
    sessionStorage.setItem(TOKEN_KEY, token);
  }

  function clearAuth() {
    localStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
    state.me = null;
    state.selectedProjectId = null;
    state.selectedProjectName = "";
    state.projects = [];
    state.lastFaqs = [];
    state.cache = {
      projects: [],
      historyByProject: {},
      lastFaqsByProject: {},
      selectedProjectId: null,
    };
  }

  function _cacheKey() {
    if (!state.me) return null;
    var userPart = state.me.id || state.me.username || "anon";
    return CACHE_PREFIX + ":" + userPart;
  }

  function loadCache() {
    var k = _cacheKey();
    if (!k) return;
    try {
      var raw = localStorage.getItem(k);
      if (!raw) return;
      var data = JSON.parse(raw);
      state.cache = {
        projects: Array.isArray(data.projects) ? data.projects : [],
        historyByProject: data.historyByProject || {},
        lastFaqsByProject: data.lastFaqsByProject || {},
        selectedProjectId: data.selectedProjectId || null,
      };
    } catch (_) {}
  }

  function saveCache() {
    var k = _cacheKey();
    if (!k) return;
    try {
      localStorage.setItem(k, JSON.stringify(state.cache));
    } catch (_) {}
  }

  /** Authenticated fetch; redirects to login on 401 */
  function apiFetch(path, opts) {
    opts = opts || {};
    opts.headers = opts.headers || {};
    var tok = getToken();
    if (tok) opts.headers.Authorization = "Bearer " + tok;
    return fetch(API + path, opts).then(function (res) {
      if (res.status === 401) {
        clearAuth();
        showLoginOnly();
      }
      return res;
    });
  }

  const els = {
    loginOverlay: document.getElementById("login-overlay"),
    loginForm: document.getElementById("login-form"),
    loginUser: document.getElementById("login-user"),
    loginPass: document.getElementById("login-pass"),
    loginError: document.getElementById("login-error"),
    loginSubmit: document.getElementById("login-submit"),
    mainApp: document.getElementById("main-app"),
    whoami: document.getElementById("whoami"),
    btnAdmin: document.getElementById("btn-admin"),
    btnLogout: document.getElementById("btn-logout"),
    adminOverlay: document.getElementById("admin-overlay"),
    btnAdminClose: document.getElementById("btn-admin-close"),
    adminStats: document.getElementById("admin-stats"),
    adminNewUser: document.getElementById("admin-new-user"),
    newUserName: document.getElementById("new-user-name"),
    newUserPass: document.getElementById("new-user-pass"),
    newUserRole: document.getElementById("new-user-role"),
    adminUserMsg: document.getElementById("admin-user-msg"),
    adminUserList: document.getElementById("admin-user-list"),
    projectList: document.getElementById("project-list"),
    projectsEmpty: document.getElementById("projects-empty"),
    workspaceTitle: document.getElementById("workspace-title"),
    noProject: document.getElementById("no-project"),
    workspace: document.getElementById("workspace"),
    urlList: document.getElementById("url-list"),
    addUrlBtn: document.getElementById("add-url"),
    sitemap: document.getElementById("sitemap-url"),
    faqCount: document.getElementById("faq-count"),
    faqCountLabel: document.getElementById("faq-count-value"),
    keywords: document.getElementById("keywords"),
    country: document.getElementById("country"),
    language: document.getElementById("language"),
    pageType: document.getElementById("page-type"),
    industryNiche: document.getElementById("industry-niche"),
    form: document.getElementById("generate-form"),
    generateBtn: document.getElementById("generate-btn"),
    error: document.getElementById("error-message"),
    results: document.getElementById("results"),
    faqList: document.getElementById("faq-list"),
    schemaPre: document.getElementById("schema-json"),
    copySchemaBtn: document.getElementById("copy-schema"),
    emptyState: document.getElementById("empty-state"),
    historyList: document.getElementById("history-list"),
    historyEmpty: document.getElementById("history-empty"),
    demoBadge: document.getElementById("demo-badge"),
    modalOverlay: document.getElementById("modal-overlay"),
    btnNewProject: document.getElementById("btn-new-project"),
    projectForm: document.getElementById("project-form"),
    modalCancel: document.getElementById("modal-cancel"),
    projectName: document.getElementById("project-name"),
    projectDesc: document.getElementById("project-desc"),
  };

  function showLoginOnly() {
    els.loginOverlay.hidden = false;
    els.mainApp.hidden = true;
    els.adminOverlay.hidden = true;
  }

  function showMainApp() {
    els.loginOverlay.hidden = true;
    els.mainApp.hidden = false;
    if (state.me) {
      els.whoami.textContent = state.me.username + " · " + state.me.role;
      els.btnAdmin.hidden = state.me.role !== "admin";
    }
  }

  async function validateSession() {
    var t = getToken();
    if (!t) return false;
    try {
      var res = await fetch(API + "/api/auth/me", {
        headers: { Authorization: "Bearer " + t },
      });
      if (!res.ok) return false;
      state.me = await res.json();
      return true;
    } catch (e) {
      return false;
    }
  }

  function fillSelect(select, items) {
    select.innerHTML = "";
    items.forEach(function (item) {
      const opt = document.createElement("option");
      opt.value = item.value;
      opt.textContent = item.label;
      select.appendChild(opt);
    });
  }

  function showError(msg) {
    els.error.hidden = !msg;
    els.error.textContent = msg || "";
  }

  function escapeAttr(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML.replace(/"/g, "&quot;");
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function stripHtmlToPlain(htmlOrText) {
    if (htmlOrText == null || htmlOrText === "") return "";
    var s = String(htmlOrText);
    s = s.replace(/<a\s[^>]*\bhref\s*=\s*["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi, function (
      _,
      url,
      inner
    ) {
      var label = inner.replace(/<[^>]+>/g, "").trim();
      return label ? label + " (" + url + ")" : url;
    });
    s = s.replace(/<[^>]+>/g, "");
    return s.replace(/\s+/g, " ").trim();
  }

  function sanitizeAnswerHtml(raw) {
    if (raw == null || raw === "") return "";
    var text = String(raw);
    if (!/<a\s/i.test(text)) {
      return escapeHtml(text);
    }
    var out = "";
    var last = 0;
    var re = /<a\s[^>]*\bhref\s*=\s*["'](https?:\/\/[^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi;
    var m;
    while ((m = re.exec(text)) !== null) {
      out += escapeHtml(text.slice(last, m.index));
      var href = m[1];
      var innerText = (m[2] || "").replace(/<[^>]+>/g, "").trim();
      var label = innerText || href;
      out +=
        '<a href="' +
        escapeAttr(href) +
        '" class="faq-inline-link" target="_blank" rel="noopener noreferrer">' +
        escapeHtml(label) +
        "</a>";
      last = re.lastIndex;
    }
    out += escapeHtml(text.slice(last));
    return out;
  }

  function buildUrlRows(urls) {
    els.urlList.innerHTML = "";
    urls.forEach(function (url) {
      const row = document.createElement("div");
      row.className = "url-row";
      row.innerHTML =
        '<input type="url" class="input-field url-input" placeholder="https://example.com" value="' +
        escapeAttr(url) +
        '" />' +
        (urls.length > 1
          ? '<button type="button" class="btn btn-ghost remove-url" aria-label="Remove URL">×</button>'
          : "");
      els.urlList.appendChild(row);
    });

    els.urlList.querySelectorAll(".remove-url").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const rows = els.urlList.querySelectorAll(".url-row");
        if (rows.length <= 1) return;
        btn.closest(".url-row").remove();
      });
    });
  }

  function getUrls() {
    const inputs = els.urlList.querySelectorAll(".url-input");
    return Array.from(inputs).map(function (i) {
      return i.value.trim();
    });
  }

  function schemaMarkup(faqs) {
    return JSON.stringify(
      {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        mainEntity: faqs.map(function (f) {
          return {
            "@type": "Question",
            name: f.question,
            acceptedAnswer: {
              "@type": "Answer",
              text: stripHtmlToPlain(f.answer),
            },
          };
        }),
      },
      null,
      2
    );
  }

  function renderFaqs(faqs) {
    state.lastFaqs = faqs || [];
    if (state.selectedProjectId) {
      state.cache.lastFaqsByProject[state.selectedProjectId] = state.lastFaqs;
      saveCache();
    }
    els.faqList.innerHTML = "";
    (faqs || []).forEach(function (f, i) {
      const article = document.createElement("article");
      article.className = "faq-item";
      article.innerHTML =
        '<div class="faq-question"><span class="faq-number">Q' +
        (i + 1) +
        "</span><span>" +
        escapeHtml(f.question) +
        '</span></div><div class="faq-answer">' +
        sanitizeAnswerHtml(f.answer) +
        "</div>";
      els.faqList.appendChild(article);
    });

    const json = schemaMarkup(faqs || []);
    els.schemaPre.textContent = json;
    els.results.hidden = false;
    els.emptyState.hidden = true;

    els.copySchemaBtn.onclick = function () {
      navigator.clipboard.writeText(json).then(function () {
        const t = els.copySchemaBtn.textContent;
        els.copySchemaBtn.textContent = "Copied";
        setTimeout(function () {
          els.copySchemaBtn.textContent = t;
        }, 2000);
      });
    };
  }

  async function fetchProjects() {
    try {
      const res = await apiFetch("/api/projects");
      const data = await res.json().catch(function () {
        return {};
      });
      if (!res.ok) throw new Error(data.detail || "Failed to load projects");
      state.projects = data.projects || [];
      state.cache.projects = state.projects;
      saveCache();
      renderProjectList();
    } catch (e) {
      if (state.cache.projects && state.cache.projects.length) {
        state.projects = state.cache.projects;
        renderProjectList();
        return;
      }
      throw e;
    }
  }

  function renderProjectList() {
    els.projectList.innerHTML = "";
    els.projectsEmpty.hidden = state.projects.length > 0;

    state.projects.forEach(function (p) {
      const id = p._id;
      const name = p.name || "Untitled";
      const li = document.createElement("li");
      li.className = "project-row";

      const selectBtn = document.createElement("button");
      selectBtn.type = "button";
      selectBtn.className =
        "project-item" + (state.selectedProjectId === id ? " active" : "");
      selectBtn.setAttribute("title", "Open project");
      selectBtn.innerHTML =
        '<span class="project-item-name">' + escapeHtml(name) + "</span>";

      selectBtn.addEventListener("click", function () {
        selectProject(id, name);
      });

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "project-delete";
      delBtn.setAttribute("aria-label", "Delete project");
      delBtn.setAttribute("title", "Delete project");
      delBtn.textContent = "×";

      delBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        e.preventDefault();
        if (!confirm("Delete this project and its linked history entries?")) return;
        deleteProject(id);
      });

      li.appendChild(selectBtn);
      li.appendChild(delBtn);
      els.projectList.appendChild(li);
    });
  }

  async function deleteProject(id) {
    try {
      const res = await apiFetch("/api/projects/" + encodeURIComponent(id), {
        method: "DELETE",
      });
      if (!res.ok) {
        const d = await res.json().catch(function () {
          return {};
        });
        throw new Error(d.detail || "Delete failed");
      }
      if (state.selectedProjectId === id) {
        state.selectedProjectId = null;
        state.selectedProjectName = "";
        state.cache.selectedProjectId = null;
        els.workspace.hidden = true;
        els.noProject.hidden = false;
        els.workspaceTitle.textContent = "Select or create a project";
      }
      delete state.cache.historyByProject[id];
      delete state.cache.lastFaqsByProject[id];
      saveCache();
      await fetchProjects();
    } catch (e) {
      alert(e.message || "Could not delete");
    }
  }

  function selectProject(id, name) {
    state.selectedProjectId = id;
    state.selectedProjectName = name || "Project";
    state.cache.selectedProjectId = id;
    saveCache();
    els.noProject.hidden = true;
    els.workspace.hidden = false;
    els.workspaceTitle.textContent = state.selectedProjectName;
    renderProjectList();
    loadHistory();
    showError("");
    var cachedFaqs = state.cache.lastFaqsByProject[id];
    if (cachedFaqs && cachedFaqs.length) {
      renderFaqs(cachedFaqs);
    } else {
      els.results.hidden = true;
      els.emptyState.hidden = false;
    }
  }

  function formatWhen(iso) {
    if (!iso) return "";
    try {
      const d = new Date(iso);
      return d.toLocaleString();
    } catch (e) {
      return String(iso);
    }
  }

  async function loadHistory() {
    els.historyList.innerHTML = "";
    if (!state.selectedProjectId) return;

    let items = [];
    try {
      const path =
        "/api/history?project_id=" +
        encodeURIComponent(state.selectedProjectId) +
        "&limit=40";
      const res = await apiFetch(path);
      const data = await res.json().catch(function () {
        return {};
      });
      if (!res.ok) throw new Error(data.detail || "History load failed");
      items = data.history || [];
      if (items.length) {
        state.cache.historyByProject[state.selectedProjectId] = items;
        saveCache();
      } else if (state.cache.historyByProject[state.selectedProjectId]) {
        // Backend reset / mock DB restart: prefer browser cache to preserve UX.
        items = state.cache.historyByProject[state.selectedProjectId] || [];
      }
    } catch (_) {
      items = state.cache.historyByProject[state.selectedProjectId] || [];
    }
    els.historyEmpty.hidden = items.length > 0;

    items.forEach(function (h) {
      const parts = [];
      if (h.industry_niche) parts.push(h.industry_niche);
      if (h.keywords) parts.push("Keywords: " + h.keywords);
      if (h.language) parts.push(h.language);
      if (h.page_type) parts.push(h.page_type);
      const snippet = parts.join(" · ") || (h.result_count || 0) + " FAQs";

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "history-item";
      btn.innerHTML =
        '<div class="history-meta">' +
        escapeHtml(formatWhen(h.created_at)) +
        "</div>" +
        '<div class="history-snippet">' +
        escapeHtml(snippet) +
        "</div>";

      btn.addEventListener("click", function () {
        renderFaqs(h.faqs || []);
      });

      const li = document.createElement("li");
      li.appendChild(btn);
      els.historyList.appendChild(li);
    });
  }

  async function exportFile(format) {
    if (!state.lastFaqs.length) return;
    const title =
      (state.selectedProjectName || "FAQs").replace(/[^\w\s\-]/g, "").trim() || "FAQs";
    const res = await apiFetch("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        format: format,
        faqs: state.lastFaqs.map(function (f) {
          return { question: f.question, answer: f.answer };
        }),
        title: title,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(function () {
        return {};
      });
      throw new Error(err.detail || "Export failed");
    }
    const blob = await res.blob();
    const cd = res.headers.get("Content-Disposition") || "";
    let filename = "download";
    const m = /filename="([^"]+)"/.exec(cd);
    if (m) filename = m[1];
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function openModal() {
    els.modalOverlay.hidden = false;
    els.projectName.value = "";
    els.projectDesc.value = "";
    els.projectName.focus();
  }

  function closeModal() {
    els.modalOverlay.hidden = true;
  }

  async function loadAdminPanel() {
    els.adminUserMsg.textContent = "";
    try {
      const sr = await apiFetch("/api/admin/stats");
      const st = await sr.json();
      if (!sr.ok) throw new Error(st.detail || "Stats failed");
      els.adminStats.innerHTML =
        '<div class="stat-card"><div class="stat-num">' +
        st.users +
        '</div><div class="stat-label">Users</div></div>' +
        '<div class="stat-card"><div class="stat-num">' +
        st.projects +
        '</div><div class="stat-label">Projects</div></div>' +
        '<div class="stat-card"><div class="stat-num">' +
        st.history_runs +
        '</div><div class="stat-label">Generation runs</div></div>' +
        '<div class="stat-card"><div class="stat-num">' +
        st.faqs_generated_total +
        '</div><div class="stat-label">FAQs (total count)</div></div>';

      const ur = await apiFetch("/api/admin/users");
      const ud = await ur.json();
      if (!ur.ok) throw new Error(ud.detail || "Users list failed");
      els.adminUserList.innerHTML = "";
      (ud.users || []).forEach(function (u) {
        const li = document.createElement("li");
        li.className = "admin-user-row";
        var delBtn =
          '<button type="button" class="btn btn-ghost btn-sm admin-del-user" data-id="' +
          escapeAttr(u.id) +
          '">Remove</button>';
        li.innerHTML =
          "<span>" +
          escapeHtml(u.username) +
          '</span> <span class="muted">' +
          escapeHtml(u.role) +
          "</span> " +
          delBtn;
        els.adminUserList.appendChild(li);
      });
      els.adminUserList.querySelectorAll(".admin-del-user").forEach(function (btn) {
        btn.addEventListener("click", async function () {
          var uid = btn.getAttribute("data-id");
          if (!confirm("Remove this user?")) return;
          var dr = await apiFetch("/api/admin/users/" + encodeURIComponent(uid), {
            method: "DELETE",
          });
          var dd = await dr.json().catch(function () {
            return {};
          });
          if (!dr.ok) {
            alert(dd.detail || "Delete failed");
            return;
          }
          loadAdminPanel();
        });
      });
    } catch (e) {
      els.adminUserMsg.textContent = e.message || "Could not load admin data";
    }
  }

  /** ---------- Init ---------- */
  fillSelect(els.country, COUNTRIES);
  fillSelect(els.language, LANGUAGES);
  buildUrlRows(["https://example.com"]);

  els.loginForm.addEventListener("submit", async function (e) {
    e.preventDefault();
    els.loginError.hidden = true;
    els.loginSubmit.disabled = true;
    try {
      var res = await fetch(API + "/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: els.loginUser.value.trim(),
          password: els.loginPass.value,
        }),
      });
      var data = await res.json().catch(function () {
        return {};
      });
      if (!res.ok) {
        els.loginError.textContent =
          typeof data.detail === "string" ? data.detail : "Login failed";
        els.loginError.hidden = false;
        return;
      }
      setAuth(data.access_token);
      state.me = data.user;
      loadCache();
      els.loginPass.value = "";
      showMainApp();
      fetch(API + "/api/health")
        .then(function (r) {
          return r.json();
        })
        .then(function (h) {
          if (h && h.demo_mode) els.demoBadge.hidden = false;
        })
        .catch(function () {});
      fetchProjects().catch(function () {
        els.projectsEmpty.textContent = "Could not load projects.";
        els.projectsEmpty.hidden = false;
      });
      if (state.cache.selectedProjectId) {
        var picked = (state.cache.projects || []).find(function (p) {
          return p && p._id === state.cache.selectedProjectId;
        });
        if (picked) selectProject(picked._id, picked.name || "Project");
      }
    } finally {
      els.loginSubmit.disabled = false;
    }
  });

  els.btnLogout.addEventListener("click", function () {
    clearAuth();
    showLoginOnly();
  });

  els.btnAdmin.addEventListener("click", function () {
    els.adminOverlay.hidden = false;
    loadAdminPanel();
  });

  els.btnAdminClose.addEventListener("click", function () {
    els.adminOverlay.hidden = true;
  });

  els.adminOverlay.addEventListener("click", function (e) {
    if (e.target === els.adminOverlay) els.adminOverlay.hidden = true;
  });

  els.adminNewUser.addEventListener("submit", async function (e) {
    e.preventDefault();
    els.adminUserMsg.textContent = "";
    var name = els.newUserName.value.trim();
    var pass = els.newUserPass.value;
    if (pass.length < 6) {
      els.adminUserMsg.textContent = "Password must be at least 6 characters.";
      return;
    }
    var res = await apiFetch("/api/admin/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: name,
        password: pass,
        role: els.newUserRole.value,
      }),
    });
    var data = await res.json().catch(function () {
      return {};
    });
    if (!res.ok) {
      els.adminUserMsg.textContent = data.detail || "Could not create user";
      return;
    }
    els.newUserName.value = "";
    els.newUserPass.value = "";
    loadAdminPanel();
  });

  els.addUrlBtn.addEventListener("click", function () {
    const rows = els.urlList.querySelectorAll(".url-row");
    if (rows.length >= 10) return;
    buildUrlRows(getUrls().concat(""));
  });

  els.faqCount.addEventListener("input", function () {
    els.faqCountLabel.textContent = els.faqCount.value;
  });

  els.btnNewProject.addEventListener("click", openModal);
  els.modalCancel.addEventListener("click", closeModal);
  els.modalOverlay.addEventListener("click", function (e) {
    if (e.target === els.modalOverlay) closeModal();
  });

  els.projectForm.addEventListener("submit", async function (e) {
    e.preventDefault();
    const name = els.projectName.value.trim();
    if (!name) return;
    try {
      const res = await apiFetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name,
          description: els.projectDesc.value.trim() || "",
          urls: [],
        }),
      });
      const data = await res.json().catch(function () {
        return {};
      });
      if (!res.ok) throw new Error(data.detail || "Could not create project");
      closeModal();
      await fetchProjects();
      var createdId = data.id;
      if (createdId) {
        state.cache.selectedProjectId = createdId;
        saveCache();
      }
      selectProject(createdId, name);
    } catch (err) {
      alert(err.message || "Error");
    }
  });

  els.form.addEventListener("submit", async function (e) {
    e.preventDefault();
    if (!state.selectedProjectId) {
      showError("Select a project first.");
      return;
    }

    showError("");
    const urls = getUrls().filter(Boolean);
    if (urls.length === 0) {
      showError("Please enter at least one URL.");
      return;
    }

    const body = {
      urls: urls,
      faq_count: parseInt(els.faqCount.value, 10),
      sitemap_url: els.sitemap.value.trim() || null,
      project_id: state.selectedProjectId,
      keywords: els.keywords.value.trim() || null,
      country: els.country.value.trim() || null,
      language: els.language.value.trim() || null,
      page_type: els.pageType.value.trim() || null,
      industry_niche: els.industryNiche.value.trim() || null,
    };

    els.generateBtn.disabled = true;
    els.generateBtn.textContent = "Generating…";

    try {
      const res = await apiFetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const data = await res.json().catch(function () {
        return {};
      });

      if (!res.ok) {
        let detail = data.detail || "Failed to generate FAQs.";
        if (Array.isArray(detail)) {
          detail = detail
            .map(function (er) {
              return er.msg || String(er);
            })
            .join(" ");
        } else if (typeof detail !== "string") {
          detail = JSON.stringify(detail);
        }
        throw new Error(detail);
      }

      renderFaqs(data.faqs || []);
      await loadHistory();
      if (state.selectedProjectId && Array.isArray(data.faqs)) {
        state.cache.lastFaqsByProject[state.selectedProjectId] = data.faqs;
        saveCache();
      }
    } catch (err) {
      showError(err.message || "Something went wrong.");
      els.results.hidden = true;
      els.emptyState.hidden = false;
    } finally {
      els.generateBtn.disabled = false;
      els.generateBtn.textContent = "Generate FAQs";
    }
  });

  document.querySelectorAll("[data-export]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const fmt = btn.getAttribute("data-export");
      exportFile(fmt).catch(function (err) {
        alert(err.message || "Export failed");
      });
    });
  });

  validateSession().then(function (ok) {
    if (ok) {
      loadCache();
      showMainApp();
      fetch(API + "/api/health")
        .then(function (r) {
          return r.json();
        })
        .then(function (h) {
          if (h && h.demo_mode) els.demoBadge.hidden = false;
        })
        .catch(function () {});
      fetchProjects().catch(function () {
        els.projectsEmpty.textContent = "Could not load projects (API unreachable).";
        els.projectsEmpty.hidden = false;
      });
      if (state.cache.selectedProjectId) {
        var picked = (state.cache.projects || []).find(function (p) {
          return p && p._id === state.cache.selectedProjectId;
        });
        if (picked) selectProject(picked._id, picked.name || "Project");
      }
    } else {
      showLoginOnly();
    }
  });
})();
