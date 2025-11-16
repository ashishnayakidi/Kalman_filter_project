"""Report generation endpoints (LFM-powered)."""
from fastapi import APIRouter, HTTPException, Depends
from app.core.models import QnARequest, ReportResponse
from agent.scoring import daily_summary, minute_rollup
from lfm.runner import LocalLFM
from lfm.prompts import build_qna_prompt, build_weekly_report_prompt
from app.core.config import MODEL_PATH
from pathlib import Path
import os

router = APIRouter()

# Global LFM instance
_lfm_instance: LocalLFM = None


def get_lfm() -> LocalLFM:
    """Get or create global LFM instance (tries Ollama first, then local file)."""
    global _lfm_instance
    if _lfm_instance is None:
        # Try Ollama first
        ollama_model = os.getenv('OLLAMA_MODEL', 'sam860/lfm2:350m')
        ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        
        try:
            import requests
            response = requests.get(f"{ollama_url}/api/tags", timeout=2)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_found = any(m.get('name') == ollama_model for m in models)
                if model_found:
                    _lfm_instance = LocalLFM(model_name=ollama_model, base_url=ollama_url)
                    return _lfm_instance
        except Exception:
            pass  # Fall through to local file
        
        # Fallback to local GGUF file
        model_path = Path(MODEL_PATH)
        if not model_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Model not found. Please ensure Ollama is running with model '{ollama_model}' or download LFM2-350M-Q4_K_M.gguf to {model_path}"
            )
        _lfm_instance = LocalLFM(model_path=str(model_path))
    return _lfm_instance


@router.post("/report/qna", response_model=ReportResponse)
async def generate_qna(request: QnARequest, lfm: LocalLFM = Depends(get_lfm)):
    """Generate Q&A response about battery health."""
    # Get current summaries
    daily = daily_summary()
    minute = minute_rollup()
    
    # Build prompt
    prompt = build_qna_prompt(request.question, daily, minute)
    
    # Generate response
    try:
        answer = lfm.generate(prompt, max_tokens=512)
        return ReportResponse(report=answer, summary=daily)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating response: {str(e)}")


@router.post("/report/weekly", response_model=ReportResponse)
async def generate_weekly_report(lfm: LocalLFM = Depends(get_lfm)):
    """Generate weekly report in markdown format."""
    # Get daily summary
    daily = daily_summary()
    
    # Build prompt
    prompt = build_weekly_report_prompt(daily)
    
    # Generate report
    try:
        report = lfm.generate(prompt, max_tokens=1024)
        return ReportResponse(report=report, summary=daily)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")

