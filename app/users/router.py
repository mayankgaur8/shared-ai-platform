from fastapi import APIRouter
router = APIRouter()

@router.get("/me")
async def get_me():
    return {"detail": "Not yet implemented"}
