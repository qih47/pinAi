from fastapi import APIRouter, HTTPException
from ..utils.web_scraping import scrape_pindad_website

router = APIRouter()

@router.post("/search-website")
async def search_website(request: dict):
    """Search Pindad website for information"""
    query = request.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
    
    try:
        result = await scrape_pindad_website(query)
        return {
            "status": "success",
            "query": query,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping error: {str(e)}")