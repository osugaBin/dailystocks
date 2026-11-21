-- DrX Daily 社区功能 · Cloudflare D1 数据库结构
-- 用法：在 Cloudflare 控制台 D1 数据库的 Console 里整段粘贴执行一次即可。
-- 含：账号（含会员字段预留）、会话、留言/回复、点赞、限频事件。

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  nickname TEXT NOT NULL,
  pass_hash TEXT NOT NULL,               -- PBKDF2-SHA256，格式 pbkdf2:迭代:盐:哈希（均 base64）
  role TEXT NOT NULL DEFAULT 'user',     -- user | member | admin
  member_until TEXT,                     -- 会员到期日 YYYY-MM-DD；role='member' 时生效，NULL 表示长期
  status TEXT NOT NULL DEFAULT 'active', -- active | banned
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,           -- 只存会话令牌的 SHA-256，不存原文
  user_id INTEGER NOT NULL REFERENCES users(id),
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL,                    -- 文章路径，如 /custom/xxx.html
  user_id INTEGER REFERENCES users(id),  -- 游客留言为 NULL
  guest_name TEXT,
  parent_id INTEGER REFERENCES comments(id),  -- 回复指向父留言；NULL 为顶层留言
  body TEXT NOT NULL,
  like_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'visible',     -- visible | hidden | deleted（软删）
  ip TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_comments_slug ON comments(slug, status, created_at);

CREATE TABLE IF NOT EXISTS likes (
  comment_id INTEGER NOT NULL REFERENCES comments(id),
  identity TEXT NOT NULL,                -- 'u<用户id>' 或 'a<匿名令牌>'
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (comment_id, identity)
);

CREATE TABLE IF NOT EXISTS rate_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ip TEXT NOT NULL,
  action TEXT NOT NULL,                  -- register | login | comment
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_rate ON rate_events(ip, action, created_at);

-- 密码重置令牌（2026-11-21 追加；只存令牌 SHA-256，1 小时过期、用后即删）
CREATE TABLE IF NOT EXISTS password_resets (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
