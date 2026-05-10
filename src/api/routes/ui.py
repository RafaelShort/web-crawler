from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(include_in_schema=False)

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"active": "dashboard"},
    )


@router.get("/crawler", response_class=HTMLResponse)
async def crawler_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="crawler.html",
        context={"active": "crawler"},
    )


@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="search.html",
        context={"active": "search"},
    )


@router.get("/services", response_class=HTMLResponse)
async def services_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="services.html",
        context={"active": "services"},
    )
