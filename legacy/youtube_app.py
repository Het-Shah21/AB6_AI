import logging
import uuid
import json
import asyncio
from fastapi import FastAPI, Request, Form, HTTPException, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from legacy.youtube_agent.schemas import YouTubeEvent, AgentState
from legacy.youtube_agent.agent import YouTubeAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("youtube_app")

app = FastAPI(title="AB6 AI - YouTube Learning Agent")
agent = YouTubeAgent()
sessions: dict[str, AgentState] = {}

USER_CREDENTIALS = {"admin": "admin123", "demo": "demo123", "test": "test123"}

class EventPayload(BaseModel):
    session_id: str
    event: YouTubeEvent

class StartPayload(BaseModel):
    session_id: str
    video_url: str
    video_id: str

class FinishPayload(BaseModel):
    session_id: str


LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AB6 AI - Login</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;display:flex;align-items:center;justify-content:center}
  .card{background:#1e293b;border-radius:16px;padding:48px;width:400px;box-shadow:0 25px 50px rgba(0,0,0,0.4)}
  h1{font-size:24px;margin-bottom:8px;color:#f8fafc}
  .subtitle{color:#94a3b8;font-size:14px;margin-bottom:32px}
  label{display:block;font-size:13px;font-weight:500;color:#cbd5e1;margin-bottom:6px}
  input{width:100%;padding:12px 16px;background:#0f172a;border:1px solid #334155;border-radius:8px;color:#e2e8f0;font-size:14px;outline:none;transition:border-color 0.2s;margin-bottom:20px}
  input:focus{border-color:#3b82f6}
  button{width:100%;padding:12px;background:#3b82f6;color:white;border:none;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer;transition:background 0.2s}
  button:hover{background:#2563eb}
  .error{background:#7f1d1d;border:1px solid #dc2626;padding:12px;border-radius:8px;color:#fca5a5;font-size:13px;margin-bottom:20px}
  .pipeline-badge{display:flex;gap:4px;justify-content:center;margin-top:24px;flex-wrap:wrap}
  .badge{background:#334155;color:#94a3b8;padding:4px 10px;border-radius:12px;font-size:10px;font-weight:500;letter-spacing:0.5px}
  .badge.active{background:#1e40af;color:#93c5fd}
</style>
</head>
<body>
<div class="card">
  <h1>AB6 AI Agent</h1>
  <p class="subtitle">Enter your credentials to begin your learning session</p>
  <div class="error" id="error" style="display:{error_display}">{error_msg}</div>
  <form method="POST" action="/login">
    <label for="name">Name</label>
    <input type="text" id="name" name="name" placeholder="e.g. John Doe" required autofocus>
    <label for="password">Password</label>
    <input type="password" id="password" name="password" placeholder="Enter password" required>
    <button type="submit">Start Learning Session</button>
  </form>
  <div class="pipeline-badge">
    <span class="badge active">PRIOR INFO</span><span class="badge">→</span><span class="badge">OBSERVE</span>
    <span class="badge">→</span><span class="badge">ANALYZE</span><span class="badge">→</span><span class="badge">INFERENCE</span>
    <span class="badge">→</span><span class="badge">INTERPRET</span><span class="badge">→</span><span class="badge">INTELLIGENCE</span>
    <span class="badge">→</span><span class="badge">FEEDBACK</span>
  </div>
</div>
</body>
</html>"""


WATCH_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AB6 AI - Watch Video</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}
  .container{max-width:960px;margin:0 auto;padding:24px}
  .header{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px}
  .header h1{font-size:20px;color:#f8fafc}
  .user-badge{background:#1e293b;padding:6px 14px;border-radius:20px;font-size:13px;color:#93c5fd}
  .card{background:#1e293b;border-radius:12px;padding:24px;margin-bottom:20px}
  .url-input-row{display:flex;gap:12px}
  .url-input-row input{flex:1;padding:12px 16px;background:#0f172a;border:1px solid #334155;border-radius:8px;color:#e2e8f0;font-size:14px;outline:none}
  .url-input-row input:focus{border-color:#3b82f6}
  .url-input-row input:disabled{opacity:0.5}
  button{padding:12px 24px;background:#3b82f6;color:white;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;transition:background 0.2s;white-space:nowrap}
  button:hover{background:#2563eb}
  button:disabled{opacity:0.5;cursor:not-allowed}
  button.danger{background:#dc2626}
  button.danger:hover{background:#b91c1c}
  button.secondary{background:#475569}
  button.secondary:hover{background:#64748b}
  .player-wrapper{position:relative;width:100%;aspect-ratio:16/9;background:#000;border-radius:8px;overflow:hidden;margin-bottom:20px}
  .player-wrapper.hidden{display:none}
  #player{width:100%;height:100%}
  .stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px;margin-bottom:20px}
  .stat{background:#0f172a;border-radius:8px;padding:12px;text-align:center}
  .stat .value{font-size:22px;font-weight:700;color:#f8fafc}
  .stat .label{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;margin-top:4px}
  .event-log{background:#0f172a;border-radius:8px;padding:12px;max-height:200px;overflow-y:auto;font-family:'Courier New',monospace;font-size:11px}
  .event-log .entry{padding:3px 0;border-bottom:1px solid #1e293b;color:#94a3b8}
  .event-log .entry:last-child{border-bottom:none}
  .event-log .highlight{color:#6ee7b7}
  .event-log .warn{color:#fbbf24}
  .actions{display:flex;gap:12px;justify-content:center;margin-top:16px}
  .hidden{display:none !important}
  .pipeline-bar{display:flex;gap:6px;justify-content:center;margin-bottom:20px;flex-wrap:wrap}
  .pipe-step{background:#1e293b;color:#475569;padding:4px 12px;border-radius:12px;font-size:11px;font-weight:500;letter-spacing:0.3px}
  .pipe-step.active{background:#1e3a5f;color:#60a5fa}
  .pipe-step.done{background:#064e3b;color:#6ee7b7}
  .pipe-arrow{color:#334155;font-size:12px;line-height:24px}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>AB6 AI - Video Learning Session</h1>
    <span class="user-badge">{user_id}</span>
  </div>
  <div class="pipeline-bar">
    <span class="pipe-step active">PRIOR INFO</span><span class="pipe-arrow">→</span>
    <span class="pipe-step">OBSERVE</span><span class="pipe-arrow">→</span>
    <span class="pipe-step">ANALYZE</span><span class="pipe-arrow">→</span>
    <span class="pipe-step">INFERENCE</span><span class="pipe-arrow">→</span>
    <span class="pipe-step">INTERPRET</span><span class="pipe-arrow">→</span>
    <span class="pipe-step">INTELLIGENCE</span><span class="pipe-arrow">→</span>
    <span class="pipe-step">FEEDBACK</span>
  </div>
  <div class="card">
    <label style="display:block;font-size:13px;font-weight:500;color:#cbd5e1;margin-bottom:8px">Enter YouTube Video URL</label>
    <div class="url-input-row">
      <input type="text" id="youtubeUrl" placeholder="https://www.youtube.com/watch?v=..." value="">
      <button id="loadBtn" onclick="loadVideo()">Load Video</button>
    </div>
  </div>
  <div class="player-wrapper hidden" id="playerWrapper"><div id="player"></div></div>
  <div class="stats-grid">
    <div class="stat"><div class="value" id="statTime">0:00</div><div class="label">Current Time</div></div>
    <div class="stat"><div class="value" id="statDuration">0:00</div><div class="label">Duration</div></div>
    <div class="stat"><div class="value" id="statSpeed">1.0x</div><div class="label">Speed</div></div>
    <div class="stat"><div class="value" id="statEvents">0</div><div class="label">Events Tracked</div></div>
    <div class="stat"><div class="value" id="statStatus">-</div><div class="label">Status</div></div>
  </div>
  <div class="actions">
    <button id="finishBtn" class="danger hidden" onclick="finishSession()">Finish Video & Analyze</button>
  </div>
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <span style="font-size:14px;font-weight:500">Event Log</span>
    </div>
    <div class="event-log" id="eventLog"><div class="entry">Waiting for video to load...</div></div>
  </div>
</div>
<script>
var SESSION_ID = '{session_id}';
var USER_ID = '{user_id}';
var player = null;
var eventCount = 0;
var isPlaying = false;
var lastVideoTime = 0;
var batchTimer = null;
var tabSwitchCount = 0;

function logEvent(type, detail) {
  var log = document.getElementById('eventLog');
  var entry = document.createElement('div');
  var time = new Date().toLocaleTimeString();
  entry.className = 'entry' + (type === 'tracked' ? ' highlight' : '');
  entry.textContent = '[' + time + '] ' + detail;
  log.appendChild(entry);
  log.scrollTop = log.scrollHeight;
}

function logWarn(detail) {
  var log = document.getElementById('eventLog');
  var entry = document.createElement('div');
  var time = new Date().toLocaleTimeString();
  entry.className = 'entry warn';
  entry.textContent = '[' + time + '] ' + detail;
  log.appendChild(entry);
  log.scrollTop = log.scrollHeight;
}

function extractVideoId(url) {
  var m = url.match(/^([a-zA-Z0-9_-]{11})$/);
  if (m) return m[1];
  m = url.match(/(?:youtube\\.com\\/watch\\?v=|youtu\\.be\\/|youtube\\.com\\/embed\\/|youtube\\.com\\/v\\/)([a-zA-Z0-9_-]{11})/);
  if (m) return m[1];
  return null;
}

function sendEvent(eventType, videoTime, extraData) {
  eventCount++;
  document.getElementById('statEvents').textContent = eventCount;
  var payload = JSON.stringify({
    session_id: SESSION_ID,
    event: { event_type: eventType, timestamp: Date.now()/1000, video_time: Math.round(videoTime*10)/10, data: extraData||{} }
  });
  var xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/event', true);
  xhr.setRequestHeader('Content-Type', 'application/json');
  xhr.send(payload);
  logEvent('tracked', eventType + ' @ ' + Math.round(videoTime) + 's' + (extraData ? ' ' + JSON.stringify(extraData) : ''));
}

function loadVideo() {
  var url = document.getElementById('youtubeUrl').value.trim();
  var videoId = extractVideoId(url);
  if (!videoId) { logWarn('Invalid YouTube URL'); return; }
  document.getElementById('loadBtn').disabled = true;
  document.getElementById('youtubeUrl').disabled = true;
  document.getElementById('playerWrapper').classList.remove('hidden');
  document.getElementById('finishBtn').classList.remove('hidden');
  var xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/start', true);
  xhr.setRequestHeader('Content-Type', 'application/json');
  xhr.send(JSON.stringify({session_id:SESSION_ID, video_url:url, video_id:videoId}));
  xhr.onload = function() { logEvent('system', 'Session started: ' + videoId); };
  if (typeof YT !== 'undefined' && YT.Player) { createPlayer(videoId); }
  else { window.onYouTubeIframeAPIReady = function() { createPlayer(videoId); }; }
}

function createPlayer(videoId) {
  player = new YT.Player('player', {
    height: '100%', width: '100%',
    videoId: videoId,
    playerVars: {autoplay:0, rel:0, modestbranding:1, enablejsapi:1, origin:'http://127.0.0.1:8000'},
    events: {onReady:onPlayerReady, onStateChange:onPlayerStateChange, onError:onPlayerError}
  });
}

function onPlayerError(e) {
  var msgs = {2:'Invalid parameter', 100:'Video not found', 101:'Embedding disabled', 150:'Embedding disabled'};
  logWarn('Player error ' + e.data + ': ' + (msgs[e.data] || 'Unknown'));
  document.getElementById('loadBtn').disabled = false;
  document.getElementById('youtubeUrl').disabled = false;
}

function onPlayerReady(e) {
  var dur = player.getDuration();
  document.getElementById('statDuration').textContent = formatTime(dur);
  sendEvent('video_metadata', 0, {duration:dur, video_id:player.getVideoData().videoId});
  logEvent('system', 'Player ready - duration: ' + formatTime(dur));
  document.getElementById('loadBtn').disabled = false;
}

function onPlayerStateChange(e) {
  var time = player.getCurrentTime();
  var names = {'-1':'unstarted','0':'ended','1':'playing','2':'paused','3':'buffering','5':'cued'};
  document.getElementById('statStatus').textContent = names[e.data]||'unknown';
  if (e.data === 1) {
    if (lastVideoTime > 0 && Math.abs(time-lastVideoTime) > 1) {
      sendEvent('seek', time, {from:Math.round(lastVideoTime*10)/10, to:Math.round(time*10)/10});
    }
    sendEvent('play', time, {}); isPlaying = true; startTimeTracking();
  } else if (e.data === 2) {
    sendEvent('pause', time, {}); isPlaying = false; lastVideoTime = time;
  } else if (e.data === 0) {
    sendEvent('video_end', time, {}); isPlaying = false; logEvent('system','Video ended');
    setTimeout(finishSession, 1000);
  } else if (e.data === 3) {
    sendEvent('buffering', time, {});
  }
}

function onPlayerError(e) { logWarn('Player error: '+e.data); }

function startTimeTracking() {
  if (!isPlaying) return;
  var time = player.getCurrentTime();
  document.getElementById('statTime').textContent = formatTime(time);
  sendEvent('timeupdate', time, {});
  setTimeout(startTimeTracking, 2000);
}

function formatTime(s) {
  if (!s||isNaN(s)) return '0:00';
  return Math.floor(s/60) + ':' + (Math.floor(s%60)<10?'0':'') + Math.floor(s%60);
}

document.addEventListener('visibilitychange', function() {
  if (!player) return;
  var time = player.getCurrentTime();
  if (document.hidden) { tabSwitchCount++; sendEvent('tab_switch', time, {hidden:true, count:tabSwitchCount}); logWarn('Tab switched away'); }
  else { sendEvent('tab_switch', time, {hidden:false, count:tabSwitchCount}); logEvent('system','Tab returned to video'); }
});

function finishSession() {
  if (player) { try { player.pauseVideo(); } catch(e) {} }
  isPlaying = false;
  document.getElementById('finishBtn').disabled = true;
  document.getElementById('finishBtn').textContent = 'Analyzing...';
  var xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/finish', true);
  xhr.setRequestHeader('Content-Type', 'application/json');
  xhr.responseType = 'json';
  xhr.onload = function() {
    if (xhr.response && xhr.response.redirect) { window.location.href = xhr.response.redirect; }
    else { window.location.href = '/results?session_id=' + SESSION_ID; }
  };
  xhr.onerror = function() { window.location.href = '/results?session_id=' + SESSION_ID; };
  xhr.send(JSON.stringify({session_id:SESSION_ID}));
}
</script>
<script src="https://www.youtube.com/iframe_api"></script>
</body>
</html>"""


def build_results_html(state: AgentState, user_id: str) -> str:
    struggle = state.struggle_segments
    ctx = state.interpreted_context
    analysis = state.agent_state.get("analysis_summary", {})
    engagement = state.agent_state.get("overall_engagement", 0.5)

    ec = "high" if engagement >= 0.6 else "medium" if engagement >= 0.3 else "low"
    epct = round(engagement * 100)
    severity = ctx.get("severity", "none")
    sev_labels = {"none": "NONE", "low": "LOW", "medium": "MODERATE", "high": "SIGNIFICANT"}
    sev_label = sev_labels.get(severity, severity.upper())

    seg_html = ""
    for s in state.segment_analyses:
        if s.was_skipped:
            color = "#1e293b"
        elif s.struggle_score >= 0.6:
            color = "#dc2626"
        elif s.struggle_score >= 0.35:
            color = "#eab308"
        else:
            color = "#22c55e"
        seg_html += f'<div class="seg" style="background:{color}"><div class="tooltip">{s.start_time:.0f}s-{s.end_time:.0f}s · {s.struggle_score}</div></div>'

    rec_html = ""
    for r in state.intelligence_recommendations[:8]:
        rec_html += f'<div class="rec-item">&#9642; {r}</div>'
    if not rec_html:
        rec_html = '<div class="rec-item" style="border-left-color:#22c55e"><strong>Great work!</strong> No revision needed.</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AB6 AI - Analysis Results</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}}
  .container{{max-width:800px;margin:0 auto;padding:32px 24px}}
  .header{{text-align:center;margin-bottom:32px}}
  .header h1{{font-size:28px;color:#f8fafc;margin-bottom:8px}}
  .header .subtitle{{color:#94a3b8;font-size:14px}}
  .card{{background:#1e293b;border-radius:12px;padding:24px;margin-bottom:20px}}
  .card h2{{font-size:18px;color:#f8fafc;margin-bottom:16px}}
  .ring-box{{display:flex;align-items:center;justify-content:center;gap:24px;flex-wrap:wrap}}
  .ring{{width:100px;height:100px;border-radius:50%;display:flex;align-items:center;justify-content:center;position:relative}}
  .ring-inner{{text-align:center}}
  .ring-inner .val{{font-size:28px;font-weight:700;color:#f8fafc}}
  .ring-inner .lbl{{font-size:10px;color:#64748b;text-transform:uppercase}}
  .ring.high{{background:conic-gradient(#22c55e {epct}%, #1e293b {epct}%)}}
  .ring.medium{{background:conic-gradient(#eab308 {epct}%, #1e293b {epct}%)}}
  .ring.low{{background:conic-gradient(#ef4444 {epct}%, #1e293b {epct}%)}}
  .sev{{display:inline-flex;padding:4px 14px;border-radius:12px;font-size:12px;font-weight:600}}
  .sev.none{{background:#064e3b;color:#6ee7b7}}
  .sev.low{{background:#1e3a5f;color:#93c5fd}}
  .sev.medium{{background:#713f12;color:#fde047}}
  .sev.high{{background:#7f1d1d;color:#fca5a5}}
  .stats-row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:12px;margin-bottom:20px}}
  .stat-box{{background:#0f172a;border-radius:8px;padding:16px;text-align:center}}
  .stat-box .num{{font-size:24px;font-weight:700;color:#f8fafc}}
  .stat-box .lbl{{font-size:11px;color:#64748b;text-transform:uppercase;margin-top:4px}}
  .rec-item{{background:#0f172a;border-left:3px solid #3b82f6;padding:14px 16px;border-radius:0 8px 8px 0;margin-bottom:10px;font-size:14px;line-height:1.5;color:#e2e8f0}}
  .rec-item strong{{color:#60a5fa}}
  .section-map{{display:flex;height:40px;border-radius:8px;overflow:hidden;margin-bottom:20px}}
  .section-map .seg{{flex:1;transition:all 0.2s;position:relative;cursor:pointer}}
  .section-map .seg:hover{{transform:scaleY(1.3)}}
  .tooltip{{position:absolute;bottom:100%;left:50%;transform:translateX(-50%);background:#0f172a;color:#e2e8f0;padding:4px 8px;border-radius:4px;font-size:10px;white-space:nowrap;opacity:0;pointer-events:none;transition:opacity 0.2s}}
  .section-map .seg:hover .tooltip{{opacity:1}}
  .narrative-box{{background:#0f172a;border-radius:8px;padding:16px;font-size:14px;line-height:1.6;color:#cbd5e1;border-left:3px solid #3b82f6}}
  a.button{{display:inline-flex;padding:12px 24px;background:#3b82f6;color:white;text-decoration:none;border-radius:8px;font-size:14px;font-weight:600;margin:4px}}
  a.button:hover{{background:#2563eb}}
  a.button.sec{{background:#475569}}
  a.button.sec:hover{{background:#64748b}}
  .pipeline-bar{{display:flex;gap:6px;justify-content:center;margin-bottom:24px;flex-wrap:wrap}}
  .pstep{{background:#064e3b;color:#6ee7b7;padding:4px 12px;border-radius:12px;font-size:11px;font-weight:500}}
  .parrow{{color:#334155;font-size:12px;line-height:24px}}
</style>
</head>
<body>
<div class="container">
<div class="pipeline-bar">
<span class="pstep">PRIOR INFO</span><span class="parrow">&#8594;</span>
<span class="pstep">OBSERVE</span><span class="parrow">&#8594;</span>
<span class="pstep">ANALYZE</span><span class="parrow">&#8594;</span>
<span class="pstep">INFERENCE</span><span class="parrow">&#8594;</span>
<span class="pstep">INTERPRET</span><span class="parrow">&#8594;</span>
<span class="pstep">INTELLIGENCE</span><span class="parrow">&#8594;</span>
<span class="pstep">FEEDBACK</span>
</div>
<div class="header"><h1>Analysis Complete</h1><p class="subtitle">{user_id} &middot; {state.video_id or 'completed'}</p></div>
<div class="card">
<h2>Engagement & Overview</h2>
<div class="ring-box">
<div class="ring {ec}"><div class="ring-inner"><div class="val">{engagement:.2f}</div><div class="lbl">Engagement</div></div></div>
<div style="text-align:center"><div><span class="sev {severity}">{sev_label}</span></div><div style="margin-top:8px;font-size:13px;color:#94a3b8">Struggle Severity</div></div>
</div>
</div>
<div class="card">
<h2>Session Statistics</h2>
<div class="stats-row">
<div class="stat-box"><div class="num">{len(state.raw_events)}</div><div class="lbl">Events</div></div>
<div class="stat-box"><div class="num">{len(state.segment_analyses)}</div><div class="lbl">Segments</div></div>
<div class="stat-box"><div class="num">{len(struggle)}</div><div class="lbl">Struggle Areas</div></div>
<div class="stat-box"><div class="num">{analysis.get('total_pauses',0)}</div><div class="lbl">Pauses</div></div>
<div class="stat-box"><div class="num">{analysis.get('total_rewatches',0)}</div><div class="lbl">Rewatches</div></div>
<div class="stat-box"><div class="num">{analysis.get('average_playback_speed',1.0)}x</div><div class="lbl">Avg Speed</div></div>
</div>
</div>
<div class="card">
<h2>Video Section Map</h2>
<p style="font-size:13px;color:#94a3b8;margin-bottom:12px">Green=easy Yellow=moderate Red=struggle Dark=skipped</p>
<div class="section-map">{seg_html}</div>
</div>
<div class="card">
<h2>Recommendations</h2>
{rec_html}
</div>
<div class="card">
<h2>Narrative Summary</h2>
<div class="narrative-box">{state.narrative or 'Analysis completed successfully.'}</div>
</div>
<div style="text-align:center;margin-top:24px">
<a href="/" class="button">Start New Session</a>
<a href="/watch" class="button sec">Watch Another Video</a>
<a href="/logout" class="button sec">Logout</a>
</div>
</div>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def login_page(user_id: str = Cookie(None)):
    if user_id:
        return RedirectResponse(url="/watch", status_code=302)
    return LOGIN_HTML.replace("{error_display}", "none").replace("{error_msg}", "")


@app.post("/login", response_class=HTMLResponse)
async def login(name: str = Form(...), password: str = Form(...)):
    expected_pw = USER_CREDENTIALS.get(name)
    if not expected_pw or expected_pw != password:
        return LOGIN_HTML.replace("{error_display}", "block").replace("{error_msg}", "Invalid credentials. Try admin/admin123"), 401
    response = RedirectResponse(url="/watch", status_code=302)
    response.set_cookie(key="user_id", value=name, max_age=3600)
    return response


@app.get("/watch", response_class=HTMLResponse)
async def watch_page(user_id: str = Cookie(None)):
    if not user_id:
        return RedirectResponse(url="/", status_code=302)
    session_id = str(uuid.uuid4())
    sessions[session_id] = AgentState(user_id=user_id, session_id=session_id, video_id="")
    html = WATCH_HTML.replace("{session_id}", session_id).replace("{user_id}", user_id)
    return html


@app.post("/api/start")
async def start_session(payload: StartPayload):
    if payload.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    state = sessions[payload.session_id]
    state.video_id = payload.video_id
    state.agent_state["video_url"] = payload.video_url
    logger.info("Session %s started for video %s", payload.session_id, payload.video_id)
    return {"status": "ok", "video_id": payload.video_id}


@app.post("/api/event")
async def track_event(payload: EventPayload):
    if payload.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    sessions[payload.session_id].raw_events.append(payload.event)
    return {"status": "ok"}


@app.post("/api/finish")
async def finish_session(payload: FinishPayload):
    if payload.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    state = sessions[payload.session_id]
    logger.info("Finishing session %s with %d events", payload.session_id, len(state.raw_events))
    result = await agent.run_pipeline(state)
    sessions[payload.session_id] = result
    return {"status": "ok", "redirect": f"/results?session_id={payload.session_id}"}


@app.get("/results", response_class=HTMLResponse)
async def results_page(session_id: str, user_id: str = Cookie(None)):
    if session_id not in sessions:
        return HTMLResponse("Session not found. <a href='/'>Start over</a>", status_code=404)
    return build_results_html(sessions[session_id], user_id or "unknown")


@app.get("/logout")
async def logout():
    r = RedirectResponse(url="/", status_code=302)
    r.delete_cookie("user_id")
    return r


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("youtube_app:app", host="127.0.0.1", port=8000, reload=True)
