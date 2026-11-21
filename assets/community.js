/* DrX Daily 社区前端：留言/回复/点赞 + 账号 + 管理员。
   所有用户内容一律用 textContent 渲染，不拼 innerHTML，天然防 XSS。 */
(function () {
  "use strict";
  function lang() {
    return document.documentElement.getAttribute("data-lang") === "en" ? "en" : "zh";
  }
  function T(zh, en) { return lang() === "en" ? en : zh; }
  function el(tag, cls, text) {
    var d = document.createElement(tag);
    if (cls) d.className = cls;
    if (text !== undefined && text !== null) d.textContent = text;
    return d;
  }
  function api(path, opts) {
    opts = opts || {};
    opts.credentials = "same-origin";
    if (opts.body && typeof opts.body !== "string") {
      opts.headers = { "Content-Type": "application/json" };
      opts.body = JSON.stringify(opts.body);
    }
    return fetch(path, opts).then(function (r) {
      return r.json().catch(function () { return { ok: false, error: "Network error" }; })
        .then(function (j) { j._status = r.status; return j; });
    });
  }
  var state = { me: null, meLoaded: false };

  function refreshHeader() {
    var links = document.querySelectorAll(".drx-account-link");
    links.forEach(function (a) {
      var span = a.querySelector(".lz");
      var spanEn = a.querySelector(".le");
      if (state.me) {
        if (span) span.textContent = state.me.nickname;
        if (spanEn) spanEn.textContent = state.me.nickname;
      }
    });
  }
  function loadMe(cb) {
    api("/api/me").then(function (j) {
      state.me = j && j.ok ? j.user : null;
      state.meLoaded = true;
      refreshHeader();
      if (cb) cb(state.me);
    }).catch(function () { state.meLoaded = true; if (cb) cb(null); });
  }

  /* ---------------- 留言区 ---------------- */
  function slugOf() {
    var p = location.pathname;
    try { p = decodeURIComponent(p); } catch (e) {}
    if (p.endsWith("/index.html")) p = p.slice(0, -"index.html".length);
    return p;
  }

  function initComments() {
    var box = document.getElementById("drx-comments");
    if (!box) return;
    var listBox = box.querySelector(".comments-list");
    var formBox = box.querySelector(".comments-form");
    var slug = slugOf();

    function commentNode(c, depth) {
      var wrap = el("div", "cmt depth-" + Math.min(depth, 3));
      wrap.id = "cmt-" + c.id;
      var head = el("div", "cmt-head");
      head.appendChild(el("span", "cmt-author", c.author || T("游客", "Guest")));
      if (c.author_is_admin) head.appendChild(el("span", "cmt-badge badge-admin", T("管理员", "Admin")));
      else if (c.author_is_member) head.appendChild(el("span", "cmt-badge badge-member", T("会员", "Member")));
      head.appendChild(el("span", "cmt-time", String(c.created_at || "").slice(0, 16)));
      wrap.appendChild(head);
      wrap.appendChild(el("p", "cmt-body", c.body));
      var acts = el("div", "cmt-acts");
      var likeBtn = el("button", "cmt-like" + (c.liked ? " liked" : ""), "♥ " + (c.like_count || 0));
      likeBtn.type = "button";
      likeBtn.addEventListener("click", function () {
        api("/api/like", { method: "POST", body: { comment_id: c.id } }).then(function (j) {
          if (j.ok) { c.liked = j.liked; c.like_count = j.like_count; likeBtn.textContent = "♥ " + j.like_count; likeBtn.classList.toggle("liked", j.liked); }
          else alert(j.error || "Error");
        });
      });
      acts.appendChild(likeBtn);
      var replyBtn = el("button", "cmt-replybtn", T("回复", "Reply"));
      replyBtn.type = "button";
      acts.appendChild(replyBtn);
      wrap.appendChild(acts);
      var slot = el("div", "cmt-replyslot");
      wrap.appendChild(slot);
      replyBtn.addEventListener("click", function () {
        if (slot.firstChild) { slot.innerHTML = ""; return; }
        slot.appendChild(buildForm(c.id, function () { slot.innerHTML = ""; load(); }));
      });
      return wrap;
    }

    function render(comments) {
      listBox.innerHTML = "";
      if (!comments.length) {
        listBox.appendChild(el("p", "cmt-empty", T("还没有留言，来抢沙发。", "No comments yet. Be the first.")));
        return;
      }
      var byId = {};
      comments.forEach(function (c) { byId[c.id] = c; });
      var children = {};
      comments.forEach(function (c) {
        var key = c.parent_id && byId[c.parent_id] ? c.parent_id : 0;
        (children[key] = children[key] || []).push(c);
      });
      function appendKids(parentId, container, depth) {
        (children[parentId] || []).forEach(function (c) {
          var node = commentNode(c, depth);
          container.appendChild(node);
          var kidsBox = el("div", "cmt-kids");
          node.appendChild(kidsBox);
          appendKids(c.id, kidsBox, depth + 1);
        });
      }
      appendKids(0, listBox, 0);
    }

    function buildForm(parentId, onDone) {
      var form = el("div", "cmt-form");
      var nameInput = null;
      if (!state.me) {
        nameInput = el("input", "cmt-name");
        nameInput.type = "text";
        nameInput.maxLength = 30;
        nameInput.placeholder = T("昵称（游客必填，或登录后留言）", "Nickname (required for guests)");
        try { nameInput.value = localStorage.getItem("drx_guest_name") || ""; } catch (e) {}
        form.appendChild(nameInput);
      } else {
        form.appendChild(el("p", "cmt-as", T("以 ", "Commenting as ") + state.me.nickname));
      }
      var ta = el("textarea", "cmt-text");
      ta.rows = parentId ? 2 : 3;
      ta.maxLength = 2000;
      ta.placeholder = parentId ? T("写下你的回复…", "Write a reply...") : T("写下你的留言…", "Write a comment...");
      form.appendChild(ta);
      var row = el("div", "cmt-formrow");
      var submit = el("button", "cmt-submit", parentId ? T("回复", "Reply") : T("发表留言", "Post comment"));
      submit.type = "button";
      var msg = el("span", "cmt-msg");
      submit.addEventListener("click", function () {
        var payload = { slug: slug, body: ta.value };
        if (parentId) payload.parent_id = parentId;
        if (!state.me) {
          payload.guest_name = nameInput.value;
          try { localStorage.setItem("drx_guest_name", nameInput.value); } catch (e) {}
        }
        submit.disabled = true;
        api("/api/comments", { method: "POST", body: payload }).then(function (j) {
          submit.disabled = false;
          if (j.ok) { ta.value = ""; msg.textContent = ""; if (onDone) onDone(); else load(); }
          else msg.textContent = j.error || "Error";
        }).catch(function () { submit.disabled = false; msg.textContent = "Network error"; });
      });
      row.appendChild(submit);
      row.appendChild(msg);
      form.appendChild(row);
      return form;
    }

    function load() {
      api("/api/comments?slug=" + encodeURIComponent(slug)).then(function (j) {
        if (j._status === 503) {
          listBox.innerHTML = "";
          listBox.appendChild(el("p", "cmt-empty", T("留言功能即将开通。", "Comments are coming soon.")));
          formBox.innerHTML = "";
          return;
        }
        if (j.ok) render(j.comments);
      });
    }
    formBox.appendChild(buildForm(null, null));
    loadMe(function () {
      formBox.innerHTML = "";
      formBox.appendChild(buildForm(null, null));
      load();
    });
    load();
    new MutationObserver(function () {
      formBox.innerHTML = "";
      formBox.appendChild(buildForm(null, null));
      load();
    }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-lang"] });
  }

  /* ---------------- 账号页 ---------------- */
  function initAccount() {
    var box = document.getElementById("drx-account");
    if (!box) return;
    function render() {
      box.innerHTML = "";
      if (state.me) {
        var card = el("div", "acct-card");
        card.appendChild(el("h2", "", state.me.nickname));
        card.appendChild(el("p", "", state.me.email));
        var roleText = state.me.is_admin ? T("管理员", "Admin")
          : state.me.is_member ? T("会员", "Member") + (state.me.member_until ? T("（有效期至 ", " (until ") + state.me.member_until + ")" : "")
          : T("普通用户", "User");
        card.appendChild(el("p", "acct-role", roleText));
        if (!state.me.is_member && !state.me.is_admin) {
          card.appendChild(el("p", "acct-note", T("会员由管理员开通：付款后联系管理员并提供注册邮箱即可。", "Membership is activated by the admin: pay, then contact the admin with your account email.")));
        }
        var out = el("button", "cmt-submit", T("退出登录", "Log out"));
        out.type = "button";
        out.addEventListener("click", function () {
          api("/api/logout", { method: "POST", body: {} }).then(function () { state.me = null; refreshHeader(); render(); });
        });
        card.appendChild(out);
        if (state.me.is_admin) {
          var adm = el("p", "");
          var a = el("a", "", T("进入管理后台", "Open admin panel"));
          a.href = "admin.html";
          adm.appendChild(a);
          card.appendChild(adm);
        }
        box.appendChild(card);
        return;
      }
      var wrap = el("div", "acct-card");
      var mode = "login";
      var title = el("h2", "", T("登录", "Log in"));
      wrap.appendChild(title);
      var email = el("input", "cmt-name"); email.type = "email"; email.placeholder = T("邮箱", "Email");
      var nick = el("input", "cmt-name"); nick.type = "text"; nick.placeholder = T("昵称（注册时填写）", "Nickname (for registration)"); nick.style.display = "none";
      var pw = el("input", "cmt-name"); pw.type = "password"; pw.placeholder = T("密码（至少 8 位）", "Password (min 8 chars)");
      var msg = el("p", "cmt-msg");
      var submit = el("button", "cmt-submit", T("登录", "Log in"));
      submit.type = "button";
      var toggle = el("button", "cmt-replybtn", T("没有账号？去注册", "No account? Register"));
      toggle.type = "button";
      toggle.addEventListener("click", function () {
        mode = mode === "login" ? "register" : "login";
        title.textContent = mode === "login" ? T("登录", "Log in") : T("注册", "Register");
        submit.textContent = mode === "login" ? T("登录", "Log in") : T("注册并登录", "Register & log in");
        toggle.textContent = mode === "login" ? T("没有账号？去注册", "No account? Register") : T("已有账号？去登录", "Have an account? Log in");
        nick.style.display = mode === "register" ? "" : "none";
        msg.textContent = "";
      });
      submit.addEventListener("click", function () {
        var path = mode === "login" ? "/api/login" : "/api/register";
        var payload = { email: email.value, password: pw.value };
        if (mode === "register") payload.nickname = nick.value;
        submit.disabled = true;
        api(path, { method: "POST", body: payload }).then(function (j) {
          submit.disabled = false;
          if (j.ok) { state.me = j.user; refreshHeader(); render(); }
          else msg.textContent = j.error || "Error";
        }).catch(function () { submit.disabled = false; msg.textContent = "Network error"; });
      });
      [email, nick, pw].forEach(function (i) { wrap.appendChild(i); });
      var row = el("div", "cmt-formrow");
      row.appendChild(submit); row.appendChild(toggle);
      wrap.appendChild(row);
      wrap.appendChild(msg);
      var forgotLink = el("button", "cmt-replybtn", T("忘记密码？", "Forgot password?"));
      forgotLink.type = "button";
      forgotLink.addEventListener("click", function () {
        box.innerHTML = "";
        var card = el("div", "acct-card");
        card.appendChild(el("h2", "", T("找回密码", "Reset password")));
        card.appendChild(el("p", "acct-note", T("输入注册邮箱，我们会把重置链接发到你的邮箱（1 小时内有效）。", "Enter your account email and we will send you a reset link (valid for 1 hour).")));
        var em = el("input", "cmt-name"); em.type = "email"; em.placeholder = T("注册邮箱", "Account email"); em.value = email.value;
        var m2 = el("p", "cmt-msg");
        var send = el("button", "cmt-submit", T("发送重置链接", "Send reset link"));
        send.type = "button";
        send.addEventListener("click", function () {
          send.disabled = true;
          api("/api/forgot-password", { method: "POST", body: { email: em.value } }).then(function (j) {
            send.disabled = false;
            if (j.ok) { m2.style.color = "var(--muted)"; m2.textContent = T("如果该邮箱已注册，重置链接已经发出，请查收邮箱（也看看垃圾箱）。", "If that email is registered, a reset link is on its way. Please check your inbox (and spam folder)."); }
            else m2.textContent = j.error || "Error";
          }).catch(function () { send.disabled = false; m2.textContent = "Network error"; });
        });
        var back = el("button", "cmt-replybtn", T("返回登录", "Back to login"));
        back.type = "button";
        back.addEventListener("click", render);
        card.appendChild(em); card.appendChild(send); card.appendChild(back); card.appendChild(m2);
        box.appendChild(card);
      });
      wrap.appendChild(forgotLink);
      box.appendChild(wrap);
    }
    loadMe(render);
  }

  /* ---------------- 管理页 ---------------- */
  function initAdmin() {
    var box = document.getElementById("drx-admin");
    if (!box) return;
    function render() {
      box.innerHTML = "";
      if (!state.me || !state.me.is_admin) {
        box.appendChild(el("p", "cmt-empty", T("需要管理员登录。", "Admin login required.")));
        return;
      }
      box.appendChild(el("h2", "", T("用户管理", "Users")));
      var usersBox = el("div", "");
      box.appendChild(usersBox);
      box.appendChild(el("h2", "", T("留言管理（最新 200 条）", "Comments (latest 200)")));
      var cmtsBox = el("div", "");
      box.appendChild(cmtsBox);

      function loadUsers() {
        api("/api/admin/users").then(function (j) {
          usersBox.innerHTML = "";
          if (!j.ok) { usersBox.appendChild(el("p", "cmt-msg", j.error || "Error")); return; }
          var table = el("table", "adm-table");
          var thead = el("tr", "");
          [T("邮箱", "Email"), T("昵称", "Nickname"), T("角色", "Role"), T("会员到期", "Member until"), T("状态", "Status"), T("操作", "Actions")].forEach(function (h) {
            thead.appendChild(el("th", "", h));
          });
          table.appendChild(thead);
          j.users.forEach(function (u) {
            var tr = el("tr", "");
            tr.appendChild(el("td", "", u.email));
            tr.appendChild(el("td", "", u.nickname));
            var roleTd = el("td", "");
            var sel = el("select", "");
            ["user", "member", "admin"].forEach(function (r) {
              var o = el("option", "", r); o.value = r; if (u.role === r) o.selected = true; sel.appendChild(o);
            });
            roleTd.appendChild(sel); tr.appendChild(roleTd);
            var untilTd = el("td", "");
            var until = el("input", ""); until.type = "date"; until.value = u.member_until || "";
            untilTd.appendChild(until); tr.appendChild(untilTd);
            tr.appendChild(el("td", "", u.status));
            var actTd = el("td", "");
            var save = el("button", "cmt-replybtn", T("保存", "Save")); save.type = "button";
            save.addEventListener("click", function () {
              api("/api/admin/user", { method: "POST", body: { id: u.id, role: sel.value, member_until: until.value } })
                .then(function (r) { alert(r.ok ? T("已保存", "Saved") : (r.error || "Error")); });
            });
            var ban = el("button", "cmt-replybtn", u.status === "active" ? T("停用", "Ban") : T("启用", "Unban")); ban.type = "button";
            ban.addEventListener("click", function () {
              api("/api/admin/user", { method: "POST", body: { id: u.id, status: u.status === "active" ? "banned" : "active" } })
                .then(function () { loadUsers(); });
            });
            var reset = el("button", "cmt-replybtn", T("重置密码", "Reset PW")); reset.type = "button";
            reset.addEventListener("click", function () {
              api("/api/admin/reset-password", { method: "POST", body: { id: u.id } }).then(function (r) {
                if (r.ok && r.emailed) alert(T("重置链接已发送到该用户的注册邮箱", "Reset link emailed to the user"));
                else if (r.ok) prompt(T("临时密码（只显示一次，请转告用户）", "Temporary password (shown once)"), r.temp_password);
                else alert(r.error || "Error");
              });
            });
            actTd.appendChild(save); actTd.appendChild(ban); actTd.appendChild(reset);
            tr.appendChild(actTd);
            table.appendChild(tr);
          });
          usersBox.appendChild(table);
        });
      }
      function loadComments() {
        api("/api/admin/comments?status=all").then(function (j) {
          cmtsBox.innerHTML = "";
          if (!j.ok) { cmtsBox.appendChild(el("p", "cmt-msg", j.error || "Error")); return; }
          j.comments.forEach(function (c) {
            var row = el("div", "adm-cmt");
            var txt = el("div", "adm-cmt-main");
            txt.appendChild(el("span", "cmt-author", c.author || ""));
            txt.appendChild(el("span", "cmt-time", " " + c.slug + " · " + String(c.created_at || "").slice(0, 16) + " · " + c.status + " · ♥ " + c.like_count));
            txt.appendChild(el("p", "cmt-body", c.body));
            row.appendChild(txt);
            var acts = el("div", "cmt-acts");
            [["hide", T("隐藏", "Hide")], ["unhide", T("恢复", "Unhide")], ["delete", T("删除", "Delete")]].forEach(function (pair) {
              var b = el("button", "cmt-replybtn", pair[1]); b.type = "button";
              b.addEventListener("click", function () {
                api("/api/admin/comment", { method: "POST", body: { id: c.id, action: pair[0] } }).then(function () { loadComments(); });
              });
              acts.appendChild(b);
            });
            row.appendChild(acts);
            cmtsBox.appendChild(row);
          });
        });
      }
      loadUsers();
      loadComments();
    }
    loadMe(render);
  }

  /* ---------------- 重置密码页 ---------------- */
  function initReset() {
    var box = document.getElementById("drx-reset");
    if (!box) return;
    var token = new URLSearchParams(location.search).get("token") || "";
    var card = el("div", "acct-card");
    card.appendChild(el("h2", "", T("设置新密码", "Set a new password")));
    if (!token) {
      card.appendChild(el("p", "cmt-msg", T("链接缺少令牌，请从邮件里的完整链接打开。", "This link is missing its token. Please open the full link from the email.")));
      box.appendChild(card);
      return;
    }
    var pw1 = el("input", "cmt-name"); pw1.type = "password"; pw1.placeholder = T("新密码（至少 8 位）", "New password (min 8 chars)");
    var pw2 = el("input", "cmt-name"); pw2.type = "password"; pw2.placeholder = T("再输一次新密码", "Repeat new password");
    var msg = el("p", "cmt-msg");
    var submit = el("button", "cmt-submit", T("确认重置", "Reset password"));
    submit.type = "button";
    submit.addEventListener("click", function () {
      if (pw1.value !== pw2.value) { msg.textContent = T("两次输入的密码不一致", "Passwords do not match"); return; }
      submit.disabled = true;
      api("/api/reset-password", { method: "POST", body: { token: token, password: pw1.value } }).then(function (j) {
        submit.disabled = false;
        if (j.ok) {
          card.innerHTML = "";
          card.appendChild(el("h2", "", T("密码已重置", "Password reset")));
          card.appendChild(el("p", "", T("请用新密码重新登录。", "Please log in with your new password.")));
          var a = el("a", "", T("去登录", "Go to login")); a.href = "account.html";
          card.appendChild(a);
        } else msg.textContent = j.error || "Error";
      }).catch(function () { submit.disabled = false; msg.textContent = "Network error"; });
    });
    card.appendChild(pw1); card.appendChild(pw2); card.appendChild(submit); card.appendChild(msg);
    box.appendChild(card);
  }

  document.addEventListener("DOMContentLoaded", function () {
    initComments();
    initAccount();
    initAdmin();
    initReset();
    if (!document.getElementById("drx-comments") && !document.getElementById("drx-account") && !document.getElementById("drx-admin")) {
      loadMe(null);
    }
  });
})();
