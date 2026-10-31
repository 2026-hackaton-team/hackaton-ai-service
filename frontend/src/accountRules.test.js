import test from 'node:test';
import assert from 'node:assert/strict';
import {findAccount,normalizePhone,normalizeUsername,signupError,profileUpdateError,publicProfile} from './accountRules.js';
const valid = {username:'Maeum_01',password:'DemoPass123!',confirmation:'DemoPass123!',name:'체험 사용자',phone:'010-1234-5678',email:'sample@example.com',workplace:'마음전자',organization:'인사팀',workType:'일반 회사원',visibility:'친구에게만 공개'};
test('signup validates fields and normalizes ID and phone without persisting confirmation', () => {
  assert.equal(signupError(valid),'');
  assert.equal(signupError({...valid,workplace:'',organization:''}),'');
  assert.equal(normalizeUsername(' MAEUM_01 '),'maeum_01');
  assert.equal(normalizePhone('+82 (10) 1234-5678'),'+821012345678');
  for (const patch of [{username:'a'},{username:'a@b.com'},{password:'short'},{confirmation:'different'},{name:' '},{phone:'call-me'},{email:'bad-address'},{workType:''},{visibility:'아무거나'}]) assert.notEqual(signupError({...valid,...patch}),'');
});
test('duplicate IDs and emails are rejected case-insensitively', () => {
  assert.match(signupError(valid,[{username:'maeum_01'}]),/아이디/);
  assert.match(signupError(valid,[{email:'SAMPLE@EXAMPLE.COM'}]),/이메일/);
});
test('login uses the ID only', () => {
  const accounts = [{username:'maeum_01',email:'sample@example.com'}];
  assert.equal(findAccount(accounts,' MAEUM_01 '),accounts[0]);
  assert.equal(findAccount(accounts,'sample@example.com'),undefined);
  assert.equal(findAccount(accounts,''),undefined);
  assert.equal(findAccount(accounts,'missing'),undefined);
});
test('profile update keeps password optional and blocks emails used by other accounts', () => {
  const base = {phone:'010-1111-2222',email:'me@example.com',workplace:'',organization:'',workType:'공무원',visibility:'비공개'};
  const accounts = [{username:'me',email:'me@example.com'},{username:'other',email:'other@example.com'}];
  assert.equal(profileUpdateError(base,accounts,'me'),'');
  assert.match(profileUpdateError({...base,email:'OTHER@example.com'},accounts,'me'),/이메일/);
  assert.match(profileUpdateError({...base,password:'NewPass123!',confirmation:'NewPass123!'},accounts,'me'),/현재 비밀번호/);
  assert.equal(profileUpdateError({...base,currentPassword:'x',password:'NewPass123!',confirmation:'NewPass123!'},accounts,'me'),'');
  assert.notEqual(profileUpdateError({...base,currentPassword:'x',password:'NewPass123!',confirmation:'nope'},accounts,'me'),'');
  assert.equal(publicProfile({username:'me',name:'나',email:'me@example.com',salt:'s',hash:'h'}).hash,undefined);
});
