from fastapi import APIRouter
router = APIRouter()

@router.get("")
async def list_models():
    return {"models": [], "detail": "Module stub"}

@router.post("")
async def register_model():
    return {"detail": "Not yet implemented"}
