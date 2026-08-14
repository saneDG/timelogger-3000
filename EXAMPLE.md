<!DOCTYPE html>

<html class="dark" lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>AI Log Generator - Timelogger</title>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com" rel="preconnect"/>
<link crossorigin="" href="https://fonts.gstatic.com" rel="preconnect"/>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&amp;family=JetBrains+Mono:wght@450&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<script id="tailwind-config">
        tailwind.config = {
            darkMode: "class",
            theme: {
                extend: {
                    "colors": {
                        "on-surface": "#e3e2e3",
                        "surface-base": "#08090a",
                        "surface-tint": "#a4c9ff",
                        "surface-dim": "#121315",
                        "on-tertiary-container": "#461f00",
                        "tertiary": "#ffb786",
                        "primary-fixed-dim": "#a4c9ff",
                        "on-primary-container": "#002a52",
                        "on-secondary-fixed-variant": "#454a00",
                        "outline-variant": "#404753",
                        "surface-container-high": "#292a2b",
                        "surface-interface": "#141414",
                        "on-background": "#e3e2e3",
                        "tertiary-container": "#df7415",
                        "surface-container-low": "#1b1c1d",
                        "accent-glow": "rgba(28, 133, 232, 0.2)",
                        "text-muted": "#8a8f98",
                        "inverse-surface": "#e3e2e3",
                        "tertiary-fixed-dim": "#ffb786",
                        "inverse-primary": "#005fad",
                        "on-tertiary": "#502400",
                        "primary-container": "#3492f6",
                        "surface-container-highest": "#343536",
                        "surface-variant": "#343536",
                        "secondary-fixed-dim": "#c3d000",
                        "on-tertiary-fixed": "#311300",
                        "on-tertiary-fixed-variant": "#723600",
                        "tertiary-fixed": "#ffdcc6",
                        "border-subtle": "rgba(255, 255, 255, 0.08)",
                        "on-secondary-fixed": "#1b1d00",
                        "surface-elevated": "#0f1011",
                        "secondary-fixed": "#dfed1a",
                        "primary-fixed": "#d4e3ff",
                        "on-primary-fixed": "#001c39",
                        "on-secondary-container": "#5d6400",
                        "surface": "#121315",
                        "border-strong": "rgba(255, 255, 255, 0.15)",
                        "secondary": "#f5ff7d",
                        "on-secondary": "#2f3300",
                        "surface-bright": "#38393a",
                        "surface-container": "#1f2021",
                        "secondary-container": "#d7e404",
                        "on-error-container": "#ffdad6",
                        "outline": "#8a919e",
                        "surface-container-lowest": "#0d0e0f",
                        "on-primary": "#00315d",
                        "on-surface-variant": "#c0c7d5",
                        "error": "#ffb4ab",
                        "inverse-on-surface": "#303032",
                        "on-primary-fixed-variant": "#004884",
                        "background": "#121315",
                        "on-error": "#690005",
                        "primary": "#a4c9ff",
                        "error-container": "#93000a"
                    },
                    "borderRadius": {
                        "DEFAULT": "0.125rem",
                        "lg": "0.25rem",
                        "xl": "0.5rem",
                        "full": "0.75rem"
                    },
                    "spacing": {
                        "unit": "4px",
                        "margin-mobile": "16px",
                        "container-max": "1440px",
                        "margin-desktop": "32px",
                        "gutter": "16px"
                    },
                    "fontFamily": {
                        "label-mono": ["JetBrains Mono"],
                        "label-caps": ["Inter"],
                        "body-lg": ["Inter"],
                        "headline-md": ["Inter"],
                        "headline-lg": ["Inter"],
                        "body-md": ["Inter"],
                        "display-lg": ["Inter"]
                    },
                    "fontSize": {
                        "label-mono": ["12px", { "lineHeight": "1.4", "letterSpacing": "0.02em", "fontWeight": "450" }],
                        "label-caps": ["11px", { "lineHeight": "1.4", "letterSpacing": "0.05em", "fontWeight": "600" }],
                        "body-lg": ["16px", { "lineHeight": "1.5", "letterSpacing": "-0.01em", "fontWeight": "400" }],
                        "headline-md": ["24px", { "lineHeight": "1.3", "letterSpacing": "-0.01em", "fontWeight": "500" }],
                        "headline-lg": ["32px", { "lineHeight": "1.2", "letterSpacing": "-0.02em", "fontWeight": "600" }],
                        "body-md": ["14px", { "lineHeight": "1.5", "letterSpacing": "0", "fontWeight": "400" }],
                        "display-lg": ["48px", { "lineHeight": "1.1", "letterSpacing": "-0.02em", "fontWeight": "600" }]
                    }
                },
            },
        }
    </script>
<style>
        /* Custom scrollbar for deep dark theme */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #08090a;
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.2);
        }
        
        .glow-button {
            position: relative;
        }
        .glow-button::before {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 100%;
            height: 100%;
            background: radial-gradient(circle, rgba(164,201,255,0.15) 0%, transparent 70%);
            z-index: -1;
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        .glow-button:hover::before {
            opacity: 1;
        }

        .micro-interaction {
            transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1);
        }
    </style>
</head>
<body class="bg-surface-base text-on-surface font-body-md min-h-screen antialiased selection:bg-primary selection:text-on-primary-container overflow-x-hidden">
<!-- TopNavBar -->
<nav class="hidden md:flex fixed top-0 right-0 left-[240px] h-14 bg-surface-base/50 backdrop-blur-md border-b border-border-subtle items-center justify-between px-margin-desktop w-full ml-[240px] z-40">
<div class="flex items-center">
<!-- Search bar 'on_left' -->
<div class="relative flex items-center group">
<span class="material-symbols-outlined absolute left-3 text-text-muted text-sm group-focus-within:text-primary transition-colors" data-icon="search">search</span>
<input class="bg-surface-interface border border-border-subtle rounded-md py-1.5 pl-9 pr-4 text-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-2 focus:ring-accent-glow transition-all w-64 placeholder-text-muted" placeholder="Search logs..." type="text"/>
</div>
</div>
<div class="flex items-center gap-4">
<button class="p-2 rounded-full hover:bg-surface-variant/50 text-text-muted hover:text-on-surface transition-colors micro-interaction relative">
<span class="material-symbols-outlined" data-icon="notifications">notifications</span>
<span class="absolute top-1.5 right-1.5 w-2 h-2 bg-primary rounded-full"></span>
</button>
<button class="p-2 rounded-full hover:bg-surface-variant/50 text-text-muted hover:text-on-surface transition-colors micro-interaction">
<span class="material-symbols-outlined" data-icon="bolt">bolt</span>
</button>
<div class="h-8 w-8 rounded-full overflow-hidden border border-border-strong cursor-pointer hover:border-primary transition-colors">
<img alt="Professional avatar" class="w-full h-full object-cover" data-alt="A highly detailed close-up portrait of a high-performance professional in a dimly lit, futuristic office environment. Cool blue screen light subtly illuminates their focused expression. The mood is intense, precise, and sleekly modern, fitting a high-end AI tool aesthetic." src="https://lh3.googleusercontent.com/aida-public/AB6AXuCVPoZKEqlZUs-tuZD_LKXh38tE9JOfZ2iKfrLCBzzc7meHJGu-QC1MzWphiSePON1rNzYiRVhOAWlMQKz7yg9ktfAzxJveOB4nIhdQ2J1A4Yzkt9RNZVIhJ-s4RUdmcN1lx5jUr8RPwAMKr2MhjeceZiaOWdRWxdUSGct3GUy4WsSg56FVz5YLUSOHxDxb4Jp-iZEmL2-XAr91F8Q6LwXLgQBPYw5sDgOEmvAIw-h5JMZ9beK7UM5A"/>
</div>
</div>
</nav>
<!-- SideNavBar -->
<aside class="hidden md:flex fixed h-screen w-[240px] left-0 top-0 bg-surface-base/80 backdrop-blur-xl border-r border-border-subtle flex-col py-6 px-4 z-50">
<div class="mb-10 px-2">
<h1 class="font-headline-md text-headline-md font-bold text-on-surface tracking-tighter flex items-center gap-2">
<span class="material-symbols-outlined text-primary" data-icon="change_history">change_history</span>
                Timelogger
            </h1>
<p class="font-label-mono text-label-mono text-text-muted mt-1 uppercase tracking-widest">AI Precision</p>
</div>
<nav class="flex-1 flex flex-col gap-2">
<a class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-text-muted font-normal hover:bg-surface-variant/10 hover:text-on-surface transition-colors group micro-interaction" href="#">
<span class="material-symbols-outlined text-lg opacity-70 group-hover:opacity-100" data-icon="dashboard">dashboard</span>
<span>Dashboard</span>
</a>
<a class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-text-muted font-normal hover:bg-surface-variant/10 hover:text-on-surface transition-colors group micro-interaction" href="#">
<span class="material-symbols-outlined text-lg opacity-70 group-hover:opacity-100" data-icon="monitoring">monitoring</span>
<span>Activity Monitor</span>
</a>
<a class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-primary font-bold border-r-2 border-primary bg-primary/5 hover:bg-surface-variant/10 transition-colors group micro-interaction" href="#" style="transform: scale(0.98);">
<span class="material-symbols-outlined text-lg" data-icon="history" data-weight="fill" style="font-variation-settings: 'FILL' 1;">history</span>
<span>Time Logs</span>
</a>
<a class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-text-muted font-normal hover:bg-surface-variant/10 hover:text-on-surface transition-colors group micro-interaction" href="#">
<span class="material-symbols-outlined text-lg opacity-70 group-hover:opacity-100" data-icon="settings">settings</span>
<span>Settings</span>
</a>
</nav>
<div class="mt-auto pt-6">
<button class="w-full py-2.5 px-4 rounded-lg bg-surface-interface border border-border-strong text-on-surface font-body-md hover:border-primary/50 hover:bg-surface-variant/20 transition-all flex items-center justify-center gap-2 micro-interaction">
<span class="material-symbols-outlined text-sm" data-icon="add">add</span>
                Generate Logs
            </button>
</div>
</aside>
<!-- BottomNavBar (Mobile Only) -->
<nav class="md:hidden fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center justify-center">
<div class="bg-surface-dim/90 backdrop-blur-xl border border-border-strong rounded-full px-6 py-3 w-auto shadow-[0_0_20px_rgba(28,133,232,0.1)] cursor-pointer hover:bg-surface-bright/20 transition-colors">
<div class="flex items-center gap-3 text-primary animate-pulse font-label-mono text-label-mono">
<span class="material-symbols-outlined" data-icon="radio_button_checked" data-weight="fill" style="font-variation-settings: 'FILL' 1;">radio_button_checked</span>
<span>Live Monitoring</span>
</div>
</div>
</nav>
<!-- Main Content Canvas -->
<main class="md:ml-[240px] pt-14 min-h-screen flex flex-col p-margin-mobile md:p-margin-desktop max-w-container-max mx-auto w-full">
<!-- Header Section -->
<header class="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4 border-b border-border-subtle pb-6">
<div>
<div class="flex items-center gap-3 mb-2">
<span class="px-2.5 py-1 rounded-sm bg-tertiary-container/10 border border-tertiary/20 text-tertiary font-label-mono text-label-mono uppercase">Unconfirmed</span>
<h2 class="font-headline-lg text-headline-lg-mobile md:text-headline-lg text-on-surface font-semibold tracking-tight">AI Log Generator</h2>
</div>
<p class="text-text-muted text-body-md max-w-2xl">Review raw activity captured by the system alongside AI-generated professional descriptions before committing to the final timesheet.</p>
</div>
<div class="flex items-center gap-3">
<button class="px-4 py-2 rounded-md border border-border-strong bg-surface-interface text-on-surface hover:bg-surface-variant/30 hover:border-text-muted transition-colors font-body-md flex items-center gap-2 micro-interaction">
<span class="material-symbols-outlined text-sm" data-icon="filter_list">filter_list</span>
                    Filter
                </button>
<button class="px-5 py-2 rounded-md bg-gradient-to-b from-primary to-inverse-primary border border-primary/20 text-on-primary-container font-body-md font-medium hover:brightness-110 transition-all flex items-center gap-2 glow-button micro-interaction shadow-[0_0_15px_rgba(164,201,255,0.15)]">
<span class="material-symbols-outlined text-sm" data-icon="auto_awesome">auto_awesome</span>
                    Generate Descriptions
                </button>
</div>
</header>
<!-- Bento Grid Layout for Data -->
<div class="grid grid-cols-1 gap-gutter flex-1">
<!-- List Header (Hidden on small mobile) -->
<div class="hidden sm:grid grid-cols-12 gap-4 px-4 pb-2 border-b border-border-subtle/50 text-text-muted font-label-caps text-label-caps uppercase">
<div class="col-span-2">Time Block</div>
<div class="col-span-4">Raw Activity (Before)</div>
<div class="col-span-5">AI Description (After)</div>
<div class="col-span-1 text-right">Action</div>
</div>
<!-- Log Item 1 -->
<div class="bg-surface-interface border border-border-strong rounded-xl p-4 sm:p-0 hover:bg-[#ffffff05] transition-colors group relative overflow-hidden">
<!-- Left Accent Line -->
<div class="absolute left-0 top-0 bottom-0 w-1 bg-primary/40 opacity-0 group-hover:opacity-100 transition-opacity"></div>
<div class="sm:grid grid-cols-12 gap-4 sm:px-4 sm:py-5 items-start">
<!-- Time -->
<div class="col-span-2 flex flex-col mb-3 sm:mb-0">
<span class="font-label-mono text-label-mono text-on-surface">09:00 - 10:30</span>
<span class="font-label-caps text-label-caps text-text-muted mt-1">1h 30m</span>
<div class="mt-2 flex gap-1">
<span class="w-1.5 h-1.5 rounded-full bg-secondary-fixed"></span>
<span class="w-1.5 h-1.5 rounded-full bg-border-subtle"></span>
</div>
</div>
<!-- Before -->
<div class="col-span-4 mb-4 sm:mb-0 pr-4 border-r border-border-subtle/30">
<div class="flex items-center gap-2 mb-2">
<span class="material-symbols-outlined text-text-muted text-sm" data-icon="raw_on">raw_on</span>
<span class="font-label-caps text-label-caps text-text-muted uppercase">Captured Data</span>
</div>
<div class="font-label-mono text-label-mono text-text-muted bg-surface-base p-3 rounded-lg border border-border-subtle break-words">
                            &gt; VSCode active (45m): index.tsx, auth.ts<br/>
                            &gt; Chrome active (30m): github.com/prs, slack.com<br/>
                            &gt; Terminal (15m): git commit, npm run build
                        </div>
</div>
<!-- After -->
<div class="col-span-5 mb-4 sm:mb-0 relative">
<div class="flex items-center gap-2 mb-2">
<span class="material-symbols-outlined text-primary text-sm" data-icon="edit_document">edit_document</span>
<span class="font-label-caps text-label-caps text-primary uppercase">AI Proposed</span>
</div>
<div class="text-on-surface font-body-md bg-primary/5 p-3 rounded-lg border border-primary/20 shadow-[inset_0_0_10px_rgba(164,201,255,0.05)]">
                            Implemented new authentication flow in frontend application. Reviewed pending pull requests on GitHub and finalized build configuration for staging deployment.
                        </div>
</div>
<!-- Actions -->
<div class="col-span-1 flex sm:flex-col items-center justify-end sm:justify-start gap-2 h-full">
<button class="p-2 rounded-md hover:bg-surface-variant text-text-muted hover:text-on-surface transition-colors w-full flex justify-center micro-interaction" title="Edit">
<span class="material-symbols-outlined text-[20px]" data-icon="edit">edit</span>
</button>
<button class="p-2 rounded-md hover:bg-primary/20 text-primary transition-colors w-full flex justify-center border border-transparent hover:border-primary/30 micro-interaction" title="Confirm">
<span class="material-symbols-outlined text-[20px]" data-icon="check_circle">check_circle</span>
</button>
</div>
</div>
</div>
<!-- Log Item 2 -->
<div class="bg-surface-interface border border-border-strong rounded-xl p-4 sm:p-0 hover:bg-[#ffffff05] transition-colors group relative overflow-hidden">
<div class="absolute left-0 top-0 bottom-0 w-1 bg-primary/40 opacity-0 group-hover:opacity-100 transition-opacity"></div>
<div class="sm:grid grid-cols-12 gap-4 sm:px-4 sm:py-5 items-start">
<div class="col-span-2 flex flex-col mb-3 sm:mb-0">
<span class="font-label-mono text-label-mono text-on-surface">11:00 - 11:45</span>
<span class="font-label-caps text-label-caps text-text-muted mt-1">45m</span>
<div class="mt-2 flex gap-1">
<span class="w-1.5 h-1.5 rounded-full bg-secondary-fixed"></span>
</div>
</div>
<div class="col-span-4 mb-4 sm:mb-0 pr-4 border-r border-border-subtle/30">
<div class="flex items-center gap-2 mb-2">
<span class="material-symbols-outlined text-text-muted text-sm" data-icon="raw_on">raw_on</span>
<span class="font-label-caps text-label-caps text-text-muted uppercase">Captured Data</span>
</div>
<div class="font-label-mono text-label-mono text-text-muted bg-surface-base p-3 rounded-lg border border-border-subtle break-words">
                            &gt; Zoom (45m): "Weekly Sync - Design Team"<br/>
                            &gt; Figma active (background)
                        </div>
</div>
<div class="col-span-5 mb-4 sm:mb-0">
<div class="flex items-center gap-2 mb-2">
<span class="material-symbols-outlined text-primary text-sm" data-icon="edit_document">edit_document</span>
<span class="font-label-caps text-label-caps text-primary uppercase">AI Proposed</span>
</div>
<div class="text-on-surface font-body-md bg-primary/5 p-3 rounded-lg border border-primary/20 shadow-[inset_0_0_10px_rgba(164,201,255,0.05)]">
                            Participated in Weekly Design Team Sync. Discussed ongoing UI updates and reviewed Figma prototypes for upcoming sprint.
                        </div>
</div>
<div class="col-span-1 flex sm:flex-col items-center justify-end sm:justify-start gap-2 h-full">
<button class="p-2 rounded-md hover:bg-surface-variant text-text-muted hover:text-on-surface transition-colors w-full flex justify-center micro-interaction" title="Edit">
<span class="material-symbols-outlined text-[20px]" data-icon="edit">edit</span>
</button>
<button class="p-2 rounded-md hover:bg-primary/20 text-primary transition-colors w-full flex justify-center border border-transparent hover:border-primary/30 micro-interaction" title="Confirm">
<span class="material-symbols-outlined text-[20px]" data-icon="check_circle">check_circle</span>
</button>
</div>
</div>
</div>
<!-- Empty State / Footer action area -->
<div class="mt-4 flex justify-center pb-10">
<button class="px-6 py-2.5 rounded-full border border-border-strong bg-surface-base text-text-muted hover:text-on-surface hover:border-border-subtle transition-colors font-label-caps text-label-caps flex items-center gap-2 tracking-widest uppercase">
                    Load More Unconfirmed
                    <span class="material-symbols-outlined text-sm" data-icon="expand_more">expand_more</span>
</button>
</div>
</div>
</main>
</body></html>
