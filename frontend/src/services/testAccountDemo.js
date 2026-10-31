// 테스트 계정의 로그인 값만 정의한다. 친구·받은 일정은 미리 채우지 않는다.
export const TEST_USERNAME = 'test1234';
export const TEST_PROFILE_ID = 'TEST1234';
export const matchesTestLogin = (username, password) => String(username || '').trim().toLowerCase() === TEST_USERNAME && password === TEST_USERNAME;
