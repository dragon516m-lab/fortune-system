/* 占い鑑定システム フロントエンド */

let currentFileId = null;
let currentReadingText = "";
let currentFortuneData = null;
let currentHistoryId = null;

// ===== 初期化 =====
document.addEventListener("DOMContentLoaded", () => {
  loadHistory();

  document.getElementById("fortune-form").addEventListener("submit", handleSubmit);
  document.getElementById("image-btn").addEventListener("click", generateFortuneImage);
  document.getElementById("download-btn").addEventListener("click", handleDownload);
  document.getElementById("copy-btn").addEventListener("click", handleCopy);
  document.getElementById("new-reading-btn").addEventListener("click", resetForm);
  document.getElementById("retry-btn").addEventListener("click", handleRetry);
  document.getElementById("threads-btn").addEventListener("click", handleThreadsPost);
  document.getElementById("detail-option-cb").addEventListener("change", handleDetailOptionChange);
  document.getElementById("generate-questions-btn").addEventListener("click", generateFollowUpQuestions);
  document.getElementById("chat-open-btn").addEventListener("click", openChat);
  document.getElementById("chat-send-btn").addEventListener("click", sendChatMessage);
  document.getElementById("chat-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); sendChatMessage(); }
  });

  // 生年月日の最大値を今日に設定
  document.getElementById("birthdate").max = new Date().toISOString().split("T")[0];
});

// ===== フォーム送信 =====
async function handleSubmit(e) {
  e.preventDefault();

  const name = document.getElementById("name").value.trim();
  const birthdate = document.getElementById("birthdate").value;
  const concern = document.getElementById("concern").value.trim();

  if (!birthdate || !concern) {
    alert("生年月日とお悩みを入力してください");
    return;
  }

  // UI をローディング状態に
  const submitBtn = document.getElementById("submit-btn");
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="btn-icon">⏳</span> 鑑定中...';

  const resultSection = document.getElementById("result-section");
  const statsGrid = document.getElementById("fortune-stats");
  const loading = document.getElementById("loading");
  const readingText = document.getElementById("reading-text");
  const actionButtons = document.getElementById("action-buttons");

  resultSection.classList.remove("hidden");
  statsGrid.classList.add("hidden");
  loading.classList.remove("hidden");
  readingText.textContent = "";
  actionButtons.classList.add("hidden");
  currentReadingText = "";

  // スクロール
  resultSection.scrollIntoView({ behavior: "smooth" });

  try {
    const detailContext = getFollowUpContext();
    const { questions: dQuestions, answers: dAnswers } = getFollowUpArrays();
    const response = await fetch("/api/fortune", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        birthdate,
        concern,
        detail_context:     detailContext || "",
        detailed_questions: dQuestions,
        detailed_answers:   dAnswers,
        partner_birthdate:  "",
        relationship:       "",
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "エラーが発生しました");
    }

    // SSE ストリーミング読み込み
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let statsShown = false;
    let receivedDone = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = JSON.parse(line.slice(6));

        if (payload.error) {
          readingText.textContent = `エラー: ${payload.error}`;
          actionButtons.classList.remove("hidden");
          break;
        }

        if (payload.status === "connecting") {
          loading.classList.add("hidden");
          readingText.innerHTML = '<span class="cursor"></span>';
        }

        if (payload.chunk) {
          currentReadingText += payload.chunk;
          readingText.innerHTML = formatReading(currentReadingText) + '<span class="cursor"></span>';
        }

        if (payload.done) {
          receivedDone = true;
          readingText.innerHTML = formatReading(currentReadingText);
          currentFileId = payload.file_id;
          currentFortuneData = payload.fortune_data;
          currentHistoryId = payload.history_id || null;

          if (!statsShown) {
            renderFortuneStats(payload.fortune_data);
            statsGrid.classList.remove("hidden");
            statsShown = true;
          }

          actionButtons.classList.remove("hidden");
          document.getElementById("retry-area").classList.add("hidden");
          loadHistory();
        }
      }
    }

    // doneイベントなしにストリームが終了した場合
    if (!receivedDone && currentReadingText) {
      readingText.innerHTML = formatReading(currentReadingText);
      document.getElementById("retry-area").classList.remove("hidden");
    }

  } catch (err) {
    loading.classList.add("hidden");
    if (currentReadingText) {
      readingText.innerHTML = formatReading(currentReadingText);
      document.getElementById("retry-area").classList.remove("hidden");
    } else {
      readingText.textContent = `エラーが発生しました: ${err.message}`;
    }
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = '<span class="btn-icon">✨</span> 鑑定する';
  }
}

// ===== 命式データのレンダリング =====
function renderFortuneStats(data) {
  // 四柱推命
  const sc = data.shichusuimei;
  const pillarsEl = document.getElementById("pillars");
  pillarsEl.innerHTML = `
    <div class="pillar-row">
      <span class="pillar-badge" title="年柱">年 ${sc.year_pillar.pillar}</span>
      <span class="pillar-badge" title="月柱">月 ${sc.month_pillar.pillar}</span>
      <span class="pillar-badge" title="日柱">日 ${sc.day_pillar.pillar}</span>
    </div>
    <p style="font-size:0.8rem;color:#9e9e9e">日干：${sc.day_master.stem}（${sc.day_master.element}）</p>
  `;
  const fe = sc.five_elements.count;
  const fiveEl = document.getElementById("five-elements");
  fiveEl.innerHTML = `<div class="element-bar">
    ${["木","火","土","金","水"].map(e => `<span class="element-tag">${e}${fe[e]}</span>`).join("")}
  </div>`;

  // 数秘術
  const num = data.numerology;
  const numbersEl = document.getElementById("numbers");
  numbersEl.innerHTML = `
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
      <span class="number-big">${num.life_path_number}</span>
      <span style="font-size:0.8rem;color:#9e9e9e">ライフパス${num.is_master_number ? '<br><span style="color:#ffd700">マスターナンバー</span>' : ''}</span>
    </div>
    <p style="font-size:0.8rem;color:#9e9e9e">デスティニー：${num.destiny_number} / ソウル：${num.soul_number}</p>
  `;

  // 動物占い
  const ani = data.animal;
  const animalsEl = document.getElementById("animals");
  animalsEl.innerHTML = `
    <div style="display:flex;gap:16px;align-items:center;margin-bottom:8px">
      <div style="text-align:center">
        <div class="animal-emoji">${ani.year_animal.emoji}</div>
        <div style="font-size:0.75rem;color:#9e9e9e">表</div>
      </div>
      <div style="text-align:center">
        <div class="animal-emoji">${ani.day_animal.emoji}</div>
        <div style="font-size:0.75rem;color:#9e9e9e">内</div>
      </div>
    </div>
    <p style="font-size:0.78rem;color:#9e9e9e">${ani.year_animal.animal} × ${ani.day_animal.animal}</p>
  `;
}

// ===== ダウンロード =====
function handleDownload() {
  if (!currentFileId) return;
  window.location.href = `/api/download/${currentFileId}`;
}

// ===== コピー =====
async function handleCopy() {
  if (!currentReadingText) return;
  try {
    const text = currentReadingText.replace(/。(\p{Extended_Pictographic}*)/gu, (_, e) => "。" + e + "\n");
    await navigator.clipboard.writeText(text);
    showToast("コピーしました ✓");
  } catch {
    showToast("コピーに失敗しました");
  }
}

// ===== Threads投稿 =====
async function handleThreadsPost() {
  if (!currentReadingText || !currentFortuneData) return;

  const btn = document.getElementById("threads-btn");
  btn.disabled = true;
  btn.textContent = "⏳ 投稿中...";

  const text = buildThreadsText(currentFortuneData, currentReadingText);

  try {
    const res = await fetch("/api/post-threads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const data = await res.json();

    if (data.error === "threads_not_configured") {
      showToast("Threadsの設定が必要です（.envを確認）");
    } else if (data.error) {
      showToast("投稿に失敗しました: " + (data.error));
    } else {
      showToast("Threadsに投稿しました ✓");
    }
  } catch (err) {
    showToast("投稿に失敗しました");
  } finally {
    btn.disabled = false;
    btn.textContent = "🧵 Threadsに投稿";
  }
}

/** Threads用テキストを組み立てる（500字以内） */
function buildThreadsText(fortuneData, readingRaw) {
  const ani = fortuneData.animal;
  const num = fortuneData.numerology;

  // 鑑定文から最初のセクションのテキストを抜き出す
  const plain = readingRaw
    .replace(/【[^】]*】/g, "")   // 【見出し】除去
    .replace(/^\s*[-#*>]+\s*/gm, "") // Markdown記号除去
    .replace(/\n{2,}/g, "\n")
    .trim();
  const excerpt = plain.length > 200 ? plain.slice(0, 197) + "…" : plain;

  const header = [
    "✨ 天命鑑定 ✨",
    "",
    `${ani.year_animal.emoji} ${ani.year_animal.animal} × ${ani.day_animal.emoji} ${ani.day_animal.animal}`,
    `🔢 ライフパス ${num.life_path_number}`,
    "",
  ].join("\n");

  const hashtags = "\n\n#占い #四柱推命 #数秘術 #動物占い #天命鑑定";
  const maxExcerpt = 500 - header.length - hashtags.length;
  const body = plain.length > maxExcerpt ? plain.slice(0, maxExcerpt - 1) + "…" : plain;

  return header + body + hashtags;
}

// ===== 続きを取得 =====
async function handleRetry() {
  const retryArea = document.getElementById("retry-area");
  const readingText = document.getElementById("reading-text");
  const retryBtn = document.getElementById("retry-btn");

  retryBtn.disabled = true;
  retryBtn.textContent = "⏳ 続きを取得中...";

  const concern = document.getElementById("concern").value.trim();
  const partialText = currentReadingText;

  try {
    const response = await fetch("/api/continue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ partial_text: partialText, concern }),
    });

    const reader = response.body.getReader();
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

        if (payload.chunk) {
          currentReadingText += payload.chunk;
          readingText.innerHTML = formatReading(currentReadingText) + '<span class="cursor"></span>';
        }

        if (payload.done) {
          readingText.innerHTML = formatReading(currentReadingText);
          retryArea.classList.add("hidden");
        }
      }
    }
  } catch (err) {
    retryBtn.textContent = "🔄 続きを取得する";
  } finally {
    retryBtn.disabled = false;
    retryBtn.textContent = "🔄 続きを取得する";
  }
}

// ===== チャット（追加質問） =====

let chatMessages = [];

async function saveChatToHistory() {
  if (!currentHistoryId) return;
  try {
    await fetch(`/api/history/${currentHistoryId}/chat`, {
      method:  "PATCH",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ chat_messages: chatMessages }),
    });
  } catch (_) {}
}

function openChat() {
  const section = document.getElementById("chat-section");
  section.classList.remove("hidden");
  section.scrollIntoView({ behavior: "smooth" });
  document.getElementById("chat-input").focus();
}

async function sendChatMessage() {
  const input = document.getElementById("chat-input");
  const text  = input.value.trim();
  if (!text) return;
  if (!currentReadingText) {
    alert("鑑定結果が読み込まれていません。ページを再読み込みして、もう一度鑑定を実行してください。");
    return;
  }

  const sendBtn = document.getElementById("chat-send-btn");
  sendBtn.disabled = true;
  input.value = "";

  // ユーザーのバブルを追加
  chatMessages.push({ role: "user", content: text });
  appendChatBubble("user", text);

  // AIの空バブルを追加（ストリーミング用）
  const aiBubble = appendChatBubble("assistant", "");

  try {
    const concern = document.getElementById("concern").value.trim();
    const response = await fetch("/api/chat", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        fortune_context: { concern, reading: currentReadingText },
        messages: chatMessages,
      }),
    });

    const reader  = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer    = "";
    let aiText    = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = JSON.parse(line.slice(6));
        if (payload.chunk) {
          aiText += payload.chunk;
          aiBubble.innerHTML = formatReading(aiText) + '<span class="cursor"></span>';
          aiBubble.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
        if (payload.done) {
          aiBubble.innerHTML = formatReading(aiText);
          chatMessages.push({ role: "assistant", content: aiText });
          saveChatToHistory();
        }
        if (payload.error) {
          aiBubble.textContent = "エラーが発生しました";
        }
      }
    }
  } catch (err) {
    aiBubble.textContent = "エラーが発生しました";
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

function appendChatBubble(role, text) {
  const messages = document.getElementById("chat-messages");
  const wrap     = document.createElement("div");
  wrap.className = `chat-bubble-wrap ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";
  bubble.innerHTML = text ? formatReading(text) : "";

  wrap.appendChild(bubble);
  messages.appendChild(wrap);
  bubble.scrollIntoView({ behavior: "smooth", block: "nearest" });
  return bubble;
}

// ===== 詳細鑑定オプション =====

function handleDetailOptionChange(e) {
  const followUpSection = document.getElementById("follow-up-section");
  if (e.target.checked) {
    followUpSection.classList.remove("hidden");
  } else {
    followUpSection.classList.add("hidden");
    const container = document.getElementById("questions-container");
    container.classList.add("hidden");
    container.innerHTML = "";
  }
}

async function generateFollowUpQuestions() {
  const concern = document.getElementById("concern").value.trim();
  if (!concern) {
    alert("まずお悩み・ご相談を入力してください");
    return;
  }

  const btn       = document.getElementById("generate-questions-btn");
  const loading   = document.getElementById("questions-loading");
  const container = document.getElementById("questions-container");

  btn.disabled = true;
  btn.textContent = "⏳ 生成中...";
  loading.classList.remove("hidden");
  container.classList.add("hidden");
  container.innerHTML = "";

  try {
    const res  = await fetch("/api/generate-questions", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ concern }),
    });
    const data = await res.json();

    if (data.error) {
      alert("質問の生成に失敗しました: " + data.error);
      return;
    }

    renderFollowUpQuestions(data.questions);
    container.classList.remove("hidden");
  } catch (err) {
    alert("質問の生成に失敗しました");
  } finally {
    btn.disabled    = false;
    btn.textContent = "🔍 掘り下げ質問を生成する";
    loading.classList.add("hidden");
  }
}

function renderFollowUpQuestions(questions) {
  const nums = ["①", "②", "③", "④", "⑤"];
  const container = document.getElementById("questions-container");
  container.innerHTML = `
    ${questions.map((q, i) => `
      <div class="question-item">
        <p class="question-text">${nums[i] || `Q${i + 1}`} ${esc(q)}</p>
        <div class="answer-row">
          <span class="answer-label">A${i + 1}、</span>
          <textarea
            class="question-answer"
            data-qi="${i}"
            rows="2"
            placeholder="こちらに回答を入力..."
          ></textarea>
        </div>
      </div>
    `).join("")}
    <button type="button" class="btn-secondary" onclick="copyFollowUpQA()" style="margin-top:12px;width:100%;padding:10px;font-size:0.875rem">
      📋 質問文をコピー
    </button>
  `;
}

async function copyFollowUpQA() {
  const container = document.getElementById("questions-container");
  const items     = container.querySelectorAll(".question-item");
  const name      = document.getElementById("name").value.trim();
  const nums      = ["①", "②", "③", "④", "⑤"];

  const header = `${name ? name + "さん" : "お客様"}、ご購入いただきありがとうございます✨\nしっかりと診断させていただきますね\n\nまた、より深い鑑定のための質問です。\n以下の質問に、お答え出来る範囲でいいのでお答えいただけると、鑑定結果もより具体的にお返事できるかと思います☺️`;

  const qaLines = [];
  items.forEach((item, i) => {
    const q = item.querySelector(".question-text")?.textContent.trim() || "";
    qaLines.push(`\n${q}\nA${i + 1}、`);
  });

  const text = header + "\n" + qaLines.join("\n");

  try {
    await navigator.clipboard.writeText(text);
    showToast("質問文をコピーしました ✓");
  } catch {
    showToast("コピーに失敗しました");
  }
}

function getFollowUpArrays() {
  const cb        = document.getElementById("detail-option-cb");
  const container = document.getElementById("questions-container");
  if (!cb.checked || container.classList.contains("hidden") || !container.innerHTML) {
    return { questions: [], answers: [] };
  }
  const questions = [];
  const answers   = [];
  container.querySelectorAll(".question-item").forEach(item => {
    questions.push(item.querySelector(".question-text")?.textContent.trim() || "");
    answers.push(item.querySelector(".question-answer")?.value.trim() || "");
  });
  return { questions, answers };
}

function getFollowUpContext() {
  const cb        = document.getElementById("detail-option-cb");
  const container = document.getElementById("questions-container");
  if (!cb.checked || container.classList.contains("hidden") || !container.innerHTML) return null;

  const items = container.querySelectorAll(".question-item");
  if (items.length === 0) return null;

  const concern    = document.getElementById("concern").value.trim();
  let hasAnyAnswer = false;
  const qaList     = [];

  items.forEach((item) => {
    const qEl = item.querySelector(".question-text");
    const aEl = item.querySelector(".question-answer");
    const q   = qEl ? qEl.textContent.trim() : "";
    const a   = aEl ? aEl.value.trim() : "";
    if (a) hasAnyAnswer = true;
    qaList.push({ q, a });
  });

  if (!hasAnyAnswer) return null;

  let ctx = `【基本情報】\n相談内容: ${concern}\n\n【詳細情報】\n`;
  qaList.forEach(({ q, a }) => {
    ctx += `Q: ${q}\nA: ${a || "（回答なし）"}\n\n`;
  });
  ctx += "以上をもとに鑑定します";
  return ctx;
}

// ===== フォームリセット =====
function resetForm() {
  document.getElementById("result-section").classList.add("hidden");
  document.getElementById("retry-area").classList.add("hidden");
  document.getElementById("chat-section").classList.add("hidden");
  document.getElementById("chat-messages").innerHTML = "";
  document.getElementById("fortune-form").reset();
  document.getElementById("input-section").scrollIntoView({ behavior: "smooth" });
  currentFileId      = null;
  currentReadingText = "";
  currentFortuneData = null;
  currentHistoryId   = null;
  chatMessages       = [];
}

// ===== 履歴の読み込み =====
async function loadHistory() {
  try {
    const res = await fetch("/api/history-list");
    const items = await res.json();
    const listEl = document.getElementById("history-list");

    if (items.length === 0) {
      listEl.innerHTML = '<p class="empty-message">まだ鑑定履歴はありません</p>';
      return;
    }

    listEl.innerHTML = items.map(item => `
      <div class="history-item" onclick="loadReading('${item.file_id}', ${item.history_id != null ? item.history_id : 'null'})">
        <div>
          <div class="history-concern">${item.name ? `【${item.name}】` : ""}${item.concern}</div>
          <div class="history-meta">${item.timestamp} | ${item.birthdate}</div>
        </div>
        <span style="font-size:0.8rem;color:#9e9e9e">▶</span>
      </div>
    `).join("");
  } catch (err) {
    console.error("履歴の読み込みに失敗:", err);
  }
}

// ===== 過去の鑑定を表示 =====
async function loadReading(fileId, historyId) {
  try {
    let data;
    if (historyId) {
      const res = await fetch(`/api/history/${historyId}`);
      data = await res.json();
      data.reading = data.result || "";
    } else {
      const res = await fetch(`/api/reading/${fileId}`);
      data = await res.json();
    }

    const resultSection  = document.getElementById("result-section");
    const statsGrid      = document.getElementById("fortune-stats");
    const readingText    = document.getElementById("reading-text");
    const actionButtons  = document.getElementById("action-buttons");

    resultSection.classList.remove("hidden");
    readingText.innerHTML = formatReading(data.reading || "");
    actionButtons.classList.remove("hidden");

    if (data.fortune_data) {
      renderFortuneStats(data.fortune_data);
      statsGrid.classList.remove("hidden");
    } else {
      statsGrid.classList.add("hidden");
    }

    currentFileId      = fileId;
    currentReadingText = data.reading || "";
    currentHistoryId   = historyId || null;
    currentFortuneData = data.fortune_data || null;

    resultSection.scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    alert("鑑定データの読み込みに失敗しました");
  }
}

// ===== ユーティリティ =====

/**
 * プレーンテキスト → HTMLに変換。
 * Markdown記号を除去しつつ、見出し・段落・太字を適切にHTML化する。
 * innerHTMLに直接セットする前提。
 */
function formatReading(raw) {
  // ---- Step 1: 行に分割 ----
  const lines = raw.split("\n");
  const htmlParts = [];
  let blankCount = 0;

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];

    // 区切り線 (--- / ***) → 空行として扱う
    if (/^\s*[-*_]{3,}\s*$/.test(line)) {
      blankCount++;
      continue;
    }

    // 見出し: ## テキスト / 【テキスト】 / ◆ テキスト
    const headingMd  = line.match(/^#{1,3}\s+(.+)$/);
    const headingJp  = line.match(/^[【◆✦✨🔮🌙🔢🦁📜].*[】]?\s*$/);
    const headingDot = line.match(/^[◆✦★☆]\s*(.+)$/);

    if (headingMd || headingDot) {
      const text = headingMd
        ? headingMd[1].trim()
        : headingDot[1].trim();
      // 前に空白を入れる（最初の見出しは除く）
      if (htmlParts.length > 0) {
        htmlParts.push('<div class="reading-spacer"></div>');
      }
      htmlParts.push(
        '<p class="reading-heading">' + esc(text) + '</p>'
      );
      blankCount = 0;
      continue;
    }

    // 【見出し】形式（行全体が【】で始まる）
    if (/^【.+】/.test(line)) {
      if (htmlParts.length > 0) {
        htmlParts.push('<div class="reading-spacer"></div>');
      }
      const inner = line.replace(/^【/, "").replace(/】.*$/, "");
      htmlParts.push(
        '<p class="reading-heading">' + esc(line.trim()) + '</p>'
      );
      blankCount = 0;
      continue;
    }

    // 空行
    if (line.trim() === "") {
      blankCount++;
      // 2行以上の空行は段落区切りとして1つだけ挿入
      if (blankCount === 1 && htmlParts.length > 0) {
        htmlParts.push('<div class="reading-para-break"></div>');
      }
      continue;
    }

    blankCount = 0;

    // 引用 >
    line = line.replace(/^>\s?/, "");

    // インライン整形
    // **太字** / __太字__ → <strong>
    line = line.replace(/\*\*(.+?)\*\*/g, (_, t) => '<strong>' + esc(t) + '</strong>');
    line = line.replace(/__(.+?)__/g,     (_, t) => '<strong>' + esc(t) + '</strong>');
    // *斜体* / _斜体_ → 記号除去のみ
    line = line.replace(/\*(.+?)\*/g, "$1");
    line = line.replace(/_([^_]+)_/g, "$1");
    // `コード` → 記号除去
    line = line.replace(/`(.+?)`/g, "$1");

    // 通常行 — esc済みでない部分をエスケープしてから追加
    // ※上記で強タグを挿入済みなので、残りをescapeしてはいけない
    // → 代わりに生テキスト部分だけをescする処理を行う
    htmlParts.push('<p class="reading-line">' + escLine(line).replace(/。(\p{Extended_Pictographic}*)/gu, (_, e) => '。' + e + '<br>') + '</p>');
  }

  return htmlParts.join("\n");
}

/** HTMLタグを含む行の生テキスト部分だけエスケープする */
function escLine(line) {
  // <strong>...</strong> タグを保持しつつ、それ以外をエスケープ
  return line.replace(/(<strong>.*?<\/strong>)|([^<]+)/g, (match, tag, text) => {
    if (tag) return tag;           // <strong>タグはそのまま
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  });
}

/** 文字列全体をHTMLエスケープ（タグなし前提） */
function esc(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function escapeHtml(str) {
  // formatReading を使わない箇所（エラー表示など）用
  return esc(str).replace(/\n/g, "<br>");
}

// ===== 画像生成（Canvas API） =====

function generateFortuneImage() {
  if (!currentFortuneData) return;

  const name      = document.getElementById("name").value.trim() || "鑑定者";
  const birthdate = document.getElementById("birthdate").value;
  const ani = currentFortuneData.animal;
  const num = currentFortuneData.numerology;
  const sc  = currentFortuneData.shichusuimei;

  const W = 1080, H = 1350;
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");

  // ---- 背景グラデーション ----
  const bg = ctx.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0,   "#0d0b1e");
  bg.addColorStop(0.45,"#1a1040");
  bg.addColorStop(1,   "#080818");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  // 中央の紫グロー
  const glow = ctx.createRadialGradient(W/2, 380, 0, W/2, 380, 500);
  glow.addColorStop(0, "rgba(124,77,255,0.25)");
  glow.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, W, H);

  // ---- 星を散りばめる ----
  const starSeeds = [
    [112,80],[934,200],[55,450],[1020,320],[500,60],[780,110],
    [230,700],[860,650],[140,900],[970,820],[430,1100],[680,1200],
    [80,1280],[1010,1100],[320,300],[700,400],[150,550],[900,500],
    [600,750],[250,1000],[750,950],[50,1050],[1000,1000],[400,600],
    [550,200],[820,300],[180,400],[660,500],[330,800],[880,900],
  ];
  for (const [sx, sy] of starSeeds) {
    const r     = (((sx * 7 + sy * 13) % 12) / 10) + 0.5;
    const alpha = (((sx * 3 + sy * 5) % 7)  /  9) + 0.25;
    ctx.beginPath();
    ctx.arc(sx, sy, r, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(255,255,255,${alpha.toFixed(2)})`;
    ctx.fill();
  }

  // ---- 外枠（ゴールドグラデーション） ----
  const borderG = ctx.createLinearGradient(0, 0, W, H);
  borderG.addColorStop(0,   "#ffd700");
  borderG.addColorStop(0.5, "#ff9fd0");
  borderG.addColorStop(1,   "#b39ddb");
  ctx.strokeStyle = borderG;
  ctx.lineWidth = 3;
  imgRoundRect(ctx, 28, 28, W-56, H-56, 22);
  ctx.stroke();
  ctx.strokeStyle = "rgba(255,215,0,0.18)";
  ctx.lineWidth = 1;
  imgRoundRect(ctx, 40, 40, W-80, H-80, 16);
  ctx.stroke();

  const font = '"Hiragino Kaku Gothic ProN","Yu Gothic","Meiryo",sans-serif';
  ctx.textAlign = "center";
  ctx.textBaseline = "alphabetic";

  let y = 105;

  // ---- タイトルエリア ----
  ctx.font = `48px ${font}`;
  ctx.fillStyle = "#ffd700";
  ctx.fillText("✨", W/2 - 220, y + 5);
  ctx.fillText("✨", W/2 + 220, y + 5);

  y += 72;
  const titleG = ctx.createLinearGradient(W/2-300, 0, W/2+300, 0);
  titleG.addColorStop(0,   "#ffd700");
  titleG.addColorStop(0.5, "#ffb3d4");
  titleG.addColorStop(1,   "#c4b5fd");
  ctx.fillStyle = titleG;
  ctx.font = `bold 62px ${font}`;
  ctx.fillText("あなただけの鑑定書", W/2, y);

  y += 48;
  ctx.fillStyle = "rgba(179,157,219,0.75)";
  ctx.font = `28px ${font}`;
  ctx.fillText("四柱推命 × 数秘術 × 動物占い  統合鑑定", W/2, y);

  y += 44;
  imgDivider(ctx, W, y);

  // ---- プロフィールカード ----
  y += 30;
  imgCard(ctx, 60, y, W-120, 185, "rgba(124,77,255,0.12)");

  ctx.fillStyle = "rgba(255,255,255,0.45)";
  ctx.font = `24px ${font}`;
  ctx.fillText("鑑定者", W/2, y + 42);

  ctx.fillStyle = "#ffffff";
  ctx.font = `bold 54px ${font}`;
  ctx.fillText(name, W/2, y + 108);

  ctx.fillStyle = "rgba(255,255,255,0.5)";
  ctx.font = `26px ${font}`;
  ctx.fillText(imgFormatDate(birthdate), W/2, y + 150);

  y += 205;
  ctx.fillStyle = "rgba(179,157,219,0.7)";
  ctx.font = `24px ${font}`;
  ctx.fillText(
    `年柱 ${sc.year_pillar.pillar}　月柱 ${sc.month_pillar.pillar}　日柱 ${sc.day_pillar.pillar}`,
    W/2, y
  );

  y += 40;
  imgDivider(ctx, W, y);

  // ---- 動物占いセクション ----
  y += 36;
  ctx.fillStyle = "rgba(255,215,0,0.75)";
  ctx.font = `26px ${font}`;
  ctx.fillText("✦  動物占い  ✦", W/2, y);

  y += 16;
  const lx = W/2 - 195, rx = W/2 + 195;

  ctx.font = `88px sans-serif`;
  ctx.fillText(ani.year_animal.emoji, lx, y + 88);
  ctx.fillText(ani.day_animal.emoji,  rx, y + 88);

  ctx.fillStyle = "rgba(255,215,0,0.5)";
  ctx.font = `38px ${font}`;
  ctx.fillText("×", W/2, y + 60);

  ctx.fillStyle = "rgba(255,255,255,0.45)";
  ctx.font = `22px ${font}`;
  ctx.fillText("表の顔",     lx, y + 118);
  ctx.fillText("内なる本質", rx, y + 118);

  ctx.fillStyle = "#ffffff";
  ctx.font = `bold 34px ${font}`;
  ctx.fillText(ani.year_animal.animal, lx, y + 158);
  ctx.fillText(ani.day_animal.animal,  rx, y + 158);

  y += 185;
  ctx.fillStyle = "rgba(179,157,219,0.65)";
  ctx.font = `23px ${font}`;
  ctx.fillText(ani.year_animal.traits, W/2, y);

  y += 40;
  imgDivider(ctx, W, y);

  // ---- 数秘術セクション ----
  y += 36;
  ctx.fillStyle = "rgba(255,215,0,0.75)";
  ctx.font = `26px ${font}`;
  ctx.fillText("✦  数秘術  ✦", W/2, y);

  y += 18;
  const numG = ctx.createLinearGradient(W/2-70, 0, W/2+70, 0);
  numG.addColorStop(0, "#ffd700");
  numG.addColorStop(1, "#ff9fd0");
  ctx.fillStyle = numG;
  ctx.font = `bold 110px ${font}`;
  ctx.fillText(String(num.life_path_number), W/2, y + 100);

  ctx.fillStyle = "rgba(255,255,255,0.45)";
  ctx.font = `24px ${font}`;
  ctx.fillText("ライフパスナンバー" + (num.is_master_number ? "（マスターナンバー）" : ""), W/2, y + 138);

  ctx.fillStyle = "rgba(179,157,219,0.8)";
  ctx.font = `23px ${font}`;
  imgWrapText(ctx, num.life_path_meaning, W/2, y + 178, W - 180, 34);

  y += 235;
  imgDivider(ctx, W, y);

  // ---- 鑑定メッセージ抜粋 ----
  y += 36;
  ctx.fillStyle = "rgba(255,215,0,0.75)";
  ctx.font = `26px ${font}`;
  ctx.fillText("✦  鑑定メッセージ  ✦", W/2, y);

  y += 42;
  const excerpt = imgExcerpt(currentReadingText, 90);
  ctx.fillStyle = "rgba(255,255,255,0.88)";
  ctx.font = `25px ${font}`;
  imgWrapText(ctx, excerpt, W/2, y, W - 180, 38);

  // ---- フッター ----
  const today = new Date().toLocaleDateString("ja-JP",
    { year: "numeric", month: "long", day: "numeric" });
  ctx.fillStyle = "rgba(255,255,255,0.28)";
  ctx.font = `22px ${font}`;
  ctx.fillText(`鑑定日：${today}`, W/2, H - 52);

  // ダウンロード
  const link = document.createElement("a");
  link.download = `fortune_${birthdate || "reading"}.png`;
  link.href = canvas.toDataURL("image/png");
  link.click();

  showToast("画像を保存しました ✨");
}

// ---- Canvas ヘルパー ----

function imgRoundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function imgDivider(ctx, W, y) {
  const g = ctx.createLinearGradient(80, 0, W - 80, 0);
  g.addColorStop(0,   "rgba(255,215,0,0)");
  g.addColorStop(0.3, "rgba(255,215,0,0.55)");
  g.addColorStop(0.7, "rgba(255,215,0,0.55)");
  g.addColorStop(1,   "rgba(255,215,0,0)");
  ctx.save();
  ctx.strokeStyle = g;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(80, y);
  ctx.lineTo(W - 80, y);
  ctx.stroke();
  ctx.restore();
}

function imgCard(ctx, x, y, w, h, color) {
  ctx.save();
  imgRoundRect(ctx, x, y, w, h, 18);
  ctx.fillStyle = color;
  ctx.fill();
  ctx.restore();
}

function imgWrapText(ctx, text, cx, y, maxWidth, lineH) {
  let line = "";
  for (const ch of text) {
    const test = line + ch;
    if (ctx.measureText(test).width > maxWidth && line.length > 0) {
      ctx.fillText(line, cx, y);
      line = ch;
      y += lineH;
    } else {
      line = test;
    }
  }
  if (line) ctx.fillText(line, cx, y);
  return y + lineH;
}

function imgExcerpt(text, maxLen) {
  const clean = text
    .replace(/【[^】]*】/g, "")
    .replace(/◆[^\n]*/g, "")
    .replace(/\n+/g, " ")
    .trim();
  const first = clean.split("。")[0];
  const src = (first.length > 15 ? first : clean).trim();
  return src.length > maxLen ? src.slice(0, maxLen) + "…" : src;
}

function imgFormatDate(s) {
  if (!s) return "";
  const [y, m, d] = s.split("-");
  return `${y}年${parseInt(m)}月${parseInt(d)}日`;
}

function showToast(message) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 2000);
}
