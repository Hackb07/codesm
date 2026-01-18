"""Session revert functionality - undo changes to a specific point"""

from dataclasses import dataclass, field
from typing import Optional

from codesm.snapshot import Snapshot
from codesm.session.session import Session


@dataclass
class RevertState:
    """State tracking for a revert operation"""
    message_index: int
    snapshot: Optional[str] = None
    diff: Optional[str] = None
    reverted_files: list[str] = field(default_factory=list)


class SessionRevert:
    """Handles reverting session to a previous state"""
    
    def __init__(self, session: Session, snapshot: Snapshot):
        self.session = session
        self.snapshot = snapshot
        self.revert_state: Optional[RevertState] = None
    
    async def revert_to_message(self, message_index: int) -> RevertState:
        """Revert session and files to state before a message"""
        messages = self.session.messages
        
        if message_index < 0 or message_index >= len(messages):
            raise ValueError(f"Invalid message index: {message_index}")
        
        current_snapshot = await self.snapshot.track()
        
        patches = []
        for i, msg in enumerate(messages):
            if i >= message_index:
                msg_patches = msg.get("_patches", [])
                from codesm.snapshot.snapshot import Patch
                for p in msg_patches:
                    patches.append(Patch(hash=p["hash"], files=p["files"]))
        
        reverted_files = await self.snapshot.revert_files(patches)
        
        diff = ""
        if current_snapshot:
            diff = await self.snapshot.diff(current_snapshot)
        
        self.revert_state = RevertState(
            message_index=message_index,
            snapshot=current_snapshot,
            diff=diff,
            reverted_files=list(reverted_files),
        )
        
        return self.revert_state
    
    async def unrevert(self) -> bool:
        """Undo a revert, restoring to the pre-revert state"""
        if not self.revert_state or not self.revert_state.snapshot:
            return False
        
        success = await self.snapshot.restore(self.revert_state.snapshot)
        if success:
            self.revert_state = None
        return success
    
    def confirm_revert(self) -> bool:
        """Confirm the revert, removing messages from session"""
        if not self.revert_state:
            return False
        
        self.session.messages = self.session.messages[:self.revert_state.message_index]
        self.session.save()
        self.revert_state = None
        return True
    
    def cancel_revert(self) -> None:
        """Cancel revert without making changes to session"""
        self.revert_state = None
