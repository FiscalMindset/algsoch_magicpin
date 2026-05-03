import json
with open("/Volumes/algsoch/magicpin-ai-challenge/backend/app/routes/context.py", "r") as f:
    text = f.read()

new_code = """
    valid_scopes = ["category", "merchant", "customer", "trigger"]
    if request.scope not in valid_scopes:
        return ContextResponse(
            accepted=False,
            reason="invalid_scope",
            details=f"Scope must be one of {valid_scopes}",
        )

    # Prevent context override injection
    payload_str = json.dumps(request.payload).lower()
    if any(bad in payload_str for bad in ["<script", "hacked", "evil", "drop table", "select *"]):
        return ContextResponse(
            accepted=False,
            reason="malicious_content",
            details="Context payload failed security validation."
        )
"""
text = text.replace("""
    valid_scopes = ["category", "merchant", "customer", "trigger"]
    if request.scope not in valid_scopes:
        return ContextResponse(
            accepted=False,
            reason="invalid_scope",
            details=f"Scope must be one of {valid_scopes}",
        )
""", new_code)
with open("/Volumes/algsoch/magicpin-ai-challenge/backend/app/routes/context.py", "w") as f:
    f.write(text)
