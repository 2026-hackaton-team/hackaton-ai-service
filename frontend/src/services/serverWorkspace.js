import { useCallback, useEffect, useRef, useState } from 'react';
import { demoApi } from './demoApi.js';

// 계정별 SQLite 응답만 작업공간의 현재 상태로 사용한다.
export function useServerWorkspace(userId) {
  const [state, setState] = useState({ owner: '', status: 'idle', snapshot: null, error: '' });
  const current = useRef(null);
  const queue = useRef(Promise.resolve());
  const generation = useRef(0);

  useEffect(() => {
    const sequence = ++generation.current;
    current.current = null;
    queue.current = Promise.resolve();
    if (!userId) {
      setState({ owner: '', status: 'idle', snapshot: null, error: '' });
      return () => { generation.current++; };
    }
    setState({ owner: userId, status: 'loading', snapshot: null, error: '' });
    demoApi('/workspace/personal', { userId }).then(snapshot => {
      if (sequence !== generation.current) return;
      current.current = snapshot;
      setState({ owner: userId, status: snapshot.initialized ? 'ready' : 'migration', snapshot, error: '' });
    }).catch(error => {
      if (sequence === generation.current) setState({ owner: userId, status: 'error', snapshot: null, error: error.message });
    });
    return () => { generation.current++; };
  }, [userId]);

  const run = useCallback(task => {
    const sequence = generation.current;
    const owner = userId;
    const pending = queue.current.then(async () => {
      if (!owner || sequence !== generation.current || !current.current) {
        throw new Error('현재 가상 계정의 서버 데이터를 불러오지 못했습니다.');
      }
      const snapshot = await task(owner, current.current);
      if (sequence === generation.current) {
        current.current = snapshot;
        setState({ owner, status: 'ready', snapshot, error: '' });
      }
      return snapshot;
    });
    queue.current = pending.catch(() => {});
    return pending.catch(async error => {
      if (sequence === generation.current && error.message.includes('서버 데이터가 변경')) {
        try {
          const snapshot = await demoApi('/workspace/personal', { userId: owner });
          if (sequence === generation.current) {
            current.current = snapshot;
            setState({ owner, status: snapshot.initialized ? 'ready' : 'migration', snapshot, error: '' });
          }
        } catch {
          // 서버 재조회가 실패해도 기존 브라우저 자료는 변경하지 않는다.
        }
      }
      throw error;
    });
  }, [userId]);

  const commit = useCallback(change => run(async (owner, previous) => {
    if (!previous.initialized) throw new Error('브라우저 기록을 이전하거나 빈 서버 공간을 시작하세요.');
    const patch = change(previous);
    return demoApi('/workspace/personal', {
      userId: owner, method: 'PUT',
      body: {
        revision: previous.revision,
        people: patch.people ?? previous.people,
        events: patch.events ?? previous.events,
        records: patch.records ?? previous.records,
      },
    });
  }), [run]);

  const initialize = useCallback(data => run(async (owner, previous) => {
    if (previous.initialized) throw new Error('이미 초기화된 서버 기록은 다시 이전할 수 없습니다.');
    const snapshot = { revision: previous.revision, people: data.people, events: data.events, records: data.records };
    await demoApi('/workspace/migrations/preview', { userId: owner, method: 'POST', body: snapshot });
    return demoApi('/workspace/personal', { userId: owner, method: 'PUT', body: snapshot });
  }), [run]);

  return { state, commit, initialize };
}
