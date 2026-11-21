// DrX Daily 社区接口（Cloudflare Pages Functions）
// 路由：/api/register /api/login /api/logout /api/me
//       /api/comments（GET 列表 / POST 发表·回复） /api/like
//       /api/admin/users /api/admin/user /api/admin/reset-password
//       /api/admin/comments /api/admin/comment
// 依赖：Pages 项目绑定 D1 数据库为 DB；可选环境变量 ADMIN_EMAIL（该邮箱注册即管理员）。
// 设计：密码 PBKDF2-SHA256 加盐哈希；会话令牌只存 SHA-256；邮箱验证从简（管理员可重置密码）。

const PBKDF2_ITER = 100000;
const SESSION_DAYS = 30;

function json(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...extraHeaders },
  });
}
function err(msg, status = 400) { return json({ ok: false, error: msg }, status); }

function parseCookies(request) {
  const out = {};
  const raw = request.headers.get("Cookie") || "";
  for (const part of raw.split(";")) {
    const i = part.indexOf("=");
    if (i > 0) out[part.slice(0, i).trim()] = decodeURIComponent(part.slice(i + 1).trim());
  }
  return out;
}
function cookieHeader(name, value, maxAgeSec) {
  return `${name}=${encodeURIComponent(value)}; Path=/; Max-Age=${maxAgeSec}; HttpOnly; Secure; SameSite=Lax`;
}
function b64(buf) {
  let s = "";
  const bytes = new Uint8Array(buf);
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
  return btoa(s);
}
function unb64(s) {
  const bin = atob(s);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}
async function sha256hex(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((x) => x.toString(16).padStart(2, "0")).join("");
}
async function hashPassword(password) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits({ name: "PBKDF2", salt, iterations: PBKDF2_ITER, hash: "SHA-256" }, key, 256);
  return `pbkdf2:${PBKDF2_ITER}:${b64(salt)}:${b64(bits)}`;
}
async function verifyPassword(password, stored) {
  try {
    const [, iter, saltB64, hashB64] = stored.split(":");
    const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(password), "PBKDF2", false, ["deriveBits"]);
    const bits = await crypto.subtle.deriveBits(
      { name: "PBKDF2", salt: unb64(saltB64), iterations: parseInt(iter, 10), hash: "SHA-256" }, key, 256);
    return b64(bits) === hashB64;
  } catch { return false; }
}
function clientIp(request) {
  return request.headers.get("CF-Connecting-IP") || "unknown";
}
async function rateLimited(env, ip, action, max, windowMin) {
  const row = await env.DB.prepare(
    "SELECT COUNT(*) AS n FROM rate_events WHERE ip = ? AND action = ? AND created_at > datetime('now', ?)"
  ).bind(ip, action, `-${windowMin} minutes`).first();
  return row && row.n >= max;
}
async function rateHit(env, ip, action) {
  await env.DB.prepare("INSERT INTO rate_events (ip, action) VALUES (?, ?)").bind(ip, action).run();
}
async function currentUser(env, request) {
  const cookies = parseCookies(request);
  const token = cookies["drx_session"];
  if (!token) return null;
  const th = await sha256hex(token);
  const s = await env.DB.prepare("SELECT user_id FROM sessions WHERE token_hash = ? AND expires_at > datetime('now')").bind(th).first();
  if (!s) return null;
  const u = await env.DB.prepare(
    "SELECT id, email, nickname, role, member_until, status FROM users WHERE id = ?").bind(s.user_id).first();
  if (!u || u.status !== "active") return null;
  return u;
}
function publicUser(u) {
  const today = new Date().toISOString().slice(0, 10);
  const isMember = u.role === "admin" || (u.role === "member" && (!u.member_until || u.member_until >= today));
  return { id: u.id, email: u.email, nickname: u.nickname, role: u.role,
           member_until: u.member_until, is_member: isMember, is_admin: u.role === "admin" };
}
async function startSession(env, userId) {
  const tokenBytes = crypto.getRandomValues(new Uint8Array(32));
  const token = [...tokenBytes].map((x) => x.toString(16).padStart(2, "0")).join("");
  const th = await sha256hex(token);
  await env.DB.prepare(
    "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, datetime('now', ?))"
  ).bind(th, userId, `+${SESSION_DAYS} days`).run();
  return cookieHeader("drx_session", token, SESSION_DAYS * 86400);
}
async function readBody(request) {
  try { return await request.json(); } catch { return {}; }
}
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
function cleanText(s, max) {
  return String(s ?? "").replace(/\s+/g, " ").trim().slice(0, max);
}

// ---------------- 账号 ----------------

async function handleRegister(env, request) {
  const ip = clientIp(request);
  if (await rateLimited(env, ip, "register", 5, 60)) return err("注册过于频繁，请稍后再试", 429);
  const b = await readBody(request);
  const email = cleanText(b.email, 120).toLowerCase();
  const nickname = cleanText(b.nickname, 30);
  const password = String(b.password ?? "");
  if (!EMAIL_RE.test(email)) return err("邮箱格式不正确");
  if (!nickname) return err("请填写昵称");
  if (password.length < 8) return err("密码至少 8 位");
  await rateHit(env, ip, "register");
  const exists = await env.DB.prepare("SELECT id FROM users WHERE email = ?").bind(email).first();
  if (exists) return err("该邮箱已注册，请直接登录", 409);
  const role = env.ADMIN_EMAIL && email === String(env.ADMIN_EMAIL).toLowerCase() ? "admin" : "user";
  const hash = await hashPassword(password);
  const r = await env.DB.prepare(
    "INSERT INTO users (email, nickname, pass_hash, role) VALUES (?, ?, ?, ?)").bind(email, nickname, hash, role).run();
  const setCookie = await startSession(env, r.meta.last_row_id);
  const u = await env.DB.prepare("SELECT id, email, nickname, role, member_until, status FROM users WHERE id = ?")
    .bind(r.meta.last_row_id).first();
  return json({ ok: true, user: publicUser(u) }, 200, { "Set-Cookie": setCookie });
}

async function handleLogin(env, request) {
  const ip = clientIp(request);
  if (await rateLimited(env, ip, "login", 15, 10)) return err("登录尝试过于频繁，请稍后再试", 429);
  const b = await readBody(request);
  const email = cleanText(b.email, 120).toLowerCase();
  const password = String(b.password ?? "");
  await rateHit(env, ip, "login");
  const u = await env.DB.prepare(
    "SELECT id, email, nickname, role, member_until, status, pass_hash FROM users WHERE email = ?").bind(email).first();
  if (!u || !(await verifyPassword(password, u.pass_hash))) return err("邮箱或密码不正确", 401);
  if (u.status !== "active") return err("该账号已被停用，请联系管理员", 403);
  const setCookie = await startSession(env, u.id);
  return json({ ok: true, user: publicUser(u) }, 200, { "Set-Cookie": setCookie });
}

async function handleLogout(env, request) {
  const cookies = parseCookies(request);
  if (cookies["drx_session"]) {
    const th = await sha256hex(cookies["drx_session"]);
    await env.DB.prepare("DELETE FROM sessions WHERE token_hash = ?").bind(th).run();
  }
  return json({ ok: true }, 200, { "Set-Cookie": cookieHeader("drx_session", "", 0) });
}

// ---------------- 留言 / 回复 / 点赞 ----------------

async function handleListComments(env, request, url) {
  const slug = cleanText(url.searchParams.get("slug"), 300);
  if (!slug) return err("缺少文章标识");
  const me = await currentUser(env, request);
  const cookies = parseCookies(request);
  const anon = cookies["drx_anon"] || "";
  const myIdentity = me ? `u${me.id}` : (anon ? `a${anon}` : "");
  const rows = await env.DB.prepare(`
    SELECT c.id, c.parent_id, c.body, c.like_count, c.created_at,
           COALESCE(u.nickname, c.guest_name) AS author,
           CASE WHEN u.id IS NULL THEN 0
                WHEN u.role = 'admin' THEN 1
                WHEN u.role = 'member' AND (u.member_until IS NULL OR u.member_until >= date('now')) THEN 1
                ELSE 0 END AS author_is_member,
           CASE WHEN u.id IS NULL THEN 0 WHEN u.role = 'admin' THEN 1 ELSE 0 END AS author_is_admin,
           EXISTS(SELECT 1 FROM likes l WHERE l.comment_id = c.id AND l.identity = ?) AS liked
    FROM comments c LEFT JOIN users u ON u.id = c.user_id
    WHERE c.slug = ? AND c.status = 'visible'
    ORDER BY c.created_at ASC, c.id ASC LIMIT 500`).bind(myIdentity, slug).all();
  return json({ ok: true, comments: rows.results || [] });
}

async function handlePostComment(env, request) {
  const ip = clientIp(request);
  if (await rateLimited(env, ip, "comment", 10, 10)) return err("发言过于频繁，请稍后再试", 429);
  const b = await readBody(request);
  const slug = cleanText(b.slug, 300);
  const body = String(b.body ?? "").trim().slice(0, 2000);
  if (!slug) return err("缺少文章标识");
  if (!body) return err("留言内容不能为空");
  const me = await currentUser(env, request);
  let userId = null, guestName = null;
  if (me) { userId = me.id; }
  else {
    guestName = cleanText(b.guest_name, 30);
    if (!guestName) return err("游客留言请填写昵称，或先登录");
  }
  let parentId = null;
  if (b.parent_id !== undefined && b.parent_id !== null && b.parent_id !== "") {
    parentId = parseInt(b.parent_id, 10);
    const p = await env.DB.prepare("SELECT id, slug FROM comments WHERE id = ? AND status = 'visible'").bind(parentId).first();
    if (!p || p.slug !== slug) return err("要回复的留言不存在");
  }
  await rateHit(env, ip, "comment");
  const r = await env.DB.prepare(
    "INSERT INTO comments (slug, user_id, guest_name, parent_id, body, ip) VALUES (?, ?, ?, ?, ?, ?)"
  ).bind(slug, userId, guestName, parentId, body, ip).run();
  return json({ ok: true, id: r.meta.last_row_id });
}

async function handleLike(env, request) {
  const b = await readBody(request);
  const commentId = parseInt(b.comment_id, 10);
  if (!commentId) return err("参数不正确");
  const c = await env.DB.prepare("SELECT id FROM comments WHERE id = ? AND status = 'visible'").bind(commentId).first();
  if (!c) return err("留言不存在");
  const me = await currentUser(env, request);
  const cookies = parseCookies(request);
  let anon = cookies["drx_anon"] || "";
  let setCookie = null;
  if (!me && !anon) {
    anon = [...crypto.getRandomValues(new Uint8Array(16))].map((x) => x.toString(16).padStart(2, "0")).join("");
    setCookie = cookieHeader("drx_anon", anon, 365 * 86400);
  }
  const identity = me ? `u${me.id}` : `a${anon}`;
  const existing = await env.DB.prepare(
    "SELECT comment_id FROM likes WHERE comment_id = ? AND identity = ?").bind(commentId, identity).first();
  let liked;
  if (existing) {
    await env.DB.prepare("DELETE FROM likes WHERE comment_id = ? AND identity = ?").bind(commentId, identity).run();
    await env.DB.prepare("UPDATE comments SET like_count = MAX(like_count - 1, 0) WHERE id = ?").bind(commentId).run();
    liked = false;
  } else {
    await env.DB.prepare("INSERT INTO likes (comment_id, identity) VALUES (?, ?)").bind(commentId, identity).run();
    await env.DB.prepare("UPDATE comments SET like_count = like_count + 1 WHERE id = ?").bind(commentId).run();
    liked = true;
  }
  const row = await env.DB.prepare("SELECT like_count FROM comments WHERE id = ?").bind(commentId).first();
  const headers = setCookie ? { "Set-Cookie": setCookie } : {};
  return json({ ok: true, liked, like_count: row.like_count }, 200, headers);
}

// ---------------- 管理员 ----------------

async function requireAdmin(env, request) {
  const me = await currentUser(env, request);
  if (!me) return { error: err("请先登录", 401) };
  if (me.role !== "admin") return { error: err("需要管理员权限", 403) };
  return { me };
}

async function handleAdminUsers(env, request) {
  const { error } = await requireAdmin(env, request);
  if (error) return error;
  const rows = await env.DB.prepare(
    "SELECT id, email, nickname, role, member_until, status, created_at FROM users ORDER BY id DESC LIMIT 200").all();
  return json({ ok: true, users: rows.results || [] });
}

async function handleAdminUpdateUser(env, request) {
  const { error } = await requireAdmin(env, request);
  if (error) return error;
  const b = await readBody(request);
  const id = parseInt(b.id, 10);
  if (!id) return err("参数不正确");
  const role = ["user", "member", "admin"].includes(b.role) ? b.role : null;
  const status = ["active", "banned"].includes(b.status) ? b.status : null;
  const memberUntil = b.member_until === "" ? null : (b.member_until ? cleanText(b.member_until, 10) : undefined);
  if (role) await env.DB.prepare("UPDATE users SET role = ? WHERE id = ?").bind(role, id).run();
  if (status) await env.DB.prepare("UPDATE users SET status = ? WHERE id = ?").bind(status, id).run();
  if (memberUntil !== undefined) await env.DB.prepare("UPDATE users SET member_until = ? WHERE id = ?").bind(memberUntil, id).run();
  return json({ ok: true });
}

async function handleAdminResetPassword(env, request) {
  const { error } = await requireAdmin(env, request);
  if (error) return error;
  const b = await readBody(request);
  const id = parseInt(b.id, 10);
  if (!id) return err("参数不正确");
  const temp = [...crypto.getRandomValues(new Uint8Array(12))].map((x) => "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"[x % 54]).join("");
  const hash = await hashPassword(temp);
  await env.DB.prepare("UPDATE users SET pass_hash = ? WHERE id = ?").bind(hash, id).run();
  await env.DB.prepare("DELETE FROM sessions WHERE user_id = ?").bind(id).run();
  return json({ ok: true, temp_password: temp });
}

async function handleAdminComments(env, request, url) {
  const { error } = await requireAdmin(env, request);
  if (error) return error;
  const status = url.searchParams.get("status") || "all";
  const where = status === "all" ? "" : "WHERE c.status = ?";
  const stmt = env.DB.prepare(`
    SELECT c.id, c.slug, c.body, c.status, c.like_count, c.created_at,
           COALESCE(u.nickname, c.guest_name) AS author
    FROM comments c LEFT JOIN users u ON u.id = c.user_id
    ${where} ORDER BY c.id DESC LIMIT 200`);
  const rows = status === "all" ? await stmt.all() : await stmt.bind(status).all();
  return json({ ok: true, comments: rows.results || [] });
}

async function handleAdminCommentAction(env, request) {
  const { error } = await requireAdmin(env, request);
  if (error) return error;
  const b = await readBody(request);
  const id = parseInt(b.id, 10);
  const map = { hide: "hidden", unhide: "visible", delete: "deleted" };
  const st = map[b.action];
  if (!id || !st) return err("参数不正确");
  await env.DB.prepare("UPDATE comments SET status = ? WHERE id = ?").bind(st, id).run();
  return json({ ok: true });
}

// ---------------- 路由 ----------------

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, "");
  if (!env.DB) return err("留言功能尚未开通（数据库未绑定）", 503);
  try {
    if (path === "/api/register" && request.method === "POST") return await handleRegister(env, request);
    if (path === "/api/login" && request.method === "POST") return await handleLogin(env, request);
    if (path === "/api/logout" && request.method === "POST") return await handleLogout(env, request);
    if (path === "/api/me" && request.method === "GET") {
      const me = await currentUser(env, request);
      return json({ ok: true, user: me ? publicUser(me) : null });
    }
    if (path === "/api/comments" && request.method === "GET") return await handleListComments(env, request, url);
    if (path === "/api/comments" && request.method === "POST") return await handlePostComment(env, request);
    if (path === "/api/like" && request.method === "POST") return await handleLike(env, request);
    if (path === "/api/admin/users" && request.method === "GET") return await handleAdminUsers(env, request);
    if (path === "/api/admin/user" && request.method === "POST") return await handleAdminUpdateUser(env, request);
    if (path === "/api/admin/reset-password" && request.method === "POST") return await handleAdminResetPassword(env, request);
    if (path === "/api/admin/comments" && request.method === "GET") return await handleAdminComments(env, request, url);
    if (path === "/api/admin/comment" && request.method === "POST") return await handleAdminCommentAction(env, request);
    return err("接口不存在", 404);
  } catch (e) {
    return err("服务器内部错误：" + (e && e.message ? e.message : String(e)), 500);
  }
}
