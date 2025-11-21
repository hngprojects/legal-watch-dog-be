
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from models import DataRevision, ChangeDiff
from datetime import datetime
import difflib
import uuid

class ChangeDetectionService:
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_previous_revision(self, source_id: str) -> Optional[DataRevision]:
        """
        Get the most recent revision for a given source.
        Excludes soft-deleted records.
        """
        return self.db.query(DataRevision)\
            .filter(
                DataRevision.source_id == source_id,
                DataRevision.deleted_at.is_(None)  # Exclude soft-deleted
            )\
            .order_by(DataRevision.created_at.desc())\
            .first()
    
    def compare_summaries(self, old_summary: str, new_summary: str) -> bool:
        """
        Compare two AI summaries using exact string match.
        Returns True if they are DIFFERENT, False if they are the SAME.
        """
        # Handle None cases
        if old_summary is None and new_summary is None:
            return False
        if old_summary is None or new_summary is None:
            return True
        
        # Exact string comparison
        return old_summary.strip() != new_summary.strip()
    
    def generate_diff_patch(self, old_summary: str, new_summary: str) -> Dict[str, Any]:
        """
        Generate a detailed diff patch in JSON format.
        Uses Python's difflib to create a human-readable diff.
        """
        # Handle None cases
        if old_summary is None:
            old_summary = ""
        if new_summary is None:
            new_summary = ""
        
        # Generate unified diff
        old_lines = old_summary.splitlines(keepends=True)
        new_lines = new_summary.splitlines(keepends=True)
        
        diff = list(difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile='old_summary',
            tofile='new_summary',
            lineterm=''
        ))
        
        # Create structured diff patch
        diff_patch = {
            "diff_type": "text_comparison",
            "old_length": len(old_summary),
            "new_length": len(new_summary),
            "unified_diff": diff,
            "change_summary": {
                "additions": sum(1 for line in diff if line.startswith('+')),
                "deletions": sum(1 for line in diff if line.startswith('-')),
            },
            "old_preview": old_summary[:200] + "..." if len(old_summary) > 200 else old_summary,
            "new_preview": new_summary[:200] + "..." if len(new_summary) > 200 else new_summary,
        }
        
        return diff_patch
    
    def create_revision_with_detection(
        self,
        source_id: str,
        scraped_at: datetime,
        status: str,
        raw_content: str,
        extracted_data: Dict[str, Any],
        ai_summary: str
    ) -> Tuple[DataRevision, Optional[ChangeDiff]]:
        """
        Main function: Creates a new revision and detects changes.
        Returns the new revision and the change_diff (if created).
        """
        
        # Step 1: Get previous revision
        previous_revision = self.get_previous_revision(source_id)
        
        # Step 2: Determine if there's a change
        was_change_detected = False
        if previous_revision is not None:
            was_change_detected = self.compare_summaries(
                previous_revision.ai_summary,
                ai_summary
            )
        
        # Step 3: Create new revision (ALWAYS created)
        new_revision = DataRevision(
            revision_id=str(uuid.uuid4()),
            source_id=source_id,
            scraped_at=scraped_at,
            status=status,
            raw_content=raw_content,
            extracted_data=extracted_data,
            ai_summary=ai_summary,
            was_change_detected=was_change_detected,
            created_at=datetime.utcnow(),
            deleted_at=None
        )
        
        self.db.add(new_revision)
        self.db.flush()  # Get the revision_id without committing
        
        # Step 4: Create change_diff if change was detected
        change_diff = None
        if was_change_detected and previous_revision is not None:
            diff_patch = self.generate_diff_patch(
                previous_revision.ai_summary,
                ai_summary
            )
            
            change_diff = ChangeDiff(
                diff_id=str(uuid.uuid4()),
                new_revision_id=new_revision.revision_id,
                old_revision_id=previous_revision.revision_id,
                diff_patch=diff_patch,
                ai_confidence=None  # Can be populated later by AI system
            )
            
            self.db.add(change_diff)
        
        # Step 5: Commit transaction (both revision and diff together)
        self.db.commit()
        self.db.refresh(new_revision)
        if change_diff:
            self.db.refresh(change_diff)
        
        return new_revision, change_diff