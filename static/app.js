const views = {
  home: document.getElementById("view-home"),
  publish: document.getElementById("view-publish"),
  auth: document.getElementById("view-auth"),
};

const appMessage = document.getElementById("app-message");
const authActions = document.getElementById("auth-actions");
const lostList = document.getElementById("lost-list");
const foundList = document.getElementById("found-list");
const lostCount = document.getElementById("lost-count");
const foundCount = document.getElementById("found-count");
const matchPanel = document.getElementById("match-panel");
const matchCount = document.getElementById("match-count");
const centerLoginPrompt = document.getElementById("center-login-prompt");
const centerLoginButton = document.getElementById("center-login-button");
const publishForm = document.getElementById("publish-form");
const publishTitle = document.getElementById("publish-title");
const publishKindBadge = document.getElementById("publish-kind-badge");
const publishError = document.getElementById("publish-error");
const publishSubmit = document.getElementById("publish-submit");
const authError = document.getElementById("auth-error");
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const loginSubmit = document.getElementById("login-submit");
const registerSubmit = document.getElementById("register-submit");
const authTabLogin = document.getElementById("auth-tab-login");
const authTabRegister = document.getElementById("auth-tab-register");
const toast = document.getElementById("toast");

let currentKind = "lost";
let currentUser = null;
let isAuthenticated = false;
let toastTimer = null;

function showView(name) {
  Object.entries(views).forEach(([viewName, element]) => {
    element.hidden = viewName !== name;
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function makeElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = text;
  return element;
}

function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    toast.hidden = true;
  }, 3600);
}

function showAppMessage(message) {
  appMessage.textContent = message;
  appMessage.hidden = !message;
}

function hideFormError(element) {
  element.textContent = "";
  element.hidden = true;
}

function showFormError(element, message) {
  element.textContent = message;
  element.hidden = false;
}

function kindLabel(kind) {
  return kind === "lost" ? "失主" : "捡到者";
}

function ownKindLabel(kind) {
  return kind === "lost" ? "我的丢失信息" : "我的捡到信息";
}

function formatSimilarity(value) {
  return `${Math.round(Math.max(0, Math.min(1, Number(value))) * 100)}%`;
}

function locationText(location) {
  return location ? `地点：${location}` : "地点未填写";
}

function timeText(value) {
  return value ? `时间：${value}` : "时间未填写";
}

async function apiRequest(url, options = {}) {
  let response;
  try {
    response = await fetch(url, options);
  } catch {
    throw new Error("无法连接服务器，请确认服务已启动并检查网络。");
  }

  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    const detail = body && body.detail;
    if (typeof detail === "string" && detail.trim()) {
      throw new Error(detail);
    }
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => item && item.msg)
        .filter(Boolean)
        .map((message) => String(message).replace(/^Value error,\s*/, ""));
      throw new Error(messages.length ? messages.join("；") : "输入内容不符合要求。");
    }
    throw new Error(`请求失败（HTTP ${response.status}）。`);
  }
  return body || {};
}

async function loadHome() {
  showView("home");
  showAppMessage("");
  lostCount.textContent = "加载中";
  foundCount.textContent = "加载中";
  matchCount.textContent = "加载中";
  lostList.replaceChildren(makeElement("div", "empty-card", "正在读取丢失信息…"));
  foundList.replaceChildren(makeElement("div", "empty-card", "正在读取捡到信息…"));
  matchPanel.replaceChildren(makeElement("div", "empty-card", "正在读取匹配…"));

  try {
    const data = await apiRequest("/api/home");
    currentUser = data.user || null;
    isAuthenticated = Boolean(data.authenticated && currentUser);
    renderAuthActions();
    renderBoard(data.lost_posts || [], data.found_posts || []);
    renderMatches(data.match_groups || []);
  } catch (error) {
    currentUser = null;
    isAuthenticated = false;
    renderAuthActions();
    lostCount.textContent = "读取失败";
    foundCount.textContent = "读取失败";
    matchCount.textContent = "—";
    lostList.replaceChildren(makeElement("div", "empty-card", error.message));
    foundList.replaceChildren(makeElement("div", "empty-card", error.message));
    matchPanel.replaceChildren(makeElement("div", "empty-card", error.message));
    showAppMessage(error.message);
  }
}

function renderAuthActions() {
  authActions.replaceChildren();
  if (isAuthenticated && currentUser) {
    authActions.append(makeElement("span", "current-user", currentUser.username));
    const logoutButton = makeElement("button", "ghost-button", "退出");
    logoutButton.type = "button";
    logoutButton.addEventListener("click", logout);
    authActions.append(logoutButton);
    return;
  }

  const authButton = makeElement("button", "ghost-button", "登录 / 注册");
  authButton.type = "button";
  authButton.addEventListener("click", () => openAuth("login"));
  authActions.append(authButton);
}

function renderBoard(lostPosts, foundPosts) {
  renderPostList(lostList, lostCount, lostPosts, "还没有丢失信息。");
  renderPostList(foundList, foundCount, foundPosts, "还没有捡到信息。");
}

function renderPostList(container, counter, posts, emptyText) {
  counter.textContent = `${posts.length} 条`;
  if (!posts.length) {
    container.replaceChildren(makeElement("div", "empty-card", emptyText));
    return;
  }

  const cards = posts.map((post) => {
    const card = makeElement("article", `post-card${post.is_mine ? " mine" : ""}`);
    const top = makeElement("div", "post-card-top");
    top.append(makeElement("span", "post-meta", `发布者：${post.username}`));
    if (post.is_mine) top.append(makeElement("span", "mine-pill", "我的"));
    const description = makeElement("p", "post-description", post.description);
    const meta = makeElement(
      "p",
      "post-meta",
      `${locationText(post.location)} · ${timeText(post.happened_at)}`
    );
    card.append(top, description, meta);
    return card;
  });
  container.replaceChildren(...cards);
}

function renderMatches(groups) {
  if (!isAuthenticated) {
    matchCount.textContent = "登录后查看";
    matchPanel.replaceChildren();
    centerLoginPrompt.hidden = false;
    return;
  }

  centerLoginPrompt.hidden = true;
  const totalMatches = groups.reduce((total, group) => total + group.matches.length, 0);
  matchCount.textContent = `${totalMatches} 条`;
  if (!groups.length) {
    matchPanel.replaceChildren(
      makeElement("div", "empty-card", "暂时没有达到 70% 的匹配。发布后会继续自动匹配。")
    );
    return;
  }

  matchPanel.replaceChildren(...groups.map(renderMatchGroup));
}

function renderMatchGroup(group) {
  const wrapper = makeElement("section", "match-group");
  const header = makeElement("header", "match-group-header");
  header.append(
    makeElement("span", "match-tag", ownKindLabel(group.report.kind)),
    makeElement("h3", "", group.report.description),
    makeElement(
      "p",
      "match-meta",
      `${locationText(group.report.location)} · ${timeText(group.report.happened_at)}`
    )
  );

  const body = makeElement("div", "match-group-body");
  body.append(...group.matches.map(renderMatchCard));
  wrapper.append(header, body);

  const confirmButton = makeElement("button", "confirm-button", "确认找到");
  confirmButton.type = "button";
  confirmButton.addEventListener("click", () => confirmFound(group.report.id, confirmButton));
  wrapper.append(confirmButton);
  return wrapper;
}

function renderMatchCard(match) {
  const card = makeElement("article", "match-card");
  const top = makeElement("div", "match-top");
  top.append(
    makeElement("span", "match-tag", kindLabel(match.other_kind)),
    makeElement("span", "similarity-pill", formatSimilarity(match.similarity))
  );

  const description = makeElement("p", "match-description", match.other_description);
  const meta = makeElement(
    "p",
    "match-meta",
    `${locationText(match.other_location)} · ${timeText(match.other_happened_at)}`
  );

  const actions = makeElement("div", "match-actions");
  const matchButton = makeElement("button", "match-button", "匹配");
  matchButton.type = "button";
  const contactPanel = makeElement("div", "contact-panel");
  contactPanel.hidden = true;
  contactPanel.append(
    contactRow("我", match.own_username, match.own_contact),
    contactRow("对方", match.other_username, match.other_contact)
  );
  matchButton.addEventListener("click", () => {
    contactPanel.hidden = !contactPanel.hidden;
    matchButton.textContent = contactPanel.hidden ? "匹配" : "收起联系方式";
  });
  actions.append(matchButton);

  card.append(top, description, meta, actions, contactPanel);
  return card;
}

function contactRow(label, username, contact) {
  const row = makeElement("div", "contact-row");
  row.append(
    makeElement("span", "", `${label}：${username}`),
    makeElement("strong", "", contact)
  );
  return row;
}

async function confirmFound(reportId, button) {
  const confirmed = window.confirm(
    "确认已经找到？这会删除你的这条发布，并删除所有与它达到 70% 匹配的对方发布。"
  );
  if (!confirmed) return;

  button.disabled = true;
  try {
    await apiRequest(`/api/reports/${reportId}/complete`, { method: "POST" });
    await loadHome();
    showToast("已确认找到，相关发布和匹配已删除。");
  } catch (error) {
    showToast(error.message);
    button.disabled = false;
  }
}

function openPublish(kind) {
  if (!isAuthenticated) {
    openAuth("login", "请先登录后再发布信息。");
    return;
  }
  currentKind = kind;
  publishForm.reset();
  hideFormError(publishError);
  publishKindBadge.textContent = kind === "lost" ? "丢失" : "捡到";
  publishKindBadge.classList.toggle("found", kind === "found");
  publishTitle.textContent = kind === "lost" ? "发布丢失信息" : "发布捡到信息";
  showView("publish");
  document.getElementById("publish-description").focus();
}

async function submitPublish(event) {
  event.preventDefault();
  hideFormError(publishError);

  const description = document.getElementById("publish-description").value.trim();
  const contact = document.getElementById("publish-contact").value.trim();
  if (!description) {
    showFormError(publishError, "请先写一句物品描述。");
    return;
  }
  if (!contact) {
    showFormError(publishError, "请填写联系方式。");
    return;
  }

  publishSubmit.disabled = true;
  publishSubmit.textContent = "正在计算匹配…";
  try {
    const result = await apiRequest("/api/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: currentKind,
        description,
        location: document.getElementById("publish-location").value.trim() || null,
        happened_at: document.getElementById("publish-happened-at").value || null,
        contact,
      }),
    });
    await loadHome();
    showToast(
      result.match_count > 0
        ? `发布成功，找到 ${result.match_count} 条 70% 以上匹配。`
        : "发布成功，已进入池子并继续等待匹配。"
    );
  } catch (error) {
    if (error.message.includes("请先登录")) {
      openAuth("login", error.message);
    } else {
      showFormError(publishError, error.message);
    }
  } finally {
    publishSubmit.disabled = false;
    publishSubmit.textContent = "发布并匹配";
  }
}

function openAuth(mode, message = "") {
  switchAuthMode(mode || "login");
  hideFormError(authError);
  document.getElementById("login-form").reset();
  document.getElementById("register-form").reset();
  showView("auth");
  if (message) showAppMessage(message);
}

function switchAuthMode(mode) {
  const isLogin = mode !== "register";
  loginForm.hidden = !isLogin;
  registerForm.hidden = isLogin;
  authTabLogin.classList.toggle("active", isLogin);
  authTabRegister.classList.toggle("active", !isLogin);
  hideFormError(authError);
}

async function submitLogin(event) {
  event.preventDefault();
  hideFormError(authError);
  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value;
  if (!username || !password) {
    showFormError(authError, "请输入用户名和密码。");
    return;
  }

  loginSubmit.disabled = true;
  loginSubmit.textContent = "正在登录…";
  try {
    await apiRequest("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    await loadHome();
    showToast("登录成功，已进入主界面。");
  } catch (error) {
    showFormError(authError, error.message);
  } finally {
    loginSubmit.disabled = false;
    loginSubmit.textContent = "登录";
  }
}

async function submitRegister(event) {
  event.preventDefault();
  hideFormError(authError);
  const username = document.getElementById("register-username").value.trim();
  const password = document.getElementById("register-password").value;
  const confirmPassword = document.getElementById("register-confirm").value;
  if (password !== confirmPassword) {
    showFormError(authError, "两次输入的密码不一致。");
    return;
  }

  registerSubmit.disabled = true;
  registerSubmit.textContent = "正在注册…";
  try {
    await apiRequest("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    await loadHome();
    showToast("注册成功，已自动登录。");
  } catch (error) {
    showFormError(authError, error.message);
  } finally {
    registerSubmit.disabled = false;
    registerSubmit.textContent = "注册并登录";
  }
}

async function logout() {
  try {
    await apiRequest("/api/auth/logout", { method: "POST" });
  } catch (error) {
    showToast(error.message);
  }
  currentUser = null;
  isAuthenticated = false;
  await loadHome();
}

document.querySelectorAll("[data-kind]").forEach((button) => {
  button.addEventListener("click", () => openPublish(button.dataset.kind));
});
centerLoginButton.addEventListener("click", () => openAuth("login", "登录后查看自己的匹配。"));
authTabLogin.addEventListener("click", () => switchAuthMode("login"));
authTabRegister.addEventListener("click", () => switchAuthMode("register"));
document.getElementById("publish-cancel").addEventListener("click", loadHome);
document.getElementById("auth-cancel").addEventListener("click", loadHome);
publishForm.addEventListener("submit", submitPublish);
loginForm.addEventListener("submit", submitLogin);
registerForm.addEventListener("submit", submitRegister);

window.addEventListener("unhandledrejection", (event) => {
  event.preventDefault();
  showToast(event.reason && event.reason.message ? event.reason.message : "页面遇到异常，请重试。");
});

loadHome();

