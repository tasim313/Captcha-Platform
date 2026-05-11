from .models import ApiCallLog, LogEntry


def create_platform_log(
    *,
    source,
    level,
    message,
    job=None,
    job_execution=None,
    account=None,
    extra_data=None,
    exception_type="",
    exception_message="",
):
    return LogEntry.objects.create(
        source=source,
        level=level,
        message=message,
        job=job,
        job_execution=job_execution,
        account=account,
        extra_data=extra_data or {},
        exception_type=exception_type,
        exception_message=exception_message,
    )


def create_api_call_log(
    *,
    service_name,
    endpoint,
    method,
    status_code,
    duration_ms,
    account=None,
    request_body=None,
    response_body=None,
    error_message="",
):
    return ApiCallLog.objects.create(
        account=account,
        service_name=service_name,
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        duration_ms=duration_ms,
        request_body=request_body,
        response_body=response_body,
        error_message=error_message,
    )
