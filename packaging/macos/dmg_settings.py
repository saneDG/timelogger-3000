from pathlib import Path

application = defines["app"]
app_name = Path(application).name
files = [application]
symlinks = {"Applications": "/Applications"}
icon_locations = {app_name: (170, 180), "Applications": (470, 180)}
window_rect = ((100, 100), (640, 380))
icon_size = 96
text_size = 13
format = "ULFO"
