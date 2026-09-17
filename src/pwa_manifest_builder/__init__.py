"""PWA Manifest Builder: Professional PWA Manifest, Service Worker & Icon Forge Suite.

100% Python Standard Library. Zero external dependencies.
"""

# Package Metadata
__version__ = "0.1.0"
__author__ = "PWA Manifest Builder Contributors"
__license__ = "MIT"
__description__ = "Production-grade PWA manifest generator, ServiceWorker architect, and MCP protocol server"

# Domain Models
from .models import (
    PWAManifestConfig,
    ServiceWorkerConfig,
    DisplayMode,
    Orientation,
    CachingStrategy,
    IconSpec,
    ShortcutSpec,
    ShareTargetSpec,
    PWAValidationIssue,
    PWAValidationReport,
)

# Manifest Generation
from .manifest_generator import (
    generate_manifest_dict,
    generate_manifest_json,
    generate_html_meta_tags,
    generate_install_prompt_banner_html,
    save_manifest,
    build_manifest,
)

# Service Worker Generation
from .serviceworker_generator import (
    generate_service_worker,
    generate_sw_registration_script,
    save_service_worker,
)

# Icon Forge
from .icon_forge import (
    generate_icon_svg,
    generate_favicon_ico,
    generate_bmp,
    generate_ppm,
    generate_icon_pack,
    STANDARD_ICON_SIZES,
)

# Linter & Validation
from .linter import (
    validate_manifest,
    lint_manifest_file,
    is_valid_color,
)

# Catalog & Templates
from .catalog import (
    list_templates,
    get_template,
    generate_from_template,
    TEMPLATES,
    PWATemplate,
)

# Cross-platform Compatibility
from .compat import (
    atomic_write_text,
    atomic_write_bytes,
    read_text_safe,
    read_json_safe,
    write_json_safe,
    normalize_path,
    resolve_safe_path,
    safe_delete,
    get_platform_info,
    PlatformInfo,
)

# Model Context Protocol (MCP) Server
from .mcp_server import (
    handle_jsonrpc_request,
    process_request,
    run_stdio_server,
)

__all__ = [
    # Metadata
    "__version__",
    "__author__",
    "__license__",
    "__description__",
    # Models
    "PWAManifestConfig",
    "ServiceWorkerConfig",
    "DisplayMode",
    "Orientation",
    "CachingStrategy",
    "IconSpec",
    "ShortcutSpec",
    "ShareTargetSpec",
    "PWAValidationIssue",
    "PWAValidationReport",
    # Manifest
    "generate_manifest_dict",
    "generate_manifest_json",
    "generate_html_meta_tags",
    "generate_install_prompt_banner_html",
    "save_manifest",
    "build_manifest",
    # Service Worker
    "generate_service_worker",
    "generate_sw_registration_script",
    "save_service_worker",
    # Icon Forge
    "generate_icon_svg",
    "generate_favicon_ico",
    "generate_bmp",
    "generate_ppm",
    "generate_icon_pack",
    "STANDARD_ICON_SIZES",
    # Linter
    "validate_manifest",
    "lint_manifest_file",
    "is_valid_color",
    # Catalog
    "list_templates",
    "get_template",
    "generate_from_template",
    "TEMPLATES",
    "PWATemplate",
    # Compat
    "atomic_write_text",
    "atomic_write_bytes",
    "read_text_safe",
    "read_json_safe",
    "write_json_safe",
    "normalize_path",
    "resolve_safe_path",
    "safe_delete",
    "get_platform_info",
    "PlatformInfo",
    # MCP Protocol
    "handle_jsonrpc_request",
    "process_request",
    "run_stdio_server",
]
