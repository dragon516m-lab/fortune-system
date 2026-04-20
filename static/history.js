/* 鑑定履歴ページ */

let allHistory = [];
let filteredHistory = [];

document.addEventListener("DOMContentLoaded", () => {
  loadHistory();

  // Enterキーで検索
  document.getElementById("search-name").addEventListener("keydown", e => {
    if (e.key === "Enter") searchHistory();
  });

  // ESCキーでモーダルを閉じる
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") closeModal();
  });
});

// ===== 履歴読み込み =====
async function loadHistory() {
  try {
    const res = await fetch("/api/history");
    allHistory = await res.json();
    filteredHistory = allHistory;
    renderList(filteredHistory);
    updateStats(filteredHistory.length, allHistory.length);
  } catch (err) {
    document.getElementById("history-list").innerHTML =
      '<p class="empty-message" style="padding:32px">読み込みに失敗しました</p>';
    document.getElementById("stats-text").textContent = "";
  }
}

// ===== 検索・フィルタ =====
function searchHistory() {
  const name = document.getElementById("search-name").value.trim().toLowerCase();
  const date = document.getElementById("search-date").value;

  filteredHistory = allHistory.filter(h => {
    const matchName = !name || (h.name || "").toLowerCase().includes(name);
    const matchDate = !date || (h.timestamp || "").startsWith(date);
    return matchName && matchDate;
  });

  renderList(filteredHistory);
  updateStats(filteredHistory.length, allHistory.length);
}

function clearSearch() {
  document.getElementById("search-name").value = "";
  document.getElementById("search-date").value = "";
  filteredHistory = allHistory;
  renderList(filteredHistory);
  updateStats(filteredHistory.length, allHistory.length);
}

function updateStats(filtered, total) {
  const el = document.getElementById("stats-text");
  el.textContent = filtered === total
    ? `全 ${total} 件`
    : `${filtered} 件表示 / 全 ${total} 件`;
}

// ===== 一覧レンダリング =====
function renderList(items) {
  const el = document.getElementById("history-list");

  if (items.length === 0) {
    el.innerHTML = '<p class="empty-message" style="padding:32px">該当する履歴がありません</p>';
    return;
  }

  el.innerHTML = items.map(h => {
    const ts      = (h.timestamp || "").slice(0, 16).replace("T", " ");
    const concern = truncate(h.consultation || "", 45);
    const name    = h.name
      ? `<span>${escH(h.name)}</span>`
      : '<span class="anon">匿名</span>';
    const detail  = h.has_detail
      ? '<span class="badge-detail">📋 詳細鑑定</span>'
      : "";

    return `
      <div class="history-row" onclick="showDetail(${h.id})">
        <div class="history-row-id">#${h.id}</div>
        <div class="history-row-body">
          <div class="history-row-name">${name}</div>
          <div class="history-row-concern">${escH(concern)}</div>
          <div class="history-row-meta">
            <span>${ts}</span>
            <span>${h.birthdate || ""}</span>
            ${detail}
          </div>
        </div>
        <span class="history-row-arrow">▶</span>
      </div>
    `;
  }).join("");
}

// ===== 詳細モーダル =====
async function showDetail(id) {
  const modal = document.getElementById("detail-modal");
  const body  = document.getElementById("modal-body");

  modal.classList.remove("hidden");
  body.innerHTML = `
    <div class="loading" style="padding:40px">
      <div class="spinner"></div>
      <p>読み込み中...</p>
    </div>
  `;

  try {
    const res  = await fetch(`/api/history/${id}`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    renderModalContent(data);
  } catch (err) {
    body.innerHTML = '<p style="color:var(--secondary);padding:20px">読み込みに失敗しました</p>';
  }
}

function renderModalContent(data) {
  const body = document.getElementById("modal-body");
  const ts   = (data.timestamp || "").slice(0, 16).replace("T", " ");
  const qs   = data.detailed_questions || [];
  const ans  = data.detailed_answers   || [];

  // Q&Aセクション
  let qaHtml = "";
  if (qs.length > 0) {
    qaHtml = `
      <div class="modal-section">
        <h3 class="modal-section-title">📋 掘り下げQ&amp;A</h3>
        ${qs.map((q, i) => {
          const a = ans[i] || "";
          return `
            <div class="qa-item">
              <p class="qa-question">Q${i + 1}. ${escH(q)}</p>
              <p class="qa-answer ${a ? "" : "qa-answer-empty"}">
                ${a ? escH(a) : "（未回答）"}
              </p>
            </div>
          `;
        }).join("")}
      </div>
    `;
  }

  // 相手情報
  let partnerHtml = "";
  if (data.partner_birthdate || data.relationship) {
    partnerHtml = `
      <div class="modal-section">
        <h3 class="modal-section-title">👥 相手の情報</h3>
        <p class="modal-text">
          ${data.relationship ? `関係性: ${escH(data.relationship)}<br>` : ""}
          ${data.partner_birthdate ? `生年月日: ${escH(data.partner_birthdate)}` : ""}
        </p>
      </div>
    `;
  }

  body.innerHTML = `
    <div class="modal-header">
      <div class="modal-id">鑑定 #${data.id}</div>
      <h2 class="modal-name">${data.name ? escH(data.name) : '<span class="anon">匿名</span>'}</h2>
      <p class="modal-meta">${ts}　|　生年月日: ${data.birthdate || "不明"}</p>
    </div>

    <div class="modal-section">
      <h3 class="modal-section-title">💬 相談内容</h3>
      <p class="modal-text">${escH(data.consultation || "")}</p>
    </div>

    ${partnerHtml}
    ${qaHtml}

    <div class="modal-section">
      <h3 class="modal-section-title">📜 鑑定結果</h3>
      <div class="modal-reading">${formatReading(data.result || "")}</div>
    </div>

    ${renderChatSection(data.chat_messages)}

    <div class="modal-actions">
      <button onclick="downloadEntry(${data.id})" class="btn-secondary">📥 テキストダウンロード</button>
      <button onclick="closeModal()" class="btn-outline">閉じる</button>
    </div>
  `;
}

function downloadEntry(id) {
  window.location.href = `/api/history/${id}/download`;
}

function closeModal() {
  document.getElementById("detail-modal").classList.add("hidden");
}

function handleOverlayClick(e) {
  if (e.target === document.getElementById("detail-modal")) closeModal();
}

function renderChatSection(messages) {
  if (!messages || messages.length === 0) return "";
  return `
    <div class="modal-section">
      <h3 class="modal-section-title">💬 追加質問チャット</h3>
      <div class="modal-chat">
        ${messages.map(m => `
          <div class="modal-chat-bubble ${m.role}">
            <span class="modal-chat-role">${m.role === "user" ? "お客様" : "星龍🐉"}</span>
            <div class="modal-chat-text">${escH(m.content)}</div>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

// ===== 鑑定文フォーマット（index.html の formatReading 簡易版） =====
function formatReading(raw) {
  if (!raw) return '<span class="anon">鑑定結果なし</span>';
  const parts = [];
  for (const line of raw.split("\n")) {
    if (!line.trim()) {
      parts.push('<div style="height:0.5em"></div>');
      continue;
    }
    if (/^【.+】/.test(line)) {
      parts.push(`<p class="reading-heading">${escH(line.trim())}</p>`);
      continue;
    }
    const formatted = escH(line).replace(
      /。(\p{Extended_Pictographic}*)/gu,
      (_, e) => "。" + e + "<br>"
    );
    parts.push(`<p class="reading-line">${formatted}</p>`);
  }
  return parts.join("\n");
}

// ===== ユーティリティ =====
function escH(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function truncate(str, max) {
  return str.length > max ? str.slice(0, max) + "…" : str;
}
