from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import current_user
from ..models import RoadmapItem, User
from ..schemas.roadmap import RoadmapUpdate
from ..services import roadmap_service

router = APIRouter(prefix="/api/roadmap", tags=["roadmap"])


def _payload(items):
    return {"items": [roadmap_service.serialise(i) for i in items], "summary": roadmap_service.summary(items)}


@router.get("")
def get_roadmap(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _payload(roadmap_service.get_items(db, user))


@router.post("/rebuild")
def rebuild(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _payload(roadmap_service.refresh(db, user))


@router.patch("/{item_id}")
def update_item(item_id: int, data: RoadmapUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.query(RoadmapItem).filter_by(id=item_id, user_id=user.id).first()
    if item is None:
        raise HTTPException(404, "Roadmap item not found")
    item.completed = data.completed
    db.commit()
    return roadmap_service.serialise(item)
