from fastapi import APIRouter
router = APIRouter()

@router.get("/user")
async def get_user_memory():
    return {"memories": [], "detail": "Module stub"}
