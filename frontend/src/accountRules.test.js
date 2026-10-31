import test from 'node:test';
import assert from 'node:assert/strict';
import {findAccount,normalizePhone,normalizeUsername,signupError} from './accountRules.js';
const valid = {username:'Maeum_01',password:'DemoPass123!',confirmation:'DemoPass123!',name:'체험 사용자',phone:'010-1234-5678',email:'sample@example.com'};
test('signup validates six fields and normalizes ID and phone without persisting confirmation', () => {
  assert.equal(signupError(valid),'');
  assert.equal(normalizeUsername(' MAEUM_01 '),'maeum_01');
  assert.equal(normalizePhone('+82 (10) 1234-5678'),'+821012345678');
  for (const patch of [{username:'a'},{username:'a@b.com'},{password:'short'},{confirmation:'different'},{name:' '},{phone:'call-me'},{email:'bad-address'}]) assert.notEqual(signupError({...valid,...patch}),'');
});
test('duplicate IDs and emails are rejected case-insensitively', () => {
  assert.match(signupError(valid,[{username:'maeum_01'}]),/아이디/);
  assert.match(signupError(valid,[{email:'SAMPLE@EXAMPLE.COM'}]),/이메일/);
});
test('login supports new IDs and existing email-only demo accounts', () => {
  const accounts = [{username:'maeum_01',email:'sample@example.com'},{email:'legacy@example.com'}];
  assert.equal(findAccount(accounts,' MAEUM_01 '),accounts[0]);
  assert.equal(findAccount(accounts,'LEGACY@EXAMPLE.COM'),accounts[1]);
  assert.equal(findAccount(accounts,''),undefined);
  assert.equal(findAccount(accounts,'missing'),undefined);
});
