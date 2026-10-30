[app]
title = Isokratis
package.name = isokratis
package.domain = gr.byzantine
source.dir = .
source.include_exts = py
source.exclude_dirs = .github, bin, .buildozer, java
version = 2.0
requirements = python3,kivy==2.3.1,android
orientation = portrait
fullscreen = 0
android.permissions = WAKE_LOCK, RECORD_AUDIO
android.wakelock = True
android.add_src = java
android.api = 34
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 0
