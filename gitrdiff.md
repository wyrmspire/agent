# Git Diff Report

**Generated**: Sat, Dec 13, 2025 12:53:49 PM

**Local Branch**: main

**Comparing Against**: origin/main

---

## Uncommitted Changes (working directory)

### Modified/Staged Files

```
 M boot/setup.py
 M core/sandb.py
 M runsv.sh
 M tool/files.py
?? gitrdiff.md
```

### Uncommitted Diff

```diff
diff --git a/boot/setup.py b/boot/setup.py
index 8cc18a1..838ee08 100644
--- a/boot/setup.py
+++ b/boot/setup.py
@@ -100,28 +100,72 @@ def load_config() -> Dict[str, Any]:
     return config
 
 
-def setup_logging(level: str = None) -> None:
-    """Setup logging configuration.
+def setup_logging(level: str = None, session_id: str = None) -> str:
+    """Setup logging configuration with file and console output.
     
     Args:
         level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
+        session_id: Optional session ID for log file name
+        
+    Returns:
+        Path to the session log file
     """
+    from datetime import datetime
+    
     if level is None:
         level = os.getenv("AGENT_LOG_LEVEL", "INFO")
     
     # Convert string to logging level
     numeric_level = getattr(logging, level.upper(), logging.INFO)
     
-    # Configure logging
-    logging.basicConfig(
-        level=numeric_level,
-        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
-        datefmt="%Y-%m-%d %H:%M:%S",
+    # Create logs directory
+    project_root = get_project_root()
+    logs_dir = project_root / "logs"
+    logs_dir.mkdir(exist_ok=True)
+    
+    # Generate session log filename
+    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
+    if session_id:
+        log_filename = f"session_{timestamp}_{session_id[:8]}.log"
+    else:
+        log_filename = f"session_{timestamp}.log"
+    log_path = logs_dir / log_filename
+    
+    # Configure root logger
+    root_logger = logging.getLogger()
+    root_logger.setLevel(logging.DEBUG)  # Capture all, filter at handler level
+    
+    # Clear existing handlers
+    root_logger.handlers.clear()
+    
+    # Console handler (shows INFO and above)
+    console_handler = logging.StreamHandler()
+    console_handler.setLevel(numeric_level)
+    console_formatter = logging.Formatter(
+        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
+        datefmt="%Y-%m-%d %H:%M:%S"
+    )
+    console_handler.setFormatter(console_formatter)
+    root_logger.addHandler(console_handler)
+    
+    # File handler (captures everything with verbose format)
+    file_handler = logging.FileHandler(log_path, encoding='utf-8')
+    file_handler.setLevel(logging.DEBUG)
+    file_formatter = logging.Formatter(
+        "%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
+        datefmt="%Y-%m-%d %H:%M:%S"
     )
+    file_handler.setFormatter(file_formatter)
+    root_logger.addHandler(file_handler)
     
     # Reduce noise from libraries
     logging.getLogger("urllib3").setLevel(logging.WARNING)
     logging.getLogger("httpx").setLevel(logging.WARNING)
+    
+    # Log session start
+    logging.info(f"Session log started: {log_path}")
+    
+    return str(log_path)
 
 
 def setup_python_path() -> None:
diff --git a/core/sandb.py b/core/sandb.py
index f8f6982..d503493 100644
--- a/core/sandb.py
+++ b/core/sandb.py
@@ -44,9 +44,14 @@ class Workspace:
     workspace directory, preventing access to source code and config files.
     It also monitors resource usage to prevent system crashes.
     
+    Read-only project access:
+        The agent can READ files from the project root but can only WRITE
+        to the workspace directory. Sensitive files (.env, secrets) are blocked.
+    
     Example:
         ws = Workspace("/home/user/agent/workspace")
-        safe_path = ws.resolve("data/prices.csv")  # OK
+        safe_path = ws.resolve("data/prices.csv")  # OK - workspace
+        ws.resolve_project_read("flow/loops.py")   # OK - read-only project
         ws.resolve("../servr/api.py")  # Raises WorkspaceError
     """
     
@@ -55,6 +60,7 @@ class Workspace:
         workspace_root: Union[str, Path],
         max_workspace_size_gb: float = 5.0,
         min_free_ram_percent: float = 10.0,
+        allow_project_read: bool = True,
     ):
         """Initialize workspace with root directory and resource limits.
         
@@ -62,33 +68,88 @@ class Workspace:
             workspace_root: Root directory for workspace operations
             max_workspace_size_gb: Maximum workspace size in GB (default: 5GB)
             min_free_ram_percent: Minimum free RAM percentage (default: 10%)
+            allow_project_read: Allow read-only access to project files (default: True)
         """
         self.root = Path(workspace_root).resolve()
         self.max_workspace_size_bytes = int(max_workspace_size_gb * 1024 * 1024 * 1024)
         self.min_free_ram_percent = min_free_ram_percent
+        self.allow_project_read = allow_project_read
         
         # Create workspace if it doesn't exist
         self.root.mkdir(parents=True, exist_ok=True)
         
-        # Define blocked directories (relative to project root)
-        project_root = self.root.parent
-        self.blocked_dirs = [
-            project_root / ".env",
-            project_root / "servr",
-            project_root / "boot",
-            project_root / "core",
-            project_root / "gate",
-            project_root / "flow",
-            project_root / "model",
+        # Project root is parent of workspace
+        self._project_root = self.root.parent
+        
+        # Sensitive files that are NEVER readable (even with project read enabled)
+        self.sensitive_patterns = [
+            ".env",
+            ".env.*",
+            "*.pem",
+            "*.key",
+            "*secret*",
+            "*credentials*",
+            ".git/",
+        ]
+        
+        # Directories blocked for WRITE operations (relative to project root)
+        self.blocked_write_dirs = [
+            self._project_root / "servr",
+            self._project_root / "boot",
+            self._project_root / "core",
+            self._project_root / "gate",
+            self._project_root / "flow",
+            self._project_root / "model",
+            self._project_root / "tool",
+            self._project_root / "tests",
         ]
         
-        # Define blocked files
+        # Files blocked from any access
         self.blocked_files = [
-            project_root / ".env",
-            project_root / ".env.example",
-            project_root / "requirements.txt",
+            self._project_root / ".env",
+            self._project_root / ".env.example",
+            self._project_root / ".env.local",
         ]
     
+    @property
+    def project_root(self) -> Path:
+        """Get the project root directory (parent of workspace)."""
+        return self._project_root
+    
+    @property
+    def base_path(self) -> Path:
+        """Get the base path of the workspace (alias for root)."""
+        return self.root
+    
+    def _is_sensitive_file(self, path: Path) -> bool:
+        """Check if a file matches sensitive patterns."""
+        name = path.name.lower()
+        path_str = str(path).lower()
+        
+        for pattern in self.sensitive_patterns:
+            if pattern.startswith("*") and pattern.endswith("*"):
+                # Contains pattern
+                if pattern[1:-1] in name:
+                    return True
+            elif pattern.startswith("*"):
+                # Ends with pattern
+                if name.endswith(pattern[1:]):
+                    return True
+            elif pattern.endswith("*"):
+                # Starts with pattern
+                if name.startswith(pattern[:-1]):
+                    return True
+            elif pattern.endswith("/"):
+                # Directory pattern
+                if f"/{pattern}" in path_str or path_str.endswith(pattern[:-1]):
+                    return True
+            else:
+                # Exact match
+                if name == pattern:
+                    return True
+        
+        return False
+    
     @property
     def base_path(self) -> Path:
         """Get the base path of the workspace (alias for root)."""
@@ -133,16 +194,54 @@ class Workspace:
                 f"Path '{path}' is outside workspace (must be within {self.root})"
             )
         
-        # Check if path accesses blocked directories
-        for blocked_dir in self.blocked_dirs:
-            try:
-                resolved.relative_to(blocked_dir)
-                raise WorkspaceError(
-                    f"Access to '{blocked_dir.name}/' is blocked for safety"
-                )
-            except ValueError:
-                # Path is not under blocked_dir, which is good
-                pass
+        # Workspace paths don't need blocked dir checks (they're already in workspace)
+        # But check if path is a blocked file
+        if resolved in self.blocked_files:
+            raise WorkspaceError(
+                f"Access to '{resolved.name}' is blocked for safety"
+            )
+        
+        return resolved
+    
+    def resolve_project_read(self, path: Union[str, Path]) -> Path:
+        """Resolve a path for READ-ONLY access to project files.
+        
+        This allows the agent to read source code files but not modify them.
+        Sensitive files (.env, secrets, keys) are still blocked.
+        
+        Args:
+            path: Path to resolve (relative to project root or absolute)
+            
+        Returns:
+            Resolved absolute path within project
+            
+        Raises:
+            WorkspaceError: If path is outside project, blocked, or sensitive
+        """
+        if not self.allow_project_read:
+            raise WorkspaceError("Project read access is disabled")
+        
+        # Convert to Path object
+        if isinstance(path, str):
+            path = Path(path)
+        
+        # If path is relative, make it relative to project root
+        if not path.is_absolute():
+            path = self._project_root / path
+        
+        # Resolve to absolute path
+        try:
+            resolved = path.resolve()
+        except (OSError, RuntimeError) as e:
+            raise WorkspaceError(f"Cannot resolve path: {e}")
+        
+        # Check if path is within project
+        try:
+            resolved.relative_to(self._project_root)
+        except ValueError:
+            raise WorkspaceError(
+                f"Path '{path}' is outside project (must be within {self._project_root})"
+            )
         
         # Check if path is a blocked file
         if resolved in self.blocked_files:
@@ -150,6 +249,16 @@ class Workspace:
                 f"Access to '{resolved.name}' is blocked for safety"
             )
         
+        # Check if path matches sensitive patterns
+        if self._is_sensitive_file(resolved):
+            raise WorkspaceError(
+                f"Access to '{resolved.name}' is blocked (sensitive file)"
+            )
+        
+        # Verify file exists for read operations
+        if not resolved.exists():
+            raise WorkspaceError(f"Path does not exist: {resolved}")
+        
         return resolved
     
     def resolve_read(self, path: Union[str, Path]) -> Path:
diff --git a/runsv.sh b/runsv.sh
index a1bb73e..e419925 100644
--- a/runsv.sh
+++ b/runsv.sh
@@ -1 +1,28 @@
+#!/bin/bash
+# runsv.sh - Start model server and chat CLI
+# Server runs in this terminal, chat opens in a new window
+
+echo "🚀 Starting agent server + chat..."
+echo ""
+
+# Wait for server to be ready, then open chat CLI in a new terminal
+(
+    echo "⏳ Waiting for server to be ready..."
+    # Wait up to 120 seconds for server to respond
+    for i in {1..60}; do
+        if curl -s http://localhost:8000/v1/models > /dev/null 2>&1; then
+            echo "✅ Server ready! Opening chat..."
+            start bash -c "cd $(pwd) && python cli.py; echo ''; read -p 'Press Enter to close...'"
+            exit 0
+        fi
+        sleep 2
+    done
+    echo "❌ Server didn't start in time"
+) &
+
+# Start server in current terminal (shows logs)
+echo "📡 Server starting on http://localhost:8000"
+echo "💬 Chat terminal will open when server is ready..."
+echo ""
 uvicorn servr.api:app --host 0.0.0.0 --port 8000
+
diff --git a/tool/files.py b/tool/files.py
index e3b428c..dba52f7 100644
--- a/tool/files.py
+++ b/tool/files.py
@@ -66,8 +66,14 @@ class ListFiles(BaseTool):
         path_str = arguments["path"]
         
         try:
-            # Resolve path within workspace
-            path = self.workspace.resolve_read(path_str)
+            # Try workspace first
+            try:
+                path = self.workspace.resolve_read(path_str)
+                is_project = False
+            except WorkspaceError:
+                # Fall back to project read (read-only)
+                path = self.workspace.resolve_project_read(path_str)
+                is_project = True
             
             if not path.is_dir():
                 return ToolResult(
@@ -80,6 +86,10 @@ class ListFiles(BaseTool):
             # List entries
             entries = []
             for item in sorted(path.iterdir()):
+                # Skip hidden files in project (like .git)
+                if is_project and item.name.startswith('.'):
+                    continue
+                    
                 entry = {
                     "name": item.name,
                     "type": "dir" if item.is_dir() else "file",
@@ -91,8 +101,18 @@ class ListFiles(BaseTool):
                 entries.append(entry)
             
             # Format output
-            rel_path = self.workspace.get_relative_path(path)
-            output_lines = [f"Contents of {rel_path}:"]
+            if is_project:
+                # For project paths, show relative to project root
+                try:
+                    rel_path = path.relative_to(self.workspace.project_root)
+                except ValueError:
+                    rel_path = path
+                prefix = "[PROJECT READ-ONLY] "
+            else:
+                rel_path = self.workspace.get_relative_path(path)
+                prefix = ""
+            
+            output_lines = [f"{prefix}Contents of {rel_path}:"]
             for entry in entries:
                 if entry["type"] == "dir":
                     output_lines.append(f"  📁 {entry['name']}/")
@@ -141,7 +161,7 @@ class ReadFile(BaseTool):
     
     @property
     def description(self) -> str:
-        return f"Read the contents of a file within workspace (up to {self.max_size} bytes). Returns file content as text."
+        return f"Read the contents of a file (up to {self.max_size} bytes). Can read workspace files and project files (read-only)."
     
     @property
     def parameters(self) -> Dict[str, Any]:
@@ -149,7 +169,7 @@ class ReadFile(BaseTool):
             properties={
                 "path": {
                     "type": "string",
-                    "description": "File path to read (relative to workspace)",
+                    "description": "File path to read (relative to workspace or project root)",
                 },
             },
             required=["path"],
@@ -160,8 +180,14 @@ class ReadFile(BaseTool):
         path_str = arguments["path"]
         
         try:
-            # Resolve path within workspace
-            path = self.workspace.resolve_read(path_str)
+            # Try workspace first
+            try:
+                path = self.workspace.resolve_read(path_str)
+                is_project = False
+            except WorkspaceError:
+                # Fall back to project read (read-only)
+                path = self.workspace.resolve_project_read(path_str)
+                is_project = True
             
             if not path.is_file():
                 return ToolResult(
@@ -184,6 +210,15 @@ class ReadFile(BaseTool):
             # Read file
             content = path.read_text(encoding="utf-8")
             
+            # Add header for project files
+            if is_project:
+                try:
+                    rel_path = path.relative_to(self.workspace.project_root)
+                except ValueError:
+                    rel_path = path
+                header = f"[PROJECT READ-ONLY: {rel_path}]\n{'='*60}\n"
+                content = header + content
+            
             return ToolResult(
                 tool_call_id="",
                 output=content,
```

---

## Commits Ahead (local changes not on remote)

```
```

## Commits Behind (remote changes not pulled)

```
```

---

## File Changes (what you'd get from remote)

```
```

---

## Full Diff (green = new on remote, red = removed on remote)

```diff
```
