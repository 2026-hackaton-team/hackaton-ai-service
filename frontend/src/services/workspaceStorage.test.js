import test from 'node:test';
import assert from 'node:assert/strict';
import { STORAGE_KEYS, readStored, writeStored, commitWorkspace } from './workspaceStorage.js';

function memoryStorage(seed = {}) {
  const values = new Map(Object.entries(seed));
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
}

test('stored reader preserves legacy keys, fallbacks and normalization', () => {
  const storage = memoryStorage({ [STORAGE_KEYS.people]: '[{"id":"p1"}]', bad: '{', wrongShape: '{}', session: 'null' });
  assert.deepEqual(readStored(STORAGE_KEYS.people, [], items => items.map(item => ({ ...item, relation: '기타' })), storage), [{ id: 'p1', relation: '기타' }]);
  assert.deepEqual(readStored('bad', [], undefined, storage), []);
  assert.deepEqual(readStored('wrongShape', [], undefined, storage), []);
  assert.equal(readStored('session', { name: 'fallback' }, undefined, storage), null);
  assert.deepEqual(readStored('missing', ['seed'], undefined, storage), ['seed']);
  assert.deepEqual(readStored(STORAGE_KEYS.people, ['seed'], () => { throw new Error(); }, storage), ['seed']);
});

test('write failure is surfaced instead of claiming persistence', () => {
  const storage = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('quota'); } };
  assert.equal(readStored('x', 'fallback', undefined, storage), 'fallback');
  assert.throws(() => writeStored('x', { name: '민수' }, storage), /quota/);
});

test('workspace commit keeps related data together and leaves unmentioned keys alone', () => {
  const storage = memoryStorage({ [STORAGE_KEYS.events]: '[{"id":"e1"}]' });
  commitWorkspace({ people: [{ id: 'p1' }], records: [{ personId: 'p1', amount: 100000 }] }, storage);
  assert.deepEqual(JSON.parse(storage.getItem(STORAGE_KEYS.people)), [{ id: 'p1' }]);
  assert.deepEqual(JSON.parse(storage.getItem(STORAGE_KEYS.records)), [{ personId: 'p1', amount: 100000 }]);
  assert.equal(storage.getItem(STORAGE_KEYS.events), '[{"id":"e1"}]');
});

test('failed second write restores existing people and removes newly introduced keys', () => {
  for (const initial of [null, '[{"id":"old"}]']) {
    const storage = memoryStorage(initial === null ? {} : { [STORAGE_KEYS.people]: initial });
    const set = storage.setItem;
    storage.setItem = (key, value) => { if (key === STORAGE_KEYS.records) throw new Error('quota'); set(key, value); };
    assert.throws(() => commitWorkspace({ people: [{ id: 'new' }], records: [] }, storage), /quota/);
    assert.equal(storage.getItem(STORAGE_KEYS.people), initial);
    assert.equal(storage.getItem(STORAGE_KEYS.records), null);
  }
});

test('serialization or backup-read failure occurs before any workspace write', () => {
  let writes = 0;
  const circular = {}; circular.self = circular;
  const storage = { getItem: () => null, setItem: () => { writes++; } };
  assert.throws(() => commitWorkspace({ people: [], records: circular }, storage), TypeError);
  const unreadable = { ...storage, getItem() { throw new Error('blocked'); } };
  assert.throws(() => commitWorkspace({ people: [] }, unreadable), /blocked/);
  assert.equal(writes, 0);
});
