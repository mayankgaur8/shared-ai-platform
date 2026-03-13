from fastapi import APIRouter
router = APIRouter()

@router.get("/usage")
async def usage():
    return {"detail": "Not yet implemented"}
