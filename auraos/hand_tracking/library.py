"""AuraOS hand gesture library and implementation status."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GestureSpec:
    """Describes a user-facing hand gesture."""

    category: str
    gesture: str
    action: str
    status: str
    notes: str = ""


IMPLEMENTED = "implemented"
EMITTED = "event_only"
FUTURE = "future"


GESTURE_LIBRARY: tuple[GestureSpec, ...] = (
    GestureSpec("Cursor Control", "Move Index Finger", "Move Cursor", IMPLEMENTED),
    GestureSpec("Cursor Control", "Thumb + Index Pinch", "Left Click", IMPLEMENTED),
    GestureSpec("Cursor Control", "Thumb + Middle Finger Pinch", "Right Click", IMPLEMENTED),
    GestureSpec("Cursor Control", "Double Pinch", "Double Click", IMPLEMENTED),
    GestureSpec("Cursor Control", "Pinch and Hold", "Drag & Drop", IMPLEMENTED),
    GestureSpec("Cursor Control", "Open Palm", "Release Drag", IMPLEMENTED),
    GestureSpec("Navigation", "Two Fingers Up/Down", "Scroll", IMPLEMENTED),
    GestureSpec("Navigation", "Swipe Left", "Back", IMPLEMENTED),
    GestureSpec("Navigation", "Swipe Right", "Forward", IMPLEMENTED),
    GestureSpec("Navigation", "Three-Finger Swipe Left", "Previous Desktop", IMPLEMENTED),
    GestureSpec("Navigation", "Three-Finger Swipe Right", "Next Desktop", IMPLEMENTED),
    GestureSpec("Navigation", "Swipe Up", "Mission Control / Task View", IMPLEMENTED),
    GestureSpec("Navigation", "Swipe Down", "Show Desktop", IMPLEMENTED),
    GestureSpec("Window Management", "Pinch Window Title Bar + Move Hand", "Move Window", FUTURE, "Needs screen/object targeting."),
    GestureSpec("Window Management", "Spread Fingers Apart", "Maximize Window", EMITTED),
    GestureSpec("Window Management", "Pinch Fingers Together", "Minimize Window", EMITTED),
    GestureSpec("Window Management", "Push Hand Left", "Snap Window Left", EMITTED),
    GestureSpec("Window Management", "Push Hand Right", "Snap Window Right", EMITTED),
    GestureSpec("Window Management", "Push Hand Up", "Full Screen", EMITTED),
    GestureSpec("Window Management", "Push Hand Down", "Restore Window", EMITTED),
    GestureSpec("Browser Controls", "Circle Finger Clockwise", "Refresh Page", FUTURE, "Needs circle-path detection."),
    GestureSpec("Browser Controls", "Three-Finger Spread", "New Tab", EMITTED),
    GestureSpec("Browser Controls", "Three-Finger Pinch", "Close Tab", EMITTED),
    GestureSpec("Browser Controls", "Point at Link + Pinch", "Open Link", FUTURE, "Needs screen object detection."),
    GestureSpec("Browser Controls", "Point at Search Bar + Pinch", "Focus Search Bar", FUTURE, "Needs screen object detection."),
    GestureSpec("Media Controls", "Rotate Hand Clockwise", "Volume Up", FUTURE, "Needs hand rotation tracking."),
    GestureSpec("Media Controls", "Rotate Hand Counter-Clockwise", "Volume Down", FUTURE, "Needs hand rotation tracking."),
    GestureSpec("Media Controls", "Open Palm", "Play / Pause", IMPLEMENTED, "Use --action-profile media."),
    GestureSpec("Media Controls", "Swipe Right", "Next Track", IMPLEMENTED, "Use --action-profile media."),
    GestureSpec("Media Controls", "Swipe Left", "Previous Track", IMPLEMENTED, "Use --action-profile media."),
    GestureSpec("Media Controls", "Thumb Up", "Like Current Song", EMITTED),
    GestureSpec("File Management", "Point + Pinch", "Select File", FUTURE, "Needs screen object detection."),
    GestureSpec("File Management", "Air Grab", "Pick Up File", FUTURE, "Needs file target detection."),
    GestureSpec("File Management", "Move Hand", "Move File", FUTURE, "Needs file target detection."),
    GestureSpec("File Management", "Open Hand", "Drop File", FUTURE, "Needs file target detection."),
    GestureSpec("File Management", "Draw Circle Around Files", "Multi-Select", FUTURE, "Needs path selection."),
    GestureSpec("File Management", "Fist Over File", "Delete Confirmation", FUTURE, "Needs file target detection."),
    GestureSpec("AI Interaction", "Point at Text", "Summarize", FUTURE, "Needs screen OCR/context selection."),
    GestureSpec("AI Interaction", "Point at Code", "Explain Code", FUTURE, "Needs screen OCR/context selection."),
    GestureSpec("AI Interaction", "Point at Error", "Debug Error", FUTURE, "Needs screen OCR/context selection."),
    GestureSpec("AI Interaction", "Point at Image", "Describe Image", FUTURE, "Needs screen/object context."),
    GestureSpec("AI Interaction", "Point at Chart", "Analyze Chart", FUTURE, "Needs screen/object context."),
    GestureSpec("AI Interaction", "Circle Any Object", "AI Context Selection", FUTURE, "Needs path + object detection."),
    GestureSpec("AI Interaction", "Pinch and Hold for 2 Seconds", "Open AI Context Menu", EMITTED),
    GestureSpec("System Controls", "Open Palm Facing Camera", "Wake AuraOS", EMITTED),
    GestureSpec("System Controls", "Closed Fist", "Sleep AuraOS", EMITTED),
    GestureSpec("System Controls", "Wave Hand", "Cancel Current Action", FUTURE, "Needs wave classifier."),
    GestureSpec("System Controls", "Both Hands Open", "Activate Listening Mode", FUTURE, "Needs two-hand state."),
    GestureSpec("System Controls", "Both Hands Closed", "Exit Gesture Mode", FUTURE, "Needs two-hand state."),
    GestureSpec("Productivity", "Point at Notification", "Dismiss", FUTURE, "Needs screen object detection."),
    GestureSpec("Productivity", "Point at Calendar", "Open Event", FUTURE, "Needs screen object detection."),
    GestureSpec("Productivity", "Point at Folder", "Open Folder", FUTURE, "Needs screen object detection."),
    GestureSpec("Productivity", "Point at App Icon", "Launch Application", FUTURE, "Needs screen object detection."),
    GestureSpec("Productivity", "Point at Window", "Focus Window", FUTURE, "Needs screen object detection."),
    GestureSpec("Productivity", "Point at Text Field", "Start Dictation", FUTURE, "Needs screen object detection."),
    GestureSpec("Voice + Gesture", "Point at File + voice", "Open File", FUTURE, "Needs voice/gesture fusion."),
    GestureSpec("Voice + Gesture", "Point at Folder + voice", "Move Folder", FUTURE, "Needs voice/gesture fusion."),
    GestureSpec("Voice + Gesture", "Point at Image + voice", "Open Image Editor", FUTURE, "Needs voice/gesture fusion."),
    GestureSpec("Voice + Gesture", "Point at Paragraph + voice", "AI Summary", FUTURE, "Needs voice/gesture fusion."),
    GestureSpec("Voice + Gesture", "Point at Code + voice", "Code Optimization", FUTURE, "Needs voice/gesture fusion."),
    GestureSpec("Voice + Gesture", "Point at Email + voice", "Draft Reply", FUTURE, "Needs voice/gesture fusion."),
    GestureSpec("Voice + Gesture", "Point at Spreadsheet + voice", "AI Analysis", FUTURE, "Needs voice/gesture fusion."),
    GestureSpec("Voice + Gesture", "Point at PDF + voice", "AI Explanation", FUTURE, "Needs voice/gesture fusion."),
    GestureSpec("Voice + Gesture", "Grab Window + voice", "Move Window", FUTURE, "Needs voice/gesture fusion."),
    GestureSpec("Voice + Gesture", "Point at App + voice", "Close Application", FUTURE, "Needs voice/gesture fusion."),
    GestureSpec("Future Advanced", "Air Draw Circle", "Select Region", FUTURE),
    GestureSpec("Future Advanced", "Air Draw Rectangle", "Screenshot Region", FUTURE),
    GestureSpec("Future Advanced", "Air Draw Arrow", "Annotate Screen", FUTURE),
    GestureSpec("Future Advanced", "Air Draw Checkmark", "Confirm Action", FUTURE),
    GestureSpec("Future Advanced", "Air Draw Cross", "Cancel Action", FUTURE),
    GestureSpec("Future Advanced", "Air Zoom Apart", "Zoom In", FUTURE),
    GestureSpec("Future Advanced", "Air Zoom Together", "Zoom Out", FUTURE),
    GestureSpec("Future Advanced", "Rotate Both Hands", "Rotate 3D Objects", FUTURE),
    GestureSpec("Future Advanced", "Hold Palm Still for 2 Seconds", "Freeze Cursor", FUTURE),
    GestureSpec("Future Advanced", "Finger Snap", "Quick Action Shortcut", FUTURE),
)
