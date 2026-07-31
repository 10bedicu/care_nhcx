from nhcx.models.coverage_eligibility import CoverageEligibilityRequest


def get_policy_key(request: CoverageEligibilityRequest) -> str:
    insurance = request.insurance or []
    if not insurance:
        return str(request.external_id)

    focal = next((entry for entry in insurance if entry.get("focal")), insurance[0])
    policy = focal.get("policy") or {}
    memberid = policy.get("memberid") or ""
    payerid = policy.get("payerid") or ""
    productid = policy.get("productid") or ""

    if memberid or payerid or productid:
        return f"{memberid}:{payerid}:{productid}"

    return str(request.external_id)


def dedupe_requests_by_policy(
    requests: list[CoverageEligibilityRequest],
) -> list[CoverageEligibilityRequest]:
    """Keep the latest request per policy. Input must be ordered newest-first."""
    seen: set[str] = set()
    unique: list[CoverageEligibilityRequest] = []

    for request in requests:
        key = get_policy_key(request)
        if key in seen:
            continue
        seen.add(key)
        unique.append(request)

    return unique
