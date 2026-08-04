from __future__ import annotations

from enum import StrEnum


class FailureClass(StrEnum):
    INPUT_ERROR = "input_error"
    AUTH_UNAVAILABLE = "auth_unavailable"
    QUOTA_UNAVAILABLE = "quota_unavailable"
    DEFINITE_PROVIDER_FAILURE = "definite_provider_failure"
    DOWNLOAD_FAILURE = "download_failure"
    TIMEOUT_BEFORE_SUBMIT = "timeout_before_submit"
    PROVIDER_TIMEOUT = "provider_timeout"
    TASK_TIMEOUT = "task_timeout"
    INDETERMINATE_SUBMISSION = "indeterminate_submission"
    POLICY_REJECTION = "policy_rejection"
    CANCELLED = "cancelled"


FALLBACK_FAILURES = {
    FailureClass.AUTH_UNAVAILABLE,
    FailureClass.QUOTA_UNAVAILABLE,
    FailureClass.DEFINITE_PROVIDER_FAILURE,
    FailureClass.DOWNLOAD_FAILURE,
    FailureClass.TIMEOUT_BEFORE_SUBMIT,
    FailureClass.PROVIDER_TIMEOUT,
}


class MediaRouterError(RuntimeError):
    def __init__(self, message: str, failure_class: FailureClass, *, submitted: bool = False):
        super().__init__(message)
        self.failure_class = failure_class
        self.submitted = submitted
