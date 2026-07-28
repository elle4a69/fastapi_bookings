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
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = 2310;
const MODULES_CONFIG_PATH = path.join(__dirname, 'project-modules.json');
const LOGS_DIR = path.join(__dirname, 'logs');

if (!fs.existsSync(LOGS_DIR)) {
  fs.mkdirSync(LOGS_DIR, { recursive: true });
}

// Memory of running processes
const runningProcesses = new Map(); // name -> childProcess
const activeLogStreams = new Map(); // name -> writeStream

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

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

// Helper to check if port is active
function checkTcpPort(port) {
  if (!port) return Promise.resolve(false);
  return new Promise((resolve) => {
    const socket = new net.Socket();
    socket.setTimeout(300);
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

// Get runtime status of a module
async function getModuleRuntime(mod) {
  const processEntry = runningProcesses.get(mod.name);
  const isProcessAlive = processEntry ? isPidAlive(processEntry.pid) : false;
  
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
    pid: isProcessAlive ? processEntry.pid : null
  };
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

// Spawn process
async function startModuleProcess(name) {
  loadConfig();
  const mod = modulesConfig.modules.find(m => m.name === name);
  if (!mod) return { ok: false, error: 'Module not found' };

  if (runningProcesses.has(name)) {
    const proc = runningProcesses.get(name);
    if (isPidAlive(proc.pid)) {
      return { ok: false, error: 'Module already running' };
    }
  }

  const cwd = path.resolve(mod.working_dir);
  if (!fs.existsSync(cwd)) {
    return { ok: false, error: `Working directory not found: ${cwd}` };
  }

  const logFile = path.join(LOGS_DIR, `${name}.log`);
  fs.appendFileSync(logFile, `\n--- Started ${new Date().toISOString()} | cmd="${mod.command}" | cwd="${cwd}" ---\n`);

  const logStream = fs.createWriteStream(logFile, { flags: 'a' });
  activeLogStreams.set(name, logStream);

  console.log(`[Dashboard] Spawning: ${mod.command} in ${cwd}`);

  // Spawn inside a shell for compatibility on Windows
  const child = spawn(mod.command, [], {
    cwd,
    shell: true,
    env: { ...process.env, PORT: mod.port ? String(mod.port) : undefined }
  });

  child.stdout.pipe(logStream);
  child.stderr.pipe(logStream);

  runningProcesses.set(name, child);

  child.on('close', (code) => {
    console.log(`[Dashboard] Process ${name} exited with code ${code}`);
    runningProcesses.delete(name);
    logStream.end();
    activeLogStreams.delete(name);
    broadcastStatus();
  });

  return { ok: true, pid: child.pid };
}

// Kill process tree on Windows
async function stopModuleProcess(name) {
  const proc = runningProcesses.get(name);
  if (!proc) {
    // If not tracked by us, check if the port is in use and kill it
    loadConfig();
    const mod = modulesConfig.modules.find(m => m.name === name);
    if (mod && mod.port) {
      const killed = await clearPort(mod.port);
      if (killed) return { ok: true, message: 'Port cleared' };
    }
    return { ok: false, error: 'Module process not running' };
  }

  const pid = proc.pid;
  try {
    console.log(`[Dashboard] Killing process tree for PID ${pid}`);
    await execAsync(`taskkill /PID ${pid} /T /F`);
    runningProcesses.delete(name);
    return { ok: true };
  } catch (err) {
    console.error(`Error killing PID ${pid}:`, err);
    // Fallback direct kill
    try {
      proc.kill();
    } catch {}
    runningProcesses.delete(name);
    return { ok: true, warning: 'Forced kill invoked' };
  }
}

// Clean up port on Windows
async function clearPort(port) {
  try {
    const { stdout } = await execAsync(`netstat -ano | findstr :${port}`);
    const lines = stdout.split('\n').filter(Boolean);
    let killed = false;
    for (const line of lines) {
      const parts = line.trim().split(/\s+/);
      const proto = parts[0];
      const localAddr = parts[1];
      const state = parts[parts.length - 2];
      const pidStr = parts[parts.length - 1];
      const pid = parseInt(pidStr, 10);
      if (pid && pid !== process.pid && (localAddr.endsWith(`:${port}`) || localAddr.endsWith(`.0.0.0.0:${port}`))) {
        console.log(`[Dashboard] Forcefully killing zombie process PID ${pid} listening on port ${port}`);
        await execAsync(`taskkill /PID ${pid} /T /F`);
        killed = true;
      }
    }
    return killed;
  } catch {
    return false;
  }
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
  await new Promise(r => setTimeout(r, 1000));
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
  // Send initial status immediately
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
