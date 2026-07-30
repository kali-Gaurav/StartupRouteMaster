from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from api.dependencies import get_current_user
from services.ml.demand_training_manager import DemandTrainingManager

router = APIRouter(prefix="/admin/ml", tags=["admin_ml"])

@router.post("/train")
async def trigger_model_training(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    [Admin Only] Triggers the training pipeline for the Demand Predictor.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
        
    trainer = DemandTrainingManager(db)
    try:
        result = trainer.train_demand_model()
        return {"success": True, "message": "Model training complete.", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
