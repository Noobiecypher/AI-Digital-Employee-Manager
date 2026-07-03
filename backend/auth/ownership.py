from backend.auth.permissions import SystemRole


def can_access_employee(
    current_user: dict,
    employee_id: str,
) -> bool:

    if current_user["role"] in [
        SystemRole.ADMIN.value,
        SystemRole.HR.value,
        SystemRole.MANAGER.value,
    ]:
        return True

    return (
        current_user.get("employee_id")
        == employee_id
    )


def can_access_candidate(
    current_user: dict,
    candidate_id: str,
) -> bool:

    if current_user["role"] in [
        SystemRole.ADMIN.value,
        SystemRole.HR.value,
    ]:
        return True

    return (
        current_user.get("candidate_id")
        == candidate_id
    )

def can_access_goal(
    current_user: dict,
    employee_name: str,
) -> bool:

    if current_user["role"] in [
        SystemRole.ADMIN.value,
        SystemRole.HR.value,
        SystemRole.MANAGER.value,
    ]:
        return True

    return (
        current_user.get(
            "employee_name",
            ""
        ).lower()
        == employee_name.lower()
    )