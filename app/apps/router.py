from fastapi import APIRouter
router = APIRouter()

@router.get("")
async def list_apps():
    return {"apps": [], "detail": "Module stub — see CODE_EXAMPLES.md"}

@router.post("")
async def create_app():
    return {"detail": "Not yet implemented"}
