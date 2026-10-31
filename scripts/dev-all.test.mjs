import assert from 'node:assert/strict';
import { mkdtempSync, existsSync, readFileSync, unlinkSync, rmdirSync } from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { setTimeout as delay } from 'node:timers/promises';
import { createSupervisor, checkPort, readPort, waitFor } from './dev-all.mjs';

const silent = { error() {} };
const running = pid => { try { process.kill(pid, 0); return true; } catch { return false; } };

test('사용 중인 포트는 기존 서버에 영향을 주지 않고 거부한다', async () => {
  const server = net.createServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    await assert.rejects(checkPort(server.address().port), /포트/);
    assert.equal(server.listening, true);
    assert.throws(() => readPort('8000.5', 8000));
    assert.throws(() => readPort('80', 8000));
  } finally { await new Promise(resolve => server.close(resolve)); }
});

test('함께 종료할 때 실제 하위 프로세스까지 정리한다', async () => {
  const temp = mkdtempSync(path.join(os.tmpdir(), 'maeum-gyeol-launcher-'));
  const pidFile = path.join(temp, 'grandchild.pid');
  const supervisor = createSupervisor(temp, silent);
  const code = `const {spawn}=require('node:child_process');const fs=require('node:fs');const c=spawn(process.execPath,['-e','setInterval(()=>{},1000)'],{stdio:'ignore',windowsHide:true});fs.writeFileSync(process.argv[1],String(c.pid));setInterval(()=>{},1000);`;
  const { child } = supervisor.launch(process.execPath, ['-e', code, pidFile], { service: 'test', stdio: 'ignore' });
  let grandchild;
  try {
    for (let i = 0; i < 60 && !existsSync(pidFile); i++) await delay(50);
    assert.ok(existsSync(pidFile), '실제 하위 프로세스가 실행되어야 함');
    grandchild = Number(readFileSync(pidFile, 'utf8'));
    assert.equal(running(child.pid), true);
    assert.equal(running(grandchild), true);
    await supervisor.stop(0);
    for (let i = 0; i < 30 && running(grandchild); i++) await delay(50);
    assert.equal(running(child.pid), false);
    assert.equal(running(grandchild), false);
    assert.equal(await supervisor.done, 0);
  } finally {
    await supervisor.stop(0);
    if (grandchild && running(grandchild)) { try { process.kill(grandchild); } catch {} }
    if (existsSync(pidFile)) unlinkSync(pidFile);
    rmdirSync(temp);
  }
});

test('한쪽 서버가 실패하면 나머지 프로세스도 종료한다', async () => {
  const supervisor = createSupervisor(process.cwd(), silent);
  const sibling = supervisor.launch(process.execPath, ['-e', 'setInterval(()=>{},1000)'], { service: 'sibling', stdio: 'ignore' });
  supervisor.launch(process.execPath, ['-e', 'setTimeout(()=>process.exit(7),150)'], { service: 'failing', stdio: 'ignore' });
  try {
    assert.equal(await supervisor.done, 7);
    assert.equal(running(sibling.child.pid), false);
  } finally { await supervisor.stop(0); }
});

test('설치 실패와 준비 확인 시간 초과를 성공으로 처리하지 않는다', async () => {
  const supervisor = createSupervisor(process.cwd(), silent);
  try {
    await assert.rejects(supervisor.run(process.execPath, ['-e', 'process.exit(3)'], { stdio: 'ignore' }), /종료 코드 3/);
    await assert.rejects(waitFor('http://127.0.0.1:1', supervisor, () => true, 1), /서버 시작/);
  } finally { await supervisor.stop(0); }
});
