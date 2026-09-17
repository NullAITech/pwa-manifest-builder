"""Web Share Target API & File Handling API Validator and Action Simulator.

Provides W3C Web Share Target compliance validation (GET/POST, multipart/form-data,
file payload schemas) and File Handling API validation (launchQueue consumers,
MIME-type to extension mappings, and single-client vs multiple-clients launch types).
100% Python Standard Library.
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .models import (
    FileHandlerItem,
    FileHandlerSpec,
    FileHandlerValidationReport,
    FileLaunchSimulationResult,
    IconSpec,
    PWAManifestConfig,
    ShareSimulationResult,
    ShareTargetSpec,
    ShareTargetValidationReport,
)

# Standard MIME type regex pattern (e.g., text/plain, image/*, application/vnd.ms-excel)
MIME_TYPE_RE = re.compile(r"^[a-zA-Z0-9\-_+.]+/[a-zA-Z0-9\-_.+*]+$")


def _is_url_within_scope(url: str, scope: str) -> bool:
    """Checks if a URL or path is within the designated manifest scope."""
    clean_url = url.split("?")[0].split("#")[0]
    clean_scope = scope.split("?")[0].split("#")[0]

    if clean_scope.endswith("/") and not clean_url.endswith("/"):
        clean_url_dir = clean_url + "/"
    else:
        clean_url_dir = clean_url

    return clean_url.startswith(clean_scope) or clean_url_dir.startswith(clean_scope)


def validate_share_target(
    config_or_target: Union[PWAManifestConfig, ShareTargetSpec, Dict[str, Any]],
    scope: str = "/",
) -> ShareTargetValidationReport:
    """Validate Web Share Target configuration against W3C specification.
    
    Checks action resolution, method (GET vs POST), enctype requirements,
    and parameter mapping for text, URL, and multipart file transfers.
    """
    raw_target: Optional[Dict[str, Any]] = None
    resolved_scope = scope

    if isinstance(config_or_target, PWAManifestConfig):
        resolved_scope = config_or_target.scope or "/"
        if config_or_target.share_target:
            st = config_or_target.share_target
            raw_target = st.to_dict() if isinstance(st, ShareTargetSpec) else st
    elif isinstance(config_or_target, ShareTargetSpec):
        raw_target = config_or_target.to_dict()
    elif isinstance(config_or_target, dict):
        if "share_target" in config_or_target:
            st = config_or_target.get("share_target")
            raw_target = st.to_dict() if hasattr(st, "to_dict") else st
            resolved_scope = config_or_target.get("scope", scope) or "/"
        else:
            raw_target = config_or_target
            resolved_scope = scope

    if not raw_target:
        return ShareTargetValidationReport(
            is_valid=False,
            action="",
            method="GET",
            enctype="application/x-www-form-urlencoded",
            params={},
            supports_files=False,
            accepted_file_types=[],
            errors=["No share_target definition provided."],
            warnings=[],
            receiver_script="// No share_target configured.",
            share_invoker_script="// No share_target configured.",
        )

    action = str(raw_target.get("action", "")).strip()
    method = str(raw_target.get("method", "GET")).strip().upper()
    enctype = str(raw_target.get("enctype", "application/x-www-form-urlencoded")).strip().lower()
    raw_params = raw_target.get("params", {}) or {}

    errors: List[str] = []
    warnings: List[str] = []
    accepted_file_types: List[str] = []
    supports_files = False

    # 1. Validate Action
    if not action:
        errors.append("Share target is missing required 'action' URL.")
    else:
        if not _is_url_within_scope(action, resolved_scope):
            warnings.append(
                f"Share target action '{action}' appears outside manifest scope '{resolved_scope}'."
            )

    # 2. Validate Method
    if method not in ("GET", "POST"):
        errors.append(f"Invalid method '{method}'; W3C Share Target requires 'GET' or 'POST'.")

    # 3. Validate Params structure
    if not isinstance(raw_params, dict):
        errors.append("'params' must be an object with title, text, url, or files mapping.")
        raw_params = {}

    title_key = raw_params.get("title")
    text_key = raw_params.get("text")
    url_key = raw_params.get("url")
    files_val = raw_params.get("files")

    has_any_param = bool(title_key or text_key or url_key or files_val)
    if not has_any_param:
        errors.append(
            "Share target 'params' must specify at least one of: 'title', 'text', 'url', or 'files'."
        )

    # 4. Validate Files configuration
    if files_val:
        supports_files = True
        if method != "POST":
            errors.append("File sharing requires method='POST'. 'GET' cannot accept file payloads.")
        if enctype != "multipart/form-data":
            errors.append(
                f"File sharing requires enctype='multipart/form-data' (found: '{enctype}')."
            )

        # Normalize files_val to list of specs
        file_specs = [files_val] if isinstance(files_val, dict) else (files_val if isinstance(files_val, list) else [])
        if not file_specs:
            errors.append("'params.files' must be a dictionary or list of file parameter definitions.")

        for f_idx, f_spec in enumerate(file_specs):
            if not isinstance(f_spec, dict):
                errors.append(f"File parameter #{f_idx + 1} must be an object.")
                continue
            f_name = f_spec.get("name")
            if not f_name:
                errors.append(f"File parameter #{f_idx + 1} is missing required 'name' form field.")
            accept_val = f_spec.get("accept", [])
            if isinstance(accept_val, str):
                accept_types = [a.strip() for a in accept_val.split(",") if a.strip()]
            elif isinstance(accept_val, list):
                accept_types = [str(a).strip() for a in accept_val if str(a).strip()]
            else:
                accept_types = []

            if not accept_types:
                warnings.append(
                    f"File parameter '{f_name or f'#{f_idx + 1}'}' does not specify 'accept' MIME types or extensions."
                )
            else:
                accepted_file_types.extend(accept_types)

    if method == "GET" and enctype == "multipart/form-data":
        warnings.append("Method is 'GET' but enctype is 'multipart/form-data'. GET ignores multipart enctype.")

    # 5. Generate Receiver Script
    if method == "GET":
        receiver_js = f"""// Web Share Target GET Receiver Handler
// Add this script to your share receiver page ({action or '/share'})
window.addEventListener('DOMContentLoaded', () => {{
  const params = new URLSearchParams(window.location.search);
  const sharedData = {{
    title: params.get({json.dumps(title_key or "title")}),
    text: params.get({json.dumps(text_key or "text")}),
    url: params.get({json.dumps(url_key or "url")}),
  }};
  
  // Verify if any share payload was received
  if (sharedData.title || sharedData.text || sharedData.url) {{
    console.info('[PWA Share Target] Received share payload:', sharedData);
    // Dispatch to your application state or store
    if (typeof handleIncomingShare === 'function') {{
      handleIncomingShare(sharedData);
    }}
  }}
}});"""
    else:
        # POST method - ServiceWorker background fetch interceptor
        receiver_js = f"""// Web Share Target POST ServiceWorker Interceptor
// Include in your service worker (sw.js) to intercept POST requests to {action or '/share'}
self.addEventListener('fetch', (event) => {{
  const url = new URL(event.request.url);
  if (event.request.method === 'POST' && url.pathname === {json.dumps(action or '/share')}) {{
    event.respondWith((async () => {{
      try {{
        const formData = await event.request.formData();
        const sharePayload = {{
          title: formData.get({json.dumps(title_key or "title")}),
          text: formData.get({json.dumps(text_key or "text")}),
          url: formData.get({json.dumps(url_key or "url")}),
          filesCount: 0,
        }};
        
        // Cache or persist received files
        const receivedFiles = [];
        for (const [key, value] of formData.entries()) {{
          if (value instanceof File) {{
            receivedFiles.push({{ name: value.name, type: value.type, size: value.size }});
          }}
        }}
        sharePayload.filesCount = receivedFiles.length;
        
        // Store payload in Cache Storage or IndexedDB for UI consumption
        const cache = await caches.open('pwa-shared-data');
        await cache.put(
          new Request('/pwa-pending-share.json'),
          new Response(JSON.stringify({{ payload: sharePayload, files: receivedFiles }}), {{
            headers: {{ 'Content-Type': 'application/json' }}
          }})
        );
        
        // Redirect browser to target page with HTTP 303 See Other
        return Response.redirect('{action or "/share"}?shared=true', 303);
      }} catch (err) {{
        console.error('[PWA SW] Failed to process shared POST payload:', err);
        return Response.redirect('{action or "/share"}?share_error=true', 303);
      }}
    }})());
  }}
}});"""

    # 6. Generate Invocation Script
    share_invoker_js = f"""// Test Invoking Web Share Target
if (navigator.share) {{
  navigator.share({{
    title: 'Check out this awesome link!',
    text: 'Explore this progressive web application feature.',
    url: window.location.href,
  }})
  .then(() => console.log('[PWA Share] Share successful.'))
  .catch((err) => console.warn('[PWA Share] Share aborted or failed:', err));
}} else {{
  console.warn('[PWA Share] Web Share API not supported on this browser.');
}}"""

    is_valid = (len(errors) == 0)

    return ShareTargetValidationReport(
        is_valid=is_valid,
        action=action,
        method=method,
        enctype=enctype,
        params=raw_params,
        supports_files=supports_files,
        accepted_file_types=accepted_file_types,
        errors=errors,
        warnings=warnings,
        receiver_script=receiver_js,
        share_invoker_script=share_invoker_js,
    )


def validate_file_handlers(
    config_or_handlers: Union[PWAManifestConfig, List[Any], Dict[str, Any]],
    scope: str = "/",
) -> FileHandlerValidationReport:
    """Validate File Handling API (file_handlers) entries against W3C specification.
    
    Verifies action routing within scope, MIME type syntax, valid file extension formats,
    and single-client / multiple-clients launch mode.
    """
    raw_handlers: List[Any] = []
    resolved_scope = scope

    if isinstance(config_or_handlers, PWAManifestConfig):
        raw_handlers = config_or_handlers.file_handlers
        resolved_scope = config_or_handlers.scope or "/"
    elif isinstance(config_or_handlers, dict):
        raw_handlers = config_or_handlers.get("file_handlers", [])
        resolved_scope = config_or_handlers.get("scope", scope) or "/"
    elif isinstance(config_or_handlers, list):
        raw_handlers = config_or_handlers

    handlers_data: List[FileHandlerItem] = []
    errors: List[str] = []
    warnings: List[str] = []

    valid_count = 0
    invalid_count = 0

    registered_extensions: Set[str] = set()

    for idx, item in enumerate(raw_handlers):
        if isinstance(item, FileHandlerSpec):
            action = item.action
            accept = item.accept
            name = item.name
            launch_type = item.launch_type
        elif isinstance(item, dict):
            action = str(item.get("action", ""))
            accept = item.get("accept", {})
            name = item.get("name")
            launch_type = str(item.get("launch_type", "single-client"))
        else:
            invalid_count += 1
            errors.append(f"File handler #{idx + 1} must be an object or FileHandlerSpec.")
            continue

        item_issues: List[str] = []
        extensions: List[str] = []
        mime_types: List[str] = []

        # 1. Action Check
        if not action:
            item_issues.append("File handler is missing required 'action' URL.")
        else:
            if not _is_url_within_scope(action, resolved_scope):
                msg = f"File handler action '{action}' is outside manifest scope '{resolved_scope}'."
                warnings.append(msg)
                item_issues.append(msg)

        # 2. Launch Type Check
        if launch_type not in ("single-client", "multiple-clients"):
            item_issues.append(
                f"Invalid launch_type '{launch_type}'; must be 'single-client' or 'multiple-clients'."
            )

        # 3. Accept Check
        if not accept or not isinstance(accept, dict):
            item_issues.append(
                "Missing required 'accept' mapping of MIME types to file extensions."
            )
        else:
            for mime, exts in accept.items():
                mime_str = str(mime).strip()
                mime_types.append(mime_str)

                if not MIME_TYPE_RE.match(mime_str):
                    item_issues.append(
                        f"MIME type '{mime_str}' does not match standard 'type/subtype' format."
                    )

                ext_list = [exts] if isinstance(exts, str) else (exts if isinstance(exts, list) else [])
                if not ext_list:
                    item_issues.append(f"MIME type '{mime_str}' specifies no associated file extensions.")

                for ext in ext_list:
                    ext_str = str(ext).strip().lower()
                    if not ext_str.startswith("."):
                        item_issues.append(
                            f"File extension '{ext_str}' must start with a leading '.' (e.g. '.txt', '.png')."
                        )
                    else:
                        extensions.append(ext_str)
                        if ext_str in registered_extensions:
                            warnings.append(
                                f"Extension '{ext_str}' is handled by multiple file handlers."
                            )
                        registered_extensions.add(ext_str)

        is_item_valid = (len(item_issues) == 0)
        if is_item_valid:
            valid_count += 1
        else:
            invalid_count += 1
            for issue in item_issues:
                errors.append(f"Handler '{name or action or f'#{idx + 1}'}': {issue}")

        handlers_data.append(FileHandlerItem(
            action=action,
            accept=accept if isinstance(accept, dict) else {},
            name=name,
            launch_type=launch_type,
            is_valid=is_item_valid,
            extensions=extensions,
            mime_types=mime_types,
            issues=item_issues,
        ))

    # Generate Browser LaunchQueue Consumer Script
    if valid_count > 0:
        launch_queue_script = """// W3C File Handling API Consumer Implementation
// Add this script to your application's bootstrap logic
if ('launchQueue' in window && 'files' in LaunchParams.prototype) {
  launchQueue.setConsumer(async (launchParams) => {
    if (!launchParams.files || !launchParams.files.length) {
      console.info('[PWA FileHandler] App opened without associated file handles.');
      return;
    }
    
    console.info(`[PWA FileHandler] Launched with ${launchParams.files.length} file handle(s).`);
    
    for (const fileHandle of launchParams.files) {
      try {
        const file = await fileHandle.getFile();
        console.info(`[PWA FileHandler] Processing file: ${file.name} (${file.size} bytes, type: ${file.type || 'unknown'})`);
        
        // Read file content as text or arrayBuffer
        if (file.type.startsWith('text/') || file.name.endsWith('.txt') || file.name.endsWith('.md') || file.name.endsWith('.json')) {
          const textContent = await file.text();
          if (typeof onPWAFileOpened === 'function') {
            onPWAFileOpened({ name: file.name, type: file.type, content: textContent, handle: fileHandle });
          }
        } else {
          const buffer = await file.arrayBuffer();
          if (typeof onPWABinaryFileOpened === 'function') {
            onPWABinaryFileOpened({ name: file.name, type: file.type, buffer: buffer, handle: fileHandle });
          }
        }
      }} catch (err) {{
        console.error(`[PWA FileHandler] Failed to read file '${fileHandle.name}':`, err);
      }}
    }
  });
} else {
  console.info('[PWA FileHandler] Browser does not support LaunchQueue / File Handling API.');
}"""
    else:
        launch_queue_script = "// No valid file handlers configured."

    is_overall_valid = (invalid_count == 0 and len(raw_handlers) > 0)

    return FileHandlerValidationReport(
        is_valid=is_overall_valid,
        valid_count=valid_count,
        invalid_count=invalid_count,
        handlers=handlers_data,
        errors=errors,
        warnings=warnings,
        launch_queue_script=launch_queue_script,
    )


def simulate_web_share(
    config_or_target: Union[PWAManifestConfig, ShareTargetSpec, Dict[str, Any]],
    title: Optional[str] = None,
    text: Optional[str] = None,
    url: Optional[str] = None,
    files: Optional[List[Dict[str, Any]]] = None,
) -> ShareSimulationResult:
    """Simulate an incoming Web Share action against a configured share_target.
    
    Builds the exact outbound HTTP request parameters, full query URL or
    simulated multipart FormData fields, and browser client dispatch code.
    """
    report = validate_share_target(config_or_target)
    if not report.action:
        return ShareSimulationResult(
            matched=False,
            target_action="",
            method="GET",
            enctype="application/x-www-form-urlencoded",
            simulated_url="",
            query_params={},
            form_fields={},
            files_payload=[],
            client_receiver_code="// No share_target configured.",
            issues=["Share target is not configured or lacks 'action' URL."],
        )

    params_spec = report.params
    title_field = params_spec.get("title", "title")
    text_field = params_spec.get("text", "text")
    url_field = params_spec.get("url", "url")
    files_spec = params_spec.get("files")

    files_payload: List[Dict[str, Any]] = []
    if files:
        for f in files:
            files_payload.append({
                "name": f.get("name", "shared_file.bin"),
                "type": f.get("type", "application/octet-stream"),
                "size": f.get("size", 1024),
            })

    issues: List[str] = list(report.errors)

    if files_payload and not report.supports_files:
        issues.append("Incoming share payload contains files, but share_target does not accept files.")

    if report.method == "GET":
        query_dict: Dict[str, str] = {}
        if title and title_field:
            query_dict[title_field] = str(title)
        if text and text_field:
            query_dict[text_field] = str(text)
        if url and url_field:
            query_dict[url_field] = str(url)

        query_str = urllib.parse.urlencode(query_dict)
        delim = "&" if "?" in report.action else "?"
        simulated_url = f"{report.action}{delim}{query_str}" if query_str else report.action

        client_code = f"""// Simulated Client Handling for GET Share Target
const searchParams = new URLSearchParams({json.dumps('?' + query_str)});
const received = {{
  title: searchParams.get({json.dumps(title_field)}),
  text: searchParams.get({json.dumps(text_field)}),
  url: searchParams.get({json.dumps(url_field)}),
}};
console.log('Share Target Received:', received);"""

        return ShareSimulationResult(
            matched=len(issues) == 0,
            target_action=report.action,
            method="GET",
            enctype=report.enctype,
            simulated_url=simulated_url,
            query_params=query_dict,
            form_fields={},
            files_payload=[],
            client_receiver_code=client_code,
            issues=issues,
        )
    else:
        # POST Method
        form_fields: Dict[str, str] = {}
        if title and title_field:
            form_fields[title_field] = str(title)
        if text and text_field:
            form_fields[text_field] = str(text)
        if url and url_field:
            form_fields[url_field] = str(url)

        simulated_url = report.action

        client_code = f"""// Simulated ServiceWorker / Backend Handling for POST Share Target
const payload = {{
  fields: {json.dumps(form_fields, indent=2)},
  filesCount: {len(files_payload)},
  files: {json.dumps(files_payload, indent=2)},
}};
console.log('Processed POST Share Target:', payload);"""

        return ShareSimulationResult(
            matched=len(issues) == 0,
            target_action=report.action,
            method="POST",
            enctype=report.enctype,
            simulated_url=simulated_url,
            query_params={},
            form_fields=form_fields,
            files_payload=files_payload,
            client_receiver_code=client_code,
            issues=issues,
        )


def simulate_file_launch(
    config_or_handlers: Union[PWAManifestConfig, List[Any], Dict[str, Any]],
    file_name: str,
    mime_type: Optional[str] = None,
) -> FileLaunchSimulationResult:
    """Simulate opening a file from the OS shell or file manager into the PWA.
    
    Determines matching file_handler action, launch mode, and consumer dispatch code.
    """
    report = validate_file_handlers(config_or_handlers)

    if not file_name:
        return FileLaunchSimulationResult(
            handled=False,
            file_name="",
            mime_type=mime_type,
            matched_action=None,
            matched_handler_name=None,
            launch_type=None,
            simulated_launch_params={},
            consumer_dispatch_code="// No file name provided.",
            issues=["No file name provided to simulate."],
        )

    ext = os.path.splitext(file_name)[1].lower()
    inferred_mime = mime_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream"

    matched_handler: Optional[FileHandlerItem] = None

    for h in report.handlers:
        if not h.is_valid:
            continue
        # Check by extension
        if ext and ext in h.extensions:
            matched_handler = h
            break
        # Check by MIME type
        if mime_type and mime_type in h.mime_types:
            matched_handler = h
            break
        # Check wildcard mime (e.g. image/*)
        for h_mime in h.mime_types:
            if h_mime.endswith("/*") and inferred_mime.startswith(h_mime[:-2]):
                matched_handler = h
                break
        if matched_handler:
            break

    if not matched_handler:
        return FileLaunchSimulationResult(
            handled=False,
            file_name=file_name,
            mime_type=inferred_mime,
            matched_action=None,
            matched_handler_name=None,
            launch_type=None,
            simulated_launch_params={},
            consumer_dispatch_code="// No matching file handler for this file type.",
            issues=[f"No registered file handler accepts extension '{ext}' or MIME '{inferred_mime}'."],
        )

    launch_params = {
        "target_url": matched_handler.action,
        "launch_type": matched_handler.launch_type,
        "files": [
            {
                "name": file_name,
                "type": inferred_mime,
                "extension": ext,
            }
        ]
    }

    dispatch_code = f"""// Simulated LaunchQueue Consumer Dispatch for '{file_name}'
const simulatedParams = {json.dumps(launch_params, indent=2)};
console.info(`[PWA File Launch] Route to: ${{simulatedParams.target_url}}`);
console.info(`[PWA File Launch] Mode: ${{simulatedParams.launch_type}}`);
// In single-client mode: refocus existing tab; in multiple-clients mode: open new window."""

    return FileLaunchSimulationResult(
        handled=True,
        file_name=file_name,
        mime_type=inferred_mime,
        matched_action=matched_handler.action,
        matched_handler_name=matched_handler.name,
        launch_type=matched_handler.launch_type,
        simulated_launch_params=launch_params,
        consumer_dispatch_code=dispatch_code,
        issues=[],
    )
