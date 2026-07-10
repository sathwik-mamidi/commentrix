const startButton = document.getElementById("startButton");
const stopButton = document.getElementById("stopButton");
const statusRoot = document.getElementById("status");
const videoPlayer = document.getElementById("videoPlayer");
const videoTimestamp = document.getElementById("videoTimestamp");
const commentaryContainer = document.getElementById("commentary-container");
const loadingOverlay = document.getElementById("loading-overlay");

const state = {
  socket: null,
  segments: new Map(),
  timers: [],
  audioUrls: [],
  active: false,
};

function socketUrl() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws`;
}

function setStatus(message, mode = "idle") {
  const dot = statusRoot.querySelector(".status-dot");
  const label = statusRoot.querySelector("[data-status-label]");

  label.textContent = message;
  dot.className = `status-dot ${mode}`;
}

function clearTimers() {
  state.timers.forEach((timer) => window.clearTimeout(timer));
  state.timers = [];
}

function resetRun() {
  clearTimers();
  state.audioUrls.forEach((url) => URL.revokeObjectURL(url));
  state.audioUrls = [];
  state.segments.clear();
  commentaryContainer.replaceChildren();
  videoPlayer.pause();
  videoPlayer.currentTime = 0;
  state.active = false;
}

function showLoading() {
  loadingOverlay.hidden = false;
}

function hideLoading() {
  loadingOverlay.hidden = true;
}

function formatTime(seconds) {
  if (!Number.isFinite(seconds)) {
    return "0:00";
  }

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
}

function updateTimestamp() {
  videoTimestamp.textContent = `${formatTime(videoPlayer.currentTime)} / ${formatTime(videoPlayer.duration)}`;
}

function addCommentarySegment(segment) {
  const article = document.createElement("article");
  article.className = "commentary-segment";
  article.id = `segment-${segment.segment}`;

  const meta = document.createElement("p");
  meta.className = "commentary-meta";
  meta.textContent = `${segment.model} | ${segment.start_time.toFixed(1)}s-${(segment.start_time + segment.duration).toFixed(1)}s`;

  const text = document.createElement("p");
  text.className = "commentary-text";
  text.textContent = segment.commentary;

  article.append(meta, text);
  commentaryContainer.append(article);
  article.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function playVideoIfNeeded(segment) {
  if (state.active) {
    return;
  }

  hideLoading();
  state.active = true;
  videoPlayer.currentTime = segment.start_time;
  videoPlayer.play().catch(() => {
    setStatus("Click the video to allow playback", "warning");
  });
}

function audioUrlFromBase64(data) {
  const binary = atob(data);
  const bytes = new Uint8Array(binary.length);

  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }

  const url = URL.createObjectURL(new Blob([bytes], { type: "audio/mpeg" }));
  state.audioUrls.push(url);
  return url;
}

function scheduleAudioLine(audioLine) {
  const segment = state.segments.get(audioLine.segment);
  if (!segment) {
    return;
  }

  const playAt = segment.start_time + audioLine.frame;
  const delay = Math.max(0, (playAt - videoPlayer.currentTime) * 1000);
  const url = audioUrlFromBase64(audioLine.data);

  const timer = window.setTimeout(() => {
    const audio = new Audio(url);
    audio.volume = 0.85;
    audio.play().catch(() => {
      setStatus("Audio playback was blocked by the browser", "warning");
    });
  }, delay);

  state.timers.push(timer);
}

function handleMessage(event) {
  const data = JSON.parse(event.data);

  if (data.type === "segment_ready") {
    state.segments.set(data.segment, data);
    addCommentarySegment(data);
    playVideoIfNeeded(data);
    setStatus(`Processing segment ${data.segment + 1}`, "active");
    return;
  }

  if (data.type === "audio_line") {
    scheduleAudioLine(data);
    return;
  }

  if (data.type === "video_processing_finished") {
    setStatus("Generating final video", "active");
    return;
  }

  if (data.type === "final_video_ready") {
    setStatus("Final video ready", "ready");
    hideLoading();
    return;
  }

  if (data.type === "status") {
    setStatus(data.message, "active");
    return;
  }

  if (data.type === "audio_segment_error") {
    setStatus(`Audio error on segment ${data.segment + 1}`, "warning");
    return;
  }

  if (data.type === "error") {
    setStatus(data.message, "error");
    hideLoading();
  }
}

function connect() {
  state.socket = new WebSocket(socketUrl());

  state.socket.addEventListener("open", () => {
    startButton.disabled = false;
    setStatus("Connected", "ready");
  });

  state.socket.addEventListener("message", handleMessage);

  state.socket.addEventListener("close", () => {
    startButton.disabled = false;
    stopButton.disabled = true;
    setStatus("Disconnected", "idle");
  });

  state.socket.addEventListener("error", () => {
    setStatus("Connection error", "error");
  });
}

startButton.addEventListener("click", () => {
  if (!state.socket || state.socket.readyState !== WebSocket.OPEN) {
    setStatus("WebSocket is not connected", "error");
    return;
  }

  resetRun();
  videoPlayer.src = `/public/input.mp4?cb=${Date.now()}`;
  videoPlayer.load();
  showLoading();

  state.socket.send(JSON.stringify({ type: "start" }));
  startButton.disabled = true;
  stopButton.disabled = false;
  setStatus("Analyzing video", "active");
});

stopButton.addEventListener("click", () => {
  if (state.socket && state.socket.readyState === WebSocket.OPEN) {
    state.socket.send(JSON.stringify({ type: "stop" }));
  }

  resetRun();
  hideLoading();
  startButton.disabled = false;
  stopButton.disabled = true;
  setStatus("Stopped", "ready");
});

videoPlayer.addEventListener("loadedmetadata", updateTimestamp);
videoPlayer.addEventListener("timeupdate", updateTimestamp);
videoPlayer.addEventListener("ended", () => {
  setStatus("Playback complete", "ready");
});

document.addEventListener("DOMContentLoaded", () => {
  startButton.disabled = true;
  stopButton.disabled = true;
  hideLoading();
  updateTimestamp();
  connect();
});
