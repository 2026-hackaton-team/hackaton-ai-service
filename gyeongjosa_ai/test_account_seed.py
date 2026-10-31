"""발표용 test1234 가상 계정을 빈 상태로 등록한다."""

TEST_USER_ID = "TEST1234"
TEST_LOGIN = "test1234"


def extend_test_dataset(dataset):
    """기존 가상 사용자에 친구·소식·기록이 없는 테스트 계정만 추가한다."""
    if any(user["id"] == TEST_USER_ID for user in dataset["users"]):
        raise ValueError("테스트 계정 ID가 기존 데이터와 충돌합니다.")
    user = {
        "id": TEST_USER_ID, "name": "테스트 사용자", "login_id": TEST_LOGIN,
        "demo_account": True, "fictional_affiliation": "마음결 시연팀",
        "preferred_region": "서울",
        "preferred_event_types": ["결혼", "장례", "돌"],
    }
    return {**dataset, "users": [*dataset["users"], user]}
