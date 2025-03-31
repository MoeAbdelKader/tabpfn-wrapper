from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

# Assuming templates object is created in main.py and potentially passed via dependency
# For simplicity now, we might redefine it or access it differently later.
# Let's import it directly from main for now, though this isn't ideal for separation.
from main import templates

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def read_landing(request: Request):
    """Serves the main landing/login page."""
    # Placeholder: Render a simple message until landing.html is created
    return templates.TemplateResponse("landing.html", {"request": request})
    # For now, just return a simple HTML response to confirm routing works
    # return HTMLResponse("<html><body><h1>UI Landing Page (Placeholder)</h1></body></html>")

@router.get("/dashboard", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    """Serves the main dashboard page."""
    # This page will initially just render. 
    # Data loading (models list) will be done via client-side JS.
    return templates.TemplateResponse("dashboard.html", {"request": request})

@router.get("/train", response_class=HTMLResponse)
async def read_train_page(request: Request):
    """Serves the model training page."""
    return templates.TemplateResponse("train.html", {"request": request})

@router.get("/predict", response_class=HTMLResponse)
async def read_predict_page(request: Request):
    """Serves the model prediction page."""
    # Model list for dropdown will be loaded via client-side JS.
    return templates.TemplateResponse("predict.html", {"request": request}) 