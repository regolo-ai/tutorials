"""Vulnerable User Profile & Identity API (Demo Target).
Contains:
1. Cross-Site Scripting (XSS - CWE-79) via unsanitized HTML bio rendering
2. Mass Assignment (CWE-915) allowing unprivileged users to overwrite `is_admin` and `role`
"""

import html
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="UserProfile API", version="1.0.0")

USER_PROFILES = {
    "usr_101": {
        "username": "charlie",
        "bio": "Software developer & AI researcher",
        "role": "member",
        "is_admin": False
    }
}


class UpdateProfileRequest(BaseModel):
    # VULNERABLE: Mass assignment allows clients to send extra fields
    data: dict


@app.get("/profile/{user_id}/card", response_class=HTMLResponse)
def render_profile_card(user_id: str):
    """Render public HTML profile card for user.
    CRITICAL SECURITY VULNERABILITY: Stored Cross-Site Scripting (XSS CWE-79) rendering raw user bio.
    """
    if user_id not in USER_PROFILES:
        raise HTTPException(status_code=404, detail="User not found")

    profile = USER_PROFILES[user_id]
    # VULNERABLE CODE: Direct string interpolation without html.escape()
    html_content = f"""
    <html>
        <body>
            <h1>Profile: {profile['username']}</h1>
            <div class="bio">{profile['bio']}</div>
            <span class="badge">Role: {profile['role']}</span>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.put("/profile/{user_id}")
def update_profile(user_id: str, req: UpdateProfileRequest):
    """Update profile data.
    HIGH SECURITY VULNERABILITY: Mass Assignment (CWE-915) allowing unauthorized privilege escalation.
    """
    if user_id not in USER_PROFILES:
        raise HTTPException(status_code=404, detail="User not found")

    profile = USER_PROFILES[user_id]
    # VULNERABLE CODE: Overwrites entire dictionary with user-supplied keys!
    profile.update(req.data)

    return {"status": "updated", "profile": profile}
