import express from 'express';
import { WebSocketServer } from 'ws';
import http from 'http';
import path from 'path';
import fs from 'fs';
import { spawn, exec, execFile } from 'child_process';
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

// Clear port using exact JS-parsed netstat matching and LISTENING filter
async function clearPort(port) {
  if (!port) return;
  try {
    const { stdout } = await execAsync('netstat -ano');
    const lines = stdout.split('\n').filter(Boolean);
    let killed = false;
    for (const line of lines) {
      const parts = line.trim().split(/\s+/);
      const localAddr = parts[1] || '';
      const state = parts[parts.length - 2] || '';
      const pidStr = parts[parts.length - 1];
      const pid = parseInt(pidStr, 10);
      
      if (pid && pid !== process.pid && state === 'LISTENING' && (localAddr.endsWith(`:${port}`) || localAddr.endsWith(`[::]:${port}`))) {
        console.log(`[Dashboard] Forcefully killing zombie process PID ${pid} listening on port ${port}`);
        try {
          await execAsync(`taskkill /PID ${pid} /F`);
          killed = true;
        } catch {}
      }
    }
    if (killed) await sleep(800); // Give the OS time to free the socket
  } catch (err) {
    console.error('Error during clearPort:', err);
  }
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
  const healthy = portUp && mod.health_url ? await checkHealth(mod.health_url) : false;
  
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

// Docker Container Management & Monitoring
const CONTAINER_NAME_REGEX = /^[a-zA-Z0-9_.-]+$/;

function enrichContainer(c) {
  const name = c.Names || c.name || '';
  let group = 'Other';
  let role = 'Container Service';

  if (name.includes('fastapi-bookings') || name === 'fastapi_bookings') {
    group = 'FastAPI Bookings';
    if (name.includes('postgres')) role = 'PostgreSQL 16 + pgvector Database';
    else if (name.includes('redis')) role = 'Redis 7 Cache & Task Queue';
    else if (name.includes('neo4j')) role = 'Neo4j 5 Graph Database';
    else role = 'FastAPI Application Container';
  } else if (name.includes('shorturls')) {
    group = 'ShortURLs';
    if (name.includes('db')) role = 'MongoDB 7 Document Database';
    else role = 'ShortURL Service';
  } else if (name.includes('agent-memory')) {
    group = 'Agent Memory';
    if (name.includes('graphiti')) role = 'Graphiti Temporal Knowledge Graph';
    else if (name.includes('neo4j')) role = 'Agent Memory Neo4j Knowledge Store';
    else role = 'Agent Memory Service';
  } else if (name.includes('chatwoot')) {
    group = 'Chatwoot';
    if (name.includes('rails')) role = 'Chatwoot Web & API Server';
    else if (name.includes('sidekiq')) role = 'Chatwoot Background Worker';
    else if (name.includes('redis')) role = 'Chatwoot Redis Cache & PubSub';
    else if (name.includes('postgres')) role = 'Chatwoot PostgreSQL Database';
    else if (name.includes('base')) role = 'Chatwoot Base Init Container';
    else role = 'Chatwoot Service';
  } else if (name.includes('signoz')) {
    group = 'SigNoz APM';
    if (name.includes('clickhousekeeper')) role = 'ClickHouse Keeper Raft Consensus';
    else if (name.includes('clickhouse-user-scripts')) role = 'ClickHouse Schema Script Runner';
    else if (name.includes('clickhouse')) role = 'ClickHouse Columnar Telemetry DB';
    else if (name.includes('metastore')) role = 'SigNoz Metastore PostgreSQL';
    else if (name.includes('ingester')) role = 'OTel Collector & Metrics Ingester';
    else if (name.includes('migrator')) role = 'SigNoz Schema Migration Tool';
    else if (name.includes('signoz')) role = 'SigNoz Web UI & Query Service';
    else role = 'SigNoz Telemetry Component';
  }

  let health = 'none';
  if (c.HealthStatus && c.HealthStatus !== 'none') {
    health = c.HealthStatus;
  } else if (c.Status && c.Status.includes('(healthy)')) {
    health = 'healthy';
  } else if (c.Status && c.Status.includes('(unhealthy)')) {
    health = 'unhealthy';
  } else if (c.Status && c.Status.includes('(health: starting)')) {
    health = 'starting';
  }

  return {
    id: c.ID,
    name: name,
    image: c.Image,
    state: c.State || 'unknown',
    status: c.Status || '',
    health: health,
    ports: c.Ports || '',
    runningFor: c.RunningFor || '',
    createdAt: c.CreatedAt || '',
    command: c.Command || '',
    group,
    role
  };
}

let cachedContainers = null;
let lastDockerFetch = 0;
const DOCKER_CACHE_TTL_MS = 2500;

async function getDockerContainers(force = false) {
  const now = Date.now();
  if (!force && cachedContainers && (now - lastDockerFetch < DOCKER_CACHE_TTL_MS)) {
    return cachedContainers;
  }
  return new Promise((resolve) => {
    execFile('docker', ['ps', '-a', '--format', '{{json .}}'], { encoding: 'utf8', timeout: 6000 }, (err, stdout) => {
      if (err) {
        return resolve(cachedContainers || []);
      }
      try {
        const lines = (stdout || '').trim().split('\n').filter(Boolean);
        const raw = lines.map(line => {
          try { return JSON.parse(line); } catch { return null; }
        }).filter(Boolean);

        const enriched = raw.map(enrichContainer);
        const groupOrder = ['FastAPI Bookings', 'ShortURLs', 'Agent Memory', 'Chatwoot', 'SigNoz APM', 'Other'];
        enriched.sort((a, b) => {
          const gA = groupOrder.indexOf(a.group);
          const gB = groupOrder.indexOf(b.group);
          const idxA = gA === -1 ? 99 : gA;
          const idxB = gB === -1 ? 99 : gB;
          if (idxA !== idxB) return idxA - idxB;
          if (a.state === 'running' && b.state !== 'running') return -1;
          if (a.state !== 'running' && b.state === 'running') return 1;
          return a.name.localeCompare(b.name);
        });

        cachedContainers = enriched;
        lastDockerFetch = Date.now();
        resolve(enriched);
      } catch (parseErr) {
        console.error('Error parsing docker output:', parseErr);
        resolve(cachedContainers || []);
      }
    });
  });
}

async function runDockerAction(name, action) {
  if (!CONTAINER_NAME_REGEX.test(name)) {
    return { ok: false, error: 'Invalid container name format' };
  }
  if (!['start', 'stop', 'restart'].includes(action)) {
    return { ok: false, error: 'Invalid action. Allowed: start, stop, restart' };
  }
  return new Promise((resolve) => {
    execFile('docker', [action, name], { encoding: 'utf8', timeout: 30000 }, async (err, stdout, stderr) => {
      if (err) {
        return resolve({ ok: false, error: (stderr || stdout || err.message).trim() });
      }
      cachedContainers = null;
      lastDockerFetch = 0;
      await sleep(600);
      await getDockerContainers(true);
      resolve({ ok: true, name, action, output: (stdout || '').trim() });
    });
  });
}

async function getDockerLogs(name, maxLines = 150) {
  if (!CONTAINER_NAME_REGEX.test(name)) {
    return { ok: false, error: 'Invalid container name format' };
  }
  const linesToFetch = Math.min(Math.max(1, Number(maxLines) || 150), 1000);
  return new Promise((resolve) => {
    execFile('docker', ['logs', '--tail', String(linesToFetch), name], { encoding: 'utf8', timeout: 10000 }, (err, stdout, stderr) => {
      const combined = (stdout || '') + '\n' + (stderr || '');
      const lines = combined.split(/\r?\n/).filter(Boolean).slice(-linesToFetch);
      if (err && lines.length === 0) {
        return resolve({ ok: false, error: err.message, lines: [] });
      }
      resolve({ ok: true, name, lines });
    });
  });
}

// Get status of all modules and docker containers in parallel with deduplication
let statusRefreshInFlight = null;
async function getFullStatus() {
  if (statusRefreshInFlight) return statusRefreshInFlight;
  statusRefreshInFlight = (async () => {
    loadConfig();
    const [modules, docker] = await Promise.all([
      Promise.all((modulesConfig.modules || []).map(mod => getModuleRuntime(mod))),
      getDockerContainers()
    ]);
    return {
      generatedAt: new Date().toISOString(),
      modules,
      docker
    };
  })();
  try {
    return await statusRefreshInFlight;
  } finally {
    statusRefreshInFlight = null;
  }
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

// Docker endpoints
app.get('/api/docker/containers', async (req, res) => {
  try {
    const containers = await getDockerContainers(req.query.refresh === 'true');
    res.json({ ok: true, generatedAt: new Date().toISOString(), containers });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
});

app.post('/api/docker/containers/:name/:action', async (req, res) => {
  try {
    const { name, action } = req.params;
    const result = await runDockerAction(name, action);
    await broadcastStatus();
    if (!result.ok) {
      return res.status(400).json(result);
    }
    res.json(result);
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
});

app.get('/api/docker/containers/:name/logs', async (req, res) => {
  try {
    const { name } = req.params;
    const result = await getDockerLogs(name, req.query.lines);
    if (!result.ok) {
      return res.status(400).json(result);
    }
    res.json(result);
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
