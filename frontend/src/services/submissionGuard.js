// 렌더링을 기다리지 않고 잠가 같은 순간의 클릭·Enter 제출을 한 번만 저장한다.
export function createSubmissionGuard(onPendingChange = () => {}) {
  let pending = false;
  return async function submitOnce(save) {
    if (pending) return false;
    pending = true;
    onPendingChange(true);
    try {
      return await save();
    } finally {
      pending = false;
      onPendingChange(false);
    }
  };
}
