from fastapi import APIRouter
router = APIRouter()

@router.get("")
async def list_templates():
    return {"templates": [], "detail": "Module stub"}
