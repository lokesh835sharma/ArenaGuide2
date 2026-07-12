import os

renames = {
    "src/services/stadium_data.py": "src/services/venue_manager.py",
    "src/services/context_engine.py": "src/services/navigation_core.py",
    "src/models/schemas.py": "src/models/api_models.py",
    "tests/test_schemas.py": "tests/test_api_models.py",
    "tests/test_stadium_data.py": "tests/test_venue_manager.py",
    "tests/test_context_engine.py": "tests/test_navigation_core.py"
}

# 1. Rename files
for old_path, new_path in renames.items():
    if os.path.exists(old_path):
        os.rename(old_path, new_path)
        print(f"Renamed {old_path} -> {new_path}")

# 2. String replacements across all python files
replacements = {
    # Imports
    "src.services.stadium_data": "src.services.venue_manager",
    "src.services.context_engine": "src.services.navigation_core",
    "src.models.schemas": "src.models.api_models",
    "tests.test_schemas": "tests.test_api_models",
    
    # Classes & Variables
    "Stadium": "VenueMap",
    "UserContext": "VisitorState",
    "AssistResponse": "GuideOutcome",
    
    # Functions
    "get_stadium": "fetch_venue_map",
    "run_assist": "execute_navigation",
}

for root, _, files in os.walk('.'):
    if '.venv' in root or '.git' in root or '.ruff' in root or '__pycache__' in root:
        continue
    for file in files:
        if file.endswith('.py') and file != 'refactor2.py':
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original = content
            for old_str, new_str in replacements.items():
                content = content.replace(old_str, new_str)
                
            if content != original:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Updated contents in {filepath}")
