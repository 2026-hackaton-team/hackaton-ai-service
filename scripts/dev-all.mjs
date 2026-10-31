import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

const root = fileURLToPath(new URL('../', import.meta.url));

export function readPort(value, fallback) {
  const port = Number(value || fallback);
  if (!Number.isInteger(port) || port < 1024 || port > 65535) {
    throw new Error('포트는 1024~65535 사이의 정수로 설정해 주세요.');
  }
  return port;
}

export function checkPort(port) {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', () => reject(new Error(`${port} 포트를 사용 중이거나 열 수 없습니다. 기존 서버를 종료하거나 MAEUM_API_PORT / MAEUM_WEB_PORT를 바꿔 주세요.`)));
    server.listen(port, '127.0.0.1', () => server.close(resolve));
  });
}

// 이 실행기가 직접 시작한 프로세스만 종료한다. Windows에서는 Vite의 하위 프로세스도 정리한다.
export function createSupervisor(cwd, log = console) {
  const children = new Set();
  let stopping = false;
  let stopPromise;
  let finish;
  const done = new Promise(resolve => { finish = resolve; });

  async function terminate(child) {
    if (!child.pid || child.exitCode !== null || child.signalCode !== null) return;
    if (process.platform === 'win32') {
      const killer = spawn(path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'taskkill.exe'),
        ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore', windowsHide: true });
      await new Promise(resolve => {
        killer.once('error', () => { child.kill(); resolve(); });
        killer.once('close', resolve);
      });
    } else {
      try { process.kill(-child.pid, 'SIGTERM'); } catch { child.kill(); }
    }
    if (child.exitCode !== null || child.signalCode !== null) return;
    let timer;
    await new Promise(resolve => {
      const closed = () => { clearTimeout(timer); resolve(); };
      child.once('close', closed);
      timer = setTimeout(() => {
        child.removeListener('close', closed);
        try { process.platform === 'win32' ? child.kill('SIGKILL') : process.kill(-child.pid, 'SIGKILL'); } catch {}
        resolve();
      }, 3000);
    });
  }

  function stop(code = 0) {
    if (stopPromise) return stopPromise;
    stopping = true;
    stopPromise = (async () => {
      await Promise.all([...children].map(terminate));
      finish(code);
      return code;
    })();
    return stopPromise;
  }

  function launch(command, args, options = {}) {
    if (stopping) throw new Error('실행을 중단했습니다.');
    const child = spawn(command, args, {
      cwd: options.cwd || cwd, env: options.env || process.env,
      stdio: options.stdio || 'inherit', windowsHide: true,
      detached: process.platform !== 'win32',
    });
    children.add(child);
    const finished = new Promise(resolve => {
      let settled = false;
      const settle = (code, error) => {
        if (settled) return;
        settled = true;
        children.delete(child);
        resolve({ code, error });
        if (options.service && !stopping) {
          log.error(`\n${options.service}가 종료됐습니다.${error ? ` ${error.message}` : ''} 다른 서버도 종료합니다.`);
          void stop(code || 1);
        }
      };
      child.once('error', error => settle(1, error));
      child.once('close', code => settle(code ?? 1));
    });
    return { child, finished };
  }

  async function run(command, args, options) {
    const { code, error } = await launch(command, args, options).finished;
    if (stopping) throw new Error('실행을 중단했습니다.');
    if (error) throw new Error(`${command} 실행 실패: ${error.message}`);
    if (code !== 0) throw new Error(`준비 명령이 실패했습니다 (종료 코드 ${code}). 위 설치 오류를 확인해 주세요.`);
  }

  return { launch, run, stop, done, get stopping() { return stopping; } };
}

export async function waitFor(url, supervisor, validate = () => true, timeout = 60000) {
  const deadline = Date.now() + timeout;
  while (!supervisor.stopping && Date.now() < deadline) {
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(1500) });
      if (response.ok && await validate(response)) return;
    } catch {}
    await delay(250);
  }
  if (!supervisor.stopping) throw new Error(`서버 시작을 확인하지 못했습니다: ${url}\n위 실행 로그를 확인해 주세요.`);
}

function npmCli() {
  const candidates = [process.env.npm_execpath, path.join(path.dirname(process.execPath), 'node_modules/npm/bin/npm-cli.js')];
  const found = candidates.find(candidate => candidate && path.basename(candidate) === 'npm-cli.js' && existsSync(candidate));
  if (!found) throw new Error('npm 실행 파일을 찾지 못했습니다. npm이 포함된 Node.js를 설치해 주세요.');
  return found;
}

async function main() {
  const supervisor = createSupervisor(root);
  const onInterrupt = () => { console.log('\n서버와 화면을 종료합니다.'); void supervisor.stop(0); };
  process.on('SIGINT', onInterrupt);
  process.on('SIGTERM', onInterrupt);
  if (process.platform === 'win32') process.on('SIGBREAK', onInterrupt);
  try {
    const apiPort = readPort(process.env.MAEUM_API_PORT, 8000);
    const webPort = readPort(process.env.MAEUM_WEB_PORT, 5173);
    if (apiPort === webPort) throw new Error('서버와 화면 포트는 서로 달라야 합니다.');
    const python = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
    const frontend = path.join(root, 'frontend');
    const vite = path.join(frontend, 'node_modules/vite/bin/vite.js');
    await Promise.all([checkPort(apiPort), checkPort(webPort)]);
    if (process.argv.includes('--check')) {
      console.log(`포트 확인 완료: API ${apiPort}, 화면 ${webPort}`);
      console.log(`Python 환경: ${existsSync(python) ? '있음' : '첫 실행 시 생성'}`);
      console.log(`화면 의존성: ${existsSync(vite) ? '있음' : '첫 실행 시 설치'}`);
      await supervisor.stop(0);
      return;
    }

    console.log('마음결 통합 실행 준비 — 처음에는 의존성 다운로드에 시간이 걸릴 수 있습니다.');
    if (!existsSync(python)) {
      console.log('\n[준비] 프로젝트 Python 가상환경 생성');
      await supervisor.run(process.env.MAEUM_PYTHON || (process.platform === 'win32' ? 'python' : 'python3'), ['-m', 'venv', path.join(root, '.venv')]);
    }
    const requirement = path.join(root, 'requirements.txt');
    const extra = 'openai>=1.75,<3';
    const fingerprint = createHash('sha256').update(readFileSync(requirement)).update(extra).digest('hex');
    const stamp = path.join(root, '.venv', '.maeum-gyeol-requirements');
    // 기존 설치 확인 파일을 읽어 불필요한 재설치를 피한다.
    const legacyStamp = path.join(root, '.venv', '.onmaeum-requirements');
    const installed = existsSync(stamp) ? readFileSync(stamp, 'utf8') : existsSync(legacyStamp) ? readFileSync(legacyStamp, 'utf8') : '';
    if (installed !== fingerprint) {
      console.log('\n[준비] Python 의존성 설치');
      await supervisor.run(python, ['-m', 'pip', 'install', '-r', requirement, extra]);
    }
    writeFileSync(stamp, fingerprint);
    if (!existsSync(vite)) {
      console.log('\n[준비] 화면 의존성 설치');
      if (process.platform === 'win32') {
        await supervisor.run(process.execPath, [npmCli(), 'install', '--no-package-lock'], { cwd: frontend });
      } else {
        // macOS/Linux npm comes from PATH; its install path differs between Node distributions.
        await supervisor.run('npm', ['install', '--no-package-lock'], { cwd: frontend });
      }
    }

    const apiUrl = `http://127.0.0.1:${apiPort}`;
    const webUrl = `http://127.0.0.1:${webPort}`;
    console.log('\n[서버] 통합 FastAPI 시작');
    supervisor.launch(python, ['-m', 'uvicorn', 'gyeongjosa_ai.api:app', '--host', '127.0.0.1', '--port', String(apiPort)],
      { service: 'FastAPI', env: { ...process.env, PYTHONUNBUFFERED: '1' } });
    await waitFor(`${apiUrl}/api/health`, supervisor, async response => (await response.json()).status === 'ok');
    if (supervisor.stopping) return;
    console.log('\n[화면] React 개발 서버 시작');
    supervisor.launch(process.execPath, [vite, '--host', '127.0.0.1', '--port', String(webPort), '--strictPort'], {
      cwd: frontend, service: 'React', env: { ...process.env, MAEUM_API_TARGET: apiUrl },
    });
    await waitFor(webUrl, supervisor);
    if (!supervisor.stopping) {
      console.log(`\n실행 완료\n앱: ${webUrl}\n종료: Ctrl+C\n`);
      console.log('AI 자유 상담에서 가상 시연을 선택할 수 있습니다. 실모델 호출에는 CODYSSEY_API_KEY가 필요합니다.\n');
    }
    process.exitCode = await supervisor.done;
  } catch (error) {
    if (!supervisor.stopping) {
      console.error(`\n${error.message}`);
      await supervisor.stop(1);
    }
  } finally {
    process.exitCode = await supervisor.done;
    process.removeListener('SIGINT', onInterrupt);
    process.removeListener('SIGTERM', onInterrupt);
    if (process.platform === 'win32') process.removeListener('SIGBREAK', onInterrupt);
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
