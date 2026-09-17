"""
Preconfigured PWA Application Templates Catalog.

Provides 14 industry-tailored, production-ready PWA templates with preconfigured
manifests, shortcuts, color palettes, icon designs, and Service Worker caching strategies.
100% Python Standard Library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from .models import (
    PWAManifestConfig,
    ServiceWorkerConfig,
    DisplayMode,
    Orientation,
    CachingStrategy,
    IconSpec,
    ShortcutSpec,
    ShareTargetSpec
)
from .icon_forge import generate_icon_pack


@dataclass
class PWATemplate:
    """Blueprint for creating tailored PWA manifests and Service Workers."""
    id: str
    name: str
    short_name: str
    description: str
    category: str
    theme_color: str
    background_color: str
    display: DisplayMode = DisplayMode.STANDALONE
    orientation: Optional[Orientation] = None
    default_icon_name: str = "sparkles"
    categories: List[str] = field(default_factory=list)
    shortcuts: List[ShortcutSpec] = field(default_factory=list)
    caching_strategy: CachingStrategy = CachingStrategy.NETWORK_FIRST
    precache_urls: List[str] = field(default_factory=lambda: ["/", "/index.html", "/offline.html"])
    offline_fallback_url: Optional[str] = "/offline.html"
    enable_navigation_preload: bool = True
    enable_background_sync: bool = False
    background_sync_tag: str = "sync-data"
    enable_push_notifications: bool = False
    share_target: Optional[ShareTargetSpec] = None
    file_handlers: List[Dict[str, Any]] = field(default_factory=list)
    protocol_handlers: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "short_name": self.short_name,
            "description": self.description,
            "category": self.category,
            "theme_color": self.theme_color,
            "background_color": self.background_color,
            "display": self.display.value,
            "orientation": self.orientation.value if self.orientation else None,
            "default_icon_name": self.default_icon_name,
            "categories": self.categories,
            "caching_strategy": self.caching_strategy.value,
            "offline_fallback_url": self.offline_fallback_url,
            "enable_background_sync": self.enable_background_sync,
            "enable_push_notifications": self.enable_push_notifications,
        }

    def build_config(self, **overrides: Any) -> Tuple[PWAManifestConfig, ServiceWorkerConfig]:
        """
        Builds matching PWAManifestConfig and ServiceWorkerConfig instances,
        applying any custom user overrides.
        """
        # Determine base icon set
        name = overrides.get("name", self.name)
        short_name = overrides.get("short_name", self.short_name)
        theme_color = overrides.get("theme_color", self.theme_color)
        bg_color = overrides.get("background_color", self.background_color)
        icon_name = overrides.get("icon_name", self.default_icon_name)

        # Generate default icon specs if not provided
        icons = overrides.get("icons")
        if not icons:
            icon_pack = generate_icon_pack(
                name_or_letter=short_name or name,
                bg_color=theme_color,
                fg_color="#ffffff",
                icon_name=icon_name,
                base_url_prefix="/icons"
            )
            icons = icon_pack["icons"]

        manifest = PWAManifestConfig(
            name=name,
            short_name=short_name,
            description=overrides.get("description", self.description),
            start_url=overrides.get("start_url", "/"),
            scope=overrides.get("scope", "/"),
            display=overrides.get("display", self.display),
            orientation=overrides.get("orientation", self.orientation),
            theme_color=theme_color,
            background_color=bg_color,
            categories=overrides.get("categories", self.categories),
            icons=icons,
            shortcuts=overrides.get("shortcuts", self.shortcuts),
            share_target=overrides.get("share_target", self.share_target),
            file_handlers=overrides.get("file_handlers", self.file_handlers),
            protocol_handlers=overrides.get("protocol_handlers", self.protocol_handlers)
        )

        sw = ServiceWorkerConfig(
            cache_name=f"{self.id}-cache",
            cache_version=overrides.get("cache_version", "v1"),
            caching_strategy=overrides.get("caching_strategy", self.caching_strategy),
            precache_urls=overrides.get("precache_urls", self.precache_urls),
            offline_fallback_url=overrides.get("offline_fallback_url", self.offline_fallback_url),
            enable_navigation_preload=overrides.get("enable_navigation_preload", self.enable_navigation_preload),
            enable_background_sync=overrides.get("enable_background_sync", self.enable_background_sync),
            background_sync_tag=overrides.get("background_sync_tag", self.background_sync_tag),
            enable_push_notifications=overrides.get("enable_push_notifications", self.enable_push_notifications),
        )

        return manifest, sw


TEMPLATES: Dict[str, PWATemplate] = {
    "saas-dashboard": PWATemplate(
        id="saas-dashboard",
        name="SaaS Analytics & Workspace Dashboard",
        short_name="Analytics",
        description="Real-time business analytics, user metrics, and workspace reporting.",
        category="productivity",
        theme_color="#0f172a",
        background_color="#020617",
        display=DisplayMode.STANDALONE,
        default_icon_name="chart",
        categories=["business", "productivity", "utilities"],
        shortcuts=[
            ShortcutSpec(name="Metrics Overview", url="/dashboard/metrics", short_name="Metrics"),
            ShortcutSpec(name="Team Members", url="/dashboard/team", short_name="Team"),
            ShortcutSpec(name="Billing & Plans", url="/dashboard/billing", short_name="Billing")
        ],
        caching_strategy=CachingStrategy.NETWORK_FIRST,
        enable_navigation_preload=True,
        enable_push_notifications=True
    ),

    "ecommerce-store": PWATemplate(
        id="ecommerce-store",
        name="Modern Commerce & Retail Storefront",
        short_name="Store",
        description="Fast shopping experience with instant cart, offline catalog, and order tracking.",
        category="shopping",
        theme_color="#2563eb",
        background_color="#ffffff",
        display=DisplayMode.STANDALONE,
        default_icon_name="store",
        categories=["shopping", "lifestyle", "business"],
        shortcuts=[
            ShortcutSpec(name="Shopping Cart", url="/cart", short_name="Cart"),
            ShortcutSpec(name="Track Orders", url="/orders", short_name="Orders"),
            ShortcutSpec(name="Special Deals", url="/deals", short_name="Deals")
        ],
        caching_strategy=CachingStrategy.STALE_WHILE_REVALIDATE,
        enable_navigation_preload=True,
        enable_push_notifications=True
    ),

    "news-reader": PWATemplate(
        id="news-reader",
        name="Pulse Daily News & Publication Reader",
        short_name="PulseNews",
        description="Curated news feeds with full offline reading and instant bookmarking.",
        category="news",
        theme_color="#dc2626",
        background_color="#18181b",
        display=DisplayMode.STANDALONE,
        default_icon_name="book",
        categories=["news", "magazines", "lifestyle"],
        shortcuts=[
            ShortcutSpec(name="Top Headlines", url="/headlines", short_name="Headlines"),
            ShortcutSpec(name="Saved Articles", url="/saved", short_name="Saved"),
            ShortcutSpec(name="Tech News", url="/category/technology", short_name="Tech")
        ],
        caching_strategy=CachingStrategy.CACHE_FIRST,
        offline_fallback_url="/offline.html",
        enable_navigation_preload=True
    ),

    "offline-notes": PWATemplate(
        id="offline-notes",
        name="Quill Offline Markdown Notebook",
        short_name="QuillNotes",
        description="Local-first, encrypted markdown editor with background cloud synchronization.",
        category="productivity",
        theme_color="#059669",
        background_color="#111827",
        display=DisplayMode.STANDALONE,
        default_icon_name="code",
        categories=["productivity", "utilities"],
        shortcuts=[
            ShortcutSpec(name="New Note", url="/notes/new", short_name="New"),
            ShortcutSpec(name="Search Notes", url="/search", short_name="Search"),
            ShortcutSpec(name="Favorites", url="/favorites", short_name="Favorites")
        ],
        caching_strategy=CachingStrategy.CACHE_FIRST,
        enable_background_sync=True,
        background_sync_tag="sync-notes",
        file_handlers=[
            {
                "action": "/open-file",
                "name": "Markdown Document",
                "accept": {"text/markdown": [".md", ".markdown"], "text/plain": [".txt"]}
            }
        ]
    ),

    "podcast-streamer": PWATemplate(
        id="podcast-streamer",
        name="Waveform Podcast & Audio Streamer",
        short_name="Waveform",
        description="Stream and download high-fidelity podcasts and shows with background playback.",
        category="music",
        theme_color="#7c3aed",
        background_color="#09090b",
        display=DisplayMode.STANDALONE,
        default_icon_name="music",
        categories=["music", "entertainment", "news"],
        shortcuts=[
            ShortcutSpec(name="Downloaded Episodes", url="/downloads", short_name="Offline"),
            ShortcutSpec(name="Queue", url="/queue", short_name="Queue"),
            ShortcutSpec(name="Discover Shows", url="/discover", short_name="Discover")
        ],
        caching_strategy=CachingStrategy.CACHE_FIRST,
        enable_push_notifications=True
    ),

    "devtools-hub": PWATemplate(
        id="devtools-hub",
        name="DevKit Developer Utilities & Swiss Army Knife",
        short_name="DevKit",
        description="Fast offline formatters, regex analyzers, encoder tools, and playgrounds.",
        category="utilities",
        theme_color="#1e293b",
        background_color="#0f172a",
        display=DisplayMode.STANDALONE,
        default_icon_name="terminal",
        categories=["utilities", "productivity", "education"],
        shortcuts=[
            ShortcutSpec(name="JSON Formatter", url="/tools/json", short_name="JSON"),
            ShortcutSpec(name="Base64 Converter", url="/tools/base64", short_name="Base64"),
            ShortcutSpec(name="Regex Playground", url="/tools/regex", short_name="Regex")
        ],
        caching_strategy=CachingStrategy.CACHE_FIRST
    ),

    "social-messenger": PWATemplate(
        id="social-messenger",
        name="Sphere Realtime Messenger & Social",
        short_name="SphereChat",
        description="End-to-end connected instant messenger with voice, channels, and rich media sharing.",
        category="social",
        theme_color="#0284c7",
        background_color="#0f172a",
        display=DisplayMode.STANDALONE,
        default_icon_name="chat",
        categories=["social", "productivity"],
        shortcuts=[
            ShortcutSpec(name="Direct Messages", url="/messages", short_name="DMs"),
            ShortcutSpec(name="Channels", url="/channels", short_name="Channels"),
            ShortcutSpec(name="New Chat", url="/new-chat", short_name="New")
        ],
        caching_strategy=CachingStrategy.NETWORK_FIRST,
        enable_push_notifications=True,
        enable_background_sync=True,
        share_target=ShareTargetSpec(
            action="/share",
            method="POST",
            enctype="multipart/form-data",
            params={"title": "title", "text": "text", "url": "url"}
        )
    ),

    "task-tracker": PWATemplate(
        id="task-tracker",
        name="FocusFlow Kanban & Habit Tracker",
        short_name="FocusFlow",
        description="Organize daily sprints, build lasting habits, and track project deadlines.",
        category="productivity",
        theme_color="#ea580c",
        background_color="#18181b",
        display=DisplayMode.STANDALONE,
        default_icon_name="check",
        categories=["productivity", "lifestyle"],
        shortcuts=[
            ShortcutSpec(name="Today Tasks", url="/today", short_name="Today"),
            ShortcutSpec(name="Add Task", url="/tasks/add", short_name="Add"),
            ShortcutSpec(name="Habit Streaks", url="/habits", short_name="Habits")
        ],
        caching_strategy=CachingStrategy.STALE_WHILE_REVALIDATE,
        enable_background_sync=True
    ),

    "fitness-log": PWATemplate(
        id="fitness-log",
        name="Apex Fitness & Workout Companion",
        short_name="ApexFit",
        description="Log gym sets, track rest timers, and analyze personal records offline.",
        category="fitness",
        theme_color="#10b981",
        background_color="#042f2e",
        display=DisplayMode.FULLSCREEN,
        orientation=Orientation.PORTRAIT,
        default_icon_name="bolt",
        categories=["fitness", "health", "lifestyle"],
        shortcuts=[
            ShortcutSpec(name="Start Workout", url="/workout/live", short_name="Start"),
            ShortcutSpec(name="Workout History", url="/history", short_name="History"),
            ShortcutSpec(name="Rest Timer", url="/timer", short_name="Timer")
        ],
        caching_strategy=CachingStrategy.CACHE_FIRST
    ),

    "restaurant-ordering": PWATemplate(
        id="restaurant-ordering",
        name="Bistro Tabletop & Delivery Hub",
        short_name="BistroApp",
        description="Browse menus, order to your table or home, and collect loyalty points.",
        category="food",
        theme_color="#b45309",
        background_color="#fffbeb",
        display=DisplayMode.STANDALONE,
        default_icon_name="store",
        categories=["food", "lifestyle", "shopping"],
        shortcuts=[
            ShortcutSpec(name="Full Menu", url="/menu", short_name="Menu"),
            ShortcutSpec(name="My Table Order", url="/table", short_name="Table"),
            ShortcutSpec(name="Rewards Balance", url="/rewards", short_name="Rewards")
        ],
        caching_strategy=CachingStrategy.NETWORK_FIRST,
        enable_push_notifications=True
    ),

    "portfolio-app": PWATemplate(
        id="portfolio-app",
        name="Folio Interactive Developer Showcase",
        short_name="Folio",
        description="Interactive design portfolio, case studies, project demos, and resume.",
        category="personalization",
        theme_color="#3b82f6",
        background_color="#030712",
        display=DisplayMode.STANDALONE,
        default_icon_name="sparkles",
        categories=["personalization", "business"],
        shortcuts=[
            ShortcutSpec(name="Featured Projects", url="/projects", short_name="Projects"),
            ShortcutSpec(name="Download Resume", url="/resume", short_name="Resume"),
            ShortcutSpec(name="Contact Me", url="/contact", short_name="Contact")
        ],
        caching_strategy=CachingStrategy.STALE_WHILE_REVALIDATE
    ),

    "gaming-canvas": PWATemplate(
        id="gaming-canvas",
        name="ArcadeX 2D/3D Web Game Hub",
        short_name="ArcadeX",
        description="High-performance HTML5 canvas game with zero-latency offline asset caching.",
        category="games",
        theme_color="#6366f1",
        background_color="#000000",
        display=DisplayMode.FULLSCREEN,
        orientation=Orientation.LANDSCAPE,
        default_icon_name="game",
        categories=["games", "entertainment"],
        shortcuts=[
            ShortcutSpec(name="Play Arcade Mode", url="/play/arcade", short_name="Arcade"),
            ShortcutSpec(name="Leaderboards", url="/leaderboards", short_name="Rankings"),
            ShortcutSpec(name="Game Settings", url="/settings", short_name="Settings")
        ],
        caching_strategy=CachingStrategy.CACHE_FIRST
    ),

    "crypto-tracker": PWATemplate(
        id="crypto-tracker",
        name="TokenWatch Crypto & DeFi Portfolio",
        short_name="TokenWatch",
        description="Live market charts, gas trackers, and multi-chain wallet balances.",
        category="finance",
        theme_color="#eab308",
        background_color="#0f172a",
        display=DisplayMode.STANDALONE,
        default_icon_name="shield",
        categories=["finance", "utilities", "business"],
        shortcuts=[
            ShortcutSpec(name="Portfolio", url="/portfolio", short_name="Wallet"),
            ShortcutSpec(name="Gas Tracker", url="/gas", short_name="Gas"),
            ShortcutSpec(name="Top Gainers", url="/gainers", short_name="Gainers")
        ],
        caching_strategy=CachingStrategy.NETWORK_FIRST,
        enable_push_notifications=True
    ),

    "ai-assistant": PWATemplate(
        id="ai-assistant",
        name="Nova AI Intelligent Assistant",
        short_name="NovaAI",
        description="Conversational intelligence with speech transcription, vision, and tool execution.",
        category="productivity",
        theme_color="#8b5cf6",
        background_color="#09090b",
        display=DisplayMode.STANDALONE,
        default_icon_name="rocket",
        categories=["productivity", "utilities", "business"],
        shortcuts=[
            ShortcutSpec(name="New Chat", url="/chat/new", short_name="Chat"),
            ShortcutSpec(name="Voice Input", url="/voice", short_name="Voice"),
            ShortcutSpec(name="Saved Prompts", url="/prompts", short_name="Prompts")
        ],
        caching_strategy=CachingStrategy.NETWORK_FIRST,
        enable_push_notifications=True
    ),
}


def list_templates(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists all available preconfigured PWA application templates."""
    templates = [tpl.to_dict() for tpl in TEMPLATES.values()]
    if category:
        cat_lower = category.strip().lower()
        return [t for t in templates if t.get("category", "").lower() == cat_lower]
    return templates


def get_template(template_id: str) -> Optional[PWATemplate]:
    """Retrieves a template by its unique slug identifier."""
    return TEMPLATES.get(template_id.lower().strip())


def generate_from_template(
    template_id: str,
    **overrides: Any
) -> Tuple[PWAManifestConfig, ServiceWorkerConfig]:
    """
    Instantiates a PWAManifestConfig and ServiceWorkerConfig pair from a template ID,
    applying optional overrides. Raises ValueError if template not found.
    """
    tpl = get_template(template_id)
    if not tpl:
        available = ", ".join(sorted(TEMPLATES.keys()))
        raise ValueError(f"Unknown template ID '{template_id}'. Available templates: {available}")
    return tpl.build_config(**overrides)
