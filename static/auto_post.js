/* ===== note 自動投稿管理 フロントエンド ===== */

let currentDraftId   = null;
let currentTitle     = "";
let currentBody      = "";
let currentType      = "daily_fortune";

// ===== 初期化 =====
document.addEventListener("DOMContentLoaded", () => {
  loadConfig();
  loadHistory();

  // タブ
  document.querySelectorAll(".ap-gen-tab").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".ap-gen-tab").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentType = btn.dataset.type;
    });
  });

  document.getElementById("save-config-btn").addEventListener("click", saveConfig);
  document.getElementById("run-now-btn").addEventListener("click", runNow);
  document.getElementById("generate-btn").addEventListener("click", generateContent);
  document.getElementById("copy-preview-btn").addEventListener("click", copyPreview);
  document.getElementById("post-preview-btn").addEventListener("click", postToNote);
  document.getElementById("regen-btn").addEventListener("click", generateContent);
});

// ===== 設定 =====
async function loadConfig() {
  try {
    const res = await fetch("/api/auto-post/config");
    const cfg = await res.json();
    applyConfig(cfg);
  } catch (err) {
    console.error("設定読み込み失敗:", err);
  }
}

function applyConfig(cfg) {
  document.getElementById("enabled-toggle").checked = cfg.enabled;
  document.getElementById("post-time").value         = cfg.post_time || "09:00";
  document.getElementById("note-status").value       = cfg.note_status || "draft";
  document.getElementById("coconala-url").value      = cfg.coconala_url || "";
  document.getElementById("note-url").value          = cfg.note_url || "";
  document.getElementById("content-today").checked   = cfg.content_today !== false;
  document.getElementById("content-voice").checked   = cfg.content_voice !== false;

  // スケジューラーステータス
  const pill = document.getElementById("scheduler-status");
  if (cfg.enabled) {
    pill.textContent = `▶ 稼働中（${cfg.post_time} 毎日）`;
    pill.className = "ap-status-pill active";
  } else {
    pill.textContent = "⏸ 停止中";
    pill.className = "ap-status-pill inactive";
  }

  // 認証情報ステータス
  const credEl = document.getElementById("credentials-status");
  if (cfg.note_email_set && cfg.note_password_set) {
    credEl.className = "ap-info-box ok";
    credEl.innerHTML = "✅ note.com ログイン情報が設定されています（NOTE_EMAIL / NOTE_PASSWORD）";
  } else {
    credEl.className = "ap-info-box warn";
    const missing = [];
    if (!cfg.note_email_set)    missing.push("NOTE_EMAIL");
    if (!cfg.note_password_set) missing.push("NOTE_PASSWORD");
    credEl.innerHTML =
      `⚠️ .env に <strong>${missing.join(" / ")}</strong> が設定されていません。` +
      `設定されるまで生成コンテンツはローカル保存のみとなります。`;
  }

  // noteページリンク
  if (cfg.note_url) {
    const link = document.getElementById("note-url-link");
    link.href  = cfg.note_url;
    link.style.display = "";
  }

  // 最終投稿日
  if (cfg.last_post_date) {
    const info = document.getElementById("run-status");
    info.className   = "ap-run-status info";
    info.textContent = `📅 最終自動投稿日：${cfg.last_post_date}`;
    info.classList.remove("hidden");
  }
}

async function saveConfig() {
  const btn = document.getElementById("save-config-btn");
  btn.disabled = true;
  btn.textContent = "⏳ 保存中...";

  try {
    const payload = {
      enabled:       document.getElementById("enabled-toggle").checked,
      post_time:     document.getElementById("post-time").value,
      note_status:   document.getElementById("note-status").value,
      coconala_url:  document.getElementById("coconala-url").value.trim(),
      note_url:      document.getElementById("note-url").value.trim(),
      content_today: document.getElementById("content-today").checked,
      content_voice: document.getElementById("content-voice").checked,
    };
    const res = await fetch("/api/auto-post/config", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    showToast("設定を保存しました ✓");
    loadConfig(); // ステータス更新
  } catch (err) {
    showToast("保存に失敗しました: " + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "💾 設定を保存";
  }
}

// ===== 今すぐ実行 =====
async function runNow() {
  const btn      = document.getElementById("run-now-btn");
  const statusEl = document.getElementById("run-status");
  btn.disabled   = true;
  btn.textContent = "⏳ 実行中...";
  statusEl.className   = "ap-run-status info";
  statusEl.textContent = "⏳ コンテンツを生成して投稿しています...";
  statusEl.classList.remove("hidden");

  try {
    const res  = await fetch("/api/auto-post/run-now", { method: "POST" });
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    const results  = data.results || [];
    const successes = results.filter(r => r.status === "posted").length;
    const drafts    = results.filter(r => r.status?.startsWith("draft")).length;
    const errors    = results.filter(r => r.status?.startsWith("error")).length;

    let msg = `✅ 実行完了：`;
    if (successes) msg += ` ${successes}件投稿`;
    if (drafts)    msg += ` ${drafts}件ローカル保存`;
    if (errors)    msg += ` ${errors}件エラー`;

    statusEl.className   = errors > 0 ? "ap-run-status error" : "ap-run-status success";
    statusEl.textContent = msg;

    loadHistory();
    showToast("実行が完了しました");
  } catch (err) {
    statusEl.className   = "ap-run-status error";
    statusEl.textContent = "❌ エラー: " + err.message;
    showToast("実行に失敗しました");
  } finally {
    btn.disabled    = false;
    btn.textContent = "▶ 今すぐ実行";
  }
}

// ===== コンテンツ生成 =====
async function generateContent() {
  const loading   = document.getElementById("gen-loading");
  const preview   = document.getElementById("gen-preview");
  const genBtn    = document.getElementById("generate-btn");
  const postRes   = document.getElementById("post-result");

  loading.classList.remove("hidden");
  preview.classList.add("hidden");
  postRes.classList.add("hidden");
  genBtn.disabled = true;
  genBtn.textContent = "⏳ 生成中...";

  currentTitle = "";
  currentBody  = "";

  try {
    const response = await fetch("/api/auto-post/generate", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ type: currentType }),
    });

    if (!response.ok) throw new Error("生成リクエストに失敗しました");

    const reader  = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let streamText = "";

    // プレビューを先に表示してストリーム表示
    loading.classList.add("hidden");
    preview.classList.remove("hidden");
    document.getElementById("preview-title").textContent = "生成中...";
    document.getElementById("preview-body").textContent  = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = JSON.parse(line.slice(6));

        if (payload.status === "connecting") {
          document.getElementById("preview-body").textContent = "";
        }

        if (payload.chunk) {
          streamText += payload.chunk;
          // タイトルと本文をリアルタイム分割表示
          const lns = streamText.split("\n");
          document.getElementById("preview-title").textContent = lns[0] || "生成中...";
          document.getElementById("preview-body").textContent  =
            lns.slice(1).join("\n").trimStart();
        }

        if (payload.done) {
          currentDraftId = payload.draft_id;
          currentTitle   = payload.title;
          currentBody    = payload.body;
          document.getElementById("preview-title").textContent = currentTitle;
          document.getElementById("preview-body").textContent  = currentBody;
          showToast("生成が完了しました ✨");
        }

        if (payload.error) {
          loading.classList.add("hidden");
          preview.classList.add("hidden");
          showToast("生成エラー: " + payload.error);
        }
      }
    }
  } catch (err) {
    loading.classList.add("hidden");
    showToast("生成に失敗しました: " + err.message);
  } finally {
    genBtn.disabled    = false;
    genBtn.textContent = "✨ 生成する";
  }
}

async function copyPreview() {
  const text = `${currentTitle}\n\n${currentBody}`;
  try {
    await navigator.clipboard.writeText(text);
    showToast("コピーしました ✓");
  } catch {
    showToast("コピーに失敗しました");
  }
}

// ===== noteに投稿 =====
async function postToNote() {
  if (!currentTitle || !currentBody) {
    showToast("先にコンテンツを生成してください");
    return;
  }

  const btn      = document.getElementById("post-preview-btn");
  const resultEl = document.getElementById("post-result");
  btn.disabled   = true;
  btn.textContent = "⏳ 投稿中...";
  resultEl.classList.add("hidden");

  try {
    const res  = await fetch("/api/auto-post/post-note", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({
        title: currentTitle,
        body:  currentBody,
        type:  currentType,
      }),
    });
    const data = await res.json();

    if (data.error) throw new Error(data.error);

    if (data.success) {
      resultEl.className = "ap-run-status success";
      let msg = `✅ noteに投稿しました（${data.status === "draft" ? "下書き" : "公開"}）`;
      if (data.note_url) msg += `\n🔗 ${data.note_url}`;
      resultEl.textContent = msg;
      showToast("投稿しました ✓");
    } else {
      resultEl.className   = "ap-run-status info";
      resultEl.textContent = `💾 ${data.message}`;
    }
    resultEl.classList.remove("hidden");
    loadHistory();
  } catch (err) {
    resultEl.className   = "ap-run-status error";
    resultEl.textContent = "❌ エラー: " + err.message;
    resultEl.classList.remove("hidden");
    showToast("投稿に失敗しました");
  } finally {
    btn.disabled    = false;
    btn.textContent = "📤 noteに投稿";
  }
}

// ===== 履歴 =====
async function loadHistory() {
  try {
    const res  = await fetch("/api/auto-post/history");
    const list = await res.json();
    renderHistory(list);
  } catch (err) {
    console.error("履歴読み込み失敗:", err);
  }
}

function renderHistory(list) {
  const el = document.getElementById("history-list");
  if (!list.length) {
    el.innerHTML = '<p class="empty-message">まだ投稿履歴はありません</p>';
    return;
  }

  el.innerHTML = list.map(item => {
    const typeLabel = item.type === "daily_fortune" ? "🔮 今日の運勢" : "💬 お客様の声";
    const statusTag = buildStatusTag(item.status);
    const noteLink  = item.note_url
      ? `<a href="${esc(item.note_url)}" target="_blank" class="ap-nav-link" style="font-size:0.75rem">🔗 noteで見る</a>`
      : "";
    const ts = (item.created_at || "").slice(0, 16).replace("T", " ");

    return `
      <div class="ap-hist-item">
        <div class="ap-hist-left">
          <div class="ap-hist-title">${esc(item.title || "（タイトルなし）")}</div>
          <div class="ap-hist-meta">${typeLabel}　${ts}</div>
        </div>
        <div class="ap-hist-right">
          ${statusTag}
          ${noteLink}
          <button class="cn-btn-sm cn-btn-delete" onclick="deleteHistory('${esc(item.id)}')">🗑️</button>
        </div>
      </div>
    `;
  }).join("");
}

function buildStatusTag(status) {
  if (!status) return "";
  if (status === "posted") {
    return '<span class="ap-status-tag posted">✅ 投稿済</span>';
  }
  if (status.startsWith("draft")) {
    return '<span class="ap-status-tag draft">💾 保存</span>';
  }
  if (status.startsWith("error") || status.startsWith("post_failed")) {
    return '<span class="ap-status-tag error">❌ エラー</span>';
  }
  return `<span class="ap-status-tag draft">${esc(status)}</span>`;
}

async function deleteHistory(id) {
  if (!confirm("この履歴を削除しますか？")) return;
  try {
    await fetch(`/api/auto-post/history/${id}`, { method: "DELETE" });
    loadHistory();
    showToast("削除しました");
  } catch {
    showToast("削除に失敗しました");
  }
}

// ===== ユーティリティ =====
function esc(str) {
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function showToast(message) {
  const toast = document.createElement("div");
  toast.className   = "toast";
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 2000);
}
