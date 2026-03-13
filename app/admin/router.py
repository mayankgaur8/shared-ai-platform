from fastapi import APIRouter
router = APIRouter()

@router.get("/dashboard")
async def dashboard():
    return {"detail": "Admin module stub"}
