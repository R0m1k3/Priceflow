import os
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services import auth_service
from app.dependencies import get_admin_user

router = APIRouter(
    prefix="/debug",
    tags=["debug"],
    dependencies=[Depends(get_admin_user)],
)

logger = logging.getLogger(__name__)

# Chemin absolu pour les dumps de débogage (doit correspondre à celui dans direct_search_service.py)
DEBUG_DIR = "/app/debug_dumps"

class DebugFile(BaseModel):
    filename: str
    size: int
    created_at: float
    created_at_formatted: str

@router.get("/dumps", response_model=List[DebugFile])
def list_debug_dumps():
    """List all debug dump files"""
    if not os.path.exists(DEBUG_DIR):
        return []
    
    files = []
    try:
        for filename in os.listdir(DEBUG_DIR):
            filepath = os.path.join(DEBUG_DIR, filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                files.append(DebugFile(
                    filename=filename,
                    size=stat.st_size,
                    created_at=stat.st_ctime,
                    created_at_formatted=datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
                ))
        
        # Sort by creation time (newest first)
        files.sort(key=lambda x: x.created_at, reverse=True)
        return files
    except Exception as e:
        logger.error(f"Error listing debug dumps: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dumps/{filename}")
def download_debug_dump(filename: str):
    """Download a specific debug dump file"""
    if not os.path.exists(DEBUG_DIR):
        raise HTTPException(status_code=404, detail="Debug directory not found")
    
    filepath = os.path.join(DEBUG_DIR, filename)
    
    # Security check: prevent directory traversal
    if not os.path.abspath(filepath).startswith(os.path.abspath(DEBUG_DIR)):
        raise HTTPException(status_code=403, detail="Access denied")
        
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="File not found")
        
    return FileResponse(filepath, filename=filename)

@router.delete("/dumps/{filename}")
def delete_debug_dump(filename: str):
    """Delete a specific debug dump file"""
    if not os.path.exists(DEBUG_DIR):
        raise HTTPException(status_code=404, detail="Debug directory not found")

    filepath = os.path.join(DEBUG_DIR, filename)

    # Security check: prevent directory traversal
    if not os.path.abspath(filepath).startswith(os.path.abspath(DEBUG_DIR)):
        raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        os.remove(filepath)
        return {"message": "File deleted"}
    except Exception as e:
        logger.error(f"Error deleting debug dump {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dumps/site/{domain}", response_model=List[DebugFile])
def list_debug_dumps_by_site(domain: str):
    """List debug dump files for a specific site domain"""
    if not os.path.exists(DEBUG_DIR):
        return []

    # Clean domain for comparison (remove www. if present)
    clean_domain = domain.lower().strip()
    if clean_domain.startswith("www."):
        clean_domain = clean_domain[4:]

    files = []
    try:
        for filename in os.listdir(DEBUG_DIR):
            # Check if filename starts with the domain
            filename_lower = filename.lower()
            # Handle both formats: domain_query_timestamp.html and amazon.fr_query_timestamp.html
            if filename_lower.startswith(clean_domain) or filename_lower.startswith(clean_domain.replace(".", "_")):
                filepath = os.path.join(DEBUG_DIR, filename)
                if os.path.isfile(filepath):
                    stat = os.stat(filepath)
                    files.append(DebugFile(
                        filename=filename,
                        size=stat.st_size,
                        created_at=stat.st_ctime,
                        created_at_formatted=datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
                    ))

        # Sort by creation time (newest first)
        files.sort(key=lambda x: x.created_at, reverse=True)
        return files
    except Exception as e:
        logger.error(f"Error listing debug dumps for site {domain}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/dumps/site/{domain}")
def delete_debug_dumps_by_site(domain: str):
    """Delete all debug dump files for a specific site domain"""
    if not os.path.exists(DEBUG_DIR):
        return {"message": "No files found", "deleted": 0}

    # Clean domain for comparison
    clean_domain = domain.lower().strip()
    if clean_domain.startswith("www."):
        clean_domain = clean_domain[4:]

    deleted_count = 0
    try:
        for filename in os.listdir(DEBUG_DIR):
            filename_lower = filename.lower()
            if filename_lower.startswith(clean_domain) or filename_lower.startswith(clean_domain.replace(".", "_")):
                filepath = os.path.join(DEBUG_DIR, filename)
                if os.path.isfile(filepath):
                    os.remove(filepath)
                    deleted_count += 1

        return {"message": f"{deleted_count} file(s) deleted", "deleted": deleted_count}
    except Exception as e:
        logger.error(f"Error deleting debug dumps for site {domain}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
