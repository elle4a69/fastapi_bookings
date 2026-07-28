const { existsSync } = require("node:fs");
const { spawnSync } = require("node:child_process");
const { resolve } = require("node:path");

const root = resolve(__dirname, "..");
const candidates = [
  resolve(root, ".venv", "Scripts", "python.exe"),
  resolve(root, ".venv", "bin", "python"),
  "python",
];
const python = candidates.find((candidate) => candidate === "python" || existsSync(candidate));
const result = spawnSync(python, process.argv.slice(2), { cwd: root, stdio: "inherit" });
process.exit(result.status ?? 1);
