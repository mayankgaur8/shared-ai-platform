from fastapi import APIRouter
router = APIRouter()

@router.get("")
async def list_prompts():
    return {"prompts": [], "detail": "Module stub"}

@router.post("")
async def create_prompt():
    return {"detail": "Not yet implemented"}
