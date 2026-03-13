from fastapi import APIRouter
router = APIRouter()

@router.post("/documents/upload")
async def upload_document():
    return {"detail": "Not yet implemented"}

@router.post("/rag/query")
async def query_rag():
    return {"detail": "Not yet implemented"}
