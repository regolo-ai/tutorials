#!/usr/bin/env node
/**
 * Regolo.ai + Cognee MCP Memory Connector for Claude Code & OpenClaw.
 * Spawns the Python Cognee memory backend and relays JSON-RPC stdio calls.
 */

import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const pythonServerPath = join(__dirname, 'mcp_server.py');

const pythonProc = spawn('python3', [pythonServerPath], {
  stdio: ['pipe', 'pipe', 'inherit'],
});

process.stdin.pipe(pythonProc.stdin);
pythonProc.stdout.pipe(process.stdout);

pythonProc.on('exit', (code) => {
  process.exit(code || 0);
});
