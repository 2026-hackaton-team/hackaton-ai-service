import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const python = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
function run(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd: root, stdio: 'inherit' });
    child.once('error', reject);
    child.once('exit', code => code === 0 ? resolve() : reject(new Error(`${command} exited with ${code}`)));
  });
}
try {
  if (!existsSync(python)) await run(process.env.PYTHON || 'python', ['-m', 'venv', '.venv']);
  // A partially created environment may exist if ensurepip was interrupted.
  await run(python, ['-m', 'ensurepip', '--upgrade']);
  await run(python, ['-m', 'pip', 'install', '-r', 'backend/requirements.txt']);
  console.log('\n설치 완료. npm run dev:demo 로 시작하세요.');
} catch (error) {
  console.error('\nPython 3.11 이상 설치와 네트워크 연결을 확인해 주세요.', error.message);
  process.exitCode = 1;
}
