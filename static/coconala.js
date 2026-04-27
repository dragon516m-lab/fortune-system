/* ===== ococoナラ受注管理 フロントエンド ===== */

let allOrders       = [];
let activeFilter    = "all";
let modalOrderId    = null;
let modalReading    = "";
let modalFortuneData = null;

// ===== 初期化 =====
document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initManualForm();
  loadOrders();

  document.getElementById("parse-btn").addEventListener("click", handleParse);
  document.getElementById("register-parsed-btn").addEventListener("click", handleRegisterParsed);
  document.getElementById("register-manual-btn").addEventListener("click", handleRegisterManual);
  document.getElementById("add-entry-btn").addEventListener("click", addManualEntry);
  document.getElementById("bulk-fortune-btn").addEventListener("click", handleBulkFortune);

  // モーダル
  document.getElementById("modal-close").addEventListener("click", closeFortuneModal);
  document.getElementById("modal-copy-reading").addEventListener("click", copyReading);
  document.getElementById("modal-show-delivery").addEventListener("click", showDeliveryModal);
  document.getElementById("modal-save-image").addEventListener("click", saveModalImage);
  document.getElementById("delivery-close").addEventListener("click", closeDeliveryModal);
  document.getElementById("delivery-close2").addEventListener("click", closeDeliveryModal);
  document.getElementById("copy-delivery-btn").addEventListener("click", copyDelivery);
  document.getElementById("delivery-save-image-btn").addEventListener("click", saveModalImage);

  // バックドロップクリックで閉じる
  document.querySelectorAll(".cn-modal-backdrop").forEach(el => {
    el.addEventListener("click", () => {
      closeFortuneModal();
      closeDeliveryModal();
    });
  });
});

// ===== タブ =====
function initTabs() {
  document.querySelectorAll(".cn-tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".cn-tab-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      const tab = btn.dataset.tab;
      document.getElementById("tab-orders").classList.toggle("hidden", tab !== "orders");
      document.getElementById("tab-register").classList.toggle("hidden", tab !== "register");
    });
  });
}

// ===== ステータスフィルター =====
document.querySelectorAll(".cn-filter-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".cn-filter-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeFilter = btn.dataset.status;
    renderOrders();
  });
});

// ===== 受注一覧の読み込み・表示 =====
async function loadOrders() {
  try {
    const res = await fetch("/api/coconala/orders");
    allOrders = await res.json();
    renderOrders();
  } catch (err) {
    console.error("受注一覧の読み込みに失敗:", err);
  }
}

function renderOrders() {
  const listEl = document.getElementById("orders-list");
  const filtered = activeFilter === "all"
    ? allOrders
    : allOrders.filter(o => o.status === activeFilter);

  // 日付降順
  const sorted = [...filtered].sort((a, b) =>
    new Date(b.created_at) - new Date(a.created_at)
  );

  if (sorted.length === 0) {
    listEl.innerHTML = '<p class="empty-message">受注はありません</p>';
    return;
  }

  listEl.innerHTML = sorted.map(order => renderOrderCard(order)).join("");

  // 一括鑑定ボタンの表示制御
  const hasPending = allOrders.some(o => o.status === "未対応");
  document.getElementById("bulk-fortune-btn").style.display = hasPending ? "" : "none";
}

function renderOrderCard(order) {
  const statusClass = { "未対応": "pending", "鑑定中": "reading", "完了": "done" }[order.status] || "pending";
  const concernShort = order.concern.length > 60
    ? order.concern.slice(0, 60) + "..."
    : order.concern;

  const birthdateFormatted = formatDateJp(order.birthdate);

  let actionBtns = "";
  if (order.status === "未対応") {
    actionBtns = `
      <button class="cn-btn-sm cn-btn-fortune" onclick="startFortune('${order.id}')">✨ 鑑定する</button>
    `;
  } else if (order.status === "鑑定中") {
    actionBtns = `
      <button class="cn-btn-sm cn-btn-fortune" disabled>⏳ 鑑定中...</button>
    `;
  } else if (order.status === "完了") {
    actionBtns = `
      <button class="cn-btn-sm cn-btn-view"     onclick="viewReading('${order.id}')">📜 鑑定結果を見る</button>
      <button class="cn-btn-sm cn-btn-delivery" onclick="openDeliveryFor('${order.id}')">📤 納品テキスト</button>
      <button class="cn-btn-sm cn-btn-fortune"  onclick="startFortune('${order.id}')">🔄 再鑑定</button>
    `;
  }

  return `
    <div class="cn-order-card status-${statusClass}" id="card-${order.id}">
      <div class="cn-order-header">
        <div>
          <span class="cn-order-name">${esc(order.name || "（名前なし）")}</span>
          <span class="cn-order-meta">${birthdateFormatted}</span>
        </div>
        <span class="cn-status-badge ${statusClass}">${esc(order.status)}</span>
      </div>
      <div class="cn-order-concern">${esc(concernShort)}</div>
      <div class="cn-order-actions">
        ${actionBtns}
        <button class="cn-btn-sm cn-btn-delete" onclick="deleteOrder('${order.id}')">🗑️ 削除</button>
      </div>
    </div>
  `;
}

// ===== 鑑定実行 =====
async function startFortune(orderId) {
  const order = allOrders.find(o => o.id === orderId);
  if (!order) return;

  modalOrderId     = orderId;
  modalReading     = "";
  modalFortuneData = null;

  // モーダル初期化
  document.getElementById("modal-title").textContent = `🔮 ${order.name || "（名前なし）"} 様の鑑定`;
  document.getElementById("modal-info").innerHTML =
    `<strong>${esc(order.name || "（名前なし）")}</strong>　${formatDateJp(order.birthdate)}` +
    `<br><span style="color:var(--text-muted)">ご相談：${esc(order.concern.slice(0, 60))}${order.concern.length > 60 ? "…" : ""}</span>`;
  document.getElementById("modal-reading").innerHTML = "";
  document.getElementById("modal-loading").classList.remove("hidden");
  document.getElementById("modal-actions").classList.add("hidden");
  openModal("fortune-modal");

  try {
    const response = await fetch(`/api/coconala/orders/${orderId}/fortune`, {
      method: "POST",
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.error || "エラーが発生しました");
    }

    const reader  = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

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
          document.getElementById("modal-loading").classList.add("hidden");
          document.getElementById("modal-reading").innerHTML = '<span class="cursor"></span>';
        }

        if (payload.chunk) {
          modalReading += payload.chunk;
          document.getElementById("modal-reading").innerHTML =
            formatReading(modalReading) + '<span class="cursor"></span>';
        }

        if (payload.done) {
          modalReading     = payload.reading;
          modalFortuneData = payload.fortune_data;
          document.getElementById("modal-reading").innerHTML = formatReading(modalReading);
          document.getElementById("modal-actions").classList.remove("hidden");

          // 受注リスト更新
          const idx = allOrders.findIndex(o => o.id === orderId);
          if (idx !== -1) {
            allOrders[idx].status       = "完了";
            allOrders[idx].reading      = modalReading;
            allOrders[idx].fortune_data = modalFortuneData;
          }
          renderOrders();
          showToast("鑑定が完了しました ✨");
        }

        if (payload.error) {
          document.getElementById("modal-loading").classList.add("hidden");
          document.getElementById("modal-reading").textContent = `エラー: ${payload.error}`;
          const idx = allOrders.findIndex(o => o.id === orderId);
          if (idx !== -1) allOrders[idx].status = "未対応";
          renderOrders();
        }
      }
    }
  } catch (err) {
    document.getElementById("modal-loading").classList.add("hidden");
    document.getElementById("modal-reading").textContent = `エラー: ${err.message}`;
  }
}

// ===== 既存の鑑定結果を表示 =====
function viewReading(orderId) {
  const order = allOrders.find(o => o.id === orderId);
  if (!order || !order.reading) return;

  modalOrderId     = orderId;
  modalReading     = order.reading;
  modalFortuneData = order.fortune_data;

  document.getElementById("modal-title").textContent = `📜 ${order.name || "（名前なし）"} 様の鑑定結果`;
  document.getElementById("modal-info").innerHTML =
    `<strong>${esc(order.name || "（名前なし）")}</strong>　${formatDateJp(order.birthdate)}` +
    `<br><span style="color:var(--text-muted)">ご相談：${esc(order.concern.slice(0, 60))}${order.concern.length > 60 ? "…" : ""}</span>`;
  document.getElementById("modal-loading").classList.add("hidden");
  document.getElementById("modal-reading").innerHTML = formatReading(modalReading);
  document.getElementById("modal-actions").classList.remove("hidden");
  openModal("fortune-modal");
}

// ===== 納品テキスト =====
function openDeliveryFor(orderId) {
  const order = allOrders.find(o => o.id === orderId);
  if (!order || !order.reading) return;

  modalOrderId     = orderId;
  modalReading     = order.reading;
  modalFortuneData = order.fortune_data;

  showDeliveryModal();
}

function showDeliveryModal() {
  if (!modalReading) return;
  const order = allOrders.find(o => o.id === modalOrderId) || {};
  const deliveryText = buildDeliveryText(order, modalReading);
  document.getElementById("delivery-text").textContent = deliveryText;
  openModal("delivery-modal");
}

function buildDeliveryText(order, reading) {
  const name = order.name || "お客様";
  const lines = [
    `この度はご購入ありがとうございます。`,
    `鑑定結果をお届けします♪`,
    ``,
    `━━━━━━━━━━━━━━━━━━━━`,
    `✨ ${name}様の天命鑑定 ✨`,
    `━━━━━━━━━━━━━━━━━━━━`,
    ``,
    `【ご相談内容】`,
    order.concern || "",
    ``,
    `【鑑定結果】`,
    reading,
    ``,
    `━━━━━━━━━━━━━━━━━━━━`,
    ``,
    `ご不明な点がございましたら`,
    `お気軽にご質問ください。`,
    `どうぞよろしくお願いいたします🌟`,
  ];
  return lines.join("\n");
}

async function copyDelivery() {
  const text = document.getElementById("delivery-text").textContent;
  try {
    await navigator.clipboard.writeText(text);
    showToast("コピーしました ✓");
  } catch {
    showToast("コピーに失敗しました");
  }
}

async function copyReading() {
  try {
    await navigator.clipboard.writeText(modalReading);
    showToast("鑑定文をコピーしました ✓");
  } catch {
    showToast("コピーに失敗しました");
  }
}

// ===== 画像保存 =====
function saveModalImage() {
  if (!modalFortuneData) { showToast("鑑定データがありません"); return; }
  const order = allOrders.find(o => o.id === modalOrderId) || {};
  generateFortuneImage(order.name || "鑑定者", order.birthdate || "", modalFortuneData, modalReading);
}

// ===== 削除 =====
async function deleteOrder(orderId) {
  if (!confirm("この受注を削除しますか？")) return;
  try {
    await fetch(`/api/coconala/orders/${orderId}`, { method: "DELETE" });
    allOrders = allOrders.filter(o => o.id !== orderId);
    renderOrders();
    showToast("削除しました");
  } catch (err) {
    showToast("削除に失敗しました");
  }
}

// ===== 一括鑑定 =====
async function handleBulkFortune() {
  const pending = allOrders.filter(o => o.status === "未対応");
  if (pending.length === 0) { showToast("未対応の受注はありません"); return; }
  if (!confirm(`未対応の受注 ${pending.length} 件をまとめて鑑定しますか？`)) return;

  const progressEl  = document.getElementById("bulk-progress");
  const barEl       = document.getElementById("progress-bar");
  const textEl      = document.getElementById("progress-text");
  const bulkBtn     = document.getElementById("bulk-fortune-btn");

  progressEl.classList.remove("hidden");
  bulkBtn.disabled = true;
  barEl.style.width = "0%";
  textEl.textContent = "準備中...";

  try {
    const response = await fetch("/api/coconala/bulk-fortune", { method: "POST" });
    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.error || "エラーが発生しました");
    }

    const reader  = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = JSON.parse(line.slice(6));

        if (payload.status === "start") {
          textEl.textContent = `0 / ${payload.total} 件鑑定中...`;
        }

        if (payload.status === "processing") {
          textEl.textContent = `${payload.name || "（名前なし）"} 様を鑑定中... (${payload.completed}/${payload.total})`;
          barEl.style.width = `${Math.round(payload.completed / payload.total * 100)}%`;
        }

        if (payload.status === "done_one") {
          barEl.style.width = `${Math.round(payload.completed / payload.total * 100)}%`;
          textEl.textContent = `${payload.completed} / ${payload.total} 件完了`;
          // ローカルキャッシュ更新（ページリロードで最新状態を取得）
        }

        if (payload.status === "error_one") {
          showToast(`エラー: ${payload.error}`);
        }

        if (payload.status === "all_done") {
          barEl.style.width = "100%";
          textEl.textContent = `✅ 全 ${payload.total} 件中 ${payload.completed} 件完了`;
          await loadOrders();
          showToast(`一括鑑定が完了しました (${payload.completed}/${payload.total}件)`);
          setTimeout(() => progressEl.classList.add("hidden"), 3000);
        }
      }
    }
  } catch (err) {
    textEl.textContent = `エラー: ${err.message}`;
    showToast("一括鑑定に失敗しました");
  } finally {
    bulkBtn.disabled = false;
  }
}

// ===== 受注登録 - ペースト解析 =====
let parsedData = [];

function handleParse() {
  const text = document.getElementById("paste-text").value.trim();
  if (!text) { showToast("テキストを入力してください"); return; }

  parsedData = parseCoconalaText(text);
  renderParsedEntries();
  document.getElementById("parse-result").classList.remove("hidden");
}

function parseCoconalaText(text) {
  // ブロック分割（--- / === / ―― などで区切る）
  const blocks = text.split(/\n\s*(?:---+|===+|———+|ーーー+)\s*\n/);
  return blocks.map(block => parseBlock(block.trim())).filter(e => e !== null);
}

function parseBlock(block) {
  if (!block) return null;
  const lines = block.split("\n").map(l => l.trim()).filter(l => l);
  if (lines.length === 0) return null;

  let name = "", birthdate = "", concern = "";
  const usedLines = new Set();

  // ラベル付き形式を優先解析
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    // 名前
    if (/^(?:お?名前|氏名|ニックネーム|ハンドルネーム)\s*[:：]/.test(line)) {
      name = line.replace(/^[^:：]+[:：]\s*/, "").trim();
      usedLines.add(i);
      continue;
    }
    // 生年月日
    if (/^(?:生年月日|お?誕生日|birthday|birth)\s*[:：]/i.test(line)) {
      const raw = line.replace(/^[^:：]+[:：]\s*/, "").trim();
      birthdate = parseDate(raw);
      usedLines.add(i);
      continue;
    }
    // 相談内容
    if (/^(?:ご?相談(?:内容)?|お?悩み|質問|concern)\s*[:：]/i.test(line)) {
      concern = line.replace(/^[^:：]+[:：]\s*/, "").trim();
      usedLines.add(i);
      continue;
    }
  }

  // ラベルなし形式: 日付らしい行を探す
  if (!birthdate) {
    for (let i = 0; i < lines.length; i++) {
      if (usedLines.has(i)) continue;
      const d = parseDate(lines[i]);
      if (d) {
        birthdate = d;
        usedLines.add(i);
        break;
      }
    }
  }

  // 名前が見つかっていない場合: 最初の未使用行
  if (!name) {
    for (let i = 0; i < lines.length; i++) {
      if (usedLines.has(i)) continue;
      // 短い行 (30文字以内) かつ日付でなければ名前と判定
      if (lines[i].length <= 30 && !parseDate(lines[i])) {
        name = lines[i].replace(/^[■▶◆•・\-\s]+/, "").trim();
        usedLines.add(i);
        break;
      }
    }
  }

  // 相談内容が見つかっていない場合: 残りすべて
  if (!concern) {
    const remaining = lines.filter((_, i) => !usedLines.has(i));
    concern = remaining.join("\n").trim();
  }

  const errors = [];
  if (!birthdate) errors.push("生年月日が見つかりません");
  if (!concern)   errors.push("相談内容が見つかりません");

  return { name, birthdate, concern, errors, valid: errors.length === 0 };
}

function parseDate(str) {
  if (!str) return "";
  str = str.trim();

  // 和暦変換
  const eraMap = {
    "令和": 2018, "R": 2018,
    "平成": 1988, "H": 1988,
    "昭和": 1925, "S": 1925,
    "大正": 1911, "T": 1911,
    "明治": 1867, "M": 1867,
  };
  for (const [era, base] of Object.entries(eraMap)) {
    const m = str.match(new RegExp(`^${era}(\\d+)[年./](\\d+)[月./](\\d+)日?$`));
    if (m) {
      const y = base + parseInt(m[1]);
      return `${y}-${String(m[2]).padStart(2,"0")}-${String(m[3]).padStart(2,"0")}`;
    }
  }

  // YYYY年MM月DD日
  let m = str.match(/^(\d{4})[年\/\-.](\d{1,2})[月\/\-.](\d{1,2})日?$/);
  if (m) return `${m[1]}-${String(m[2]).padStart(2,"0")}-${String(m[3]).padStart(2,"0")}`;

  // YYYY/M/D or YYYY-M-D
  m = str.match(/^(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})$/);
  if (m) return `${m[1]}-${String(m[2]).padStart(2,"0")}-${String(m[3]).padStart(2,"0")}`;

  return "";
}

function renderParsedEntries() {
  const el = document.getElementById("parsed-entries");
  if (parsedData.length === 0) {
    el.innerHTML = '<p class="empty-message">解析できませんでした</p>';
    return;
  }

  el.innerHTML = parsedData.map((entry, i) => `
    <div class="cn-parsed-entry ${entry.valid ? "valid" : "invalid"}">
      <div class="cn-entry-row">
        <div>
          <div class="cn-entry-label">名前</div>
          <div class="cn-entry-value">${esc(entry.name || "（なし）")}</div>
        </div>
        <div>
          <div class="cn-entry-label">生年月日</div>
          <div class="cn-entry-value">${esc(entry.birthdate ? formatDateJp(entry.birthdate) : "（未取得）")}</div>
        </div>
      </div>
      <div>
        <div class="cn-entry-label">相談内容</div>
        <div class="cn-entry-value">${esc(entry.concern ? (entry.concern.slice(0,80) + (entry.concern.length > 80 ? "…" : "")) : "（なし）")}</div>
      </div>
      ${entry.errors.length > 0
        ? `<div class="cn-entry-error">⚠️ ${entry.errors.join(" / ")}</div>`
        : `<div style="font-size:0.75rem;color:#81c784;margin-top:4px">✅ 登録可能</div>`
      }
    </div>
  `).join("");

  const validCount = parsedData.filter(e => e.valid).length;
  document.getElementById("register-parsed-btn").textContent =
    `✅ ${validCount} 件を登録する`;
  document.getElementById("register-parsed-btn").disabled = validCount === 0;
}

async function handleRegisterParsed() {
  const valid = parsedData.filter(e => e.valid);
  if (valid.length === 0) return;

  await registerEntries(valid);
}

// ===== 手動入力 =====
let manualEntryCount = 0;

function initManualForm() {
  addManualEntry();
}

function addManualEntry() {
  manualEntryCount++;
  const n   = manualEntryCount;
  const div = document.createElement("div");
  div.className = "cn-manual-entry";
  div.id = `manual-entry-${n}`;
  div.innerHTML = `
    <div class="cn-entry-num">件 ${n}</div>
    ${n > 1 ? `<button class="cn-remove-entry" onclick="removeManualEntry(${n})">✕</button>` : ""}
    <div class="form-group">
      <label>お名前（任意）</label>
      <input type="text" class="me-name" placeholder="山田花子">
    </div>
    <div class="form-group">
      <label>生年月日 <span class="required">*</span></label>
      <input type="date" class="me-birthdate" required max="${new Date().toISOString().split("T")[0]}">
    </div>
    <div class="form-group" style="margin-bottom:0">
      <label>相談内容 <span class="required">*</span></label>
      <textarea class="me-concern" rows="3" placeholder="例：仕事での人間関係について..." required></textarea>
    </div>
  `;
  document.getElementById("manual-entries").appendChild(div);
}

function removeManualEntry(n) {
  const el = document.getElementById(`manual-entry-${n}`);
  if (el) el.remove();
}

async function handleRegisterManual() {
  const entryEls = document.querySelectorAll(".cn-manual-entry");
  const entries  = [];

  for (const el of entryEls) {
    const name      = el.querySelector(".me-name").value.trim();
    const birthdate = el.querySelector(".me-birthdate").value;
    const concern   = el.querySelector(".me-concern").value.trim();

    if (!birthdate || !concern) continue;
    entries.push({ name, birthdate, concern });
  }

  if (entries.length === 0) {
    showToast("生年月日と相談内容を入力してください");
    return;
  }

  await registerEntries(entries);

  // フォームリセット
  document.getElementById("manual-entries").innerHTML = "";
  manualEntryCount = 0;
  initManualForm();
}

async function registerEntries(entries) {
  try {
    const res  = await fetch("/api/coconala/orders", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ entries }),
    });
    const data = await res.json();

    if (data.error) throw new Error(data.error);

    showToast(`${data.created} 件の受注を登録しました ✓`);
    await loadOrders();

    // 一覧タブに切り替え
    document.querySelectorAll(".cn-tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelector('[data-tab="orders"]').classList.add("active");
    document.getElementById("tab-orders").classList.remove("hidden");
    document.getElementById("tab-register").classList.add("hidden");

    // テキストエリアリセット
    document.getElementById("paste-text").value = "";
    document.getElementById("parse-result").classList.add("hidden");
    parsedData = [];
  } catch (err) {
    showToast("登録に失敗しました: " + err.message);
  }
}

// ===== モーダル操作 =====
function openModal(id) {
  document.getElementById(id).classList.remove("hidden");
  document.body.style.overflow = "hidden";
}

function closeFortuneModal() {
  document.getElementById("fortune-modal").classList.add("hidden");
  document.body.style.overflow = "";
}

function closeDeliveryModal() {
  document.getElementById("delivery-modal").classList.add("hidden");
  document.body.style.overflow = "";
}

// ===== 画像生成（Canvas API） =====
function generateFortuneImage(name, birthdate, fortuneData, readingText) {
  if (!fortuneData) return;

  const ani = fortuneData.animal;
  const num = fortuneData.numerology;
  const sc  = fortuneData.shichusuimei;

  const W = 1080, H = 1350;
  const canvas = document.createElement("canvas");
  canvas.width  = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");

  const bg = ctx.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, "#0d0b1e");
  bg.addColorStop(0.45, "#1a1040");
  bg.addColorStop(1, "#080818");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  const glow = ctx.createRadialGradient(W/2, 380, 0, W/2, 380, 500);
  glow.addColorStop(0, "rgba(124,77,255,0.25)");
  glow.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, W, H);

  const starSeeds = [
    [112,80],[934,200],[55,450],[1020,320],[500,60],[780,110],
    [230,700],[860,650],[140,900],[970,820],[430,1100],[680,1200],
    [80,1280],[1010,1100],[320,300],[700,400],[150,550],[900,500],
  ];
  for (const [sx, sy] of starSeeds) {
    const r = (((sx*7+sy*13)%12)/10)+0.5;
    const a = (((sx*3+sy*5)%7)/9)+0.25;
    ctx.beginPath();
    ctx.arc(sx, sy, r, 0, Math.PI*2);
    ctx.fillStyle = `rgba(255,255,255,${a.toFixed(2)})`;
    ctx.fill();
  }

  const borderG = ctx.createLinearGradient(0,0,W,H);
  borderG.addColorStop(0, "#ffd700");
  borderG.addColorStop(0.5, "#ff9fd0");
  borderG.addColorStop(1, "#b39ddb");
  ctx.strokeStyle = borderG;
  ctx.lineWidth = 3;
  imgRoundRect(ctx, 28, 28, W-56, H-56, 22); ctx.stroke();

  const font = '"Hiragino Kaku Gothic ProN","Yu Gothic","Meiryo",sans-serif';
  ctx.textAlign = "center";
  ctx.textBaseline = "alphabetic";
  let y = 105;

  ctx.font = `48px ${font}`; ctx.fillStyle = "#ffd700";
  ctx.fillText("✨", W/2-220, y+5); ctx.fillText("✨", W/2+220, y+5);
  y += 72;
  const tG = ctx.createLinearGradient(W/2-300,0,W/2+300,0);
  tG.addColorStop(0,"#ffd700"); tG.addColorStop(0.5,"#ffb3d4"); tG.addColorStop(1,"#c4b5fd");
  ctx.fillStyle = tG;
  ctx.font = `bold 62px ${font}`; ctx.fillText("あなただけの鑑定書", W/2, y);
  y += 48;
  ctx.fillStyle = "rgba(179,157,219,0.75)";
  ctx.font = `28px ${font}`; ctx.fillText("四柱推命 × 数秘術 × 動物占い　統合鑑定", W/2, y);
  y += 44;
  imgDivider(ctx, W, y); y += 30;

  imgCard(ctx, 60, y, W-120, 185, "rgba(124,77,255,0.12)");
  ctx.fillStyle="rgba(255,255,255,0.45)"; ctx.font=`24px ${font}`; ctx.fillText("鑑定者", W/2, y+42);
  ctx.fillStyle="#ffffff"; ctx.font=`bold 54px ${font}`; ctx.fillText(name||"鑑定者", W/2, y+108);
  ctx.fillStyle="rgba(255,255,255,0.5)"; ctx.font=`26px ${font}`; ctx.fillText(imgFormatDate(birthdate), W/2, y+150);
  y += 205;
  ctx.fillStyle="rgba(179,157,219,0.7)"; ctx.font=`24px ${font}`;
  ctx.fillText(`年柱 ${sc.year_pillar.pillar}　月柱 ${sc.month_pillar.pillar}　日柱 ${sc.day_pillar.pillar}`, W/2, y);
  y += 40; imgDivider(ctx,W,y); y += 36;

  ctx.fillStyle="rgba(255,215,0,0.75)"; ctx.font=`26px ${font}`; ctx.fillText("✦  動物占い  ✦", W/2, y);
  y += 16;
  const lx=W/2-195, rx=W/2+195;
  ctx.font=`88px sans-serif`;
  ctx.fillText(ani.year_animal.emoji, lx, y+88); ctx.fillText(ani.day_animal.emoji, rx, y+88);
  ctx.fillStyle="rgba(255,215,0,0.5)"; ctx.font=`38px ${font}`; ctx.fillText("×", W/2, y+60);
  ctx.fillStyle="rgba(255,255,255,0.45)"; ctx.font=`22px ${font}`;
  ctx.fillText("表の顔", lx, y+118); ctx.fillText("内なる本質", rx, y+118);
  ctx.fillStyle="#ffffff"; ctx.font=`bold 34px ${font}`;
  ctx.fillText(ani.year_animal.animal, lx, y+158); ctx.fillText(ani.day_animal.animal, rx, y+158);
  y += 185;
  ctx.fillStyle="rgba(179,157,219,0.65)"; ctx.font=`23px ${font}`;
  ctx.fillText(ani.year_animal.traits, W/2, y);
  y += 40; imgDivider(ctx,W,y); y += 36;

  ctx.fillStyle="rgba(255,215,0,0.75)"; ctx.font=`26px ${font}`; ctx.fillText("✦  数秘術  ✦", W/2, y);
  y += 18;
  const nG=ctx.createLinearGradient(W/2-70,0,W/2+70,0);
  nG.addColorStop(0,"#ffd700"); nG.addColorStop(1,"#ff9fd0");
  ctx.fillStyle=nG; ctx.font=`bold 110px ${font}`; ctx.fillText(String(num.life_path_number), W/2, y+100);
  ctx.fillStyle="rgba(255,255,255,0.45)"; ctx.font=`24px ${font}`;
  ctx.fillText("ライフパスナンバー"+(num.is_master_number?"（マスターナンバー）":""), W/2, y+138);
  ctx.fillStyle="rgba(179,157,219,0.8)"; ctx.font=`23px ${font}`;
  imgWrapText(ctx, num.life_path_meaning, W/2, y+178, W-180, 34);
  y += 235; imgDivider(ctx,W,y); y += 36;

  ctx.fillStyle="rgba(255,215,0,0.75)"; ctx.font=`26px ${font}`; ctx.fillText("✦  鑑定メッセージ  ✦", W/2, y);
  y += 42;
  const excerpt = imgExcerpt(readingText, 90);
  ctx.fillStyle="rgba(255,255,255,0.88)"; ctx.font=`25px ${font}`;
  imgWrapText(ctx, excerpt, W/2, y, W-180, 38);

  const today = new Date().toLocaleDateString("ja-JP", {year:"numeric",month:"long",day:"numeric"});
  ctx.fillStyle="rgba(255,255,255,0.28)"; ctx.font=`22px ${font}`;
  ctx.fillText(`鑑定日：${today}`, W/2, H-52);

  const link = document.createElement("a");
  link.download = `fortune_${birthdate||"reading"}.png`;
  link.href = canvas.toDataURL("image/png");
  link.click();
  showToast("画像を保存しました ✨");
}

// ===== Canvas ヘルパー =====
function imgRoundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x+r, y); ctx.lineTo(x+w-r, y);
  ctx.quadraticCurveTo(x+w, y, x+w, y+r);
  ctx.lineTo(x+w, y+h-r);
  ctx.quadraticCurveTo(x+w, y+h, x+w-r, y+h);
  ctx.lineTo(x+r, y+h);
  ctx.quadraticCurveTo(x, y+h, x, y+h-r);
  ctx.lineTo(x, y+r);
  ctx.quadraticCurveTo(x, y, x+r, y);
  ctx.closePath();
}
function imgDivider(ctx, W, y) {
  const g=ctx.createLinearGradient(80,0,W-80,0);
  g.addColorStop(0,"rgba(255,215,0,0)"); g.addColorStop(0.3,"rgba(255,215,0,0.55)");
  g.addColorStop(0.7,"rgba(255,215,0,0.55)"); g.addColorStop(1,"rgba(255,215,0,0)");
  ctx.save(); ctx.strokeStyle=g; ctx.lineWidth=1;
  ctx.beginPath(); ctx.moveTo(80,y); ctx.lineTo(W-80,y); ctx.stroke(); ctx.restore();
}
function imgCard(ctx, x, y, w, h, color) {
  ctx.save(); imgRoundRect(ctx,x,y,w,h,18); ctx.fillStyle=color; ctx.fill(); ctx.restore();
}
function imgWrapText(ctx, text, cx, y, maxWidth, lineH) {
  let line="";
  for (const ch of text) {
    const test=line+ch;
    if (ctx.measureText(test).width>maxWidth && line.length>0) {
      ctx.fillText(line, cx, y); line=ch; y+=lineH;
    } else { line=test; }
  }
  if (line) ctx.fillText(line, cx, y);
  return y+lineH;
}
function imgExcerpt(text, maxLen) {
  const clean=text.replace(/【[^】]*】/g,"").replace(/◆[^\n]*/g,"").replace(/\n+/g," ").trim();
  const first=clean.split("。")[0];
  const src=(first.length>15?first:clean).trim();
  return src.length>maxLen?src.slice(0,maxLen)+"…":src;
}
function imgFormatDate(s) {
  if (!s) return "";
  const [y,m,d]=s.split("-");
  return `${y}年${parseInt(m)}月${parseInt(d)}日`;
}

// ===== ユーティリティ =====
function formatDateJp(s) {
  if (!s) return "";
  const [y, m, d] = s.split("-");
  return `${y}年${parseInt(m)}月${parseInt(d)}日`;
}

function formatReading(raw) {
  const lines = raw.split("\n");
  const htmlParts = [];
  let blankCount = 0;

  for (const line of lines) {
    if (/^\s*[-*_]{3,}\s*$/.test(line)) { blankCount++; continue; }

    const headingMd  = line.match(/^#{1,3}\s+(.+)$/);
    const headingDot = line.match(/^[◆✦★☆]\s*(.+)$/);

    if (headingMd || headingDot) {
      const text = headingMd ? headingMd[1].trim() : headingDot[1].trim();
      if (htmlParts.length > 0) htmlParts.push('<div class="reading-spacer"></div>');
      htmlParts.push('<p class="reading-heading">' + esc(text) + '</p>');
      blankCount = 0; continue;
    }

    if (/^【.+】/.test(line)) {
      if (htmlParts.length > 0) htmlParts.push('<div class="reading-spacer"></div>');
      htmlParts.push('<p class="reading-heading">' + esc(line.trim()) + '</p>');
      blankCount = 0; continue;
    }

    if (line.trim() === "") {
      blankCount++;
      if (blankCount === 1 && htmlParts.length > 0)
        htmlParts.push('<div class="reading-para-break"></div>');
      continue;
    }

    blankCount = 0;
    let l = line.replace(/^>\s?/, "");
    l = l.replace(/\*\*(.+?)\*\*/g, (_, t) => '<strong>' + esc(t) + '</strong>');
    l = l.replace(/__(.+?)__/g,     (_, t) => '<strong>' + esc(t) + '</strong>');
    l = l.replace(/\*(.+?)\*/g, "$1").replace(/_([^_]+)_/g, "$1").replace(/`(.+?)`/g, "$1");
    htmlParts.push('<p class="reading-line">' + escLine(l) + '</p>');
  }
  return htmlParts.join("\n");
}

function escLine(line) {
  return line.replace(/(<strong>.*?<\/strong>)|([^<]+)/g, (match, tag, text) => {
    if (tag) return tag;
    return text.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  });
}

function esc(str) {
  return String(str)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function showToast(message) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 2000);
}
