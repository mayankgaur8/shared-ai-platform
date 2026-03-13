from fastapi import HTTPException


class WorkflowNotFoundError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=404, detail=detail)


class WorkflowOutputParseError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=502, detail=f"Output parse error: {detail}")


class PromptRenderError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=422, detail=f"Prompt render failed: {detail}")


class ModelRouterError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=503, detail=f"Model routing failed: {detail}")


class SafetyViolationError(HTTPException):
    def __init__(self, detail: str = "Request blocked by safety policy"):
        super().__init__(status_code=400, detail=detail)


class RateLimitExceededError(HTTPException):
    def __init__(self):
        super().__init__(status_code=429, detail="Rate limit exceeded. Please try again later.")


class DocumentNotFoundError(HTTPException):
    def __init__(self, doc_id: str):
        super().__init__(status_code=404, detail=f"Document {doc_id} not found")


class UnauthorizedError(HTTPException):
    def __init__(self, detail: str = "Authentication required"):
        super().__init__(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


class ForbiddenError(HTTPException):
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(status_code=403, detail=detail)
