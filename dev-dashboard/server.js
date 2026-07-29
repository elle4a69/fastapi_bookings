import express from 'express';
import { WebSocketServer } from 'ws';
import http from 'http';
import path from 'path';
import fs from 'fs';
import { spawn, exec } from 'child_process';
import { promisify } from 'util';
import net from 'net';
import axios from 'axios';
import cors from 'cors';
import { fileURLToPath } from 'url';

const execAsync = promisify(exec);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = 2310;
const MODULES_CONFIG_PATH = path.join(__dirname, 'project-modules.json');
const LOGS_DIR = path.join(__dirname, 'logs');
const STATE_FILE = path.join(__dirname, 'pids.json');

if (!fs.existsSync(LOGS_DIR)) {
  fs.mkdirSync(LOGS_DIR, { recursive: true });
}

// Global process state memory
let trackedPids = {};
const activeLogStreams = new Map(); // name -> writeStream

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// JSON Load/Save helpers
function loadJson(filePath, fallback) {
  try {
    if (!fs.existsSync(filePath)) return fallback;
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return fallback;
  }
}

function saveJson(filePath, payload) {
  try {
    fs.writeFileSync(filePath, JSON.stringify(payload, null, 2));
  } catch (err) {
    console.error('Error saving state JSON:', err);
  }
}

function loadState() {
  trackedPids = loadJson(STATE_FILE, {});
}
loadState();

function persistPids() {
  saveJson(STATE_FILE, trackedPids);
}

// Load modules config
let modulesConfig = { modules: [] };
function loadConfig() {
  try {
    if (fs.existsSync(MODULES_CONFIG_PATH)) {
      modulesConfig = JSON.parse(fs.readFileSync(MODULES_CONFIG_PATH, 'utf8'));
    }
  } catch (err) {
    console.error('Error loading config:', err);
  }
}
loadConfig();

// Helper to inject critical binaries to PATH
function buildSpawnEnv(extra = {}) {
  const env = { ...process.env, ...extra };
  const sep = process.platform === 'win32' ? ';' : ':';
  const existing = (env.PATH || '').toLowerCase();
  
  const inject = [
    'C:\\Windows',
    'C:\\Windows\\System32',
    path.dirname(process.execPath),
    process.env.APPDATA ? path.join(process.env.APPDATA, 'npm') : '',
    'C:\\python',
    'C:\\Python311',
    'C:\\Python312',
    'C:\\Program Files\\Python312',
    'C:\\Program Files\\Python311',
    process.env.USERPROFILE ? path.join(process.env.USERPROFILE, '.local', 'bin') : '',
    process.env.APPDATA ? path.join(process.env.APPDATA, 'uv', 'bin') : '',
  ].filter(Boolean);

  for (const dir of inject) {
    if (dir && !existing.includes(dir.toLowerCase()) && fs.existsSync(dir)) {
      env.PATH = dir + sep + (env.PATH || '');
    }
  }
  return env;
}

// Clear port using exact netstat pattern matching and LISTENING filter
async function clearPort(port) {
  if (!port) return;
  try {
    const { stdout } = await execAsync(`netstat -ano | findstr ":${port} " | findstr "LISTENING"`);
    const pids = new Set();
    for (const line of stdout.split('\n')) {
      const parts = line.trim().split(/\s+/);
      const pid = parts[parts.length - 1];
      if (pid && /^\d+$/.test(pid) && pid !== '0') pids.add(pid);
    }
    for (const pid of pids) {
      try {
        console.log(`[Dashboard] Forcefully killing zombie process PID ${pid} listening on port ${port}`);
        await execAsync(`taskkill /PID ${pid} /F`);
      } catch {}
    }
    if (pids.size > 0) await sleep(800); // Give the OS time to free the socket
  } catch {}
}

// Helper to check if port is active
function checkTcpPort(port) {
  if (!port) return Promise.resolve(false);
  return new Promise((resolve) => {
    const socket = new net.Socket();
    socket.setTimeout(250);
    socket.once('connect', () => {
      socket.destroy();
      resolve(true);
    });
    socket.once('timeout', () => {
      socket.destroy();
      resolve(false);
    });
    socket.once('error', () => {
      socket.destroy();
      resolve(false);
    });
    socket.connect(port, '127.0.0.1');
  });
}

// Helper to check health URL
async function checkHealth(url) {
  if (!url) return false;
  try {
    const res = await axios.get(url, { timeout: 1000, validateStatus: () => true });
    return res.status >= 200 && res.status < 400;
  } catch {
    return false;
  }
}

// Helper to tail log file
function tailFile(filePath, maxLines = 150) {
  if (!fs.existsSync(filePath)) return [];
  try {
    const content = fs.readFileSync(filePath, 'utf8');
    const lines = content.split(/\r?\n/).filter(Boolean);
    return lines.slice(-maxLines);
  } catch (e) {
    return [`Error reading logs: ${e.message}`];
  }
}

// Helper to check logs for errors in the current session
function checkLogErrors(name) {
  try {
    const logFile = path.join(LOGS_DIR, `${name}.log`);
    if (fs.existsSync(logFile)) {
      const content = fs.readFileSync(logFile, 'utf8');
      const parts = content.split('--- Started');
      const lastSessionLog = parts[parts.length - 1] || '';
      const lastSessionLines = lastSessionLog.split(/\r?\n/).filter(Boolean).slice(-50).join('\n');
      return /Exception|Error|Traceback|critical/i.test(lastSessionLines) || (/\bFailed:\s*[1-9]/i.test(lastSessionLines)) || (/\bfailed\b/i.test(lastSessionLines) && !/\bFailed:\s*0\b/i.test(lastSessionLines));
    }
  } catch {}
  return false;
}

function isPidAlive(pid) {
  if (!pid) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

// Get runtime status of a module
async function getModuleRuntime(mod) {
  const tracked = trackedPids[mod.name];
  const isProcessAlive = tracked && tracked.pid ? isPidAlive(tracked.pid) : false;
  
  const portUp = await checkTcpPort(mod.port);
  const healthy = await checkHealth(mod.health_url);
  
  const running = isProcessAlive || portUp || healthy;
  const logError = checkLogErrors(mod.name);
  
  let status = 'stopped';
  if (running) {
    if (logError) {
      status = 'error';
    } else if (healthy || portUp) {
      status = 'running';
    } else {
      status = 'starting';
    }
  }

  return {
    name: mod.name,
    label: mod.label,
    description: mod.description,
    working_dir: mod.working_dir,
    command: mod.command,
    port: mod.port || null,
    health_url: mod.health_url || null,
    running,
    status,
    pid: isProcessAlive ? tracked.pid : null
  };
}

// Get status of all modules
async function getFullStatus() {
  loadConfig();
  const statuses = [];
  for (const mod of modulesConfig.modules) {
    const rt = await getModuleRuntime(mod);
    statuses.push(rt);
  }
  return {
    generatedAt: new Date().toISOString(),
    modules: statuses
  };
}

// Spawn process using hidden PowerShell -EncodedCommand wrapper
async function startModuleProcess(name) {
  loadConfig();
  const mod = modulesConfig.modules.find(m => m.name === name);
  if (!mod) return { ok: false, error: 'Module not found' };

  // Kill existing processes on the port and clear tracked PID tree first
  if (mod.port) await clearPort(mod.port);

  const tracked = trackedPids[name];
  if (tracked && tracked.pid) {
    try { await execAsync(`taskkill /PID ${tracked.pid} /T /F`); } catch {}
  }
  delete trackedPids[name];
  persistPids();

  const cwd = path.resolve(mod.working_dir);
  if (!fs.existsSync(cwd)) {
    return { ok: false, error: `Working directory not found: ${cwd}` };
  }

  const logFile = path.join(LOGS_DIR, `${name}.log`);
  fs.appendFileSync(logFile, `\n--- Started ${new Date().toISOString()} | cmd="${mod.command}" | cwd="${cwd}" ---\n`);

  const logStream = fs.createWriteStream(logFile, { flags: 'a' });

  if (activeLogStreams.has(name)) {
    try { activeLogStreams.get(name).end(); } catch {}
    activeLogStreams.delete(name);
  }

  console.log(`[Dashboard] Spawning: ${mod.command} in ${cwd}`);

  // Base64 encode the startup command in UTF-16LE for PowerShell
  const encodedCommand = Buffer
    .from(`$ErrorActionPreference='Continue'; ${mod.command}`, 'utf16le')
    .toString('base64');

  const windowsPowerShell = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe');
  const pwshPath = path.join(process.env.ProgramFiles || 'C:\\Program Files', 'PowerShell', '7', 'pwsh.exe');
  const shellExe = fs.existsSync(windowsPowerShell)
    ? windowsPowerShell
    : (fs.existsSync(pwshPath) ? pwshPath : 'powershell.exe');

  const child = spawn(shellExe, ['-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', encodedCommand], {
    cwd,
    detached: false,
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: buildSpawnEnv({ PORT: mod.port ? String(mod.port) : undefined })
  });

  child.stdout.pipe(logStream, { end: false });
  child.stderr.pipe(logStream, { end: false });
  activeLogStreams.set(name, logStream);

  child.on('exit', () => {
    try { logStream.end(); } catch {}
    activeLogStreams.delete(name);
    broadcastStatus();
  });

  child.on('error', (error) => {
    fs.appendFileSync(logFile, `\n[spawn-error] ${error.message}\n`);
    try { logStream.end(); } catch {}
    activeLogStreams.delete(name);
    delete trackedPids[name];
    persistPids();
  });

  trackedPids[name] = {
    pid: child.pid,
    startedAt: new Date().toISOString(),
    cwd,
    command: mod.command
  };
  persistPids();

  return { ok: true, pid: child.pid };
}

// Stop module process tree and release port
async function stopModuleProcess(name) {
  loadConfig();
  const mod = modulesConfig.modules.find(m => m.name === name);
  const tracked = trackedPids[name];

  if (tracked && tracked.pid) {
    try {
      console.log(`[Dashboard] Killing process tree for PID ${tracked.pid}`);
      await execAsync(`taskkill /PID ${tracked.pid} /T /F`);
    } catch {}
  }

  if (activeLogStreams.has(name)) {
    try { activeLogStreams.get(name).end(); } catch {}
    activeLogStreams.delete(name);
  }

  if (mod && mod.port) {
    await clearPort(mod.port);
  }

  delete trackedPids[name];
  persistPids();

  return { ok: true, message: 'Stopped' };
}

// Express endpoints
app.get('/api/status', async (req, res) => {
  const status = await getFullStatus();
  res.json(status);
});

app.post('/api/modules/:name/start', async (req, res) => {
  const result = await startModuleProcess(req.params.name);
  await broadcastStatus();
  res.json(result);
});

app.post('/api/modules/:name/stop', async (req, res) => {
  const result = await stopModuleProcess(req.params.name);
  await broadcastStatus();
  res.json(result);
});

app.post('/api/modules/:name/restart', async (req, res) => {
  await stopModuleProcess(req.params.name);
  await sleep(1000);
  const result = await startModuleProcess(req.params.name);
  await broadcastStatus();
  res.json(result);
});

app.get('/api/modules/:name/logs', (req, res) => {
  const name = req.params.name;
  const logFile = path.join(LOGS_DIR, `${name}.log`);
  const lines = tailFile(logFile, Number(req.query.lines || 150));
  res.json({ ok: true, name, lines });
});

app.get('/api/anti-gravity/state', async (req, res) => {
  try {
    const cmd = `python -c "import sys; sys.path.append(r'e:\\Projects\\King of Kings'); from anti_gravity_system.storage.database import DatabaseManager; import json; db = DatabaseManager(); print(json.dumps({'projects': db.get_all_projects(), 'sub_projects': db.get_all_sub_projects(), 'tasks': db.get_all_tasks(), 'logs': db.get_latest_logs(30)}, default=str))"`;
    const { stdout } = await execAsync(cmd);
    res.json(JSON.parse(stdout));
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
});

// HTTP server and WebSocket Server setup
const server = http.createServer(app);
const wss = new WebSocketServer({ server });

const clients = new Set();
wss.on('connection', async (ws) => {
  clients.add(ws);
  try {
    const status = await getFullStatus();
    ws.send(JSON.stringify({ type: 'status', data: status }));
  } catch (err) {
    console.error(err);
  }

  ws.on('message', async (message) => {
    try {
      const msg = JSON.parse(message);
      if (msg.type === 'get_status') {
        const status = await getFullStatus();
        ws.send(JSON.stringify({ type: 'status', data: status }));
      }
    } catch {}
  });

  ws.on('close', () => {
    clients.delete(ws);
  });
});

async function broadcastStatus() {
  const status = await getFullStatus();
  const payload = JSON.stringify({ type: 'status', data: status });
  for (const client of clients) {
    if (client.readyState === 1) {
      client.send(payload);
    }
  }
}

// Background status polling
setInterval(broadcastStatus, 3500);

server.listen(PORT, () => {
  console.log(`==================================================`);
  console.log(` Bookings App Dev Dashboard active on:`);
  console.log(` http://localhost:${PORT}`);
  console.log(`==================================================`);
});
