import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const python = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const apiPort = Number(process.env.MAEUM_API_PORT || 8000);
const webPort = Number(process.env.MAEUM_WEB_PORT || 5173);
const children = [];
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  process.exitCode = code;
  for (const child of children) if (child.exitCode === null) child.kill();
}
process.on('SIGINT', () => stop());
process.on('SIGTERM', () => stop());
process.on('exit', () => { for (const child of children) if (child.exitCode === null) child.kill(); });
function available(port) {
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('포트는 1024~65535 범위로 설정해 주세요.');
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', () => reject(new Error(`${port} 포트를 사용 중입니다. 기존 서버를 종료하거나 MAEUM_API_PORT / MAEUM_WEB_PORT를 변경해 주세요.`)));
    server.listen(port, '127.0.0.1', () => server.close(resolve));
  });
}
function launch(command, args, env = process.env) {
  const child = spawn(command, args, { cwd: root, stdio: 'inherit', env });
  children.push(child);
  child.once('error', error => { console.error(error.message); stop(1); });
  child.once('exit', code => { if (!stopping) { console.error('데모 서버가 종료되었습니다.'); stop(code || 1); } });
}
try {
  if (!existsSync(python)) throw new Error('먼저 npm run setup:demo 를 실행해 주세요.');
  if (!existsSync(path.join(root, 'node_modules/vite/bin/vite.js'))) throw new Error('먼저 npm install 을 실행해 주세요.');
  if (apiPort === webPort) throw new Error('프론트와 서버는 서로 다른 포트를 사용해야 합니다.');
  await Promise.all([available(apiPort), available(webPort)]);
  launch(python, ['-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1', '--port', String(apiPort)]);
  const apiUrl = `http://127.0.0.1:${apiPort}`;
  let ready = false;
  for (let i = 0; i < 40 && !stopping; i++) {
    try { const response = await fetch(`${apiUrl}/api/health`, { signal: AbortSignal.timeout(1500) }); if (response.ok) { ready = true; break; } } catch {}
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  if (!ready) throw new Error('FastAPI 시작에 실패했습니다. 위 오류를 확인해 주세요.');
  launch(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', String(webPort), '--strictPort'], {
    ...process.env, VITE_AI_MODE: 'server', VITE_AI_API_BASE_URL: '/api', MAEUM_API_TARGET: apiUrl,
  });
  console.log(`\n마음결 데모: http://127.0.0.1:${webPort}/\nFastAPI API 문서: ${apiUrl}/docs\n종료: Ctrl+C\n`);
} catch (error) { console.error(error.message); stop(1); }
